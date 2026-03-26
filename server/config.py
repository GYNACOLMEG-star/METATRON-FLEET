import os
import secrets

class Settings:
    DB_PATH: str = os.environ.get("DB_PATH", "metatron.db")
    SECRET_KEY: str = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    SERVER_HOST: str = os.environ.get("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.environ.get("PORT") or os.environ.get("SERVER_PORT", "8000"))
    MACHINE_TIMEOUT_SECONDS: int = int(os.environ.get("MACHINE_TIMEOUT_SECONDS", "30"))
    OPENCLAW_QUEUE_MAXSIZE: int = int(os.environ.get("OPENCLAW_QUEUE_MAXSIZE", "100"))
    HEARTBEAT_CHECK_INTERVAL: int = int(os.environ.get("HEARTBEAT_CHECK_INTERVAL", "10"))

settings = Settings()
