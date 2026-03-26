"""
handlers/lists.py — хендлеры для работы со списками.

Здесь весь пользовательский интерфейс списков:
  - команда /lists
  - навигация по категориям (callback кнопки)
  - добавление/редактирование/удаление через FSM-диалоги

Паттерн работы с callback:
  Callback приходит со строкой типа "cat:open:42" или "item:delete:7".
  Мы разбираем её на части и вызываем нужную логику.
  Ответ всегда через edit_text (редактируем то же сообщение),
  а не send_message — это чище выглядит.
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
)

router = Router()


# ── FSM States ────────────────────────────────────────────────────────────────

class ListStates(StatesGroup):
    waiting_for_category_name = State()  # ждём "🛒 Продукты" или просто "Продукты"
    waiting_for_item_text = State()      # ждём текст нового пункта
    waiting_for_item_edit = State()      # ждём новый текст пункта при редактировании


# ── /lists ────────────────────────────────────────────────────────────────────

@router.message(Command("lists"))
async def cmd_lists(message: Message, user: User, session: AsyncSession):
    """Показывает все категории пользователя."""
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
        "📋 Твои списки:",
        reply_markup=categories_keyboard(result.categories),
    )


# ── Навигация по категориям (callback) ────────────────────────────────────────

@router.callback_query(F.data == "cat:list")
async def cb_categories_list(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    """Обновить список категорий (кнопка 'Назад')."""
    list_service = ListService(session)
    result = await list_service.get_categories(user)

    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return

    await callback.message.edit_text(
        "📋 Твои списки:",
        reply_markup=categories_keyboard(result.categories or []),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:open:"))
async def cb_category_open(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    """Открыть категорию — показать её пункты."""
    category_id = int(callback.data.split(":")[2])
    list_service = ListService(session)
    result = await list_service.get_items(user, category_id)

    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return

    cat = result.category
    title = f"{cat.emoji} {cat.name}" if cat.emoji else cat.name
    items_count = len(result.items)
    checked_count = sum(1 for i in result.items if i.is_checked)

    header = f"<b>{title}</b>  ({items_count} пунктов"
    if checked_count:
        header += f", {checked_count} отмечено"
    header += ")"

    if not result.items:
        header += "\n\nСписок пуст. Добавь первый пункт!"

    await callback.message.edit_text(
        header,
        reply_markup=category_keyboard(cat, result.items),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Создание категории ────────────────────────────────────────────────────────

@router.callback_query(F.data == "cat:new")
async def cb_category_new(callback: CallbackQuery, state: FSMContext):
    """Начало диалога создания категории."""
    await callback.message.edit_text(
        "Введи название категории.\n\n"
        "Можно добавить эмодзи в начало: <code>🛒 Продукты</code>\n"
        "Или просто: <code>Фильмы</code>",
        parse_mode="HTML",
        reply_markup=back_keyboard("cat:list"),
    )
    await state.set_state(ListStates.waiting_for_category_name)
    await callback.answer()


@router.message(ListStates.waiting_for_category_name)
async def handle_category_name(
    message: Message, state: FSMContext, user: User, session: AsyncSession
):
    """Создаём категорию по введённому названию."""
    text = message.text.strip()
    if not text or len(text) > 60:
        await message.answer("Название должно быть от 1 до 60 символов. Попробуй ещё раз:")
        return

    # Парсим эмодзи: если первый символ — эмодзи, берём его отдельно
    emoji = None
    name = text
    # Простая эвристика: если первый символ не буква и не цифра — это эмодзи
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

    # После создания сразу показываем обновлённый список категорий
    categories_result = await list_service.get_categories(user)
    await message.answer(
        f"✅ {result.message}\n\n📋 Твои списки:",
        reply_markup=categories_keyboard(categories_result.categories or []),
    )


# ── Удаление категории ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cat:delete:"))
async def cb_category_delete(callback: CallbackQuery):
    """Запрашиваем подтверждение перед удалением."""
    category_id = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        "⚠️ Удалить категорию и все её пункты?",
        reply_markup=confirm_keyboard("cat_del", category_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_del:confirm:"))
async def cb_category_delete_confirm(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    category_id = int(callback.data.split(":")[2])
    list_service = ListService(session)
    result = await list_service.delete_category(user, category_id)

    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return

    # После удаления показываем обновлённый список
    categories_result = await list_service.get_categories(user)
    await callback.message.edit_text(
        f"✅ {result.message}\n\n📋 Твои списки:",
        reply_markup=categories_keyboard(categories_result.categories or []),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_del:cancel:"))
async def cb_category_delete_cancel(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    """Отмена удаления — возвращаемся к содержимому категории."""
    category_id = int(callback.data.split(":")[2])
    list_service = ListService(session)
    result = await list_service.get_items(user, category_id)

    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return

    cat = result.category
    title = f"{cat.emoji} {cat.name}" if cat.emoji else cat.name
    await callback.message.edit_text(
        f"<b>{title}</b>",
        reply_markup=category_keyboard(cat, result.items),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Добавление пункта ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("item:new:"))
async def cb_item_new(callback: CallbackQuery, state: FSMContext):
    """Начало диалога добавления пункта."""
    category_id = int(callback.data.split(":")[2])
    # Сохраняем category_id в FSM-storage чтобы использовать его в следующем шаге
    await state.update_data(category_id=category_id)
    await callback.message.edit_text(
        "Введи текст нового пункта:",
        reply_markup=back_keyboard(f"cat:open:{category_id}"),
    )
    await state.set_state(ListStates.waiting_for_item_text)
    await callback.answer()


@router.message(ListStates.waiting_for_item_text)
async def handle_item_text(
    message: Message, state: FSMContext, user: User, session: AsyncSession
):
    """Создаём пункт и показываем обновлённый список."""
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

    # Показываем обновлённый список категории
    items_result = await list_service.get_items(user, category_id)
    cat = items_result.category
    title = f"{cat.emoji} {cat.name}" if cat.emoji else cat.name

    await message.answer(
        f"✅ Добавлено!\n\n<b>{title}</b>",
        reply_markup=category_keyboard(cat, items_result.items),
        parse_mode="HTML",
    )


# ── Отметить/снять отметку ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("item:toggle:"))
async def cb_item_toggle(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    """Переключить галочку пункта и обновить клавиатуру."""
    item_id = int(callback.data.split(":")[2])
    list_service = ListService(session)
    result = await list_service.toggle_item(user, item_id)

    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return

    # Перезагружаем весь список чтобы обновить клавиатуру
    items_result = await list_service.get_items(user, result.item.category_id)
    cat = items_result.category
    title = f"{cat.emoji} {cat.name}" if cat.emoji else cat.name

    await callback.message.edit_text(
        f"<b>{title}</b>",
        reply_markup=category_keyboard(cat, items_result.items),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Редактирование пункта ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("item:edit:"))
async def cb_item_edit_start(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split(":")[2])
    await state.update_data(item_id=item_id)
    await callback.message.edit_text("Введи новый текст для пункта:")
    await state.set_state(ListStates.waiting_for_item_edit)
    await callback.answer()


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

    items_result = await list_service.get_items(user, edit_result.item.category_id)
    cat = items_result.category
    title = f"{cat.emoji} {cat.name}" if cat.emoji else cat.name

    await message.answer(
        f"✅ Изменено!\n\n<b>{title}</b>",
        reply_markup=category_keyboard(cat, items_result.items),
        parse_mode="HTML",
    )


# ── Удаление пункта ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("item:delete:"))
async def cb_item_delete(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    """Удаляем пункт сразу без подтверждения (некритичное действие)."""
    item_id = int(callback.data.split(":")[2])
    list_service = ListService(session)

    # Нужен category_id до удаления чтобы вернуться к списку
    from repositories import ListRepository
    item = await ListRepository(session).get_item(item_id)
    if not item:
        await callback.answer("Пункт уже удалён.", show_alert=True)
        return
    category_id = item.category_id

    result = await list_service.delete_item(user, item_id)

    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return

    items_result = await list_service.get_items(user, category_id)
    cat = items_result.category
    title = f"{cat.emoji} {cat.name}" if cat.emoji else cat.name

    await callback.message.edit_text(
        f"<b>{title}</b>",
        reply_markup=category_keyboard(cat, items_result.items),
        parse_mode="HTML",
    )
    await callback.answer("Удалено")


# ── Очистка отмеченных ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("item:clear:"))
async def cb_items_clear(
    callback: CallbackQuery, user: User, session: AsyncSession
):
    category_id = int(callback.data.split(":")[2])
    list_service = ListService(session)
    result = await list_service.clear_checked(user, category_id)

    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return

    items_result = await list_service.get_items(user, category_id)
    cat = items_result.category
    title = f"{cat.emoji} {cat.name}" if cat.emoji else cat.name

    await callback.message.edit_text(
        f"<b>{title}</b>",
        reply_markup=category_keyboard(cat, items_result.items),
        parse_mode="HTML",
    )
    await callback.answer(result.message)
