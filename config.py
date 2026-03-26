from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    Конфиг приложения. Pydantic-settings читает значения из .env файла
    и валидирует типы. Если обязательное поле отсутствует — сразу ошибка.
    """

    bot_token: str
    database_url: str

    # Храним как строку — pydantic-settings не будет пытаться парсить как JSON.
    # Доступ к распарсенному списку — через property ниже.
    # В .env формат: ALLOWED_USER_IDS=123456789,987654321
    allowed_user_ids_raw: str = Field(default="", alias="ALLOWED_USER_IDS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Позволяет алиасам (ALLOWED_USER_IDS) работать при инициализации
        populate_by_name=True,
    )

    def model_post_init(self, __context) -> None:
        """Вызывается после __init__ — читаем сырое значение из env напрямую."""
        import os
        from dotenv import load_dotenv
        load_dotenv()
        raw = os.getenv("ALLOWED_USER_IDS", "")
        # Сохраняем через object.__setattr__ т.к. pydantic модели иммутабельны по умолчанию
        object.__setattr__(self, "_allowed_ids_parsed", self._parse_ids(raw))

    @staticmethod
    def _parse_ids(raw: str) -> list[int]:
        """Преобразует строку '123,456' в список [123, 456]."""
        if not raw.strip():
            return []
        return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]

    @property
    def allowed_user_ids(self) -> list[int]:
        return getattr(self, "_allowed_ids_parsed", [])


# Единственный экземпляр конфига на всё приложение (singleton).
# Импортируй в других файлах: from config import settings
settings = Settings()