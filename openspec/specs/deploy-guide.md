# Scrappy — Production Deployment Guide

Step-by-step instructions to deploy Scrappy to production from scratch.
Follow the phases **in order** — each one depends on the previous.

---

## Prerequisites

Before starting, install and configure:

```bash
# AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Configure AWS CLI with your admin user credentials
aws configure
# AWS Access Key ID: [your key]
# AWS Secret Access Key: [your secret]
# Default region: us-east-1
# Default output format: json

# AWS SAM CLI
pip install aws-sam-cli

# uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify:
```bash
aws --version          # aws-cli/2.x.x
sam --version          # SAM CLI, version 1.x.x
uv --version           # uv 0.x.x
```

---

## Phase 1 — Supabase (Database)

### 1.1 Create a project

1. Go to [supabase.com](https://supabase.com) and sign in.
2. Click **New project**.
3. Fill in:
   - **Name**: `scrappy`
   - **Database password**: generate a strong one and save it — you will need it.
   - **Region**: `East US (North Virginia)` — closest to AWS `us-east-1`.
4. Click **Create new project**. Wait ~2 minutes for it to provision.

### 1.2 Get the connection string

1. In your project dashboard, go to **Settings → Database**.
2. Scroll to **Connection string**.
3. Select the **URI** tab.
4. Select mode: **Session** (important — do NOT use Transaction mode, it is incompatible with asyncpg).
5. Copy the string. It looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
6. Modify the scheme to use asyncpg:
   ```
   postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
7. Save this value — it will be stored in AWS SSM as `/scrappy/database-url`.

### 1.3 Run database migrations

With your local `.env` pointing to the Supabase DB:

```bash
# In the scrappy-backend project root
DATABASE_URL="postgresql+asyncpg://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres" \
  uv run alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade -> a4f1c8e2d905, add offers pricing and orders tables
```

> Run this again every time a new migration is added to the codebase.

---

## Phase 2 — Auth0 (Authentication)

Auth0 handles login with Google, GitHub, and other social providers. Your backend never sees passwords or OAuth tokens — it only validates the JWT that Auth0 issues.

### 2.1 Create an Auth0 account and tenant

