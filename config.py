import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    ADMIN_CHAT_ID: str = os.getenv('ADMIN_CHAT_ID', '')   # ваш личный chat_id
    FINANCE_CHAT_IDS: list = [x.strip() for x in os.getenv('FINANCE_CHAT_ID', '').split(',') if x.strip()]

    # Google Sheets
    SHEET_ID: str = os.getenv('SHEET_ID', '')             # ID таблицы из URL
    SHEET_URL: str = f"https://docs.google.com/spreadsheets/d/{os.getenv('SHEET_ID', '')}"
    GOOGLE_CREDS_FILE: str = os.getenv('GOOGLE_CREDS_FILE', 'credentials.json')

    # Рассылка
    MESSAGES_PER_SECOND: int = 10   # лимит Telegram — 30/сек, берём 10 для запаса
    RETRY_DELAY_SECONDS: int = 2    # пауза между retry

    def validate(self):
        missing = []
        for field in ['BOT_TOKEN', 'ADMIN_CHAT_ID', 'SHEET_ID']:
            if not getattr(self, field):
                missing.append(field)
        if missing:
            raise ValueError(f"Переменные окружения не заданы: {', '.join(missing)}")
