# 🤖 Жалақы бот — Инструкция по запуску

## Структура проекта

```
salary_bot/
├── bot.py           — главный файл, хендлеры команд
├── sheets.py        — работа с Google Sheets
├── sender.py        — отправка сообщений с rate limit
├── config.py        — настройки из .env
├── requirements.txt — зависимости Python
├── railway.toml     — конфиг для Railway
├── .env.example     — пример переменных окружения
└── .gitignore
```

---

## Шаг 1 — Google Service Account (доступ к таблице)

### 1.1 Создать проект в Google Cloud
1. Идёте на https://console.cloud.google.com
2. Нажимаете "Select a project" → "New Project"
3. Называете как угодно, например `salary-bot`

### 1.2 Включить Google Sheets API
1. В меню слева: "APIs & Services" → "Library"
2. Ищете "Google Sheets API" → Enable
3. Ищете "Google Drive API" → Enable

### 1.3 Создать Service Account
1. "APIs & Services" → "Credentials"
2. "+ CREATE CREDENTIALS" → "Service account"
3. Имя: `salary-bot`, нажимаете Create
4. Роль: "Editor" → Continue → Done

### 1.4 Скачать credentials.json
1. Кликаете на созданный Service Account
2. Вкладка "Keys" → "Add Key" → "Create new key"
3. Формат: JSON → Create
4. Скачается файл — переименуйте в `credentials.json`
5. Положите в папку `salary_bot/`

### 1.5 Дать доступ к таблице
1. Открываете ваш Google Sheet
2. Кнопка "Поделиться"
3. Вставляете email из credentials.json (поле `client_email`)
   Выглядит как: `salary-bot@your-project.iam.gserviceaccount.com`
4. Роль: "Редактор" → Отправить

---

## Шаг 2 — Настройка .env

Скопируйте `.env.example` в `.env`:
```bash
cp .env.example .env
```

Заполните значения:

```env
BOT_TOKEN=7959733134:AAG5IF5KqpCfBYFek7HiwJrLyv7J8PrykC0

# Ваш chat_id узнать: напишите @userinfobot в Telegram
ADMIN_CHAT_ID=ваш_chat_id

# Chat ID финансиста
FINANCE_CHAT_ID=chat_id_финансиста

# ID таблицы из URL:
# https://docs.google.com/spreadsheets/d/ВОТ_ЭТА_ЧАСТЬ/edit
SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms

GOOGLE_CREDS_FILE=credentials.json
```

---

## Шаг 3 — Деплой на Railway (бесплатно)

### 3.1 Создать аккаунт
1. Идёте на https://railway.app
2. Регистрируетесь через GitHub (нужен аккаунт GitHub)

### 3.2 Загрузить код на GitHub
```bash
# В папке salary_bot:
git init
git add .
git commit -m "Initial commit"

# Создайте репозиторий на github.com (кнопка New repository)
git remote add origin https://github.com/ВАШ_НИК/salary-bot.git
git push -u origin main
```

**ВАЖНО:** убедитесь что `.gitignore` включает `.env` и `credentials.json`
— они не должны попасть в GitHub!

### 3.3 Создать проект на Railway
1. На railway.app → "New Project"
2. "Deploy from GitHub repo" → выбираете ваш репозиторий
3. Railway автоматически определит Python

### 3.4 Добавить переменные окружения
1. В Railway → ваш проект → вкладка "Variables"
2. Добавляете все переменные из `.env`:
   - `BOT_TOKEN`
   - `ADMIN_CHAT_ID`
   - `FINANCE_CHAT_ID`
   - `SHEET_ID`
   - `GOOGLE_CREDS_FILE` = `credentials.json`

### 3.5 Загрузить credentials.json на Railway
Так как файл нельзя коммитить в git, добавляем содержимое как переменную:

1. Открываете `credentials.json` в текстовом редакторе
2. Копируете всё содержимое
3. В Railway Variables добавляете:
   - Ключ: `GOOGLE_CREDENTIALS_JSON`
   - Значение: вставляете JSON

4. Изменяете `config.py` — добавляете в конец `__init__`:
```python
# Если credentials переданы как переменная окружения
import json
creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
if creds_json:
    with open('credentials.json', 'w') as f:
        f.write(creds_json)
```

Или используйте скрипт `startup.sh`:
```bash
echo $GOOGLE_CREDENTIALS_JSON > credentials.json
python bot.py
```

И в `railway.toml` измените:
```toml
startCommand = "bash startup.sh"
```

### 3.6 Деплой
Railway автоматически задеплоит при каждом `git push`.
Смотрите логи в вкладке "Deployments".

---

## Шаг 4 — Локальный запуск (для тестирования)

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить
python bot.py
```

---

## Использование бота

### Команды для администратора

| Команда | Что делает |
|---------|-----------|
| `/send Ақпан` | Рассылает зарплату за февраль |
| `/retry Ақпан` | Повтор для тех кому не дошло |
| `/status Ақпан` | Статистика за февраль |
| `/stats` | Статистика по всем месяцам |
| `/employees` | Список всех сотрудников |
| `/help` | Список команд |

### Что происходит при рассылке
1. Бот читает лист с названием месяца из Sheets
2. Находит chat_id и сообщение для каждого
3. Отправляет по 10 сообщений/сек (безопасный лимит)
4. Каждая отправка записывается в лист `SendLog`
5. Если пользователь заблокировал бота — записывает "Бот блокталған" и идёт дальше
6. В конце присылает отчёт: сколько отправлено / ошибок / пропущено

### Структура листа SendLog (создаётся автоматически)
| Chat ID | Аты | Ай | Статус | Қате себебі | Уақыт |
|---------|-----|-----|--------|-------------|-------|
| 123456 | Айгерим | Ақпан | ✅ Жіберілді | | 2025-02-01 |
| 789012 | Берік | Ақпан | ❌ Бот блокталған | Forbidden | 2025-02-01 |

### Структура листа Feedback (создаётся автоматически)
| Chat ID | Аты | Ай | Жауап | Себеп | Уақыт |
|---------|-----|-----|-------|-------|-------|
| 123456 | Айгерим | Ақпан | Ризамын ✅ | | 2025-02-01 |
| 789012 | Берік | Ақпан | Риза емеспін ❌ | Есептеу қате | 2025-02-01 |

---

## Часто задаваемые вопросы

**Q: Нужно ли заново регистрировать сотрудников?**
A: Нет. Chat ID из старой таблицы ChatIDs работает напрямую.

**Q: Что если сотрудник заблокировал бота?**
A: Бот записывает статус "Бот блокталған" и продолжает рассылку. Не падает.

**Q: Можно ли запускать рассылку несколько раз?**
A: Да. Бот проверяет `SendLog` и пропускает тех кому уже отправил ✅.

**Q: Как узнать свой chat_id?**
A: Напишите @userinfobot в Telegram — он пришлёт ваш ID.

**Q: Railway бесплатный?**
A: Да, $5 кредитов в месяц бесплатно. Бот потребляет ~$0.50-1/месяц.

---

## Поддержка

При ошибках смотрите логи в Railway → Deployments → View Logs
Или локально в файле `bot.log`
