from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """
    Конфиг приложения. Pydantic-settings читает значения из .env файла
    и одновременно валидирует типы. Если обязательное поле отсутствует
    в .env — при запуске сразу получишь понятную ошибку.
    """

    bot_token: str
    database_url: str

    # Список разрешённых Telegram user_id.
    # В .env хранится как строка "123,456", pydantic сам разберёт.
    allowed_user_ids: list[int] = []

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_ids(cls, v):
        """Преобразует строку '123,456' в список [123, 456]."""
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v

    # Указываем pydantic-settings где искать .env файл
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Единственный экземпляр конфига на всё приложение (singleton-паттерн).
# Импортируй его в других файлах: from config import settings
settings = Settings()
