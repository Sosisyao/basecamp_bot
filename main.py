import os
import asyncio
import logging
import datetime
import requests

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from fastapi import FastAPI

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
BASECAMP_ACCOUNT_ID = os.getenv('BASECAMP_ACCOUNT_ID')
BASECAMP_ACCESS_TOKEN = os.getenv('BASECAMP_ACCESS_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TEAM = {
    "Ксения Торикина": "@Maybeksentorik",
    "Мария Петрова": "@lets_getaway",
    "Алиса Федяшова": "@Alice_Fedyashova",
}

active = True
known_tasks = set()
known_comments = set()

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok"}

def get_projects():
    url = f"https://3.basecampapi.com/{BASECAMP_ACCOUNT_ID}/projects.json"
    headers = {
        "Authorization": f"Bearer {BASECAMP_ACCESS_TOKEN}",
        "User-Agent": "BasecampBot"
    }
    response = requests.get(url, headers=headers)
    return response.json()

def get_todolists(project_id):
    url = f"https://3.basecampapi.com/{BASECAMP_ACCOUNT_ID}/buckets/{project_id}/todolists.json"
    headers = {
        "Authorization": f"Bearer {BASECAMP_ACCESS_TOKEN}",
        "User-Agent": "BasecampBot"
    }
    response = requests.get(url, headers=headers)
    return response.json()

def get_todos(project_id, todolist_id):
    url = f"https://3.basecampapi.com/{BASECAMP_ACCOUNT_ID}/buckets/{project_id}/todolists/{todolist_id}/todos.json"
    headers = {
        "Authorization": f"Bearer {BASECAMP_ACCESS_TOKEN}",
        "User-Agent": "BasecampBot"
    }
    response = requests.get(url, headers=headers)
    return response.json()

def get_comments(project_id, todo_id):
    url = f"https://3.basecampapi.com/{BASECAMP_ACCOUNT_ID}/buckets/{project_id}/todos/{todo_id}/comments.json"
    headers = {
        "Authorization": f"Bearer {BASECAMP_ACCESS_TOKEN}",
        "User-Agent": "BasecampBot"
    }
    response = requests.get(url, headers=headers)
    return response.json()

async def send_message(context: ContextTypes.DEFAULT_TYPE, text):
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)

async def check_updates(context: ContextTypes.DEFAULT_TYPE):
    if not active:
        return

    now = datetime.datetime.now()
    if not (10 <= now.hour <= 21):
        return

    projects = get_projects()
    for project in projects:
        project_id = project["id"]
        todolists = get_todolists(project_id)

        for todolist in todolists:
            todos = get_todos(project_id, todolist["id"])

            for todo in todos:
                todo_id = todo["id"]
                todo_url = todo["app_url"]
                todo_title = todo["title"]
                assignees = todo.get("assignees", [])
                due_on = todo.get("due_on", "Не указан")

                task_identifier = f"{project_id}-{todo_id}"
                if task_identifier not in known_tasks:
                    for assignee in assignees:
                        name = assignee.get("name")
                        if name in TEAM:
                            mention = TEAM[name]
                            message = f"{mention}, обрати внимание: новая задача «{todo_title}» (дедлайн: {due_on})\n{todo_url}"
                            await send_message(context, message)
                            known_tasks.add(task_identifier)

                comments = get_comments(project_id, todo_id)
                for comment in comments:
                    comment_id = comment["id"]
                    commenter = comment.get("creator", {}).get("name", "")
                    content = comment.get("content", "")
                    if comment_id not in known_comments:
                        for name, mention in TEAM.items():
                            if name in content:
                                message = f"{mention}, апдейт в задаче «{todo_title}»\n{todo_url}"
                                await send_message(context, message)
                                known_comments.add(comment_id)

async def daily_report(context: ContextTypes.DEFAULT_TYPE):
    message = "🕚 Ежедневный отчёт\n\n"
    projects = get_projects()
    task_count = {name: 0 for name in TEAM}

    for project in projects:
        project_id = project["id"]
        todolists = get_todolists(project_id)

        for todolist in todolists:
            todos = get_todos(project_id, todolist["id"])
            for todo in todos:
                assignees = todo.get("assignees", [])
                for assignee in assignees:
                    name = assignee.get("name")
                    if name in TEAM:
                        task_count[name] += 1

    for name, count in task_count.items():
        mention = TEAM[name]
        message += f"{mention} — {count} задач(и) сегодня\n"

    await send_message(context, message)

async def task_monitor_loop(application):
    while True:
        await check_updates(application.bot)
        await asyncio.sleep(600)

async def daily_report_loop(application):
    while True:
        now = datetime.datetime.now()
        target = now.replace(hour=11, minute=0, second=0, microsecond=0)
        if now > target:
            target += datetime.timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        await daily_report(application.bot)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active
    active = True
    await update.message.reply_text("✅ Мониторинг включён.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active
    active = False
    await update.message.reply_text("🛑 Мониторинг остановлен.")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) >= 3:
        full_name = f"{context.args[0]} {context.args[1]}"
        mention = context.args[2]
        TEAM[full_name] = mention
        await update.message.reply_text(f"👤 Участник {full_name} добавлен как {mention}")
    else:
        await update.message.reply_text("Используй: /добавить Имя Фамилия @ник")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) >= 2:
        full_name = f"{context.args[0]} {context.args[1]}"
        if full_name in TEAM:
            del TEAM[full_name]
            await update.message.reply_text(f"🗑 Участник {full_name} удалён.")
        else:
            await update.message.reply_text(f"❌ Участник {full_name} не найден.")
    else:
        await update.message.reply_text("Используй: /удалить Имя Фамилия")

@app.on_event("startup")
async def startup_event():
    logging.basicConfig(level=logging.INFO)
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("старт", start_command))
    application.add_handler(CommandHandler("стоп", stop_command))
    application.add_handler(CommandHandler("добавить", add_command))
    application.add_handler(CommandHandler("удалить", remove_command))

    await application.initialize()
    await application.start()

    asyncio.create_task(task_monitor_loop(application))
    asyncio.create_task(daily_report_loop(application))

    await application.updater.start_polling()
    await application.updater.idle()