1. Go to [auth0.com](https://auth0.com) and sign up.
2. During onboarding, Auth0 creates a **tenant** for you (e.g. `scrappy.us.auth0.com`).
   - Note your tenant domain: `[TENANT].us.auth0.com`

### 2.2 Create the API

1. In the Auth0 dashboard, go to **Applications → APIs**.
2. Click **Create API**.
3. Fill in:
   - **Name**: `Scrappy API`
   - **Identifier (Audience)**: `https://api.scrappy.io`
     (this is a logical identifier, not a real URL — it can be anything, but must match `AUTH0_AUDIENCE` in your backend)
   - **Signing Algorithm**: `RS256`
4. Click **Create**.

### 2.3 Create the frontend application

1. Go to **Applications → Applications → Create Application**.
2. Fill in:
   - **Name**: `Scrappy Frontend`
   - **Type**: `Single Page Web Applications`
3. Click **Create**.
4. Go to the **Settings** tab of this application.
5. Fill in:
   - **Allowed Callback URLs**: `https://[YOUR-VERCEL-DOMAIN]/auth/callback, http://localhost:3000/auth/callback`
   - **Allowed Logout URLs**: `https://[YOUR-VERCEL-DOMAIN], http://localhost:3000`
   - **Allowed Web Origins**: `https://[YOUR-VERCEL-DOMAIN], http://localhost:3000`
6. Click **Save Changes**.
7. Note the **Client ID** — the frontend will need it.

### 2.4 Enable Google social login

1. Go to **Authentication → Social**.
2. Click **Google / Gmail**.
3. For development: Auth0 provides its own Google OAuth credentials automatically. Click **Continue** to use them.
4. For production: create your own Google OAuth credentials:
   - Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services → Credentials**.
   - Click **Create Credentials → OAuth Client ID**.
   - Application type: **Web application**.
   - Authorized redirect URI: `https://[TENANT].us.auth0.com/login/callback`
   - Copy the **Client ID** and **Client Secret** back to Auth0.
5. Enable the connection for your **Scrappy Frontend** application.

### 2.5 Note the values

```
AUTH0_DOMAIN   = [TENANT].us.auth0.com
AUTH0_AUDIENCE = https://api.scrappy.io
```

---

## Phase 3 — Stripe (Payments)

### 3.1 Create a Stripe account

1. Go to [dashboard.stripe.com](https://dashboard.stripe.com) and sign up or sign in.
2. Complete business verification to enable live payments (can be skipped for now using test mode).

### 3.2 Get API keys

1. In the dashboard, go to **Developers → API keys**.
2. Note:
   - **Publishable key**: `pk_live_...` (frontend uses this)
   - **Secret key**: `sk_live_...` (backend uses this — never expose it)

> Use `pk_test_...` / `sk_test_...` for testing. Switch to live keys for production.

### 3.3 Create the webhook endpoint

1. Go to **Developers → Webhooks → Add endpoint**.
2. Fill in:
   - **Endpoint URL**: `https://PLACEHOLDER` (you'll update this after the AWS deploy)
   - **Listen to**: select **Events on your account**
   - **Events to send**: search and select `payment_intent.succeeded`
3. Click **Add endpoint**.
4. In the webhook detail page, click **Reveal** next to **Signing secret**.
5. Note the value: `whsec_...`

```
STRIPE_SECRET_KEY      = sk_live_...
STRIPE_WEBHOOK_SECRET  = whsec_...
```

---

## Phase 4 — AWS Setup

### 4.1 Store secrets in SSM Parameter Store

All secrets are stored in AWS SSM so they are never hardcoded in the template or Lambda config. Run each command replacing the placeholder values:

```bash
aws ssm put-parameter \
  --name /scrappy/database-url \
  --value "postgresql+asyncpg://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres" \
  --type SecureString \
  --region us-east-1

aws ssm put-parameter \
  --name /scrappy/admin-api-key \
  --value "generate-a-long-random-string-here" \
  --type SecureString \
  --region us-east-1

aws ssm put-parameter \
  --name /scrappy/auth0-domain \
  --value "[TENANT].us.auth0.com" \
  --type SecureString \
  --region us-east-1

aws ssm put-parameter \
  --name /scrappy/auth0-audience \
  --value "https://api.scrappy.io" \
  --type SecureString \
  --region us-east-1

aws ssm put-parameter \
  --name /scrappy/stripe-secret-key \
  --value "sk_live_..." \
  --type SecureString \
  --region us-east-1

aws ssm put-parameter \
  --name /scrappy/stripe-webhook-secret \
  --value "whsec_..." \
  --type SecureString \
  --region us-east-1

aws ssm put-parameter \
  --name /scrappy/google-maps-api-key \
  --value "AIza..." \
  --type SecureString \
  --region us-east-1
```

Verify all parameters were created:
```bash
aws ssm describe-parameters \
  --parameter-filters "Key=Path,Values=/scrappy" \
  --region us-east-1 \
  --query "Parameters[*].Name"
```

Expected output:
```json
[
  "/scrappy/admin-api-key",
  "/scrappy/auth0-audience",
  "/scrappy/auth0-domain",
  "/scrappy/database-url",
  "/scrappy/google-maps-api-key",
  "/scrappy/stripe-secret-key",
  "/scrappy/stripe-webhook-secret"
]
```

### 4.2 Create the ECR repository

This stores the Docker image for the API Lambda (the FastAPI app).

```bash
aws ecr create-repository \
  --repository-name scrappy-backend \
  --region us-east-1
```

Note the `repositoryUri` from the output:
```
[ACCOUNT-ID].dkr.ecr.us-east-1.amazonaws.com/scrappy-backend
```

### 4.3 First deploy with SAM

SAM provisions all the AWS infrastructure: API Lambda, 5 scraping Lambdas, Step Functions state machine, S3 results bucket, and API Gateway.

```bash
# From the scrappy-backend project root
sam build
sam deploy --guided
```

Answer the prompts:
```
Stack Name [sam-app]: scrappy
AWS Region [us-east-1]: us-east-1
Confirm changes before deploy [y/N]: y
Allow SAM CLI IAM role creation [Y/n]: Y
Disable rollback [y/N]: N
Save arguments to configuration file [Y/n]: Y
SAM configuration file [samconfig.toml]: samconfig.toml
SAM configuration environment [default]: default
```

SAM will show a changeset. Review it and confirm with `y`.

Wait for the deploy to complete (~3-5 minutes). At the end, note the **Outputs**:

```
Key         ApiUrl
Value       https://[ID].execute-api.us-east-1.amazonaws.com

Key         StateMachineArn
Value       arn:aws:states:us-east-1:[ACCOUNT]:stateMachine:scrappy-ScrapingStateMachine-[ID]

Key         ResultsBucketName
Value       scrappy-results-[ACCOUNT]-us-east-1
```

### 4.4 Set STATE_MACHINE_ARN on the API Lambda

The API Lambda needs to know the ARN of the State Machine to trigger scraping jobs. SAM cannot wire this automatically (circular reference), so set it once manually.

First, find the exact Lambda function name:
```bash
aws lambda list-functions \
  --region us-east-1 \
  --query "Functions[?starts_with(FunctionName, 'scrappy-ApiFunction')].FunctionName"
```

Then update its environment:
```bash
aws lambda update-function-configuration \
  --function-name scrappy-ApiFunction-[ID] \
  --environment "Variables={
    STATE_MACHINE_ARN=arn:aws:states:us-east-1:[ACCOUNT]:stateMachine:scrappy-ScrapingStateMachine-[ID],
    RESULTS_BUCKET=scrappy-results-[ACCOUNT]-us-east-1
  }" \
  --region us-east-1
```

> This only needs to be done once. CI/CD only updates the function code, not its configuration.

---

## Phase 5 — IAM Role for GitHub Actions (OIDC)

GitHub Actions authenticates with AWS using short-lived tokens (OIDC) instead of long-lived access keys. This is the recommended approach — no AWS credentials stored in GitHub.

### 5.1 Register the GitHub OIDC provider in AWS

This is done once per AWS account:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  --region us-east-1
```

Verify:
```bash
aws iam list-open-id-connect-providers
```

### 5.2 Create the trust policy

Create a file `trust-policy.json` (replace `[ACCOUNT-ID]`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::[ACCOUNT-ID]:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:maxi-89/scrappy-backend:*"
        }
      }
    }
  ]
}
```

### 5.3 Create the role

```bash
aws iam create-role \
  --role-name scrappy-github-deploy \
  --assume-role-policy-document file://trust-policy.json
```

Note the `Arn` from the output:
```
arn:aws:iam::[ACCOUNT-ID]:role/scrappy-github-deploy
```

### 5.4 Create the permissions policy

Create a file `deploy-policy.json` (replace `[ACCOUNT-ID]`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRAuth",
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    },
    {
      "Sid": "ECRPush",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "arn:aws:ecr:us-east-1:[ACCOUNT-ID]:repository/scrappy-backend"
    },
    {
      "Sid": "LambdaDeploy",
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration"
      ],
      "Resource": "arn:aws:lambda:us-east-1:[ACCOUNT-ID]:function:scrappy-ApiFunction-*"
    }
  ]
}
```

Attach it to the role:
```bash
aws iam put-role-policy \
  --role-name scrappy-github-deploy \
  --policy-name scrappy-deploy-policy \
  --policy-document file://deploy-policy.json
