from pydantic_settings import BaseSettings

_DEV_DEFAULT = "change-me"


class Settings(BaseSettings):
    app_env: str = "dev"
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_db: str = "thuyetminh"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = _DEV_DEFAULT
    refresh_token_secret: str = _DEV_DEFAULT
    secret_key: str = _DEV_DEFAULT
    access_token_expire_min: int = 30
    refresh_token_expire_days: int = 7
    # bootstrap super admin: dev có mặc định, non-dev bắt buộc đặt qua env
    superadmin_username: str = "admin"
    superadmin_password: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    owner_daily_limit: int = 10
    pii_retention_days: int = 180
    cors_origins: str = "http://localhost:5173,http://localhost:4173"
    # quên mật khẩu: link đặt lại trỏ về frontend; gửi qua SMTP nếu có cấu hình
    public_base_url: str = "http://localhost:5173"
    password_reset_expire_min: int = 30
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    # ảnh quán
    max_image_bytes: int = 2 * 1024 * 1024

    def assert_secure(self) -> None:
        """Fail fast ở non-dev nếu còn secret mặc định hoặc thiếu mật khẩu super admin."""
        if self.app_env == "dev":
            return
        for name in ("jwt_secret", "refresh_token_secret", "secret_key"):
            if getattr(self, name).startswith(_DEV_DEFAULT):
                raise RuntimeError(f"{name.upper()} chưa được cấu hình")
        if not self.superadmin_password:
            raise RuntimeError("SUPERADMIN_PASSWORD chưa được cấu hình")

    @property
    def bootstrap_password(self) -> str:
        return self.superadmin_password or "admin12345"  # chỉ dùng ở dev

    @property
    def secure_cookies(self) -> bool:
        return self.app_env != "dev"

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)


settings = Settings()
