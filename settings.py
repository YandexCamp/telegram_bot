from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
    FOLDER_ID: str = os.getenv('FOLDER_ID')
    SERVICE_ACCOUNT_ID: str = os.getenv('SERVICE_ACCOUNT_ID')
    KEY_ID: str = os.getenv('KEY_ID')
    PRIVATE_KEY: str = os.getenv('PRIVATE_KEY')
    SECRET_KEY: str = os.getenv('SECRET_KEY')
    IDENTIFIER: str = os.getenv('IDENTIFIER')
