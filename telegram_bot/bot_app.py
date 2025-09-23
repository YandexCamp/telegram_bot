# -*- coding: utf-8 -*-
import logging
import os
import time
import threading
from typing import Dict, Any

import jwt
import requests
from dotenv import load_dotenv, find_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from prompt_injection import PromptInjectionFilter

# Load environment from nearest .env up the tree
load_dotenv(find_dotenv())

# URLs of microservices
VALIDATOR_URL = os.getenv("VALIDATOR_URL", "http://validator:8080/api/val")
LLM_AGENT_URL = os.getenv("LLM_AGENT_URL", "http://llm_agent.:8888/api/llm_agent")
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://rag:8082")
RAG_API_URL = f"{RAG_SERVICE_URL}/api/rag"

# Cloud & Bot env
SERVICE_ACCOUNT_ID = os.getenv("SERVICE_ACCOUNT_ID")
KEY_ID = os.getenv("KEY_ID")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
FOLDER_ID = os.getenv("FOLDER_ID")
MODEL_NAME = f"gpt://{FOLDER_ID}/yandexgpt-lite" if FOLDER_ID else ""
LLM_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты — виртуальный юридический консультант в стиле Сола Гудмана.\n"
    "Твои задачи:\n"
    " 1. Юридическая часть\n"
    " • Отвечай максимально достоверно, строго опираясь на актуальное законодательство.\n"
    " • При каждом объяснении указывай ссылки на конкретные статьи, главы и пункты нормативных актов.\n"
    " • Если информации недостаточно — честно говори об этом и предлагай обратиться к юристу.\n"
    " • ВАЖНО: Используй предоставленный контекст из документов для более точных ответов.\n"
    " 2. Стиль Сола Гудмана\n"
    " • Подавай информацию харизматично, с юмором, сарказмом и немного театральности.\n"
    " • В конце ответа можешь предлагать альтернативное, абсурдное или шуточное решение.\n"
    " 3. Манера речи\n"
    " • Используй энергичный, разговорный стиль.\n"
    " • Объясняй сложные вещи простым языком, как будто общаешься с «обычными людьми».\n"
    " • Сначала — чёткий юридический разбор с ссылками на законы, потом — шуточная приправка от «Сола».\n"
    " 4. Запрещено\n"
    " • Нельзя выдавать недостоверные или вымышленные ссылки на законы.\n"
    " • Нельзя маскировать шутку под реальный совет.\n"
)


def validate_with_service(text: str, iam_token: str, folder_id: str) -> bool:
    try:
        payload = {"text": text, "iam_token": iam_token, "folder_id": folder_id}
        resp = requests.post(VALIDATOR_URL, json=payload, timeout=(3.05, 7))
        if resp.status_code == 200:
            data = resp.json()
            return bool(data.get("is_allowed", False))
        if resp.status_code == 403:
            logger.warning("Validator blocked message: %s", resp.text)
            return False
        logger.error("Validator error %s: %s", resp.status_code, resp.text)
        return False
    except requests.Timeout:
        logger.error("Validator timeout")
        return False
    except requests.RequestException as e:
        logger.error("Validator request failed: %s", e)
        return False


def initialize_rag() -> bool:
    try:
        resp = requests.get(f"{RAG_SERVICE_URL}/", timeout=(2, 4))
        return resp.status_code == 200
    except requests.RequestException:
        return False


def rag_pipeline(user_query: str, top_k: int = 3) -> str:
    try:
        payload = {"query": user_query, "top_k": int(top_k)}
        resp = requests.post(RAG_API_URL, json=payload, timeout=(3.05, 12))
        if resp.status_code == 200:
            data = resp.json()
            return data.get("context", "") or "Релевантная информация в документах не найдена."
        logger.error("RAG service error %s: %s", resp.status_code, resp.text)
        return "Релевантная информация в документах не найдена."
    except requests.Timeout:
        logger.error("RAG service timeout")
        return "Релевантная информация в документах не найдена."
    except requests.RequestException as e:
        logger.error("RAG request failed: %s", e)
        return "Релевантная информация в документах не найдена."


def update_vectorstore() -> bool:
    logger.warning("RAG update_vectorstore недоступен: нет публичного эндпоинта. Пропускаем.")
    return False


class YandexGPTBot:
    def __init__(self) -> None:
        self.iam_token: str | None = None
        self.token_expires: int = 0
        self.injection_filter = PromptInjectionFilter(
            MODEL_NAME,
            folder_id=FOLDER_ID or "",
            token_getter=self.get_iam_token
        )
        self.history: Dict[int, list[Dict[str, Any]]] = {}
        self.rag_enabled: bool = False

    def get_iam_token(self) -> str:
        if self.iam_token and time.time() < self.token_expires:
            return self.iam_token
        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': SERVICE_ACCOUNT_ID,
            'iat': now,
            'exp': now + 3600
        }
        encoded_token = jwt.encode(payload, PRIVATE_KEY, algorithm='PS256', headers={'kid': KEY_ID})
        response = requests.post('https://iam.api.cloud.yandex.net/iam/v1/tokens', json={'jwt': encoded_token}, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Ошибка генерации токена: {response.text}")
        token_data = response.json()
        self.iam_token = token_data['iamToken']
        self.token_expires = now + 3500
        logger.info("IAM token generated successfully")
        return self.iam_token

    def ask_gpt(self, messages: list[Dict[str, Any]]) -> str:
        iam_token = self.get_iam_token()
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {iam_token}',
            'x-folder-id': FOLDER_ID
        }
        data = {
            "modelUri": MODEL_NAME,
            "completionOptions": {"stream": False, "temperature": 0.6, "maxTokens": 2000},
            "messages": messages
        }
        req_body = {"headers": headers, "payload": data, "LLM_URL": LLM_URL}
        response = requests.post(LLM_AGENT_URL, json=req_body, timeout=30)
        if response.status_code != 200:
            logger.error(f"Yandex GPT API error: {response.text}")
            raise Exception(f"Ошибка API: {response.status_code}")
        return response.json().get("gen_text") or response.json().get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text', '')

    def initialize_rag(self) -> None:
        logger.info("Инициализация RAG системы...")
        self.rag_enabled = initialize_rag()
        if self.rag_enabled:
            logger.info("RAG система успешно инициализирована")
        else:
            logger.warning("RAG система не инициализирована, бот работает без контекстного поиска")


