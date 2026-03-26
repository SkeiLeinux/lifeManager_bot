"""
services/list_service.py — бизнес-логика для списков.

Здесь проверяем что пользователь имеет право на операцию
(принадлежит ли категория его семье), и координируем работу репозитория.
"""

from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import ListCategory, ListItem, User
from repositories import ListRepository


@dataclass
class ListServiceResult:
    success: bool
    message: str = ""
    category: ListCategory | None = None
    item: ListItem | None = None
    items: list[ListItem] | None = None
    categories: list[ListCategory] | None = None


class ListService:
    def __init__(self, session: AsyncSession):
        self.list_repo = ListRepository(session)
        self.session = session

    def _format_category_title(self, category: ListCategory) -> str:
        """Красиво форматирует название категории: '🛒 Продукты'."""
        if category.emoji:
            return f"{category.emoji} {category.name}"
        return category.name

    async def _check_category_access(
        self, category_id: int, family_id: int
    ) -> ListCategory | None:
        """
        Проверить что категория принадлежит семье пользователя.
        Это защита от ситуации когда кто-то перебирает ID и пытается
        получить доступ к чужим данным.
        """
        category = await self.list_repo.get_category(category_id)
        if not category or category.family_id != family_id:
            return None
        return category

    # ── Категории ─────────────────────────────────────────────────────────

    async def get_categories(self, user: User) -> ListServiceResult:
        """Получить все категории семьи пользователя."""
        if not user.family_id:
            return ListServiceResult(
                success=False,
                message="Сначала создай группу или вступи в неё (/family).",
            )
        categories = await self.list_repo.get_categories(user.family_id)
        return ListServiceResult(success=True, categories=categories)

    async def create_category(
        self, user: User, name: str, emoji: str | None = None
    ) -> ListServiceResult:
        """Создать новую категорию списков."""
        if not user.family_id:
            return ListServiceResult(
                success=False,
                message="Сначала создай группу или вступи в неё (/family).",
            )

        # Очищаем эмодзи — берём только первый символ если передали строку
        if emoji:
            emoji = emoji.strip()[:2]  # эмодзи могут быть 2 байта

        category = await self.list_repo.create_category(
            family_id=user.family_id,
            created_by=user.id,
            name=name.strip(),
            emoji=emoji,
        )
        await self.session.commit()

        return ListServiceResult(
            success=True,
            message=f"Категория {self._format_category_title(category)} создана!",
            category=category,
        )

    async def delete_category(
        self, user: User, category_id: int
    ) -> ListServiceResult:
        """Удалить категорию вместе со всеми её пунктами."""
        if not user.family_id:
            return ListServiceResult(success=False, message="Нет доступа.")

        category = await self._check_category_access(category_id, user.family_id)
        if not category:
            return ListServiceResult(
                success=False, message="Категория не найдена."
            )

        title = self._format_category_title(category)
        await self.list_repo.delete_category(category_id)
        await self.session.commit()

        return ListServiceResult(
            success=True,
            message=f"Категория «{title}» и все её пункты удалены.",
        )

    # ── Пункты списка ──────────────────────────────────────────────────────

    async def get_items(
        self, user: User, category_id: int
    ) -> ListServiceResult:
        """Получить все пункты категории."""
        if not user.family_id:
            return ListServiceResult(success=False, message="Нет доступа.")

        category = await self._check_category_access(category_id, user.family_id)
        if not category:
            return ListServiceResult(
                success=False, message="Категория не найдена."
            )

        items = await self.list_repo.get_items(category_id)
        return ListServiceResult(success=True, category=category, items=items)

    async def add_item(
        self, user: User, category_id: int, text: str
    ) -> ListServiceResult:
        """Добавить пункт в список."""
        if not user.family_id:
            return ListServiceResult(success=False, message="Нет доступа.")

        category = await self._check_category_access(category_id, user.family_id)
        if not category:
            return ListServiceResult(
                success=False, message="Категория не найдена."
            )

        item = await self.list_repo.create_item(
            category_id=category_id,
            added_by=user.id,
            text=text.strip(),
        )
        await self.session.commit()

        return ListServiceResult(
            success=True,
            message=f"Добавлено: {item.text}",
            item=item,
        )

    async def edit_item(
        self, user: User, item_id: int, new_text: str
    ) -> ListServiceResult:
        """Изменить текст пункта."""
        if not user.family_id:
            return ListServiceResult(success=False, message="Нет доступа.")

        item = await self.list_repo.get_item(item_id)
        if not item:
            return ListServiceResult(success=False, message="Пункт не найден.")

        # Проверяем доступ через родительскую категорию
        category = await self._check_category_access(item.category_id, user.family_id)
        if not category:
            return ListServiceResult(success=False, message="Нет доступа.")

        item = await self.list_repo.update_item_text(item_id, new_text.strip())
        await self.session.commit()

        return ListServiceResult(
            success=True,
            message=f"Пункт изменён: {item.text}",
            item=item,
        )

    async def toggle_item(
        self, user: User, item_id: int
    ) -> ListServiceResult:
        """Отметить/снять отметку с пункта."""
        if not user.family_id:
            return ListServiceResult(success=False, message="Нет доступа.")

        item = await self.list_repo.get_item(item_id)
        if not item:
            return ListServiceResult(success=False, message="Пункт не найден.")

        category = await self._check_category_access(item.category_id, user.family_id)
        if not category:
            return ListServiceResult(success=False, message="Нет доступа.")

        item = await self.list_repo.toggle_item(item_id)
        await self.session.commit()

        return ListServiceResult(success=True, item=item)

    async def delete_item(
        self, user: User, item_id: int
    ) -> ListServiceResult:
        """Удалить пункт из списка."""
        if not user.family_id:
            return ListServiceResult(success=False, message="Нет доступа.")

        item = await self.list_repo.get_item(item_id)
        if not item:
            return ListServiceResult(success=False, message="Пункт не найден.")

        category = await self._check_category_access(item.category_id, user.family_id)
        if not category:
            return ListServiceResult(success=False, message="Нет доступа.")

        await self.list_repo.delete_item(item_id)
        await self.session.commit()

        return ListServiceResult(success=True, message="Пункт удалён.")

    async def clear_checked(
        self, user: User, category_id: int
    ) -> ListServiceResult:
        """Удалить все отмеченные пункты (например, куплено в магазине)."""
        if not user.family_id:
            return ListServiceResult(success=False, message="Нет доступа.")

        category = await self._check_category_access(category_id, user.family_id)
        if not category:
            return ListServiceResult(success=False, message="Категория не найдена.")

        count = await self.list_repo.clear_checked_items(category_id)
        await self.session.commit()

        return ListServiceResult(
            success=True,
            message=f"Удалено отмеченных пунктов: {count}",
        )
