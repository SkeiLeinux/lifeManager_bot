"""
handlers/lists.py — хендлеры для работы со списками.

Ключевые изменения по сравнению с первой версией:
  1. callback.answer() вызывается В НАЧАЛЕ хендлера — Telegram сразу получает
     подтверждение и не показывает "часики". Потом можно делать любые запросы к БД.
  2. Список отображается как текст сообщения (format_items_text),
     а не как кнопки — текст не обрезается.
  3. Редактирование и удаление — через выбор номера пункта (numbers_keyboard),
     а не отдельные кнопки у каждого пункта.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User
from services import ListService
from handlers.keyboards import (
    categories_keyboard,
    category_keyboard,
    confirm_keyboard,
    back_keyboard,
    numbers_keyboard,
    format_items_text,
)

router = Router()


# ── FSM States ────────────────────────────────────────────────────────────────

class ListStates(StatesGroup):
    waiting_for_category_name = State()
    waiting_for_item_text = State()
    waiting_for_item_edit = State()   # ждём новый текст (после выбора номера)


# ── Вспомогательная функция ───────────────────────────────────────────────────

async def _show_category(
    target,  # Message или CallbackQuery
    user: User,
    session: AsyncSession,
    category_id: int,
    prefix: str = "",
):
    """
    Показывает/обновляет содержимое категории.
    Используется из многих хендлеров — вынесено чтобы не дублировать.
    """
    list_service = ListService(session)
    result = await list_service.get_items(user, category_id)

    if not result.success:
        if isinstance(target, CallbackQuery):
            await target.answer(result.message, show_alert=True)
        else:
            await target.answer(result.message)
        return

    text = (prefix + "\n\n" if prefix else "") + format_items_text(
        result.category, result.items
    )
    keyboard = category_keyboard(result.category, result.items)

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")


# ── /lists ────────────────────────────────────────────────────────────────────

@router.message(Command("lists"))
async def cmd_lists(message: Message, user: User, session: AsyncSession):
    list_service = ListService(session)
    result = await list_service.get_categories(user)

    if not result.success:
        await message.answer(result.message)
        return

    if not result.categories:
        await message.answer(
            "У тебя пока нет списков.\nНажми кнопку ниже чтобы создать первый!",
            reply_markup=categories_keyboard([]),
        )
        return

    await message.answer(
        "📋 <b>Твои списки:</b>",
        reply_markup=categories_keyboard(result.categories),
        parse_mode="HTML",
    )


# ── Навигация по категориям ───────────────────────────────────────────────────

@router.callback_query(F.data == "cat:list")
async def cb_categories_list(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    await callback.answer()  # ← сразу, до запросов к БД
    list_service = ListService(session)
    result = await list_service.get_categories(user)

    if not result.success:
        await callback.message.edit_text(result.message)
        return

    await callback.message.edit_text(
        "📋 <b>Твои списки:</b>",
        reply_markup=categories_keyboard(result.categories or []),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cat:open:"))
async def cb_category_open(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    await callback.answer()  # ← сразу
    category_id = int(callback.data.split(":")[2])
    await _show_category(callback, user, session, category_id)


# ── Создание категории ────────────────────────────────────────────────────────

@router.callback_query(F.data == "cat:new")
async def cb_category_new(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "Введи название категории.\n\n"
        "Можно добавить эмодзи в начало: <code>🛒 Продукты</code>\n"
        "Или просто: <code>Фильмы</code>",
        parse_mode="HTML",
        reply_markup=back_keyboard("cat:list"),
    )
    await state.set_state(ListStates.waiting_for_category_name)


@router.message(ListStates.waiting_for_category_name)
async def handle_category_name(
    message: Message, state: FSMContext, user: User, session: AsyncSession
):
    text = message.text.strip()
    if not text or len(text) > 60:
        await message.answer("Название должно быть от 1 до 60 символов. Попробуй ещё раз:")
        return

    emoji = None
    name = text
    if text and not text[0].isalnum() and not text[0].isspace():
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            emoji = parts[0]
            name = parts[1]

    list_service = ListService(session)
    result = await list_service.create_category(user, name, emoji)
    await state.clear()

    if not result.success:
        await message.answer(result.message)
        return

    categories_result = await list_service.get_categories(user)
    await message.answer(
        f"✅ {result.message}\n\n📋 <b>Твои списки:</b>",
        reply_markup=categories_keyboard(categories_result.categories or []),
        parse_mode="HTML",
    )


# ── Удаление категории ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cat:delete:"))
async def cb_category_delete(callback: CallbackQuery):
    await callback.answer()
    category_id = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        "⚠️ Удалить категорию и все её пункты?",
        reply_markup=confirm_keyboard("cat_del", category_id),
    )


@router.callback_query(F.data.startswith("cat_del:confirm:"))
async def cb_category_delete_confirm(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    await callback.answer()
    category_id = int(callback.data.split(":")[2])
    list_service = ListService(session)
    result = await list_service.delete_category(user, category_id)

    if not result.success:
        await callback.message.edit_text(result.message)
        return

    categories_result = await list_service.get_categories(user)
    await callback.message.edit_text(
        f"✅ {result.message}\n\n📋 <b>Твои списки:</b>",
        reply_markup=categories_keyboard(categories_result.categories or []),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cat_del:cancel:"))
async def cb_category_delete_cancel(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    await callback.answer()
    category_id = int(callback.data.split(":")[2])
    await _show_category(callback, user, session, category_id)


# ── Добавление пункта ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("item:new:"))
async def cb_item_new(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    category_id = int(callback.data.split(":")[2])
    await state.update_data(category_id=category_id)
    await callback.message.edit_text(
        "Введи текст нового пункта:",
        reply_markup=back_keyboard(f"cat:open:{category_id}"),
    )
    await state.set_state(ListStates.waiting_for_item_text)


@router.message(ListStates.waiting_for_item_text)
async def handle_item_text(
    message: Message, state: FSMContext, user: User, session: AsyncSession
):
    data = await state.get_data()
    category_id = data["category_id"]

    text = message.text.strip()
    if not text or len(text) > 500:
        await message.answer("Текст должен быть от 1 до 500 символов. Попробуй ещё раз:")
        return

    list_service = ListService(session)
    add_result = await list_service.add_item(user, category_id, text)
    await state.clear()

    if not add_result.success:
        await message.answer(add_result.message)
        return

    await _show_category(message, user, session, category_id, prefix="✅ Добавлено!")


# ── Toggle (отметить по номеру) ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("item:toggle:"))
async def cb_item_toggle(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    await callback.answer()  # ← сразу — убирает "часики"
    item_id = int(callback.data.split(":")[2])
    list_service = ListService(session)
    result = await list_service.toggle_item(user, item_id)

    if not result.success:
        return

    await _show_category(callback, user, session, result.item.category_id)


# ── Редактирование: выбор пункта ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("item:edit_ask:"))
async def cb_item_edit_ask(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    """Показываем пронумерованные кнопки — пользователь выбирает какой пункт редактировать."""
    await callback.answer()
    category_id = int(callback.data.split(":")[2])
    list_service = ListService(session)
    result = await list_service.get_items(user, category_id)

    if not result.success or not result.items:
        return

    text = format_items_text(result.category, result.items)
    await callback.message.edit_text(
        text + "\n\n<i>Выбери номер пункта для редактирования:</i>",
        reply_markup=numbers_keyboard(result.items, "edit", category_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("item:edit_pick:"))
async def cb_item_edit_pick(callback: CallbackQuery, state: FSMContext):
    """Пользователь выбрал номер — просим ввести новый текст."""
    await callback.answer()
    item_id = int(callback.data.split(":")[2])
    await state.update_data(item_id=item_id)
    await callback.message.edit_text("Введи новый текст для пункта:")
    await state.set_state(ListStates.waiting_for_item_edit)


@router.message(ListStates.waiting_for_item_edit)
async def handle_item_edit(
    message: Message, state: FSMContext, user: User, session: AsyncSession
):
    data = await state.get_data()
    item_id = data["item_id"]

    new_text = message.text.strip()
    if not new_text or len(new_text) > 500:
        await message.answer("Текст должен быть от 1 до 500 символов. Попробуй ещё раз:")
        return

    list_service = ListService(session)
    edit_result = await list_service.edit_item(user, item_id, new_text)
    await state.clear()

    if not edit_result.success:
        await message.answer(edit_result.message)
        return

    await _show_category(
        message, user, session, edit_result.item.category_id, prefix="✅ Изменено!"
    )


# ── Удаление: выбор пункта ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("item:delete_ask:"))
async def cb_item_delete_ask(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    """Показываем пронумерованные кнопки — пользователь выбирает какой пункт удалить."""
    await callback.answer()
    category_id = int(callback.data.split(":")[2])
    list_service = ListService(session)
    result = await list_service.get_items(user, category_id)

    if not result.success or not result.items:
        return

    text = format_items_text(result.category, result.items)
    await callback.message.edit_text(
        text + "\n\n<i>Выбери номер пункта для удаления:</i>",
        reply_markup=numbers_keyboard(result.items, "delete", category_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("item:delete_pick:"))
async def cb_item_delete_pick(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    """Удаляем сразу по нажатию без доп. подтверждения."""
    await callback.answer("Удалено")
    item_id = int(callback.data.split(":")[2])
    list_service = ListService(session)

    from repositories import ListRepository
    item = await ListRepository(session).get_item(item_id)
    if not item:
        return
    category_id = item.category_id

    await list_service.delete_item(user, item_id)
    await _show_category(callback, user, session, category_id)


# ── Очистка отмеченных ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("item:clear:"))
async def cb_items_clear(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    await callback.answer()
    category_id = int(callback.data.split(":")[2])
    list_service = ListService(session)
    result = await list_service.clear_checked(user, category_id)

    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return

    await _show_category(callback, user, session, category_id, prefix=f"🧹 {result.message}")