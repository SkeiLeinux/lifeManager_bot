"""
repositories/list_repository.py — CRUD для категорий и пунктов списков.
"""

from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import ListCategory, ListItem


class ListRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Категории ─────────────────────────────────────────────────────────

    async def get_categories(self, family_id: int) -> list[ListCategory]:
        """Все категории семьи, отсортированные по имени."""
        result = await self.session.execute(
            select(ListCategory)
            .where(ListCategory.family_id == family_id)
            .order_by(ListCategory.name)
        )
        return list(result.scalars().all())

    async def get_category(self, category_id: int) -> ListCategory | None:
        """
        Категория вместе с её пунктами (один запрос вместо N+1).
        selectinload — говорит SQLAlchemy сразу подгрузить связанные items.
        Без него при обращении к category.items был бы отдельный SQL-запрос.
        """
        result = await self.session.execute(
            select(ListCategory)
            .where(ListCategory.id == category_id)
            .options(selectinload(ListCategory.items))
        )
        return result.scalar_one_or_none()

    async def create_category(
        self,
        family_id: int,
        created_by: int,
        name: str,
        emoji: str | None = None,
    ) -> ListCategory:
        category = ListCategory(
            family_id=family_id,
            created_by=created_by,
            name=name,
            emoji=emoji,
        )
        self.session.add(category)
        await self.session.flush()
        return category

    async def delete_category(self, category_id: int) -> bool:
        """
        Удалить категорию. cascade='all, delete-orphan' в модели
        автоматически удалит все пункты этой категории.
        Возвращает True если категория была найдена и удалена.
        """
        category = await self.session.get(ListCategory, category_id)
        if not category:
            return False
        await self.session.delete(category)
        await self.session.flush()
        return True

    # ── Пункты списка ──────────────────────────────────────────────────────

    async def get_items(self, category_id: int) -> list[ListItem]:
        """Все пункты категории, отсортированные по позиции."""
        result = await self.session.execute(
            select(ListItem)
            .where(ListItem.category_id == category_id)
            .order_by(ListItem.position)
        )
        return list(result.scalars().all())

    async def get_item(self, item_id: int) -> ListItem | None:
        return await self.session.get(ListItem, item_id)

    async def create_item(
        self,
        category_id: int,
        added_by: int,
        text: str,
    ) -> ListItem:
        """
        Создать пункт. position = max текущих позиций + 1,
        чтобы новый пункт всегда оказывался последним.
        """
        max_pos_result = await self.session.execute(
            select(func.max(ListItem.position))
            .where(ListItem.category_id == category_id)
        )
        max_pos = max_pos_result.scalar() or 0

        item = ListItem(
            category_id=category_id,
            added_by=added_by,
            text=text,
            position=max_pos + 1,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def update_item_text(self, item_id: int, new_text: str) -> ListItem | None:
        item = await self.get_item(item_id)
        if item:
            item.text = new_text
            await self.session.flush()
        return item

    async def toggle_item(self, item_id: int) -> ListItem | None:
        """Переключить галочку пункта (отмечен / не отмечен)."""
        item = await self.get_item(item_id)
        if item:
            item.is_checked = not item.is_checked
            await self.session.flush()
        return item

    async def delete_item(self, item_id: int) -> bool:
        item = await self.get_item(item_id)
        if not item:
            return False
        await self.session.delete(item)
        await self.session.flush()
        return True

    async def clear_checked_items(self, category_id: int) -> int:
        """
        Удалить все отмеченные пункты категории.
        Удобно для списка покупок: купил всё — очистил.
        Возвращает количество удалённых пунктов.
        """
        result = await self.session.execute(
            delete(ListItem)
            .where(
                ListItem.category_id == category_id,
                ListItem.is_checked == True,  # noqa: E712
            )
            .returning(ListItem.id)
        )
        return len(result.fetchall())
