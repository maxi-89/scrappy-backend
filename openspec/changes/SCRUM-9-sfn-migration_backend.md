# Backend Implementation Plan: SCRUM-9 SFN Migration — Async Scraping via AWS Step Functions

## Overview

Migrate the scraping worker from FastAPI `BackgroundTasks` (which blocks the Lambda invocation) to
**AWS Step Functions Standard Workflow**. The API Lambda returns `202` immediately after starting a
state machine execution. Three separate Lambda functions handle each step of the scraping lifecycle.

**Root cause for migration**: Mangum runs `BackgroundTasks` synchronously within the same Lambda
invocation. API Gateway has a hard 29-second timeout. Any scrape taking longer causes a `504` on the
client side while the job may complete internally — producing inconsistent state.

**Layers involved**: Application · Infrastructure · Presentation (Router) · IaC (SAM)

---

## Architecture Context

### New files

| File | Purpose |
|---|---|
| `lambdas/__init__.py` | Package init |
| `lambdas/scraping_init_handler.py` | Lambda entry point: marks job `running` |
| `lambdas/scraping_scraper_handler.py` | Lambda entry point: calls Google Maps Places API |
| `lambdas/scraping_saver_handler.py` | Lambda entry point: bulk-saves businesses, marks `completed` |
| `lambdas/scraping_mark_failed_handler.py` | Lambda entry point: marks job `failed` (Catch target) |
| `app/infrastructure/aws/__init__.py` | Package init |
| `app/infrastructure/aws/sfn_client.py` | boto3 Step Functions starter adapter |
| `statemachine/scraping_workflow.asl.json` | State Machine definition (Amazon States Language) |
| `template.yaml` | AWS SAM template (IaC) |
| `samconfig.toml` | SAM deployment defaults |

### Modified files

| File | Change |
|---|---|
| `app/application/workers/scraping_worker.py` | Remove `run()` / `run_by_id()` and `session_factory`; expose `fetch_businesses()` and `map_to_domain()` as public methods |
| `app/infrastructure/dependencies.py` | Remove `get_scraping_worker()`; add `get_sfn_client()` |
| `app/presentation/routers/scraping_jobs_router.py` | Remove `BackgroundTasks` + worker; inject `SfnStarterClient` |
| `pyproject.toml` | Add `boto3` dev dependency; add mypy override |
| `.env.example` | Add `STATE_MACHINE_ARN`, `AWS_REGION` |
| `openspec/specs/backend-standards.mdc` | Add Step Functions deployment section |
| `tests/unit/presentation/test_scraping_jobs_router.py` | Replace `mock_worker` with `mock_sfn` |
| `tests/unit/application/test_scraping_worker.py` | Remove tests for `run()` / `run_by_id()` |

---

## Architecture Diagram

```
         Client
            │
            │  POST /admin/scraping-jobs
            ▼
   ┌────────────────┐
   │   API Lambda   │  (FastAPI + Mangum)
   └───────┬────────┘
           │ 1. create job (status=pending)
           │ 2. sfn.start_execution(job_id)
           │ 3. return 202 ──────────────────► Client receives response immediately
           ▼
   ┌────────────────────────────────────────────────────┐
   │          Step Functions Standard Workflow           │
   │                                                    │
   │  ┌─────────────┐  ┌──────────────┐  ┌──────────┐  │
   │  │ Init Lambda │→ │Scraper Lambda│→ │  Saver   │  │
   │  │ running     │  │ Places API   │  │  Lambda  │  │
   │  │ started_at  │  │ retry x3     │  │ save_many│  │
   │  └─────────────┘  └──────────────┘  │ completed│  │
   │         │ (any Catch)      │ (Catch) └──────────┘  │
   │         └──────────────────┘                       │
   │                    │                               │
   │           ┌────────▼────────┐                      │
   │           │  MarkFailed     │                      │
   │           │  Lambda         │                      │
   │           │  status=failed  │                      │
   │           └─────────────────┘                      │
   └────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 0: Create Feature Branch

```bash
git checkout master
git pull origin master
git checkout -b feature/SCRUM-9-sfn-migration-backend
```

---

### Step 1: Tests for SfnStarterClient (failing first)

**File**: `tests/unit/infrastructure/test_sfn_client.py`

Cover:
- `start_execution(job_id)` calls `boto3_client.start_execution` with the correct `stateMachineArn`
  and a JSON-encoded `input` containing `{"job_id": job_id}`
- Execution `name` is `f"scraping-{job_id}"` (Step Functions requires unique execution names)
- If boto3 raises a `ClientError`, it propagates (no swallowing)

Mock strategy: `unittest.mock.patch("boto3.client")` at the module level so the real AWS SDK is
never called.

---

### Step 2: Implement SfnStarterClient

**File**: `app/infrastructure/aws/sfn_client.py`

```python
import json
import os
from typing import Any

