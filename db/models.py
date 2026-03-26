"""
db/models.py — SQLAlchemy модели (описание таблиц через Python-классы).

Каждый класс = одна таблица в базе данных.
SQLAlchemy умеет работать с SQLite и PostgreSQL через один и тот же код —
меняется только строка подключения (DATABASE_URL в .env).

DeclarativeBase — базовый класс от SQLAlchemy 2.0.
Все наши модели наследуются от него, и SQLAlchemy "знает" о них.
"""

from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Общий базовый класс для всех моделей."""
    pass


class Family(Base):
    """
    Семья / группа пользователей с общим доступом к данным.
    Ты и твоя девушка будете в одной Family — все списки общие.

    invite_code — короткий код (например 'ABC123') по которому
    можно вступить в группу. Генерируется при создании.
    """
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    invite_code: Mapped[str] = mapped_column(String(20), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships — SQLAlchemy подгрузит связанные объекты по запросу.
    # back_populates указывает на поле в обратной модели.
    users: Mapped[list["User"]] = relationship(back_populates="family")
    list_categories: Mapped[list["ListCategory"]] = relationship(
        back_populates="family"
    )


class User(Base):
    """
    Пользователь Telegram.
    Создаётся автоматически при первом /start.
    family_id — nullable: пользователь может быть не в семье
    (одиночный режим) до тех пор пока не создаст или не вступит.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # telegram_id — это число которое Telegram присваивает каждому юзеру.
    # BigInteger нужен потому что у Telegram ID бывают очень большие.
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str] = mapped_column(String(200))
    family_id: Mapped[int | None] = mapped_column(
        ForeignKey("families.id"), nullable=True
    )
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Amsterdam")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    family: Mapped["Family | None"] = relationship(back_populates="users")
    list_items_added: Mapped[list["ListItem"]] = relationship(
        back_populates="added_by_user"
    )


class ListCategory(Base):
    """
    Категория списка: 'Продукты', 'Фильмы', 'Путешествия' и т.п.
    Принадлежит семье — видна всем участникам.

    emoji — необязательное, но делает UI симпатичнее: 🛒 Продукты.
    created_by — кто создал категорию (для истории, не для ограничений).
    """
    __tablename__ = "list_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))
    emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    family: Mapped["Family"] = relationship(back_populates="list_categories")
    items: Mapped[list["ListItem"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
        # cascade означает: удалил категорию — удалились все её пункты
    )


class ListItem(Base):
    """
    Пункт списка. Принадлежит категории.

    position — порядок отображения. При добавлении ставим max+1.
    is_checked — для списков типа 'Продукты' где пункты отмечают галочкой.
    updated_at — обновляется при каждом изменении текста или статуса.
    added_by — FK на users.id, показывает кто добавил пункт.
    """
    __tablename__ = "list_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("list_categories.id"), index=True
    )
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    category: Mapped["ListCategory"] = relationship(back_populates="items")
    added_by_user: Mapped["User"] = relationship(back_populates="list_items_added")
