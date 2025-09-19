"""
Скрипт для запуска Telegram Bot микросервиса
"""

import subprocess
import sys
import time

def install_requirements():
    """Устанавливает зависимости"""
    print("Установка зависимостей...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Зависимости установлены")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки зависимостей: {e}")
        return False

def start_service():
    """Запускает микросервис"""
    print("Запуск Telegram Bot микросервиса...")
    print("Сервис будет доступен по адресу: http://localhost:9999")
    print("Для остановки нажмите Ctrl+C")
    print("=" * 50)
    
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n🛑 Сервис остановлен")

if __name__ == "__main__":
    print("🚀 Telegram Bot Microservice Launcher")
    print("=" * 50)
    
    if install_requirements():
        start_service()
    else:
        print("❌ Не удалось установить зависимости. Проверьте подключение к интернету.")

