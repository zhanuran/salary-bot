import logging
from datetime import datetime
from typing import Optional
import gspread
from google.oauth2.service_account import Credentials
from config import Config

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

# Названия листов в вашей таблице
SHEET_CHAT_IDS = 'ChatIDs'
SHEET_FEEDBACK = 'Feedback'
SHEET_SEND_LOG = 'SendLog'


class SheetsClient:
    def __init__(self):
        self.config = Config()
        import os, json
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            creds = Credentials.from_service_account_info(
                json.loads(creds_json), scopes=SCOPES
            )
        else:
            creds = Credentials.from_service_account_file(
                self.config.GOOGLE_CREDS_FILE, scopes=SCOPES
            )
        self.gc = gspread.authorize(creds)
        self.spreadsheet = self.gc.open_by_key(self.config.SHEET_ID)
        self._ensure_sheets_exist()

    def _ensure_sheets_exist(self):
        """Создаём нужные листы если их нет."""
        existing = [s.title for s in self.spreadsheet.worksheets()]

        if SHEET_SEND_LOG not in existing:
            ws = self.spreadsheet.add_worksheet(SHEET_SEND_LOG, rows=5000, cols=8)
            ws.append_row(['Chat ID', 'Аты', 'Ай', 'Статус', 'Қате себебі', 'Уақыт'])
            ws.format('A1:F1', {'textFormat': {'bold': True}})
            logger.info(f"Лист '{SHEET_SEND_LOG}' создан")

        if SHEET_FEEDBACK not in existing:
            ws = self.spreadsheet.add_worksheet(SHEET_FEEDBACK, rows=5000, cols=6)
            ws.append_row(['Chat ID', 'Аты', 'Ай', 'Жауап', 'Себеп', 'Уақыт'])
            ws.format('A1:F1', {'textFormat': {'bold': True}})
            logger.info(f"Лист '{SHEET_FEEDBACK}' создан")

    # ─────────────────────────────────────────────
    # Сотрудники (ChatIDs)
    # ─────────────────────────────────────────────

    def get_all_employees(self) -> list[dict]:
        ws = self.spreadsheet.worksheet(SHEET_CHAT_IDS)
        rows = ws.get_all_values()
        result = []
        for row in rows[1:]:
            if len(row) >= 2 and row[1]:
                result.append({
                    'name': row[0],
                    'chat_id': str(row[1]).strip(),
                    'department': row[2].strip() if len(row) > 2 and row[2] else 'Белгісіз'
                })
        return result

    def find_employee(self, chat_id: str) -> Optional[dict]:
        employees = self.get_all_employees()
        for emp in employees:
            if emp['chat_id'] == str(chat_id):
                return emp
        return None

    def register_employee(self, chat_id: str, name: str, username: str = ''):
        ws = self.spreadsheet.worksheet(SHEET_CHAT_IDS)
        ws.append_row([name, chat_id, '', str(datetime.now())])
        logger.info(f"Registered: {name} ({chat_id})")

    def get_name(self, chat_id: str) -> str:
        emp = self.find_employee(chat_id)
        return emp['name'] if emp else 'Анықталмаған'

    # ─────────────────────────────────────────────
    # Зарплатные сообщения (лист по имени месяца)
    # ─────────────────────────────────────────────

    def get_salary_messages(self, month: str) -> list[dict]:
        """
        Читает фиксированный лист 'Рассылка'.
        Формат: A=Имя, B=Chat ID, C=Текст сообщения
        """
        ws = self.spreadsheet.worksheet('Рассылка')
        rows = ws.get_all_values()
        result = []

        for row in rows[1:]:  # пропускаем заголовок
            if len(row) < 3:
                continue

            chat_id = str(row[1]).strip()
            message = str(row[2]).strip()

            if chat_id and message:
                result.append({
                    'chat_id': chat_id,
                    'message': message
                })

        logger.info(f"{len(result)} хабарлама дайын")
        return result

    # ─────────────────────────────────────────────
    # SendLog — лог отправок
    # ─────────────────────────────────────────────

    def log_send(self, chat_id: str, name: str, month: str,
                 status: str, error: str = ''):
        ws = self.spreadsheet.worksheet(SHEET_SEND_LOG)
        ws.append_row([
            chat_id, name, month, status, error, str(datetime.now())
        ])

    def is_already_sent(self, chat_id: str, month: str) -> bool:
        ws = self.spreadsheet.worksheet(SHEET_SEND_LOG)
        rows = ws.get_all_values()
        for row in rows[1:]:
            if (len(row) >= 4
                    and str(row[0]) == str(chat_id)
                    and row[2] == month
                    and row[3].startswith('✅')):
                return True
        return False

    def get_failed_sends(self, month: str) -> list[dict]:
        ws = self.spreadsheet.worksheet(SHEET_SEND_LOG)
        rows = ws.get_all_values()
        failed = []
        sent_ids = set()

        # Сначала собираем успешно отправленные
        for row in rows[1:]:
            if len(row) >= 4 and row[2] == month and row[3].startswith('✅'):
                sent_ids.add(str(row[0]))

        # Теперь неудачные (те которых нет в успешных)
        seen = set()
        for row in rows[1:]:
            if (len(row) >= 4
                    and row[2] == month
                    and row[3].startswith('❌')
                    and str(row[0]) not in sent_ids
                    and str(row[0]) not in seen):
                failed.append({'chat_id': str(row[0]), 'name': row[1]})
                seen.add(str(row[0]))

        return failed

    def update_send_status(self, chat_id: str, month: str, status: str):
        ws = self.spreadsheet.worksheet(SHEET_SEND_LOG)
        rows = ws.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            if len(row) >= 3 and str(row[0]) == str(chat_id) and row[2] == month:
                ws.update_cell(i, 4, status)
                return

    # ─────────────────────────────────────────────
    # Feedback
    # ─────────────────────────────────────────────

    def save_feedback(self, chat_id: str, name: str, month: str,
                      answer: str, reason: str = ''):
        ws = self.spreadsheet.worksheet(SHEET_FEEDBACK)
        ws.append_row([
            chat_id, name, month, answer, reason, str(datetime.now())
        ])

    # ─────────────────────────────────────────────
    # Статистика
    # ─────────────────────────────────────────────

    def get_stats(self, month: str) -> dict:
        log_ws = self.spreadsheet.worksheet(SHEET_SEND_LOG)
        log_rows = log_ws.get_all_values()[1:]

        fb_ws = self.spreadsheet.worksheet(SHEET_FEEDBACK)
        fb_rows = fb_ws.get_all_values()[1:]

        month_logs = [r for r in log_rows if len(r) >= 3 and r[2] == month]
        month_fb = [r for r in fb_rows if len(r) >= 3 and r[2] == month]

        total_sent = len([r for r in month_logs if r[3].startswith('✅')])
        blocked = len([r for r in month_logs if 'blocked' in r[4].lower() or '403' in r[4]])
        happy = len([r for r in month_fb if 'Ризамын' in r[3]])
        unhappy = len([r for r in month_fb if 'Риза емес' in r[3]])
        no_response = total_sent - happy - unhappy

        return {
            'total_sent': total_sent,
            'blocked': blocked,
            'happy': happy,
            'unhappy': unhappy,
            'no_response': max(0, no_response)
        }

    def get_all_months_stats(self) -> list[dict]:
        log_ws = self.spreadsheet.worksheet(SHEET_SEND_LOG)
        log_rows = log_ws.get_all_values()[1:]
        fb_ws = self.spreadsheet.worksheet(SHEET_FEEDBACK)
        fb_rows = fb_ws.get_all_values()[1:]

        months = sorted(set(
            r[2] for r in log_rows if len(r) >= 3 and r[2]
        ))

        result = []
        for month in months:
            stats = self.get_stats(month)
            stats['month'] = month
            result.append(stats)

        return result
    def get_stats_by_department(self, month: str) -> dict:
        employees = self.get_all_employees()
        dept_map = {e['chat_id']: e['department'] for e in employees}

        log_ws = self.spreadsheet.worksheet(SHEET_SEND_LOG)
        log_rows = log_ws.get_all_values()[1:]
        fb_ws = self.spreadsheet.worksheet(SHEET_FEEDBACK)
        fb_rows = fb_ws.get_all_values()[1:]

        month_logs = [r for r in log_rows if len(r) >= 4 and r[2] == month and r[3].startswith('✅')]
        month_fb = [r for r in fb_rows if len(r) >= 4 and r[2] == month]

        departments = {}
        for row in month_logs:
            chat_id = str(row[0])
            dept = dept_map.get(chat_id, 'Белгісіз')
            if dept not in departments:
                departments[dept] = {'sent': 0, 'happy': 0, 'unhappy': 0}
            departments[dept]['sent'] += 1

        for row in month_fb:
            chat_id = str(row[0])
            dept = dept_map.get(chat_id, 'Белгісіз')
            if dept not in departments:
                departments[dept] = {'sent': 0, 'happy': 0, 'unhappy': 0}
            if 'Ризамын' in row[3]:
                departments[dept]['happy'] += 1
            elif 'Риза емес' in row[3]:
                departments[dept]['unhappy'] += 1

        return departments

    def get_complaints(self, month: str) -> list[dict]:
        fb_ws = self.spreadsheet.worksheet(SHEET_FEEDBACK)
        fb_rows = fb_ws.get_all_values()[1:]

        complaints = []
        for row in fb_rows:
            if len(row) >= 4 and row[2] == month and 'Риза емес' in row[3]:
                complaints.append({
                    'name': row[1],
                    'reason': row[4] if len(row) > 4 and row[4] else '—',
                })
        return complaints
