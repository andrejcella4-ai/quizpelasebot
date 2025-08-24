#!/usr/bin/env python3
"""
Скрипт для загрузки текстов бота из JSON файла в базу данных через API.

Использование:
    python seed_bot_texts.py texts.json

Формат JSON файла:
[
    {
        "text_name": "single_game_answer",
        "label": "Результат одиночной игры",
        "description": "Сообщение с результатами после завершения одиночной игры",
        "unformatted_text": "🏁 Викторина завершена! ..."
    },
    ...
]
"""

import json
import sys
import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from pathlib import Path


load_dotenv(Path(__file__).parent.parent / '.env')


async def upload_texts(json_file_path: str):
    """Загружает тексты из JSON файла в API."""
    
    # Читаем JSON файл
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            texts = json.load(f)
    except FileNotFoundError:
        print(f"Ошибка: файл {json_file_path} не найден")
        return False
    except json.JSONDecodeError as e:
        print(f"Ошибка при разборе JSON: {e}")
        return False
    
    if not isinstance(texts, list):
        print("Ошибка: JSON должен содержать массив объектов")
        return False
    
    # Получаем настройки из переменных окружения
    api_url = os.getenv('API_URL', 'http://localhost:8000')
    system_token = os.getenv('BOT_SYSTEM_TOKEN') or os.getenv('BOT_TOKEN')
    
    if not system_token:
        print("Ошибка: не задан BOT_SYSTEM_TOKEN или BOT_TOKEN")
        return False
    
    # Формируем payload
    payload = {'texts': texts}
    headers = {
        'Authorization': f'Token {system_token}',
        'Content-Type': 'application/json'
    }
    
    # Отправляем запрос
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{api_url}/bot-texts/bulk-upsert/',
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Успешно загружено:")
                    print(f"   Создано: {result.get('created', 0)}")
                    print(f"   Обновлено: {result.get('updated', 0)}")
                    print(f"   Всего: {result.get('total', 0)}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка {response.status}: {error_text}")
                    return False
    except Exception as e:
        print(f"❌ Ошибка при отправке запроса: {e}")
        return False


def main():
    """Главная функция."""
    if len(sys.argv) != 2:
        print("Использование: python seed_bot_texts.py <json_file>")
        print("Пример: python seed_bot_texts.py texts.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    print(f"Загрузка текстов из {json_file}...")
    
    success = asyncio.run(upload_texts(json_file))
    
    if success:
        print("🎉 Загрузка завершена успешно!")
        sys.exit(0)
    else:
        print("💥 Загрузка завершилась с ошибкой")
        sys.exit(1)


if __name__ == '__main__':
    main()