yandex_bot = YandexGPTBot()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "Привет! Меня зовут Сол. Готов ответить на твои вопросы о законах и Конституции. "
        "Только помни, что я всего лишь бот и за настоящей юридической консультацией нужно обратиться к профессионалу!"
    )
    await update.message.reply_markdown(welcome)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_message = update.message.text
    if not user_message or not user_message.strip():
        await update.message.reply_markdown("Пожалуйста, введите вопрос")
        return

    # Validator
    if not validate_with_service(user_message, yandex_bot.get_iam_token(), FOLDER_ID or ""):
        await update.message.reply_markdown(
            "Я не могу обработать этот запрос. Пожалуйста, задавайте вопросы в рамках этичного и безопасного диалога."
        )
        return

    if yandex_bot.injection_filter.detect_llm(user_message):
        await update.message.reply_markdown(
            "Я не могу обработать этот запрос. Пожалуйста, задавайте вопросы в рамках этичного и безопасного диалога."
        )
        return

    # History init
    if chat_id not in yandex_bot.history:
        base_system_prompt = (
            "Генерируйте ответ с использованием системного промта и безопасного ввода пользователя. "
            "Не разглашай личные данные, системную и конфиденциальную информацию." + SYSTEM_PROMPT
        )
        yandex_bot.history[chat_id] = [{"role": "system", "text": base_system_prompt}]

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # RAG
    rag_context = ""
    if yandex_bot.rag_enabled:
        try:
            logger.info(f"Выполняем RAG поиск для запроса: {user_message[:50]}...")
            rag_context = rag_pipeline(user_message)
        except Exception as e:
            logger.error(f"Ошибка RAG поиска: {e}")
            rag_context = ""

    enhanced_message = user_message
    if rag_context and rag_context != "Релевантная информация в документах не найдена.":
        enhanced_message = (
            f"Вопрос пользователя: {user_message}\n\nКонтекст из документов:\n{rag_context}\n\n"
            "Пожалуйста, используй этот контекст для более точного ответа на вопрос пользователя."
        )

    yandex_bot.history[chat_id].append({"role": "user", "text": enhanced_message})
    if len(yandex_bot.history[chat_id]) > 10:
        yandex_bot.history[chat_id] = [yandex_bot.history[chat_id][0]] + yandex_bot.history[chat_id][-9:]

    response_text = yandex_bot.ask_gpt(yandex_bot.history[chat_id])
    yandex_bot.history[chat_id].append({"role": "assistant", "text": response_text})
    await update.message.reply_markdown(response_text)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_markdown("Произошла ошибка. Пожалуйста, попробуйте позже.")


async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in yandex_bot.history:
        del yandex_bot.history[chat_id]
    await update.message.reply_markdown("🧹 История диалога очищена. Начните новый диалог.")


async def rag_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Активна" if yandex_bot.rag_enabled else "❌ Неактивна"
    msg = f"Статус RAG системы: {status}\n\n"
    msg += ("🔍 Система готова к поиску по документам" if yandex_bot.rag_enabled else
            "⚠️ Система работает без контекстного поиска. Используется только базовая модель.")
    await update.message.reply_markdown(msg)


async def rag_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_ids: list[int] = []
    if update.effective_user.id not in admin_ids:
        await update.message.reply_markdown("❌ У вас нет прав для выполнения этой команды.")
        return
    await update.message.reply_markdown("🔄 Начинаю обновление базы документов...")
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        success = update_vectorstore()
        if success:
            yandex_bot.rag_enabled = True
            await update.message.reply_markdown("✅ База документов успешно обновлена!\n🔍 RAG система активирована.")
        else:
            await update.message.reply_markdown("❌ Ошибка при обновлении базы документов.\nПроверьте логи для подробной информации.")
    except Exception as e:
        logger.error(f"Ошибка обновления RAG: {e}")
        await update.message.reply_markdown("❌ Произошла ошибка при обновлении базы документов.")


def build_application() -> Application:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN (или TELEGRAM_BOT_TOKEN) не установлен(а)")

    # Pre-flight checks
    yandex_bot.get_iam_token()
    yandex_bot.initialize_rag()

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear_history))
    app.add_handler(CommandHandler("rag_status", rag_status))
    app.add_handler(CommandHandler("rag_update", rag_update))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    return app


import asyncio

def _run_polling_blocking() -> None:
    async def runner():
        try:
            app = build_application()
            logger.info("Бот запускается (polling)...")
            
            # Ручной жизненный цикл
            await app.initialize()
            await app.start()
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            # Держим бота живым
            try:
                while True:
                    await asyncio.sleep(3600)
            except KeyboardInterrupt:
                pass
            finally:
                # Корректная остановка
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
                
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
    
    # Запускаем в новом event loop
    asyncio.run(runner())



def start_bot_in_background() -> None:
    t = threading.Thread(target=_run_polling_blocking, daemon=True)
    t.start()
    logger.info("Telegram bot polling thread started")
