# Используем официальный Python образ
FROM python:3.11-slim

# Безопасные настройки Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаём непривилегированного пользователя и назначаем права
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser

# Открываем порт
EXPOSE 8080

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD python -c "import urllib.request,sys;\
    import urllib.error;\
    url='http://127.0.0.1:8080/';\
    try:\
        with urllib.request.urlopen(url, timeout=2) as r: sys.exit(0 if r.status==200 else 1)\
    except Exception: sys.exit(1)"

# Команда запуска (uvicorn без reload)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
