"""
handlers/keyboards.py — все инлайн-клавиатуры бота.

Держим клавиатуры отдельно от логики хендлеров — так их легко
переиспользовать и менять внешний вид не трогая логику.

Как работают callback_data:
  Когда пользователь нажимает кнопку, Telegram отправляет боту
  строку callback_data. Мы парсим её чтобы понять что нажали.
  Формат: "action:param1:param2" — простой и надёжный.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db.models import ListCategory, ListItem


def categories_keyboard(categories: list[ListCategory]) -> InlineKeyboardMarkup:
    """Список категорий — каждая кнопка открывает категорию."""
    buttons = []
    for cat in categories:
        title = f"{cat.emoji} {cat.name}" if cat.emoji else cat.name
        buttons.append([
            InlineKeyboardButton(
                text=title,
                callback_data=f"cat:open:{cat.id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="＋ Новая категория", callback_data="cat:new"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def category_keyboard(
    category: ListCategory,
    items: list[ListItem],
) -> InlineKeyboardMarkup:
    """
    Содержимое категории.
    Каждый пункт — две кнопки: галочка и удалить.
    Внизу — кнопки управления.
    """
    buttons = []
    for item in items:
        check_icon = "✅" if item.is_checked else "☐"
        buttons.append([
            # Кнопка с текстом пункта — отмечает/снимает галочку
            InlineKeyboardButton(
                text=f"{check_icon} {item.text}",
                callback_data=f"item:toggle:{item.id}",
            ),
            # Кнопка редактировать
            InlineKeyboardButton(
                text="✏️",
                callback_data=f"item:edit:{item.id}",
            ),
            # Кнопка удалить
            InlineKeyboardButton(
                text="🗑",
                callback_data=f"item:delete:{item.id}",
            ),
        ])

    # Строка кнопок под списком
    controls = [
        InlineKeyboardButton(text="＋ Добавить", callback_data=f"item:new:{category.id}"),
    ]
    # Кнопка очистки появляется только если есть отмеченные пункты
    if any(i.is_checked for i in items):
        controls.append(
            InlineKeyboardButton(
                text="🧹 Очистить отмеченные",
                callback_data=f"item:clear:{category.id}",
            )
        )
    buttons.append(controls)

    buttons.append([
        InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"cat:delete:{category.id}"),
        InlineKeyboardButton(text="‹ Назад", callback_data="cat:list"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard(action: str, target_id: int) -> InlineKeyboardMarkup:
    """Универсальное подтверждение опасных действий (удаление)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, удалить",
                callback_data=f"{action}:confirm:{target_id}",
            ),
            InlineKeyboardButton(
                text="✗ Отмена",
                callback_data=f"{action}:cancel:{target_id}",
            ),
        ]
    ])


def back_keyboard(callback_data: str, text: str = "‹ Назад") -> InlineKeyboardMarkup:
    """Простая кнопка 'назад'."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=callback_data)]
    ])