import boto3


class SfnStarterClient:
    def __init__(self) -> None:
        self._client: Any = boto3.client(
            "stepfunctions",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
        self._state_machine_arn = os.environ["STATE_MACHINE_ARN"]

    def start_execution(self, job_id: str) -> None:
        self._client.start_execution(
            stateMachineArn=self._state_machine_arn,
            name=f"scraping-{job_id}",
            input=json.dumps({"job_id": job_id}),
        )
```

**Notes**:
- boto3 has no official type stubs → use `Any` for the client and add a mypy override for `boto3`
- `start_execution` is a synchronous boto3 call; the router wraps it in `asyncio.to_thread`
- `STATE_MACHINE_ARN` is read from env; never hardcoded

---

### Step 3: Dependency injection

**File**: `app/infrastructure/dependencies.py`

- Remove `get_scraping_worker()` and its `ScrapingWorker` / `AsyncSessionLocal` /
  `_GOOGLE_MAPS_API_KEY` references
- Add:

```python
from app.infrastructure.aws.sfn_client import SfnStarterClient

def get_sfn_client() -> SfnStarterClient:
    return SfnStarterClient()
```

---

### Step 4: Update router

**File**: `app/presentation/routers/scraping_jobs_router.py`

Remove `BackgroundTasks` and `ScrapingWorker`. Inject `SfnStarterClient`:

```python
import asyncio
from fastapi import APIRouter, Depends
from app.infrastructure.aws.sfn_client import SfnStarterClient
from app.infrastructure.dependencies import get_admin_key, get_scraping_job_service, get_sfn_client

@router.post("", response_model=ScrapingJobResponse, status_code=202)
async def create_scraping_job(
    payload: CreateScrapingJobRequest,
    _: str = Depends(get_admin_key),
    service: ScrapingJobService = Depends(get_scraping_job_service),
    sfn: SfnStarterClient = Depends(get_sfn_client),
) -> ScrapingJobResponse:
    response = await service.create_job(payload)
    await asyncio.to_thread(sfn.start_execution, response.id)
    return response
```

---

### Step 5: Update router tests

**File**: `tests/unit/presentation/test_scraping_jobs_router.py`

- Replace `mock_worker` fixture with `mock_sfn` (`MagicMock` with `start_execution` as a regular
  `MagicMock`, not async — it's a sync call)
- Update all POST test dependency overrides: `get_sfn_client` instead of `get_scraping_worker`
- Rename `test_create_job_schedules_background_task` →
  `test_create_job_starts_sfn_execution` and assert `mock_sfn.start_execution` was called once
  with `response.id`

---

### Step 6: Refactor ScrapingWorker

**File**: `app/application/workers/scraping_worker.py`

Step Functions handles orchestration; the worker becomes a stateless helper used by Lambda handlers:

- Remove `run()`, `run_by_id()`, `_mark_running()`
- Remove `session_factory` from `__init__`
- Rename `_fetch_businesses` → `fetch_businesses` (public)
- Rename `_map_to_domain` → `map_to_domain` (public)
- Constructor only takes `google_maps_api_key: str`

Update `tests/unit/application/test_scraping_worker.py` to remove tests for the removed methods
and keep/update tests for `fetch_businesses` and `map_to_domain`.

---

### Step 7: Lambda handlers

Each handler: synchronous Lambda entry point (`handler(event, context)`) that calls
`asyncio.run(_async_handler(event))` internally.

**`lambdas/scraping_init_handler.py`**
- Input: `{"job_id": "..."}`
- Load job from DB, set `status="running"`, `started_at=now(UTC)`
- Output: `{"job_id": "...", "category": "...", "zone": "..."}`

**`lambdas/scraping_scraper_handler.py`**
- Input: `{"job_id": "...", "category": "...", "zone": "..."}`
- Reconstruct a minimal `ScrapingJob` from event fields (no DB read needed)
- Instantiate `ScrapingWorker(google_maps_api_key=os.environ["GOOGLE_MAPS_API_KEY"])`
- Call `await worker.fetch_businesses(job)`
- Serialize each `Business` to a dict (use `dataclasses.asdict`, converting `Decimal` → `str`)
- Output: `{"job_id": "...", "businesses": [...]}`

**`lambdas/scraping_saver_handler.py`**
- Input: `{"job_id": "...", "businesses": [...]}`
- Deserialize dicts back to `Business` domain objects
- Bulk-insert with `biz_repo.save_many(businesses)`
- Update job: `status="completed"`, `records_scraped=len(businesses)`, `finished_at=now(UTC)`
- Output: `{"job_id": "...", "records_saved": N}`

**`lambdas/scraping_mark_failed_handler.py`**
- Input: `{"job_id": "...", "error": {"Error": "...", "Cause": "..."}}` (Step Functions Catch shape)
- Update job: `status="failed"`, `error_message=event["error"]["Cause"]`, `finished_at=now(UTC)`
- Output: `{"job_id": "..."}`

---

### Step 8: Tests for Lambda handlers

**File**: `tests/unit/lambdas/test_scraping_handlers.py`

Test each handler in isolation:
- Mock `AsyncSessionLocal`, `ScrapingJobRepository`, `BusinessRepository`
- Mock `ScrapingWorker.fetch_businesses` for the scraper handler
- Assert correct repo methods are called with correct arguments
- Assert the returned dict has the expected keys/values
- Test the `MarkFailed` handler with the exact Step Functions Catch payload shape

---

### Step 9: State Machine definition (ASL)

**File**: `statemachine/scraping_workflow.asl.json`

```json
{
  "Comment": "Scrappy async scraping workflow",
  "StartAt": "InitJob",
  "States": {
    "InitJob": {
      "Type": "Task",
      "Resource": "${ScrapingInitFunctionArn}",
      "Next": "ScrapeBusinesses",
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "Next": "MarkFailed",
        "ResultPath": "$.error"
      }]
    },
    "ScrapeBusinesses": {
      "Type": "Task",
      "Resource": "${ScrapingScraperFunctionArn}",
      "Retry": [{
        "ErrorEquals": [
          "Lambda.ServiceException",
          "Lambda.AWSLambdaException",
          "Lambda.TooManyRequestsException",
          "Lambda.SdkClientException"
        ],
        "IntervalSeconds": 5,
        "MaxAttempts": 3,
        "BackoffRate": 2.0
      }],
      "Next": "SaveBusinesses",
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "Next": "MarkFailed",
        "ResultPath": "$.error"
      }]
    },
    "SaveBusinesses": {
      "Type": "Task",
      "Resource": "${ScrapingSaverFunctionArn}",
      "Next": "Done",
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "Next": "MarkFailed",
        "ResultPath": "$.error"
      }]
    },
    "MarkFailed": {
      "Type": "Task",
      "Resource": "${ScrapingMarkFailedFunctionArn}",
      "Next": "Done"
    },
    "Done": {
      "Type": "Succeed"
    }
  }
}
```

**Notes**:
- `ResultPath: "$.error"` merges error info into the existing input, preserving `job_id` for the
  `MarkFailed` handler
- `${...}` substitution variables are resolved by SAM's `DefinitionSubstitutions` at deploy time
- The Retry block targets Lambda infrastructure errors (throttling, timeouts), not application
  errors (e.g. Google Maps quota) — those are caught by the `Catch` clause

---

### Step 10: SAM Template (IaC)

**File**: `template.yaml`

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Runtime: python3.12
    MemorySize: 512
    Environment:
      Variables:
        DATABASE_URL: !Sub "{{resolve:ssm:/scrappy/database-url}}"

Resources:

  # ── API Lambda ────────────────────────────────────────────────────────────
  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Timeout: 30
      Policies:
        - Statement:
            Effect: Allow
            Action: states:StartExecution
            Resource: !Ref ScrapingStateMachine
      Environment:
        Variables:
          STATE_MACHINE_ARN: !Ref ScrapingStateMachine
          ADMIN_API_KEY: !Sub "{{resolve:ssm:/scrappy/admin-api-key}}"
          AUTH0_DOMAIN: !Sub "{{resolve:ssm:/scrappy/auth0-domain}}"
          AUTH0_AUDIENCE: !Sub "{{resolve:ssm:/scrappy/auth0-audience}}"
      Events:
        Api:
          Type: HttpApi
          Properties:
            Path: /{proxy+}
            Method: ANY

  # ── Scraping Lambdas ──────────────────────────────────────────────────────
  ScrapingInitFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: lambdas.scraping_init_handler.handler
      Timeout: 30

  ScrapingScraperFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: lambdas.scraping_scraper_handler.handler
      Timeout: 300  # 5 min — 3 pages × Google Maps latency
      Environment:
        Variables:
          GOOGLE_MAPS_API_KEY: !Sub "{{resolve:ssm:/scrappy/google-maps-api-key}}"

  ScrapingSaverFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: lambdas.scraping_saver_handler.handler
      Timeout: 60

  ScrapingMarkFailedFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: lambdas.scraping_mark_failed_handler.handler
      Timeout: 30

  # ── State Machine ─────────────────────────────────────────────────────────
  ScrapingStateMachine:
    Type: AWS::Serverless::StateMachine
    Properties:
      DefinitionUri: statemachine/scraping_workflow.asl.json
      DefinitionSubstitutions:
        ScrapingInitFunctionArn: !GetAtt ScrapingInitFunction.Arn
        ScrapingScraperFunctionArn: !GetAtt ScrapingScraperFunction.Arn
        ScrapingSaverFunctionArn: !GetAtt ScrapingSaverFunction.Arn
        ScrapingMarkFailedFunctionArn: !GetAtt ScrapingMarkFailedFunction.Arn
      Policies:
        - LambdaInvokePolicy:
            FunctionName: !Ref ScrapingInitFunction
        - LambdaInvokePolicy:
            FunctionName: !Ref ScrapingScraperFunction
        - LambdaInvokePolicy:
            FunctionName: !Ref ScrapingSaverFunction
        - LambdaInvokePolicy:
            FunctionName: !Ref ScrapingMarkFailedFunction

Outputs:
  ApiUrl:
    Value: !Sub "https://${ServerlessHttpApi}.execute-api.${AWS::Region}.amazonaws.com"
  StateMachineArn:
    Value: !Ref ScrapingStateMachine
```

