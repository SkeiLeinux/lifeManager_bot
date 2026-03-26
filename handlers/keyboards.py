"""
handlers/keyboards.py — все инлайн-клавиатуры бота.

Новый подход к отображению списков:
  - Содержимое списка рендерится в ТЕКСТЕ сообщения (полный текст, без обрезки)
  - Кнопки — только для действий: toggle по номеру, добавить, редактировать, удалить
  - Это стандартный паттерн для Telegram-ботов со списками
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


def format_items_text(category: ListCategory, items: list[ListItem]) -> str:
    """
    Форматирует содержимое категории как текст сообщения.
    Список живёт здесь — не в кнопках — поэтому текст не обрезается.
    """
    title = f"{category.emoji} {category.name}" if category.emoji else category.name
    checked_count = sum(1 for i in items if i.is_checked)
    n = len(items)

    # Русское склонение
    if n % 10 == 1 and n % 100 != 11:
        noun = "пункт"
    elif 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        noun = "пункта"
    else:
        noun = "пунктов"

    header = f"<b>{title}</b>"
    if items:
        header += f"  <i>({n} {noun}"
        if checked_count:
            header += f", отмечено: {checked_count}"
        header += ")</i>"

    if not items:
        return header + "\n\n<i>Список пуст. Нажми + Добавить</i>"

    lines = []
    for i, item in enumerate(items, 1):
        icon = "✅" if item.is_checked else "☐"
        lines.append(f"{icon}  <b>{i}.</b>  {item.text}")

    return header + "\n\n" + "\n".join(lines)


def category_keyboard(
    category: ListCategory,
    items: list[ListItem],
) -> InlineKeyboardMarkup:
    """
    Клавиатура категории.

    Верхние ряды — кнопки с номерами для быстрого toggle (отметить/снять).
    По 5 кнопок в ряд.
    Нижние ряды — добавить, редактировать, удалить, назад.
    """
    buttons = []

    # Ряды с номерами для toggle
    if items:
        row = []
        for i, item in enumerate(items, 1):
            label = f"✅{i}" if item.is_checked else str(i)
            row.append(InlineKeyboardButton(
                text=label,
                callback_data=f"item:toggle:{item.id}",
            ))
            if len(row) == 5:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

    # Добавить
    buttons.append([
        InlineKeyboardButton(text="＋ Добавить", callback_data=f"item:new:{category.id}"),
    ])

    # Редактировать и удалить пункт
    if items:
        buttons.append([
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"item:edit_ask:{category.id}"),
            InlineKeyboardButton(text="🗑 Удалить пункт", callback_data=f"item:delete_ask:{category.id}"),
        ])
        if any(i.is_checked for i in items):
            buttons.append([
                InlineKeyboardButton(
                    text="🧹 Удалить отмеченные пункты",
                    callback_data=f"item:clear:{category.id}",
                )
            ])

    buttons.append([
        InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"cat:delete:{category.id}"),
        InlineKeyboardButton(text="‹ Назад", callback_data="cat:list"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard(action: str, target_id: int) -> InlineKeyboardMarkup:
    """Универсальное подтверждение опасных действий."""
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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=callback_data)]
    ])


def numbers_keyboard(
    items: list[ListItem], action: str, category_id: int
) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора пункта по номеру (для редактирования/удаления).
    action: 'edit' или 'delete'
    """
    buttons = []
    row = []
    for i, item in enumerate(items, 1):
        row.append(InlineKeyboardButton(
            text=str(i),
            callback_data=f"item:{action}_pick:{item.id}",
        ))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(text="✗ Отмена", callback_data=f"cat:open:{category_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)