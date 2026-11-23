# Corpsite

Описание проекта Corpsite.

## Установка

1. Клонируйте репозиторий:
   git clone https://github.com/SergeyK3/corpsite.git
2. Перейдите в папку проекта:
   cd corpsite
3. Создайте и активируйте виртуальное окружение:
   python -m venv venv
   
   Для Windows:
   venv\Scripts\activate
   
   Для Linux/Mac:
   source venv/bin/activate
4. Установите зависимости:
   pip install -r requirements.txt

## Local Development

Одна команда из корня репозитория (встроенный терминал Cursor):

```bash
npm run dev
```

Скрипт последовательно:

1. `docker compose up -d --wait` — Postgres с ожиданием healthcheck
2. backend — `uvicorn` на `http://127.0.0.1:8000`
3. ожидание `http-get://127.0.0.1:8000/health` (GET, не HEAD)
4. frontend — Next.js на `http://localhost:3000`

Откройте в браузере: **http://localhost:3000**

`Ctrl+C` в терминале останавливает backend и frontend (через `concurrently -k`).

### Предварительные требования

- Docker Desktop (для Postgres)
- Python 3.x с зависимостями проекта (`pip install -r requirements.txt` или активный `venv`)
- Node.js 20+
- Файл `.env` в корне (скопируйте из `.env.example`)

### Отдельные команды

| Команда | Назначение |
|---------|------------|
| `npm run db` | Только Postgres (`docker compose up -d --wait`) |
| `npm run backend` | Только FastAPI backend |
| `npm run frontend` | Только Next.js UI |

### Backend pytest (отдельная БД)

Pytest использует **только** `TEST_DATABASE_URL` (обязательно, без fallback на `DATABASE_URL`). Подробности: [tests/README.md](tests/README.md).

Кратко:

```bash
# создать БД (один раз)
psql "postgresql://postgres:postgres@127.0.0.1:5432/postgres" -c "CREATE DATABASE corpsite_test;"

# миграции на test DB
DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite_test alembic upgrade head

# тесты (TEST_DATABASE_URL в .env)
python -m pytest -q
```

## Использование

(Добавьте инструкции по использованию)
