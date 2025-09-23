# Используем официальный Python образ
FROM python:3.11-slim

# Безопасные настройки Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Устанавливаем системные зависимости для компиляции
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем директорию для векторного хранилища
RUN mkdir -p vectorstore_faiss

# Создаём непривилегированного пользователя и назначаем права
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

# Открываем порт
EXPOSE 8082

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request,sys;\
    import urllib.error;\
    url='http://127.0.0.1:8082/';\
    try:\
        with urllib.request.urlopen(url, timeout=3) as r: sys.exit(0 if r.status==200 else 1)\
    except Exception: sys.exit(1)"

# Команда запуска (uvicorn без reload)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082", "--workers", "2"]
