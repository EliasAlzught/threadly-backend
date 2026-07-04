"""
إعدادات التطبيق - يقرأها من environment variables
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Threadly API"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://threadly:threadly_dev_password@localhost:5432/threadly_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 أيام

    # MinIO / S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "threadly-images"
    MINIO_SECURE: bool = False

    # AI Provider Configuration
    AI_PROVIDER: str = "groq"  # groq | gemini | ollama
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Email
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM_EMAIL: str = "noreply@threadly.app"

    # Firebase (للـ Push Notifications)
    FIREBASE_CREDENTIALS_PATH: str = ""

    # ===== الاشتراكات والتاجر =====
    # القيم الافتراضية لأول تشغيل فقط - بعدها تُدار من جدول platform_settings
    # عبر لوحة الأدمن (PUT /api/admin/settings).
    DEFAULT_FREE_TRIAL_ENABLED: bool = True
    DEFAULT_FREE_TRIAL_DAYS: int = 14
    DEFAULT_MONTHLY_PRICE: float = 9.99
    DEFAULT_MONTHLY_PERIOD_DAYS: int = 30
    SUBSCRIPTION_CURRENCY: str = "USD"
    # تنبيه قرب انتهاء الاشتراك قبل كم يوم
    SUBSCRIPTION_EXPIRY_WARNING_DAYS: int = 3

    # إيميلات تُمنح صلاحية الأدمن تلقائياً عند التشغيل (bootstrap)
    ADMIN_EMAILS: list[str] = []

    # CORS
    CORS_ORIGINS: list[str] = ["*"]  # في الإنتاج: حدد domains معينة

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