```

---

## Phase 6 — GitHub Repository Secret

1. Go to your GitHub repo: `github.com/maxi-89/scrappy-backend`
2. Click **Settings → Secrets and variables → Actions**.
3. Click **New repository secret**.
4. Fill in:
   - **Name**: `AWS_DEPLOY_ROLE_ARN`
   - **Value**: `arn:aws:iam::[ACCOUNT-ID]:role/scrappy-github-deploy`
5. Click **Add secret**.

---

## Phase 7 — Update Stripe Webhook URL

Now that you have the API Gateway URL from Phase 4.3:

1. Go to **Stripe → Developers → Webhooks**.
2. Click on the webhook endpoint you created in Phase 3.3.
3. Click **Update endpoint**.
4. Set URL to:
   ```
   https://[ID].execute-api.us-east-1.amazonaws.com/webhooks/stripe
   ```
5. Save.

> To test the webhook locally: use `stripe listen --forward-to localhost:8000/webhooks/stripe`

---

## Phase 8 — First Release

Trigger the CI/CD pipeline by pushing a version tag to `master`:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Monitor the pipeline at:
```
https://github.com/maxi-89/scrappy-backend/actions
```

The pipeline runs two jobs in sequence:
1. **Tests & Quality** — ruff, mypy, pytest (must pass before deploy)
2. **Build & Deploy** — Docker build → push to ECR → update Lambda

Total time: ~4-6 minutes.

---

## Phase 9 — Custom Domain

This phase sets up `api.scrappy.io` (backend) and `scrappy.io` (frontend) instead of the auto-generated AWS and Vercel URLs. It requires owning the domain and having access to its DNS settings.

### 9.1 Buy or transfer the domain to Route 53

**Option A — Register a new domain in Route 53:**
1. Go to **AWS Console → Route 53 → Domains → Register domain**.
2. Search for `scrappy.io`, select it, and complete the purchase.
3. Route 53 automatically creates a **Hosted Zone** for the domain.

**Option B — Use a domain registered elsewhere (GoDaddy, Namecheap, etc.):**
1. Go to **Route 53 → Hosted zones → Create hosted zone**.
2. Fill in:
   - **Domain name**: `scrappy.io`
   - **Type**: Public hosted zone
3. Click **Create hosted zone**.
4. Route 53 shows 4 **NS (nameserver) records** — e.g.:
   ```
   ns-123.awsdns-12.com
   ns-456.awsdns-34.net
   ns-789.awsdns-56.org
   ns-012.awsdns-78.co.uk
   ```
5. Go to your domain registrar (GoDaddy, Namecheap, etc.) and replace its nameservers with these 4 values.
6. DNS propagation takes 10 minutes to 48 hours.

### 9.2 Request an SSL certificate in ACM

API Gateway requires an ACM certificate **in `us-east-1`** for custom domains.

```bash
aws acm request-certificate \
  --domain-name "scrappy.io" \
  --subject-alternative-names "*.scrappy.io" \
  --validation-method DNS \
  --region us-east-1
