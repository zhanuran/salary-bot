import asyncio
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from sheets import SheetsClient
from sender import SalarySender
from config import Config

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

sheets = SheetsClient()
config = Config()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    name = update.effective_user.first_name or 'Аноним'
    username = update.effective_user.username or ''
    already = sheets.find_employee(chat_id)
    if already:
        await update.message.reply_text(
            f"Сәлем, {already['name']}! Сіз бұрын тіркелгенсіз ✅\n"
            f"Сұрақтарыңыз болса қаржыгерге жазыңыз."
        )
        return
    sheets.register_employee(chat_id, name, username)
    logger.info(f"New registration: {name} ({chat_id})")
    await update.message.reply_text(
        f"Сәлем, {name}! 👋\n\n"
        f"Сіз сәтті тіркелдіңіз ✅\n\n"
        f"Жалақы есептелгенде сізге хабарлама келеді.\n"
        f"Сұрақтарыңыз болса қаржыгерге жазыңыз 🫶"
    )
    await context.bot.send_message(
        chat_id=config.ADMIN_CHAT_ID,
        text=f"🆕 Жаңа тіркелу:\n👤 {name}\n🆔 {chat_id}\n📎 @{username}"
    )


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split('|')
    if parts[0] != 'feedback' or len(parts) < 4:
        return
    _, chat_id, month, answer = parts[0], parts[1], parts[2], parts[3]
    name = sheets.get_name(chat_id)
    if answer == 'Ризамын':
        sheets.save_feedback(chat_id, name, month, 'Ризамын ✅', '')
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Жауабыңызға рақмет! ✅")
        sheets.update_send_status(chat_id, month, 'Ризамын ✅')
    elif answer == 'Риза емеспін':
        context.user_data['waiting_reason'] = {
            'chat_id': chat_id,
            'month': month,
            'name': name
        }
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "Түсіндіріңіз, неліктен риза емессіз?\n"
            "Себебін жазыңыз, қаржыгер сізбен байланысады. 👇"
        )
        sheets.update_send_status(chat_id, month, 'Риза емеспін ❌')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    text = update.message.text
    waiting = context.user_data.get('waiting_reason')
    if waiting and waiting['chat_id'] == chat_id:
        month = waiting['month']
        name = waiting['name']
        sheets.save_feedback(chat_id, name, month, 'Риза емеспін ❌', text)
        context.user_data.pop('waiting_reason', None)
        await update.message.reply_text(
            "Жауабыңызға рақмет! Қаржыгеріңіз жақын арада байланысады 🫶"
        )
        for fid in config.FINANCE_CHAT_IDS:
            await context.bot.send_message(
                chat_id=fid,
                text=(
                    f"⚠️ Риза емес:\n"
                    f"👤 {name} ({chat_id})\n"
                    f"📅 Ай: {month}\n"
                    f"💬 Себеп: {text}"
                )
            )
        logger.info(f"Complaint from {name} ({chat_id}): {text}")


async def cmd_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(config.ADMIN_CHAT_ID):
        return
    args = context.args
    month = ' '.join(args) if args else None
    if not month:
        await update.message.reply_text("Айды көрсетіңіз:\n/send Ақпан")
        return
    await update.message.reply_text(f"⏳ {month} айына жіберу басталды...")
    sender = SalarySender(context.bot, sheets, config)
    result = await sender.send_all(month)
    await update.message.reply_text(
        f"✅ Жіберілді: {result['sent']}\n"
        f"❌ Қате: {result['failed']}\n"
        f"⏭ Өткізілді: {result['skipped']}\n\n"
        f"Қайта жіберу үшін: /retry {month}"
    )


