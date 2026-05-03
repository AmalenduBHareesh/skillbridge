# src/core/config.py
#
# PURPOSE: Load all environment variables into a typed Settings object.
# Using pydantic-settings means if a required variable is missing,
# the app will CRASH at startup with a clear error — better than
# mysterious failures at runtime.

from pydantic_settings import BaseSettings  # pydantic v2 settings helper


class Settings(BaseSettings):
    # DATABASE_URL: full postgres connection string.
    # pydantic will read this from the .env file automatically.
    DATABASE_URL: str

    # SECRET_KEY: random bytes used to sign/verify JWTs.
    # If an attacker gets this they can mint any token they want.
    SECRET_KEY: str

    # ALGORITHM: the signing algorithm. HS256 = HMAC-SHA256, symmetric.
    ALGORITHM: str = "HS256"

    # ACCESS_TOKEN_EXPIRE_MINUTES: how long a normal JWT lives.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # MONITORING_TOKEN_EXPIRE_MINUTES: short-lived scoped token for monitoring officer.
    MONITORING_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour

    # MONITORING_API_KEY: the hardcoded key the monitoring officer must present
    # alongside their JWT to get a scoped token. In prod this would be in a
    # secrets manager and rotatable.
    MONITORING_API_KEY: str = "monitoring-secret-api-key-2024"

    class Config:
        # pydantic-settings will look for a .env file in the working directory
        env_file = ".env"
        # If the same var appears in both the .env file and the real environment,
        # the real environment wins. Good for CI/CD.
        env_file_encoding = "utf-8"


# Instantiate once at import time. Every other module imports this object.
# This is the "singleton settings" pattern — one source of truth.
settings = Settings()