```

Note the `CertificateArn` from the output.

**Validate the certificate via DNS:**

```bash
# Get the CNAME validation record
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:us-east-1:[ACCOUNT]:certificate/[ID] \
  --region us-east-1 \
  --query "Certificate.DomainValidationOptions[0].ResourceRecord"
```

Output:
```json
{
  "Name": "_abc123.scrappy.io.",
  "Type": "CNAME",
  "Value": "_def456.acm-validations.aws."
}
```

Add this CNAME record to Route 53:
```bash
# Get your Hosted Zone ID first
aws route53 list-hosted-zones \
  --query "HostedZones[?Name=='scrappy.io.'].Id" \
  --output text
# Returns: /hostedzone/[ZONE-ID]

# Create the validation CNAME record
aws route53 change-resource-record-sets \
  --hosted-zone-id [ZONE-ID] \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "_abc123.scrappy.io.",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{"Value": "_def456.acm-validations.aws."}]
      }
    }]
  }'
```

Wait for the certificate to be validated (~2-5 minutes):
```bash
aws acm wait certificate-validated \
  --certificate-arn arn:aws:acm:us-east-1:[ACCOUNT]:certificate/[ID] \
  --region us-east-1
```

### 9.3 Create custom domain in API Gateway

1. Go to **AWS Console → API Gateway → Custom domain names → Create**.
2. Fill in:
   - **Domain name**: `api.scrappy.io`
   - **ACM certificate**: select the certificate created in 9.2
3. Click **Create domain name**.
4. Note the **API Gateway domain name** shown after creation — e.g.:
   ```
   d-abc123xyz.execute-api.us-east-1.amazonaws.com
   ```

**Map the custom domain to the API stage:**
1. In the custom domain detail, click **API mappings → Add new mapping**.
2. Select your API and stage (`$default`).
3. Leave **Path** empty (maps the root).
4. Click **Save**.

### 9.4 Point api.scrappy.io to API Gateway (Route 53)

```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id [ZONE-ID] \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.scrappy.io.",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z2FDTNDATAQYW2",
          "DNSName": "d-abc123xyz.execute-api.us-east-1.amazonaws.com.",
          "EvaluateTargetHealth": false
        }
      }
    }]
  }'
```

> `Z2FDTNDATAQYW2` is the fixed Route 53 Hosted Zone ID for API Gateway — it is always this value regardless of region.

Verify (wait 1-2 minutes for DNS):
```bash
curl https://api.scrappy.io/offers
```

### 9.5 Deploy frontend to Vercel and point scrappy.io

**Deploy to Vercel:**
1. Go to [vercel.com](https://vercel.com) → **New Project**.
2. Import the `scrappy-frontend` GitHub repository.
3. Set environment variables in Vercel dashboard:
   ```
   NEXT_PUBLIC_API_URL        = https://api.scrappy.io
   NEXT_PUBLIC_AUTH0_DOMAIN   = [TENANT].us.auth0.com
   NEXT_PUBLIC_AUTH0_CLIENT_ID = [CLIENT-ID from Phase 2.3]
   NEXT_PUBLIC_AUTH0_AUDIENCE  = https://api.scrappy.io
   NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY = pk_live_...
   ```
4. Click **Deploy**. Vercel assigns a URL: `scrappy-frontend.vercel.app`.

**Add custom domain in Vercel:**
1. In the project dashboard, go to **Settings → Domains**.
2. Add `scrappy.io` and `www.scrappy.io`.
3. Vercel shows the DNS records to create.

**Add the records in Route 53:**
```bash
# scrappy.io → Vercel (A record with Vercel's IP)
aws route53 change-resource-record-sets \
  --hosted-zone-id [ZONE-ID] \
  --change-batch '{
    "Changes": [
      {
        "Action": "CREATE",
        "ResourceRecordSet": {
          "Name": "scrappy.io.",
          "Type": "A",
          "TTL": 300,
          "ResourceRecords": [{"Value": "76.76.21.21"}]
        }
      },
      {
        "Action": "CREATE",
        "ResourceRecordSet": {
          "Name": "www.scrappy.io.",
          "Type": "CNAME",
          "TTL": 300,
          "ResourceRecords": [{"Value": "cname.vercel-dns.com."}]
        }
      }
    ]
  }'
