# manual_tests.py

import asyncio
import json
import time
from typing import Optional

import requests
from aiokafka import AIOKafkaProducer

BASE_URL = "http://localhost:8003"
UUID = int(time.time())


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================


def get_auth_token(login: str = "test@example.com", password: str = "qwerty123") -> Optional[str]:
    try:
        r = requests.post(f"{BASE_URL}/login", json={"login": login, "password": password})
        if r.status_code == 200:
            return r.json()["access_token"]
        return None
    except Exception as e:
        print(f"   Ошибка получения токена: {e}")
        return None


def get_headers(token: str = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def ensure_seller_exists():
    import subprocess

    sql = """
    INSERT INTO sellers (seller_id, username, email, password, is_verified)
    VALUES (1, 'test_seller', 'seller@test.com', 'test123', true)
    ON CONFLICT (seller_id) DO NOTHING;
    """

    cmd = [
        "docker",
        "exec",
        "ads-moderation-postgres-1",
        "psql",
        "-U",
        "postgres",
        "-d",
        "moderation",
        "-c",
        sql,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("   Продавец готов")
    else:
        print(f"   Ошибка создания продавца: {result.stderr}")


def create_test_advertisement() -> Optional[int]:
    import subprocess
    import time

    item_id = int(time.time() * 1000000) % 10000000

    sql = f"""
    INSERT INTO advertisement (item_id, seller_id, name, description, category, images_qty, is_closed)
    VALUES ({item_id}, 1, 'Тестовое объявление {item_id}', 'Создано для ручного тестирования', 5, 3, false)
    RETURNING item_id;
    """

    cmd = [
        "docker",
        "exec",
        "ads-moderation-postgres-1",
        "psql",
        "-U",
        "postgres",
        "-d",
        "moderation",
        "-t",
        "-A",
        "-c",
        sql,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        output = result.stdout.strip().split("\n")[0]
        if output.isdigit():
            print(f"   Создано объявление с ID: {output}")
            return int(output)

    return None


def create_multiple_ads(count: int = 3) -> list:
    ads = []
    print(f"\nСоздание {count} тестовых объявлений")

    ensure_seller_exists()

    for i in range(count):
        ad_id = create_test_advertisement()
        if ad_id:
            ads.append(ad_id)
            print(f"   {i + 1}. Создано объявление {ad_id}")
        else:
            print(f"   {i + 1}. Не удалось создать объявление")

    return ads


# =============================================================================
# ТЕСТЫ ОБЪЯВЛЕНИЙ И МОДЕРАЦИИ
# =============================================================================


def test_predict(token: str, item_id: int = None):
    print("\n1. ТЕСТ /predict (синхронное предсказание)")

    if item_id is None:
        item_id = int(time.time()) % 10000

    data = {
        "seller_id": 1,
        "is_verified_seller": True,
        "item_id": item_id,
        "name": f"iPhone 13 {item_id}",
        "description": "Новый телефон, отличное состояние",
        "category": 5,
        "images_qty": 3,
    }

    try:
        r = requests.post(f"{BASE_URL}/predict", json=data, headers=get_headers(token))
        print(f"   Статус: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print(f"   Нарушение: {result['is_violation']}")
            print(f"   Вероятность: {result['probability']:.3f}")
            return item_id
    except Exception as e:
        print(f"   Ошибка: {e}")
    return None


def test_simple_predict(item_id: int, token: str):
    print(f"\n2. ТЕСТ /simple_predict (предсказание по ID: {item_id})")

    try:
        r = requests.post(
            f"{BASE_URL}/simple_predict", json={"item_id": item_id}, headers=get_headers(token)
        )
        print(f"   Статус: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print(f"   Нарушение: {result['is_violation']}")
            print(f"   Вероятность: {result['probability']:.3f}")
        elif r.status_code == 404:
            print(f"   Объявление {item_id} не найдено или закрыто")
    except Exception as e:
        print(f"   Ошибка: {e}")


def test_async_predict(item_id: int, token: str) -> Optional[int]:
    print(f"\n3. ТЕСТ /async_predict (асинхронное предсказание для ID: {item_id})")

    try:
        r = requests.post(
            f"{BASE_URL}/async_predict", json={"item_id": item_id}, headers=get_headers(token)
        )
        print(f"   Статус: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            task_id = result.get("task_id")
            print(f"   Task ID: {task_id}")
            print(f"   Статус: {result['status']}")
            return task_id
        elif r.status_code == 404:
            print(f"   Объявление {item_id} не найдено")
    except Exception as e:
        print(f"   Ошибка: {e}")
    return None


def test_moderation_result(task_id: int, token: str):
    print(f"\n4. ТЕСТ /moderation_result/{task_id}")

    try:
        r = requests.get(f"{BASE_URL}/moderation_result/{task_id}", headers=get_headers(token))
        print(f"   Статус: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print(f"   Task ID: {result['task_id']}")
            print(f"   Статус: {result['status']}")
            if result["status"] == "completed":
                print(f"   Нарушение: {result['is_violation']}")
                print(f"   Вероятность: {result['probability']:.3f}")
    except Exception as e:
        print(f"   Ошибка: {e}")


def test_close_ad(item_id: int, token: str):
    print(f"\n5. ТЕСТ /close (закрытие объявления ID: {item_id})")

    try:
        r = requests.post(
            f"{BASE_URL}/close", json={"item_id": item_id}, headers=get_headers(token)
        )
        print(f"   Статус: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print(f"   Успех: {result['success']}")
            print(f"   Сообщение: {result['message']}")
    except Exception as e:
        print(f"   Ошибка: {e}")


# =============================================================================
# ТЕСТЫ ПОЛЬЗОВАТЕЛЕЙ
# =============================================================================


def test_create_user():
    print("\n6. ТЕСТ /users (создание пользователя)")

    data = {
        "name": f"Тестовый пользователь {UUID}",
        "login": f"user_{UUID}@test.com",
        "password": "qwerty123",
    }

    try:
        r = requests.post(
            f"{BASE_URL}/users/", json=data, headers={"Content-Type": "application/json"}
        )
        print(f"   Статус: {r.status_code}")
        if r.status_code == 201:
            result = r.json()
            print(f"   ID: {result['id']}")
            print(f"   Имя: {result['name']}")
            print(f"   Логин: {result['login']}")
            return result["id"], data["login"], data["password"]
        else:
            print(f"   Ошибка: {r.text}")
    except Exception as e:
        print(f"   Ошибка: {e}")
    return None, None, None


def test_login_user(login: str, password: str) -> Optional[str]:
    print(f"\n7. ТЕСТ /login (авторизация: {login})")

    try:
        r = requests.post(f"{BASE_URL}/login", json={"login": login, "password": password})
        print(f"   Статус: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print("   Успешный вход")
            return result["access_token"]
        elif r.status_code == 401:
            print("   Неверный логин или пароль")
        else:
            print(f"   Ошибка: {r.text}")
    except Exception as e:
        print(f"   Ошибка: {e}")
    return None


def test_get_current_user(token: str):
    print("\n8. ТЕСТ /users/current (текущий пользователь)")

    try:
        r = requests.get(f"{BASE_URL}/users/current", headers=get_headers(token))
        print(f"   Статус: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print(f"   ID: {result['id']}")
            print(f"   Имя: {result['name']}")
            print(f"   Логин: {result['login']}")
            print(f"   Заблокирован: {result['is_blocked']}")
        elif r.status_code == 401:
            print("   Неавторизован")
        else:
            print(f"   Ошибка: {r.text}")
    except Exception as e:
        print(f"   Ошибка: {e}")


def test_get_all_users(token: str):
    print("\n9. ТЕСТ /users (список пользователей)")

    try:
        r = requests.get(f"{BASE_URL}/users/", headers=get_headers(token))
        print(f"   Статус: {r.status_code}")
        if r.status_code == 200:
            users = r.json()
            print(f"   Найдено пользователей: {len(users)}")
            for user in users[:3]:
                print(f"   - {user['id']}: {user['name']} ({user['login']})")
            if len(users) > 3:
                print(f"   ... и еще {len(users) - 3}")
        elif r.status_code == 401:
            print("   Неавторизован")
        else:
            print(f"   Ошибка: {r.text}")
    except Exception as e:
        print(f"   Ошибка: {e}")


def test_block_user(user_id: int, token: str):
    print(f"\n10. ТЕСТ /users/block/{user_id} (блокировка)")

    try:
        r = requests.patch(f"{BASE_URL}/users/block/{user_id}", headers=get_headers(token))
        print(f"   Статус: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print(f"   Пользователь {result['id']} заблокирован")
            print(f"   Заблокирован: {result['is_blocked']}")
        elif r.status_code == 403:
            print("   Нельзя заблокировать другого пользователя")
        elif r.status_code == 401:
            print("   Неавторизован")
        else:
            print(f"   Ошибка: {r.text}")
    except Exception as e:
        print(f"   Ошибка: {e}")


def test_delete_user(user_id: int, token: str):
    print(f"\n11. ТЕСТ DELETE /users/{user_id}")

    try:
        r = requests.delete(f"{BASE_URL}/users/{user_id}", headers=get_headers(token))
        print(f"   Статус: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print(f"   Пользователь {result['id']} удален")
        elif r.status_code == 403:
            print("   Нельзя удалить другого пользователя")
        elif r.status_code == 401:
            print("   Неавторизован")
        else:
            print(f"   Ошибка: {r.text}")
    except Exception as e:
        print(f"   Ошибка: {e}")


# =============================================================================
# ТЕСТЫ KAFKA
# =============================================================================


async def send_kafka_test_message():
    print("\n12. ТЕСТ Kafka (отправка сообщения)")

    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092", value_serializer=lambda v: json.dumps(v).encode()
    )

    try:
        await producer.start()
        test_message = {"item_id": 999, "task_id": 999999, "retry_count": 0}
        await producer.send("moderation", test_message)
        print("   Сообщение отправлено в топик 'moderation'")
        print(f"   Данные: {test_message}")
    except Exception as e:
        print(f"   Ошибка Kafka: {e}")
    finally:
        await producer.stop()


async def send_kafka_dlq_test():
    print("\n13. ТЕСТ Kafka DLQ (отправка в dead letter queue)")

    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092", value_serializer=lambda v: json.dumps(v).encode()
    )

    try:
        await producer.start()
        test_message = {
            "item_id": 999,
            "task_id": 888888,
            "retry_count": 3,
            "error": "Test error message",
        }
        await producer.send("moderation_dlq", test_message)
        print("   Сообщение отправлено в топик 'moderation_dlq'")
        print(f"   Данные: {test_message}")
    except Exception as e:
        print(f"   Ошибка Kafka: {e}")
    finally:
        await producer.stop()


# =============================================================================
# КОМПЛЕКСНЫЕ СЦЕНАРИИ
# =============================================================================


def test_full_moderation_flow(token: str, ad_id: int):
    print("\n" + "=" * 60)
    print("КОМПЛЕКСНЫЙ ТЕСТ 1: Полный цикл модерации")
    print("=" * 60)
    print(f"   Используем объявление: {ad_id}")

    test_simple_predict(ad_id, token)

    task_id = test_async_predict(ad_id, token)

    if task_id:
        print("\n   Ожидание обработки (3 секунды)...")
        time.sleep(3)
        test_moderation_result(task_id, token)
    else:
        print("   Не удалось получить task_id")

    test_close_ad(ad_id, token)
    test_simple_predict(ad_id, token)


def test_close_and_predict_flow(token: str, ad_id: int):
    print("\n" + "=" * 60)
    print("КОМПЛЕКСНЫЙ ТЕСТ 2: Закрытие объявления")
    print("=" * 60)
    print(f"   Используем объявление: {ad_id}")

    test_simple_predict(ad_id, token)
    test_close_ad(ad_id, token)
    test_simple_predict(ad_id, token)
    test_close_ad(ad_id, token)


def test_user_lifecycle():
    print("\n" + "=" * 60)
    print("КОМПЛЕКСНЫЙ ТЕСТ 3: Жизненный цикл пользователя")
    print("=" * 60)

    user_id, login, password = test_create_user()
    if not user_id:
        print("Не удалось создать пользователя")
        return

    token = test_login_user(login, password)
    if not token:
        print("Не удалось получить токен")
        return

    test_get_current_user(token)
    test_get_all_users(token)
    test_block_user(user_id, token)
    test_delete_user(user_id, token)


# =============================================================================
# ЗАПУСК ТЕСТОВ
# =============================================================================


def run_all_tests():
    print("\n" + "=" * 60)
    print("ЗАПУСК ВСЕХ РУЧНЫХ ТЕСТОВ")
    print("=" * 60 + "\n")

    user_id, login, password = test_create_user()
    if not user_id:
        print("Не удалось создать пользователя для тестов")
        return

    token = test_login_user(login, password)
    if not token:
        print("Не удалось получить токен")
        return

    test_predict(token)

    ads = create_multiple_ads(2)
    if len(ads) >= 2:
        test_full_moderation_flow(token, ads[0])
        test_close_and_predict_flow(token, ads[1])
    else:
        print("Не удалось создать достаточно объявлений для тестов")


async def run_kafka_tests():
    print("\n" + "=" * 60)
    print("ЗАПУСК KAFKA ТЕСТОВ")
    print("=" * 60 + "\n")

    await send_kafka_test_message()
    await send_kafka_dlq_test()


if __name__ == "__main__":
    import sys

    print("Доступные команды:")
    print("   python manual_tests.py all          # все тесты")
    print("   python manual_tests.py moderation   # только тесты модерации")
    print("   python manual_tests.py users        # только тесты пользователей")
    print("   python manual_tests.py kafka        # только Kafka тесты")
    print("   python manual_tests.py flow         # комплексные сценарии")

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "all":
            run_all_tests()
            asyncio.run(run_kafka_tests())

        elif command == "moderation":
            user_id, login, password = test_create_user()
            if login:
                token = test_login_user(login, password)
                if token:
                    ad_id = create_test_advertisement()
                    if ad_id:
                        test_predict(token, ad_id)
                        test_simple_predict(ad_id, token)
                        task_id = test_async_predict(ad_id, token)
                        if task_id:
                            time.sleep(2)
                            test_moderation_result(task_id, token)
                        test_close_ad(ad_id, token)

        elif command == "users":
            test_user_lifecycle()

        elif command == "kafka":
            asyncio.run(run_kafka_tests())

        elif command == "flow":
            user_id, login, password = test_create_user()
            if login:
                token = test_login_user(login, password)
                if token:
                    ads = create_multiple_ads(2)
                    if len(ads) >= 2:
                        test_full_moderation_flow(token, ads[0])
                        test_close_and_predict_flow(token, ads[1])

        else:
            print(f"Неизвестная команда: {command}")
    else:
        print("\nУкажите команду. Пример: python manual_tests.py all")
