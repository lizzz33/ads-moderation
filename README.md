# Ads Moderation Service

Сервис модерации объявлений с использованием ML-модели для определения нарушений. Поддерживает синхронные и асинхронные запросы, кэширование результатов и метрики для мониторинга.

## Функциональность

- **Синхронная модерация** (`/predict`) — мгновенное предсказание по данным объявления
- **Модерация по ID** (`/simple_predict`) — предсказание с кэшированием результатов
- **Асинхронная модерация** (`/async_predict`) — обработка через Kafka для длительных операций
- **Получение результатов** (`/moderation_result/{task_id}`) — проверка статуса асинхронной задачи
- **Закрытие объявлений** (`/close`) — удаление объявления и связанных кэшей
- **Управление пользователями** — регистрация, авторизация (JWT), блокировка, удаление

## Технологический стек

| Компонент | Технология |
|-----------|------------|
| Язык | Python 3.13 |
| Веб-фреймворк | FastAPI |
| Базы данных | PostgreSQL, Redis |
| Очереди сообщений | Apache Kafka (Redpanda) |
| ML-модель | scikit-learn, MLflow |
| Мониторинг | Prometheus, Grafana |
| Тестирование | pytest, pytest-asyncio |
| Контейнеризация | Docker, Docker Compose |

## Архитектура

```
┌─────────┐     POST /async_predict     ┌─────────────┐
│ Client  │ ───────────────────────────► │   FastAPI   │
└─────────┘                              └──────┬──────┘
                                                 │
                                                 ▼
                                        ┌────────────────┐
                                        │  Kafka Topic   │
                                        │ "moderation"   │
                                        └────────┬───────┘
                                                 │
        ┌────────────────────────────────────────┼────────────────────────────────────────┐
        │                                        │                                        │
        ▼                                        ▼                                        ▼
┌────────────┐                          ┌────────────┐                          ┌────────────┐
│  Worker 1  │                          │  Worker 2  │                          │  Worker N  │
└─────┬──────┘                          └─────┬──────┘                          └─────┬──────┘
      │                                        │                                        │
      └────────────────────────────────────────┼────────────────────────────────────────┘
                                               │
                    ┌──────────────────────────┴──────────────────────────┐
                    │                                                     │
                    ▼                                                     ▼
          ┌──────────────────┐                                  ┌─────────────────┐
          │   PostgreSQL     │                                  │   Kafka DLQ     │
          │ moderation_results│                                  │"moderation_dlq" │
          └──────────────────┘                                  └─────────────────┘
```

## Быстрый старт

### Требования

- Docker и Docker Compose
- Python 3.13 (для локального запуска тестов)

### Запуск с Docker Compose

```bash
# Клонировать репозиторий
git clone <repository-url>
cd ads-moderation

# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps
```

Сервисы будут доступны на портах:

| Сервис | URL | Логин/Пароль |
|--------|-----|--------------|
| API | http://localhost:8003 | — |
| Grafana | http://localhost:3000 | admin/admin |
| Prometheus | http://localhost:9090 | — |
| Redpanda Console | http://localhost:8080 | — |

### Переменные окружения

Создайте файл `.env` в корне проекта:

```env
# MLflow
USE_MLFLOW=true

# PostgreSQL
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=moderation

# Kafka
KAFKA_BOOTSTRAP=localhost:9092
TOPIC=moderation
DLQ_TOPIC=moderation_dlq
CONSUMER_GROUP=moderation-worker

# API
API_PORT=8003

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Retry
MAX_RETRIES=3
RETRY_DELAY_SECONDS=5

# JWT
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## API Эндпоинты

### Пользователи

| Метод | Эндпоинт | Описание | Доступ |
|-------|----------|----------|--------|
| POST | `/users/` | Регистрация пользователя | Публичный |
| POST | `/login` | Авторизация (JWT) | Публичный |
| GET | `/users/` | Список пользователей | Требуется JWT |
| GET | `/users/current` | Текущий пользователь | Требуется JWT |
| GET | `/users/{user_id}` | Получить пользователя по ID | Требуется JWT |
| PATCH | `/users/block/{user_id}` | Заблокировать пользователя | Требуется JWT |
| DELETE | `/users/{user_id}` | Удалить пользователя | Требуется JWT |

### Модерация

| Метод | Эндпоинт | Описание | Доступ |
|-------|----------|----------|--------|
| POST | `/predict` | Синхронное предсказание по данным | Требуется JWT |
| POST | `/simple_predict` | Предсказание по ID объявления (с кэшем) | Требуется JWT |
| POST | `/async_predict` | Асинхронное предсказание (Kafka) | Требуется JWT |
| GET | `/moderation_result/{task_id}` | Получить результат асинхронной задачи | Требуется JWT |
| POST | `/close` | Закрыть объявление (очистить кэш) | Требуется JWT |

## Примеры запросов

### 1. Регистрация пользователя

```bash
curl -X POST http://localhost:8003/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "login": "test@example.com",
    "password": "qwerty123"
  }'
