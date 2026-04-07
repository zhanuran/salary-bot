import asyncio
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden, BadRequest, RetryAfter, TelegramError

logger = logging.getLogger(__name__)


class SalarySender:
    """
    Отправляет зарплатные сообщения с:
    - rate limiting (не более N сообщений/сек)
    - обработкой всех ошибок Telegram
    - логированием каждой отправки
    - пропуском уже отправленных
    """

    def __init__(self, bot: Bot, sheets, config):
        self.bot = bot
        self.sheets = sheets
        self.config = config
        self.delay = 1.0 / config.MESSAGES_PER_SECOND  # пауза между сообщениями

    async def send_all(self, month: str) -> dict:
        """Главная функция рассылки."""
        messages = self.sheets.get_salary_messages(month)

        if not messages:
            logger.warning(f"Нет сообщений для месяца: {month}")
            return {'sent': 0, 'failed': 0, 'skipped': 0}

        sent = 0
        failed = 0
        skipped = 0

        logger.info(f"Рассылка начата: {month}, {len(messages)} получателей")

        for item in messages:
            chat_id = item['chat_id']
            message = item['message']

            # Пропускаем уже отправленных
            if self.sheets.is_already_sent(chat_id, month):
                skipped += 1
                continue

            result = await self._send_one(chat_id, message, month)

            if result['success']:
                sent += 1
            else:
                failed += 1

            # Пауза для соблюдения rate limit
            await asyncio.sleep(self.delay)

        logger.info(f"Рассылка завершена: ✅{sent} ❌{failed} ⏭{skipped}")
        return {'sent': sent, 'failed': failed, 'skipped': skipped}

    async def retry_failed(self, month: str) -> dict:
        """Повторная отправка только неудачным."""
        failed_list = self.sheets.get_failed_sends(month)

        if not failed_list:
            return {'sent': 0, 'failed': 0}

        # Получаем все сообщения месяца для поиска текста
        all_messages = self.sheets.get_salary_messages(month)
        msg_by_id = {m['chat_id']: m['message'] for m in all_messages}

        sent = 0
        failed = 0

        for item in failed_list:
            chat_id = item['chat_id']
            message = msg_by_id.get(chat_id)

            if not message:
                logger.warning(f"Сообщение не найдено для {chat_id}")
                continue

            result = await self._send_one(chat_id, message, month)
            if result['success']:
                sent += 1
            else:
                failed += 1

            await asyncio.sleep(self.delay)

        return {'sent': sent, 'failed': failed}

    async def _send_one(self, chat_id: str, message: str, month: str) -> dict:
        """Отправляет одно сообщение, обрабатывает все ошибки."""
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                'Ризамын ✅',
                callback_data=f'feedback|{chat_id}|{month}|Ризамын'
            ),
            InlineKeyboardButton(
                'Риза емеспін ❌',
                callback_data=f'feedback|{chat_id}|{month}|Риза емеспін'
            )
        ]])

        name = self.sheets.get_name(chat_id)

        try:
            await self.bot.send_message(
                chat_id=int(chat_id),
                text=message,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            self.sheets.log_send(chat_id, name, month, '✅ Жіберілді')
            logger.info(f"✅ {name} ({chat_id})")
            return {'success': True}

        except Forbidden:
            # Пользователь заблокировал бота
            error = 'Бот блокталған'
            self.sheets.log_send(chat_id, name, month, '❌ Бот блокталған', error)
            logger.warning(f"❌ BLOCKED: {name} ({chat_id})")
            return {'success': False, 'error': error}

        except BadRequest as e:
            # Неверный chat_id или другая ошибка запроса
            error = f'BadRequest: {str(e)}'
            self.sheets.log_send(chat_id, name, month, '❌ Қате chat_id', error)
            logger.error(f"❌ BAD REQUEST: {name} ({chat_id}): {e}")
            return {'success': False, 'error': error}

        except RetryAfter as e:
            # Telegram просит подождать — ждём и повторяем
            wait_time = e.retry_after + 1
            logger.warning(f"Rate limit! Waiting {wait_time}s...")
            await asyncio.sleep(wait_time)
            return await self._send_one(chat_id, message, month)  # рекурсивный retry

        except TelegramError as e:
            # Любая другая ошибка Telegram
            error = str(e)
            self.sheets.log_send(chat_id, name, month, '❌ Telegram қатесі', error)
            logger.error(f"❌ TELEGRAM ERROR: {name} ({chat_id}): {e}")
            return {'success': False, 'error': error}

        except Exception as e:
            # Неожиданная ошибка — логируем и продолжаем
            error = str(e)
            self.sheets.log_send(chat_id, name, month, '❌ Белгісіз қате', error)
            logger.error(f"❌ UNKNOWN ERROR: {name} ({chat_id}): {e}")
            return {'success': False, 'error': error}
