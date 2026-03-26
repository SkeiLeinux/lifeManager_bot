# Life Manager Bot

Telegram-бот для совместного ведения списков в паре.

## Быстрый старт

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Настройка
```bash
cp .env.example .env
```
Открой `.env` и заполни:
- `BOT_TOKEN` — токен от @BotFather
- `ALLOWED_USER_IDS` — твой Telegram ID и ID партнёра (узнать у @userinfobot)

### 3. Запуск
```bash
python bot.py
```
База данных `life_manager.db` создастся автоматически при первом запуске.

---

## Структура проекта

```
life_manager_bot/
├── bot.py              # точка входа
├── config.py           # настройки из .env
├── db/
│   ├── models.py       # таблицы БД (SQLAlchemy)
│   └── database.py     # подключение и сессии
├── repositories/       # CRUD операции с БД
│   ├── user_repository.py
│   ├── family_repository.py
│   └── list_repository.py
├── services/           # бизнес-логика
│   ├── user_service.py
│   └── list_service.py
└── handlers/           # Telegram хендлеры
    ├── common.py       # /start, /help, /family
    ├── lists.py        # /lists и управление списками
    ├── keyboards.py    # все инлайн-клавиатуры
    └── middleware.py   # авторизация и сессии
```

## Переезд на PostgreSQL

1. Установи драйвер: `pip install asyncpg`
2. В `.env` замени `DATABASE_URL`:
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/life_manager
   ```
3. Создай БД в PostgreSQL: `CREATE DATABASE life_manager;`
4. Перезапусти бота — таблицы создадутся автоматически.

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и статус |
| `/lists` | Открыть списки |
| `/family` | Управление группой |
| `/help` | Помощь |