**IAM principles enforced**:
- API Lambda has `states:StartExecution` on this specific State Machine only (not `*`)
- State Machine has `lambda:InvokeFunction` on each scraping Lambda only (not `*`)
- Secrets injected via SSM Parameter Store (`{{resolve:ssm:...}}`), never in plaintext

---

### Step 11: SAM deployment config

**File**: `samconfig.toml`

```toml
version = 0.1

[default.build.parameters]
use_container = false

[default.deploy.parameters]
stack_name = "scrappy-backend"
region = "us-east-1"
confirm_changeset = true
capabilities = "CAPABILITY_IAM"
resolve_s3 = true
```

---

### Step 12: Update pyproject.toml

- Add `boto3` to `[tool.uv] dev-dependencies` (available in Lambda runtime, only needed locally)
- Add mypy override:

```toml
[[tool.mypy.overrides]]
module = "boto3"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "botocore.*"
ignore_missing_imports = true
```

---

### Step N: Update documentation

- `.env.example` → add `STATE_MACHINE_ARN=arn:aws:states:us-east-1:123456789:stateMachine:scrappy-ScrapingStateMachine-xxx` and `AWS_REGION=us-east-1`
- `openspec/specs/backend-standards.mdc` → add Step Functions / SAM deployment section
- `openspec/specs/api-spec.yml` → no change (HTTP contract unchanged)

