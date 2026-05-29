from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # База данных
    DATABASE_URL: str = "sqlite+aiosqlite:///./messenger.db"
    # Ключ для прозрачного шифрования SQLite (через SQLCipher, если установлен пакет
    # sqlcipher3-binary/pysqlcipher3). Если пуст — шифрование отключено.
    DB_ENCRYPTION_KEY: str = ""
    # Принудительный TLS для PostgreSQL (sslmode=require). На SQLite не влияет.
    DB_REQUIRE_TLS: bool = True

    REDIS_URL: str = "redis://localhost:6379"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # Аутентификация
    SECRET_KEY: str = "super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 часа

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Файлы
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 100
    ALLOWED_UPLOAD_EXT: str = (
        "jpg,jpeg,png,gif,webp,bmp,svg,"
        "mp4,webm,mov,mkv,avi,"
        "mp3,wav,ogg,m4a,opus,flac,aac,"
        "pdf,doc,docx,xls,xlsx,ppt,pptx,txt,csv,zip,rar,7z"
    )

    # Бэкапы БД
    BACKUP_DIR: str = "backups"
    BACKUP_INTERVAL_HOURS: int = 6
    BACKUP_KEEP: int = 30  # сколько последних бэкапов хранить

    # Среда исполнения
    ENV: str = "development"  # production / development

    @property
    def cors_origins_list(self):
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def allowed_extensions(self):
        return {e.strip().lower().lstrip(".") for e in self.ALLOWED_UPLOAD_EXT.split(",") if e.strip()}

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() in ("prod", "production")

    class Config:
        env_file = ".env"


settings = Settings()


def validate_security_config():
    """Проверка критичных параметров безопасности при старте."""
    import warnings
    issues = []
    if settings.is_production:
        if settings.SECRET_KEY == "super-secret-key-change-in-production" or len(settings.SECRET_KEY) < 32:
            issues.append("SECRET_KEY должен быть установлен (не менее 32 символов) в production")
        if "sqlite" in settings.DATABASE_URL and not settings.DB_ENCRYPTION_KEY:
            warnings.warn("В production рекомендуется DB_ENCRYPTION_KEY (SQLCipher) или PostgreSQL c TLS")
    if issues:
        raise RuntimeError("Небезопасная конфигурация: " + "; ".join(issues))
