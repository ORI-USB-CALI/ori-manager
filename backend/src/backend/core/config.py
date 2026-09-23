from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    app_env: str = "development"

    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "ori_manager"
    database_user: str = "ori_user"
    database_password: SecretStr
    database_sslmode: str = "require"
    document_storage_provider: str = "local"
    document_storage_path: str = "var/documentos"
    microsoft_client_id: str | None = None
    microsoft_client_secret: SecretStr | None = None
    microsoft_refresh_token: SecretStr | None = None
    microsoft_storage_root: str | None = None
    email_provider: str = "local"
    brevo_api_key: SecretStr | None = None
    email_from_address: str | None = None
    email_from_name: str | None = None
    public_frontend_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=self.database_password.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            query={"sslmode": self.database_sslmode},
        )


settings = Settings()
