import os
import json
from dotenv import load_dotenv

load_dotenv()

# Записываем credentials.json из переменной окружения (для Railway)
creds = os.getenv('GOOGLE_CREDENTIALS_JSON')
if creds:
    with open('credentials.json', 'w') as f:
        f.write(creds)


class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    ADMIN_CHAT_ID: str = os.getenv('ADMIN_CHAT_ID', '')
    FINANCE_CHAT_IDS: list = [x.strip() for x in os.getenv('FINANCE_CHAT_ID', '').split(',') if x.strip()]

    # Google Sheets
    SHEET_ID: str = os.getenv('SHEET_ID', '')
    SHEET_URL: str = f"https://docs.google.com/spreadsheets/d/{os.getenv('SHEET_ID', '')}/edit"
    GOOGLE_CREDS_FILE: str = os.getenv('GOOGLE_CREDS_FILE', 'credentials.json')

    # Рассылка
    MESSAGES_PER_SECOND: int = 10
    RETRY_DELAY_SECONDS: int = 2
