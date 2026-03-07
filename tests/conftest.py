import os

# Set required environment variables for all tests before any module imports them.
os.environ.setdefault("AUTH0_DOMAIN", "test.auth0.com")
os.environ.setdefault("AUTH0_AUDIENCE", "https://test.api.scrappy.io")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
