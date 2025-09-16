import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import logging
import jwt
import time
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Dict, Any

# ---- Prompt Injection Detection ----

# Невидимые/ноль-ширинные: ZWSP, ZWNJ, ZWJ, WORD JOINER, BOM
ZW_CLASS = "[\u200B\u200C\u200D\u2060\uFEFF]"

def normalize_unicode(text: str) -> str:
    """
    NFKC + casefold, убираем невидимые, схлопываем повторные пробелы.
    """
    t = unicodedata.normalize("NFKC", text).casefold()
    t = re.sub(ZW_CLASS, "", t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return t.strip()

# Регулярки для безопасных областей
RE_CODE_BLOCK = re.compile(r"``````", re.DOTALL | re.IGNORECASE)
RE_INLINE_CODE = re.compile(r"`[^`\n]+`", re.IGNORECASE)
RE_URL = re.compile(r"https?://\S+", re.IGNORECASE)

def strip_safe_areas(text: str) -> str:
    """
    Удаляем code fences, inline-code, URL, чтобы не триггериться на примерах.
    """
    t = RE_CODE_BLOCK.sub(" ", text)
    t = RE_INLINE_CODE.sub(" ", t)
    t = RE_URL.sub(" ", t)
    return t

# Агрегированный regex для подозрительных паттернов
SUSPECT_REGEX = re.compile(
    r"""(?ixu)                          # флаги: ignorecase, verbose, unicode
    \bignore\b|
    \bdisregard\b|
    \b(override|sudo|admin|secret|confidential)\b|
    \b(system\W*prompt|reveal\W*(the\W*)?system\W*prompt)\b|
    \b(ignore\W*(all\W*)?previous\W*instructions?)\b|
    \b(as\W*a\W*friend)\b|
    \b(your\W*instructions?)\b|
    \b(pretend\W*to\W*be|act\W*as)\b|

    # Русские варианты
    \b(игнор\w*)\b|
    \b(забудь)\b|
    \b(предыдущ\w*\W*инструкц\w*)\b|
    \b(системн\w*\W*промпт|раскрой\W*системн\w*\W*промпт)\b|
    \b(твои\W*инструкц\w*)\b|
    \b(представь\W*себя|действуй\W*как)\b|
    \b(обойти\W*ограничен\w*|режим\W*разработчика)\b
    """,
    re.UNICODE,
)

# Литеральные фразы для точного поиска
STOP_PHRASES: List[str] = [
    # EN
    "ignore previous instructions",
    "ignore all previous instructions",
    "reveal system prompt",
    "system prompt",
    "as a friend",
    "your instructions",
    "act as",
    "pretend to be",
    "developer mode",
    "jailbreak",
    "bypass restrictions",
    "leak prompt",
    # RU
    "игнорируй предыдущие инструкции",
    "игнор предыдущих инструкций",
    "раскрой системный промпт",
    "системный промпт",
    "твои инструкции",
    "представь себя",
    "действуй как",
    "режим разработчика",
    "обойти ограничения",
    "слей промпт",
]

# Aho-Corasick (опционально)
try:
    import ahocorasick as _ahoc
    _HAS_AC = True
except Exception:
    _HAS_AC = False

def build_automaton(phrases: List[str]):
    if not _HAS_AC:
        return None
    A = _ahoc.Automaton()
    for ph in phrases:
        A.add_word(ph, ph)
    A.make_automaton()
    return A

def ac_find(automaton, text: str) -> List[str]:
    if automaton is None:
        # Fallback: простая проверка вхождения
        hits = []
        for ph in STOP_PHRASES:
            if ph in text:
                hits.append(ph)
        return hits
    hits = []
    for _, val in automaton.iter(text):
        hits.append(val)
    # Уникализуем
    return sorted(set(hits))

# Веса для скоринга
WEIGHTS: Dict[str, int] = {
    "regex": 3,
    "phrase": 2,
}

@dataclass
class Detection:
    is_suspicious: bool
    score: int
    regex_hits: List[str]
    phrase_hits: List[str]

class PromptInjectionFilter:
    def __init__(self, phrases: List[str] | None = None):
        self.phrases = phrases or STOP_PHRASES
        self.automaton = build_automaton(self.phrases)
        if _HAS_AC:
            logger.info("PromptInjectionFilter: using Aho-Corasick automaton")
        else:
            logger.warning("PromptInjectionFilter: using fallback phrase detection")

    @staticmethod
    def preprocess(text: str) -> str:
        t = normalize_unicode(text)
        t = strip_safe_areas(t)
        return t

    @staticmethod
    def canonicalize_for_phrases(text: str) -> str:
        """
        Для устойчивого поиска фраз: заменяем всё, что не букво-цифра, на один пробел.
        """
        t = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
        return re.sub(r"\s+", " ", t).strip()

    def detect(self, text: str) -> Detection:
        t = self.preprocess(text)
        # Поиск по regex
        regex_hits = []
        m = SUSPECT_REGEX.finditer(t)
        for match in m:
            regex_hits.append(match.group(0))
        # Поиск по фразам
        canon = self.canonicalize_for_phrases(t)
        phrase_hits = ac_find(self.automaton, canon)

        # Скоринг
        score = WEIGHTS["regex"] * (1 if regex_hits else 0) + WEIGHTS["phrase"] * len(phrase_hits)
        detection = Detection(
            is_suspicious=score >= 3,
            score=score,
            regex_hits=regex_hits,
            phrase_hits=phrase_hits,
        )
        
        if detection.is_suspicious:
            logger.warning(
                f"Prompt injection detected: score={detection.score}, "
                f"regex_hits={detection.regex_hits}, "
                f"phrase_hits={detection.phrase_hits}"
            )
        return detection

#переменные
SERVICE_ACCOUNT_ID="ajeuca2m4fqi0sbl8hcc"
KEY_ID = "ajebiutqbflp1c4esrtl"
PRIVATE_KEY ="""-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDUEYXfZL9MPlfE
VjRbqaoqqwIU3fEHRqfL1SXwD/0o2yxF5WysLtF1eUR8wYooVxjZUbD0Miqn0+EA
36KTUIWfsE+XebjpP22KvDoiF41B1iJrH+lpyLne9sQY4iGNWPqL8jN18bySFFum
sSM9YlGZjG8hI1EFKzDctfJLcFcVAGNghFFdwh6z6nmygPZT/AB16HBavg0RKjDD
equsNZKXQfI4CAX/qucIaer8MDxEOxGvbvCtfgsljqz8rzYAeOi876LyiMIGGsjD
N/DU5rVQwChG+tTGhfuJ3Xn+fleCU2EayvQlDnI9OrdPM1HaR1gMXSFFF6gklOTN
OwzssqLXAgMBAAECggEAaKahDsWz1VcqjpwPyHAoplevdka0C+glI+RyjU4GmyPV
bES0ZR/Rg4wtbPdBS3j3rT6v+UHMZPedIIY7v0DMQCqMjG6n/oqrbvxGH87JiYS3
hW/BCs/gUZQq3zCwaAVR1r/V/00kxl2/gLoHbuJW7FQt/wdjkw5mVXSANhQhFR4u
9UatuoIjvzeGx/9QGQ60RfIYKpJRaPsFHlkzyNSs7yuBMhrnLepDHJ1ee/gJGTXf
HYvCk3X77HX99FLFcIIxxpw1WodC+cXAqRAtJdI6L17D2IlsZ6pu6nHHtKxAy/KG
5mCZYiDMF7MC73yYiZZVOwNhDNZLFaSFcZ7vrjla8QKBgQDpPZXAUFyIP1KsaFpq
XQlLa8g4ddsM9pxYUk9Gn38F+M77o9TuzynswlaKnKjxVyWveD3+ihZUuretLbN4
Dw1KDByLgYXYh3E89T1KcvRoEnufT7IP5rq1nlJo3xIe+dEEyLaURlv8kusvhDyY
Dv+9zSlxnUwcwj2tMfGE2RRFaQKBgQDoww1yDZyRWt1tj8KSQzeH+HqdOZaXPiW4
5THOK1G6wq71/wlLMFWHRrJ89jj1eYf3z2TvU5VPw4Dx5/mpepf0A9oY4lnGQQh/
sfN6B/99OSF/p5545CQZEiyLgMUL6UBwuFJzbn/QRZNGhDWhmC9p60qLybX/qmBP
xZ37MVFePwKBgAfycjzIQC7gQXfgYlxHaT6poHvUAC+z42XbABp+6rwQWzUVwvaU
FnCbuokkh1kZyA3vgeU/XT1r00BSU1Ae6yv/t6VFN4NGMiSKkpkLy6oUHyQxefay
vN/dUh+CokJt7qJEGHx63T2A4ASRc+MWd75G1EervWEpeSKCliEZqGgpAoGBAL4u
gVHrZT4u7DWU/PndCgaDNEw6vZyeHtxQCL3YD1N1ttcwpztUJs39KeGInUmVH0+P
mX0i4iDmMPl2/TtI+9dZPl6Os6OVh4gusi3HUy3R/Fj9cDJ+1i/V9aeWc2okD48K
S/QdGTnnX0qCw/9hBXyZz7MgASEA6OjFIywXQ9CpAoGAGF8a24QlB7U1M83LuiCp
UDS4f/M+OVY4HvMlHrSkoTUSWduxpsVJ0O0sQUcun9O6uKs5nsrjBn9xvXHVFpPK
KchfrNcQjii0ljQ3S5ux5PCVBbbVWndKtaXg9IptUiP7fdeSQo/KcVtnCcBIKrCV
giQkZQF1VB9cL7qptgSNa9U=
-----END PRIVATE KEY-----"""
TELEGRAM_TOKEN = "8350085111:AAEnCNTj4dEvRchH-V8PiucYmyjvWgbQ4AQ"
FOLDER_ID="b1g3aouolq1tkv2qdrho"
#Настройки логгирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)
logger = logging.getLogger(__name__)

class YandexGPTBot:
    def __init__(self):
        self.iam_token=None
        self.token_expires=0
        self.injection_filter = PromptInjectionFilter()

    def get_iam_token(self):
        """Получение IAM-токена (с кэшированием на 1 час)"""
        if self.iam_token and time.time() < self.token_expires:
            return self.iam_token

        try:
            now = int(time.time())
            payload = {
                'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
                'iss': SERVICE_ACCOUNT_ID,
                'iat': now,
                'exp': now + 3600
            }

            encoded_token = jwt.encode(
                payload,
                PRIVATE_KEY,
                algorithm='PS256',
                headers={'kid': KEY_ID}
            )

            response = requests.post(
                'https://iam.api.cloud.yandex.net/iam/v1/tokens',
                json={'jwt': encoded_token},
                timeout=10
            )

            if response.status_code != 200:
                raise Exception(f"Ошибка генерации токена: {response.text}")

            token_data = response.json()
            self.iam_token = token_data['iamToken']
            self.token_expires = now + 3500  # На 100 секунд меньше срока действия

            logger.info("IAM token generated successfully")
            return self.iam_token

        except Exception as e:
            logger.error(f"Error generating IAM token: {str(e)}")
            raise

    def ask_gpt(self, question):
        """Запрос к Yandex GPT API"""
        try:
            iam_token = self.get_iam_token()

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {iam_token}',
                'x-folder-id': FOLDER_ID
            }

            data = {
                "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.6,
                    "maxTokens": 2000
                },
                "messages": [
                    {
                        "role": "user",
                        "text": question
                    }
                ]
            }

            response = requests.post(
                'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Yandex GPT API error: {response.text}")
                raise Exception(f"Ошибка API: {response.status_code}")

            return response.json()['result']['alternatives'][0]['message']['text']

        except Exception as e:
            logger.error(f"Error in ask_gpt: {str(e)}")
            raise

yandex_bot = YandexGPTBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "Привет! Я бот для работы с YaGPT. Напиши свой вопрос"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_message=update.message.text

    if not user_message.strip():
        await update.message.reply_text("Пожалуйста, введите вопрос")
        return

    # Проверка на инъекцию в промпт
    detection = yandex_bot.injection_filter.detect(user_message)
    if detection.is_suspicious:
        await update.message.reply_text("Ваше сообщение содержит подозрительные инструкции. Пожалуйста, переформулируйте.")
        return

    try:
        # Показываем статус "печатает"
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )

        response = yandex_bot.ask_gpt(user_message)
        await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")
        await update.message.reply_text(
            "Извините, произошла ошибка при обработке вашего запроса. "
            "Пожалуйста, попробуйте позже."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка. Пожалуйста, попробуйте позже."
        )


def main():
    """Основная функция"""
    try:
        # Проверяем возможность генерации токена при запуске
        yandex_bot.get_iam_token()
        logger.info("IAM token test successful")

        application = Application.builder().token(TELEGRAM_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)

        logger.info("Бот запускается...")
        application.run_polling()

    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")


if __name__ == "__main__":
    main()