---

## Deployment Instructions

### Prerequisites

1. **AWS CLI** configured: `aws configure` (region, access key, secret key)
2. **AWS SAM CLI** installed:
   ```bash
   pip install aws-sam-cli
   # or on macOS: brew install aws-sam-cli
   ```
3. **SSM Parameters** created in AWS (one-time setup):
   ```bash
   aws ssm put-parameter --name /scrappy/database-url        --type SecureString --value "postgresql+asyncpg://..."
   aws ssm put-parameter --name /scrappy/google-maps-api-key --type SecureString --value "AIza..."
   aws ssm put-parameter --name /scrappy/admin-api-key       --type SecureString --value "your-key"
   aws ssm put-parameter --name /scrappy/auth0-domain        --type SecureString --value "xxx.auth0.com"
   aws ssm put-parameter --name /scrappy/auth0-audience      --type SecureString --value "https://api.scrappy.com"
   ```

### First deployment (interactive)

```bash
uv sync
sam build
sam deploy --guided
# Prompts:
#   Stack Name: scrappy-backend
#   AWS Region: us-east-1
#   Confirm changes before deploy: Y
#   Allow SAM CLI IAM role creation: Y
#   Save arguments to samconfig.toml: Y
```

SAM will output the `ApiUrl` and `StateMachineArn` at the end. Copy `StateMachineArn` to your
local `.env` as `STATE_MACHINE_ARN` for any local integration testing.

### Subsequent deployments

```bash
sam build && sam deploy
# Uses defaults from samconfig.toml — no prompts
```

### Local development (no real AWS needed)

For unit tests, mock `boto3.client`. For integration testing of Lambda handlers without AWS:

