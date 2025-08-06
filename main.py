import os
import asyncio
import logging
import datetime
import requests

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from fastapi import FastAPI, Request

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
BASECAMP_ACCOUNT_ID = os.getenv('BASECAMP_ACCOUNT_ID')
BASECAMP_ACCESS_TOKEN = os.getenv('BASECAMP_ACCESS_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TEAM = {
    "@Maybeksentorik": ["Ксения Торикина", "Ксения", "Ксения Т."],
    "@lets_getaway": ["Мария Петрова", "Мария", "Мария П."],
    "@Alice_Fedyashova": ["Алиса Федяшова", "Алиса", "Алиса Ф."]
}

active = True
known_tasks = set()
known_comments = set()

app = FastAPI()
application = None

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
    print(f"[DEBUG] get_projects — Status code: {response.status_code}")
    print(f"[DEBUG] get_projects — URL: {url}")
    print(f"[DEBUG] get_projects — Response (first 300): {response.text[:300]}")
    try:
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to parse JSON in get_projects: {e}")
        return []

def get_todolists(project_id):
    url = f"https://3.basecampapi.com/{BASECAMP_ACCOUNT_ID}/buckets/{project_id}/todolists.json"
    headers = {
        "Authorization": f"Bearer {BASECAMP_ACCESS_TOKEN}",
        "User-Agent": "BasecampBot"
    }
    response = requests.get(url, headers=headers)
    print(f"[DEBUG] get_todolists — Status code: {response.status_code}")
    print(f"[DEBUG] get_todolists — URL: {url}")
    print(f"[DEBUG] get_todolists — Response (first 300): {response.text[:300]}")
    try:
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to parse JSON in get_todolists: {e}")
        return []

def get_todos(project_id, todolist_id):
    url = f"https://3.basecampapi.com/{BASECAMP_ACCOUNT_ID}/buckets/{project_id}/todolists/{todolist_id}/todos.json"
    headers = {
        "Authorization": f"Bearer {BASECAMP_ACCESS_TOKEN}",
        "User-Agent": "BasecampBot"
    }
    response = requests.get(url, headers=headers)
    print(f"[DEBUG] get_todos — Status code: {response.status_code}")
    print(f"[DEBUG] get_todos — URL: {url}")
    print(f"[DEBUG] get_todos — Response (first 300): {response.text[:300]}")
    try:
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to parse JSON in get_todos: {e}")
        return []

def get_comments(project_id, todo_id):
    url = f"https://3.basecampapi.com/{BASECAMP_ACCOUNT_ID}/buckets/{project_id}/todos/{todo_id}/comments.json"
    headers = {
        "Authorization": f"Bearer {BASECAMP_ACCESS_TOKEN}",
        "User-Agent": "BasecampBot"
    }
    response = requests.get(url, headers=headers)
    print(f"[DEBUG] get_comments — Status code: {response.status_code}")
    print(f"[DEBUG] get_comments — URL: {url}")
    print(f"[DEBUG] get_comments — Response (first 300): {response.text[:300]}")
    try:
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to parse JSON in get_comments: {e}")
        return []

async def send_message(bot, text):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)

def resolve_mention(name):
    for mention, variants in TEAM.items():
        if name in variants:
            return mention
    return None

async def check_updates(bot):
    if not active:
        return
    now = datetime.datetime.now()
    if not (10 <= now.hour <= 21):
        return

    projects = get_projects()
    for project in projects:
        project_id = project["id"]
        todolists = get_todolists(project_id)
        if not todolists:
            continue
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
                        mention = resolve_mention(name)
                        if mention:
                            message = f"{mention}, обрати внимание: новая задача «{todo_title}» (дедлайн: {due_on})\n{todo_url}"
                            await send_message(bot, message)
                            known_tasks.add(task_identifier)

                comments = get_comments(project_id, todo_id)
                for comment in comments:
                    comment_id = comment["id"]
                    content = comment.get("content", "")
                    if comment_id not in known_comments:
                        for mention, variants in TEAM.items():
                            for name in variants:
                                if name in content:
                                    message = f"{mention}, апдейт в задаче «{todo_title}»\n{todo_url}"
                                    await send_message(bot, message)
                                    known_comments.add(comment_id)
                                    break

async def daily_report(bot):
    message = "🕚 Ежедневный отчёт\n\n"
    task_count = {mention: 0 for mention in TEAM}
    projects = get_projects()
    for project in projects:
        project_id = project["id"]
        todolists = get_todolists(project_id)
        for todolist in todolists:
            todos = get_todos(project_id, todolist["id"])
            for todo in todos:
                assignees = todo.get("assignees", [])
                for assignee in assignees:
                    name = assignee.get("name")
                    mention = resolve_mention(name)
                    if mention:
                        task_count[mention] += 1
    for mention, count in task_count.items():
        message += f"{mention} — {count} задач(и) сегодня\n"
    await send_message(bot, message)

async def task_monitor_loop(bot):
    while True:
        await check_updates(bot)
        await asyncio.sleep(600)

async def daily_report_loop(bot):
    while True:
        now = datetime.datetime.now()
        target = now.replace(hour=11, minute=0, second=0, microsecond=0)
        if now > target:
            target += datetime.timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        await daily_report(bot)

@app.on_event("startup")
async def startup_event():
    global application
    logging.basicConfig(level=logging.INFO)
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    webhook_url = "https://basecamp-bot.onrender.com"
    await application.bot.set_webhook(url=webhook_url)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    await application.initialize()
    await application.start()
    asyncio.create_task(task_monitor_loop(application.bot))
    asyncio.create_task(daily_report_loop(application.bot))

@app.on_event("shutdown")
async def shutdown_event():
    await application.stop()
    await application.shutdown()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active
    active = True
    await update.message.reply_text("✅ Monitoring is ON.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active
    active = False
    await update.message.reply_text("🛑 Monitoring is OFF.")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) >= 3:
        full_name = f"{context.args[0]} {context.args[1]}"
        mention = context.args[2]
        if mention not in TEAM:
            TEAM[mention] = []
        TEAM[mention].append(full_name)
        await update.message.reply_text(f"👤 {full_name} added as {mention}")
    else:
        await update.message.reply_text("Usage: /add Firstname Lastname @nickname")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) >= 2:
        full_name = f"{context.args[0]} {context.args[1]}"
        for mention, names in TEAM.items():
            if full_name in names:
                TEAM[mention].remove(full_name)
                await update.message.reply_text(f"🗑 {full_name} removed.")
                return
        await update.message.reply_text(f"❌ {full_name} not found.")
    else:
        await update.message.reply_text("Usage: /remove Firstname Lastname")

@app.post("/")
async def telegram_webhook(update: Request):
    json_data = await update.json()
    telegram_update = Update.de_json(json_data, application.bot)
    await application.process_update(telegram_update)
    return {"status": "ok"}
