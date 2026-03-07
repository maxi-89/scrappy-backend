# AWS Lambda container image — Scrappy Backend
FROM public.ecr.aws/lambda/python:3.12

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR ${LAMBDA_TASK_ROOT}

# Install production dependencies first (layer cache)
COPY pyproject.toml uv.lock ./
RUN uv pip install --system --no-dev .

# Copy application source
COPY app/ ./app/
COPY main.py .

# Lambda invokes this handler: main.handler (Mangum)
CMD ["main.handler"]
