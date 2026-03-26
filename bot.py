"""
bot.py — точка входа. Здесь собирается всё вместе и запускается бот.

Порядок важен:
  1. Создаём бота и dispatcher
  2. Регистрируем middleware
  3. Включаем роутеры
  4. При старте создаём таблицы в БД
  5. Запускаем polling
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from db import create_tables
from db.database import async_session_maker
from handlers import common, lists
from handlers.middleware import AuthMiddleware

# Настраиваем логирование — будем видеть в консоли что происходит
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    # Bot — объект для отправки запросов к Telegram API.
    # DefaultBotProperties задаёт настройки по умолчанию для всех сообщений.
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Dispatcher — "мозг" aiogram. Он получает обновления от Telegram
    # и направляет их в нужные хендлеры.
    # MemoryStorage хранит FSM-состояния в памяти.
    # Для продакшна лучше использовать RedisStorage — он выживает при рестарте.
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware для работы с базой данных.
    # Оно добавляет сессию в data['session'] для каждого апдейта.
    # Используем фабричный паттерн чтобы каждый запрос получал свою сессию.
    from aiogram import BaseMiddleware
    from aiogram.types import TelegramObject
    from typing import Any, Callable, Awaitable

    class SessionMiddleware(BaseMiddleware):
        async def __call__(
            self,
            handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: dict[str, Any],
        ) -> Any:
            async with async_session_maker() as session:
                data["session"] = session
                return await handler(event, data)

    # Порядок регистрации middleware важен:
    # SessionMiddleware должна быть первой — она создаёт сессию,
    # AuthMiddleware использует её чтобы найти/создать пользователя.
    dp.update.middleware(SessionMiddleware())
    dp.update.middleware(AuthMiddleware())

    # Регистрируем роутеры — они содержат хендлеры команд и callback-ов.
    # common сначала: там /start и /help
    dp.include_router(common.router)
    dp.include_router(lists.router)

    # Создаём таблицы при первом запуске (если их ещё нет)
    logger.info("Инициализация базы данных...")
    await create_tables()

    # Удаляем вебхук если был (на случай переключения с webhook на polling)
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Бот запущен!")
    try:
        # Polling — бот сам спрашивает у Telegram: "есть новые сообщения?"
        # allowed_updates=dp.resolve_used_update_types() — оптимизация:
        # Telegram будет присылать только те типы обновлений, которые
        # реально обрабатываются в хендлерах.
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