async def cmd_retry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(config.ADMIN_CHAT_ID):
        return
    args = context.args
    month = ' '.join(args) if args else None
    if not month:
        await update.message.reply_text("Айды көрсетіңіз:\n/retry Ақпан")
        return
    await update.message.reply_text(f"⏳ Қайта жіберу: {month}...")
    sender = SalarySender(context.bot, sheets, config)
    result = await sender.retry_failed(month)
    await update.message.reply_text(
        f"✅ Жіберілді: {result['sent']}\n"
        f"❌ Әлі де қате: {result['failed']}"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(config.ADMIN_CHAT_ID):
        return
    args = context.args
    month = ' '.join(args) if args else None
    if not month:
        await update.message.reply_text("Айды көрсетіңіз:\n/status Ақпан")
        return
    stats = sheets.get_stats(month)
    text = (
        f"📊 *{month} — статистика*\n\n"
        f"📤 Барлығы жіберілді: {stats['total_sent']}\n"
        f"✅ Ризамын: {stats['happy']}\n"
        f"❌ Риза емес: {stats['unhappy']}\n"
        f"🔇 Жауап жоқ: {stats['no_response']}\n"
        f"🚫 Бот блокталған: {stats['blocked']}\n\n"
        f"📋 Толық есеп: {config.SHEET_URL}"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def cmd_dept_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(config.ADMIN_CHAT_ID):
        return
    args = context.args
    month = ' '.join(args) if args else None
    if not month:
        await update.message.reply_text("Айды көрсетіңіз:\n/dept Ақпан")
        return
    departments = sheets.get_stats_by_department(month)
    if not departments:
        await update.message.reply_text(f"'{month}' айы бойынша деректер жоқ.")
        return
    lines = [f"📊 *{month} — бөлімдер бойынша*\n"]
    for dept, s in sorted(departments.items()):
        no_resp = max(0, s['sent'] - s['happy'] - s['unhappy'])
        lines.append(
            f"🏢 *{dept}*\n"
            f"  📤 Жіберілді: {s['sent']}\n"
            f"  ✅ Ризамын: {s['happy']}\n"
            f"  ❌ Риза емес: {s['unhappy']}\n"
            f"  🔇 Жауап жоқ: {no_resp}\n"
        )
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def cmd_complaints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(config.ADMIN_CHAT_ID):
        return
    args = context.args
    month = ' '.join(args) if args else None
    if not month:
        await update.message.reply_text("Айды көрсетіңіз:\n/complaints Ақпан")
        return
    complaints = sheets.get_complaints(month)
    if not complaints:
        await update.message.reply_text(f"'{month}' айында шағымдар жоқ ✅")
        return
    lines = [f"❌ *{month} — риза емес ({len(complaints)} адам)*\n"]
    for c in complaints:
        lines.append(f"👤 *{c['name']}*\n💬 {c['reason']}\n")
    text = '\n'.join(lines)
    if len(text) > 4000:
        text = text[:4000] + '\n\n_...толық тізім Feedback парағында_'
    await update.message.reply_text(text, parse_mode='Markdown')


async def cmd_stats_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(config.ADMIN_CHAT_ID):
        return
    all_stats = sheets.get_all_months_stats()
    lines = ["📊 *Барлық айлар бойынша статистика*\n"]
    for row in all_stats:
        lines.append(
            f"📅 *{row['month']}*: "
            f"✅{row['happy']} ❌{row['unhappy']} 🔇{row['no_response']}"
        )
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def cmd_employees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(config.ADMIN_CHAT_ID):
        return
    employees = sheets.get_all_employees()
    total = len(employees)
    lines = [f"👥 *Барлық қызметкерлер: {total}*\n"]
    for emp in employees[:50]:
        dept = emp.get('department', '')
        dept_str = f" [{dept}]" if dept and dept != 'Белгісіз' else ''
        lines.append(f"• {emp['name']}{dept_str} — `{emp['chat_id']}`")
    if total > 50:
        lines.append(f"\n_...және тағы {total - 50} адам_")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(config.ADMIN_CHAT_ID):
        return
    text = (
        "🤖 *Жалақы бот — командалар*\n\n"
        "/send [ай] — рассылка\n"
        "/retry [ай] — повтор неудачным\n"
        "/status [ай] — статистика за месяц\n"
        "/dept [ай] — статистика по отделам\n"
        "/complaints [ай] — список риза емес\n"
        "/stats — все месяцы\n"
        "/employees — список сотрудников\n"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


def main():
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('send', cmd_send))
    app.add_handler(CommandHandler('retry', cmd_retry))
    app.add_handler(CommandHandler('status', cmd_status))
    app.add_handler(CommandHandler('dept', cmd_dept_status))
    app.add_handler(CommandHandler('complaints', cmd_complaints))
    app.add_handler(CommandHandler('stats', cmd_stats_all))
    app.add_handler(CommandHandler('employees', cmd_employees))
    app.add_handler(CommandHandler('help', cmd_help))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r'^feedback\|'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот іске қосылды ✅")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
