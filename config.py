"""
WhistleVault configuration.

All secrets and environment-specific values are loaded from environment
variables (via python-dotenv locally). Never commit a real .env file.
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


def _database_url() -> str:
    """
    Build a SQLAlchemy-compatible, SSL-enforced Postgres URL.

    Render/Neon/Supabase all provide a DATABASE_URL in the
    postgres:// or postgresql:// form. SQLAlchemy 1.4+/2.x requires the
    'postgresql://' scheme, and we force sslmode=require unless the
    caller already specified one (important for managed cloud Postgres).
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        if os.environ.get("FLASK_ENV") == "testing":
            return "sqlite:///:memory:"
        raise RuntimeError("DATABASE_URL must be set; configure PostgreSQL for this environment.")

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    if url.startswith("postgresql://") and "sslmode" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"

    return url


class BaseConfig:
    # --- Core ---
    SECRET_KEY = os.environ.get("SECRET_KEY")
    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = False
    TESTING = False

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Stateless app + pooled connections so the backend scales horizontally
    # behind a load balancer without exhausting the DB's connection limit.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": int(os.environ.get("DB_POOL_SIZE", 5)),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", 10)),
    }

    # --- Sessions / cookies ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    # --- Admin (single hardcoded account per spec, overridable via env) ---
    # NOTE: change these via environment variables before deploying publicly.
    # The defaults exist only so the app boots out-of-the-box in dev.
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
    ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")

    # --- OTP ---
    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = int(os.environ.get("OTP_EXPIRY_MINUTES", 10))
    OTP_MAX_ATTEMPTS = 5
    PASSWORD_RESET_EXPIRY_MINUTES = int(os.environ.get("PASSWORD_RESET_EXPIRY_MINUTES", 30))

    # --- Mail (abstracted; falls back to console/log "simulated" sender) ---
    MAIL_PROVIDER = os.environ.get("MAIL_PROVIDER", "console")  # console | smtp
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "no-reply@whistlevault.local")

    # --- Uploads ---
    MEDIA_FOLDER = os.environ.get("MEDIA_FOLDER", os.path.join(basedir, "media"))
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB upload cap
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # --- Storage backend abstraction (local | s3) ---
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "s3")
    S3_BUCKET = os.environ.get("S3_BUCKET", "")
    S3_REGION = os.environ.get("S3_REGION", "")
    S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")

    # --- Rate limiting ---
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    # --- Pagination ---
    POSTS_PER_PAGE = 12
    COMMENTS_PAGE_SIZE = 200  # comments are loaded as a full tree, not paginated

    # --- AI (Groq) ---
    # Optional. If unset, AI-assisted category suggestion / moderation
    # flagging / PII warnings are silently skipped (see utils/ai.py) --
    # the app is fully functional without this key.
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    # Groq's model lineup changes over time; check console.groq.com/docs/models
    # for the current list and override here if the default is retired.
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")


class DevelopmentConfig(BaseConfig):
    ENV = "development"
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    ENV = "production"
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    return config_by_name.get(os.environ.get("FLASK_ENV", "production"), ProductionConfig)
