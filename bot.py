"""
bot.py — точка входа.

Изменение: вместо create_all() теперь запускаем alembic upgrade head.
Это значит что при каждом старте бота все новые миграции применяются
автоматически. Безопасно — если миграций нет, ничего не происходит.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject
from typing import Any, Callable, Awaitable

from config import settings
from db.database import async_session_maker
from handlers import common, lists
from handlers.middleware import AuthMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_migrations():
    """
    Запускает alembic upgrade head синхронно.
    Alembic не асинхронный, поэтому вызываем через subprocess —
    это стандартный подход для запуска миграций при старте приложения.
    """
    import subprocess, sys
    logger.info("Применяем миграции базы данных...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        encoding="utf-8",  # явно указываем UTF-8 — иначе Windows использует cp1251
    )
    if result.returncode != 0:
        logger.error(f"Ошибка миграций:\n{result.stderr}")
        raise RuntimeError("Не удалось применить миграции")
    logger.info("Миграции применены успешно")


class SessionMiddleware(BaseMiddleware):
    """Создаёт сессию БД для каждого входящего апдейта."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session_maker() as session:
            data["session"] = session
            return await handler(event, data)


async def main():
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    for observer in (dp.message, dp.callback_query):
        observer.middleware(SessionMiddleware())
        observer.middleware(AuthMiddleware())

    dp.include_router(common.router)
    dp.include_router(lists.router)

    run_migrations()

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен!")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())