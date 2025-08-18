#!/usr/bin/env python
"""
Простой скрипт для запуска заполнения базы данных
"""

import os
import sys

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Запускаем основной скрипт
from populate_database import main

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Операция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1) 