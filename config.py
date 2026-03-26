import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    allowed_user_ids_raw: str = ""
    # Telegram ID администратора — сюда приходят уведомления об ошибках.
    # Узнать свой ID можно у @userinfobot в Telegram.
    admin_telegram_id: int | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    @property
    def allowed_user_ids(self) -> list[int]:
        if not self.allowed_user_ids_raw.strip():
            return []
        return [
            int(x.strip())
            for x in self.allowed_user_ids_raw.split(",")
            if x.strip().isdigit()
        ]


settings = Settings()