```

### 2. Авторизация

```bash
curl -X POST http://localhost:8003/login \
  -H "Content-Type: application/json" \
  -d '{
    "login": "test@example.com",
    "password": "qwerty123"
  }'
```

### 3. Синхронное предсказание

```bash
curl -X POST http://localhost:8003/predict \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "seller_id": 1,
    "is_verified_seller": true,
    "item_id": 123,
    "name": "iPhone 13",
    "description": "Новый телефон, отличное состояние",
    "category": 5,
    "images_qty": 3
  }'
```

### 4. Предсказание по ID объявления (с кэшированием)

```bash
curl -X POST http://localhost:8003/simple_predict \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"item_id": 123}'
```

### 5. Асинхронное предсказание

```bash
curl -X POST http://localhost:8003/async_predict \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"item_id": 123}'
```

### 6. Получение результата асинхронной задачи

```bash
curl -X GET http://localhost:8003/moderation_result/1 \
  -H "Authorization: Bearer <token>"
```

### 7. Закрытие объявления

```bash
curl -X POST http://localhost:8003/close \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"item_id": 123}'
```

## Тестирование

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Запуск тестов

| Команда | Описание |
|---------|----------|
| `pytest` | Все тесты |
| `pytest -m unit` | Только юнит-тесты |
| `pytest -m integration` | Только интеграционные тесты |
| `pytest tests/test_redis.py` | Тесты Redis |
| `pytest tests/test_users.py` | Тесты пользователей |
| `pytest --cov=app tests/` | С покрытием кода |

### Ручное тестирование

```bash
# Все ручные тесты
python manual_tests.py all

# Только модерация
python manual_tests.py moderation

# Только пользователи
python manual_tests.py users

# Только Kafka
python manual_tests.py kafka

# Комплексные сценарии
python manual_tests.py flow
```

## Структура проекта

```
ads-moderation/
├── app/
│   ├── clients/              # Клиенты для внешних сервисов
│   │   ├── kafka.py          # Kafka producer/consumer
│   │   ├── postgres.py       # PostgreSQL с пулом соединений
│   │   ├── redis.py          # Redis клиент
│   │   └── settings.py       # Настройки окружения
│   ├── db/migrations/        # SQL миграции
│   │   ├── V001__initial.sql
│   │   └── V002__add_is_closed.sql
│   ├── models/               # Pydantic модели
│   │   ├── ads.py
│   │   ├── token.py
│   │   └── users.py
│   ├── repositories/         # Репозитории (работа с БД и кэшем)
│   │   ├── ads.py
│   │   ├── moderation.py
│   │   ├── prediction.py
│   │   └── users.py
│   ├── routers/              # API эндпоинты
│   │   ├── moderation.py
│   │   ├── users.py
│   │   └── utils.py
│   ├── services/             # Бизнес-логика
│   │   ├── auth.py           # JWT авторизация
│   │   └── users.py          # Управление пользователями
│   ├── workers/              # Фоновые воркеры
│   │   └── moderation_worker.py  # Kafka consumer
│   ├── dependencies.py       # DI зависимости
│   ├── errors.py             # Кастомные исключения
│   ├── main.py               # Точка входа FastAPI
│   └── model.py              # Загрузка ML-модели
├── observability/
│   ├── prometheus/
│   │   └── prometheus.yml    # Конфигурация Prometheus
│   ├── metrics.py            # Метрики для мониторинга
│   └── middleware.py         # Middleware для метрик
├── tests/                    # Тесты
├── manual_tests.py           # Ручные тесты
├── load_test.js              # Скрипт для НТ
├── Makefile                  # Инструкция для воркера
├── docker-compose.yml        # Конфигурация Docker Compose
├── Dockerfile                # Dockerfile для приложения
├── requirements.txt          # Зависимости Python
├── pytest.ini                # Конфигурация pytest
└── README.md                 # Документация
```

## Мониторинг

### Доступные интерфейсы

| Сервис | URL | Доступ |
|--------|-----|--------|
| Prometheus | http://localhost:9090 | Открытый |
| Grafana | http://localhost:3000 | admin/admin |
| Redpanda Console | http://localhost:8080 | Открытый |

### Метрики

| Метрика | Тип | Описание |
|---------|-----|----------|
| `prediction_duration_seconds` | Histogram | Время выполнения предсказания |
| `model_prediction_probability` | Histogram | Вероятность нарушения |
| `predictions_total` | Counter | Общее количество предсказаний |
| `prediction_errors_total` | Counter | Количество ошибок предсказания |
| `db_query_duration_seconds` | Histogram | Время выполнения SQL запросов |
| `kafka_messages_processed_total` | Counter | Количество обработанных сообщений |

## Остановка сервисов

```bash
# Остановить все сервисы
docker-compose down

# Остановить с удалением томов (очистка данных)
docker-compose down -v
```