```

> Vercel's IP `76.76.21.21` is their standard A record for root domains. Confirm the exact values in Vercel's domain settings page for your project.

### 9.6 Update all services with the final URLs

Now that you have real domains, update the configurations set in earlier phases:

**Auth0 — update callback URLs (Phase 2.3):**
- **Allowed Callback URLs**: `https://scrappy.io/auth/callback, http://localhost:3000/auth/callback`
- **Allowed Logout URLs**: `https://scrappy.io, http://localhost:3000`
- **Allowed Web Origins**: `https://scrappy.io, http://localhost:3000`

**Stripe — update webhook URL (Phase 7):**
- New URL: `https://api.scrappy.io/webhooks/stripe`

---

## Phase 10 — Verification Checklist

After the first deploy, verify each component:

```bash
# 1. API is reachable (use custom domain if Phase 9 is done, otherwise the raw API Gateway URL)
curl https://api.scrappy.io/docs
# or: curl https://[ID].execute-api.us-east-1.amazonaws.com/docs

# 2. Offers endpoint works (no auth required)
curl https://api.scrappy.io/offers

# 3. Admin key works
curl -H "X-Admin-Key: [YOUR-ADMIN-KEY]" \
  https://api.scrappy.io/admin/pricing

# 4. Lambda logs (CloudWatch)
aws logs tail /aws/lambda/scrappy-ApiFunction-[ID] --follow

# 5. Step Functions state machine exists
aws stepfunctions list-state-machines \
  --region us-east-1 \
  --query "stateMachines[*].name"

# 6. S3 bucket exists
aws s3 ls | grep scrappy-results
```

---

## Subsequent Releases

For all future code deploys, just tag and push:

```bash
git tag v1.0.1
git push origin v1.0.1
```

**Infrastructure changes** (adding Lambdas, modifying Step Functions, etc.) still require:
```bash
sam build && sam deploy
```

**Schema changes** (new DB migration) require running Alembic manually or as part of a pre-deploy step:
```bash
DATABASE_URL="..." uv run alembic upgrade head
```

---

## Reference: What deploys what

| Tool | Provisions | When to run |
|---|---|---|
| `alembic upgrade head` | DB tables (Supabase) | First deploy + every new migration |
| `sam deploy` | All Lambda functions, Step Functions, S3, API Gateway | First deploy + infrastructure changes |
| `git tag + push` (CI/CD) | API Lambda code (Docker image) | Every code release |
| Manual `update-function-configuration` | Lambda env vars | Once after first `sam deploy` |

## Reference: All environment variables

| Variable | Where set | Value |
|---|---|---|
| `DATABASE_URL` | SSM `/scrappy/database-url` | Supabase asyncpg connection string |
| `AUTH0_DOMAIN` | SSM `/scrappy/auth0-domain` | `[TENANT].us.auth0.com` |
| `AUTH0_AUDIENCE` | SSM `/scrappy/auth0-audience` | `https://api.scrappy.io` |
| `STRIPE_SECRET_KEY` | SSM `/scrappy/stripe-secret-key` | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | SSM `/scrappy/stripe-webhook-secret` | `whsec_...` |
| `ADMIN_API_KEY` | SSM `/scrappy/admin-api-key` | Random secret string |
| `GOOGLE_MAPS_API_KEY` | SSM `/scrappy/google-maps-api-key` | `AIza...` |
| `STATE_MACHINE_ARN` | Lambda env (manual, Phase 4.4) | ARN from SAM output |
| `RESULTS_BUCKET` | Lambda env (manual, Phase 4.4) | Bucket name from SAM output |