```bash
# Install localstack (optional — simulates AWS locally)
pip install localstack
localstack start

# Override endpoint in SfnStarterClient for local:
# boto3.client("stepfunctions", endpoint_url="http://localhost:4566")
```

For testing the full state machine flow locally with SAM + Docker:

```bash
sam local invoke ScrapingInitFunction \
  --event tests/events/init_event.json \
  --env-vars tests/events/env.json

# tests/events/init_event.json
{ "job_id": "550e8400-e29b-41d4-a716-446655440000" }
```

### Post-deployment validation

```bash
# 1. Hit the API
curl -X POST https://<api-url>/admin/scraping-jobs \
  -H "X-Admin-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"category": "restaurants", "zone": "CABA"}'

# 2. Check job status
curl https://<api-url>/admin/scraping-jobs/<job-id> \
  -H "X-Admin-Key: your-key"

# 3. Inspect execution in AWS Console
# → Step Functions → State machines → scrappy-ScrapingStateMachine → Executions
```

### Rollback

```bash
# Revert to previous CloudFormation stack version
aws cloudformation continue-update-rollback --stack-name scrappy-backend
# or delete and redeploy from a previous git tag
```

---

## Implementation Order

1. Step 0 — Create feature branch
2. Step 1–2 — `SfnStarterClient` (test first, then implement)
3. Step 3 — Update DI (`get_sfn_client`)
4. Step 4 — Update router (inject sfn, remove BackgroundTasks)
5. Step 5 — Update router tests
6. Step 6 — Refactor `ScrapingWorker` (remove orchestration, expose public helpers)
7. Step 7 — Lambda handlers (4 files)
8. Step 8 — Lambda handler tests
9. Step 9 — State Machine ASL
10. Step 10 — SAM template
11. Step 11 — SAM config
12. Step 12 — pyproject.toml (boto3 + mypy)
13. Step N — Documentation + quality checks

---

## Error Response Format

| HTTP | Condition |
|---|---|
| 202 | Job created and SFN execution started |
| 401 | Invalid or missing admin key |
| 422 | Missing/invalid request body |
| 500 | `sfn.start_execution` boto3 call fails (e.g. wrong ARN, missing permissions) |

Step Functions failures (scraping errors, DB errors inside Lambdas) are **not HTTP errors** —
they update `jobs.status` and `jobs.error_message`. Clients poll `GET /admin/scraping-jobs/{id}`.

---

## Step Functions Payload Constraint

Standard Workflow: **256 KB max per state input/output**.

The Scraper Lambda returns the full list of businesses as JSON. With ~60 results at ~1 KB each,
typical payloads are ~60 KB — well within limits. If this limit is ever approached (e.g. if
`_MAX_PAGES` is increased significantly), the mitigation is to have the Scraper Lambda persist
businesses as `draft` records in the DB and pass only `job_id` to the Saver state.

---

## Testing Checklist

- [ ] `SfnStarterClient.start_execution()` calls boto3 with correct ARN and JSON input
- [ ] Router returns 202 and calls `sfn.start_execution(job_id)` — not `BackgroundTasks`
- [ ] Init handler: sets `status=running`, `started_at`, returns `category` and `zone`
- [ ] Scraper handler: calls `fetch_businesses()`, serializes Decimals to strings
- [ ] Saver handler: deserializes businesses, saves, marks `completed`
- [ ] MarkFailed handler: sets `status=failed` with `error_message` from Catch payload
- [ ] `uv run pytest` — all tests pass
- [ ] `uv run pytest --cov=app --cov-report=term-missing` — ≥ 90%
- [ ] `uv run ruff check .` — no errors
- [ ] `uv run mypy app/` — no errors

---

## Dependencies

| Package | Where | Reason |
|---|---|---|
| `boto3` | dev only (`pyproject.toml`) | Step Functions client; pre-installed in Lambda runtime |
| `aws-sam-cli` | local tooling (not in pyproject.toml) | Build and deploy SAM stacks |

---

## Implementation Verification

- [ ] `ScrapingWorker.run()` and `run_by_id()` deleted — orchestration belongs to Step Functions
- [ ] Lambda handlers are thin: only event parsing, call to domain/infra, return dict
- [ ] `SfnStarterClient` lives in `app/infrastructure/aws/` (external adapter pattern)
- [ ] Router has zero knowledge of scraping internals — only calls `sfn.start_execution`
- [ ] IAM least-privilege: API Lambda → `states:StartExecution` only; SFN → `lambda:InvokeFunction` only
- [ ] No secrets hardcoded — all via SSM + Lambda env vars
- [ ] SAM template committed to repo
- [ ] `samconfig.toml` committed (no sensitive values)
