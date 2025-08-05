import os
import requests
import datetime
import asyncio
import logging
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASECAMP_ACCOUNT_ID = os.getenv("BASECAMP_ACCOUNT_ID")
BASECAMP_ACCESS_TOKEN = os.getenv("BASECAMP_ACCESS_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

TEAM = {
    "Ксения Торикина": "@Maybeksentorik",
    "Мария Петрова": "@lets_getaway",
    "Алиса Федяшова": "@Alice_Fedyashova"
}

seen_tasks = set()
seen_comments = set()
monitoring_enabled = True

def get_projects():
    url = f"https://3.basecampapi.com/{BASECAMP_ACCOUNT_ID}/projects.json"
    headers = {
        "Authorization": f"Bearer {BASECAMP_ACCESS_TOKEN}",
        "User-Agent": "RedTeamBot (redteam@example.com)"
    }
    response = requests.get(url, headers=headers)
    return response.json()

def get_todolists(project_id):
    url = f"https://3.basecampapi.com/{BASECAMP_ACCOUNT_ID}/buckets/{project_id}/todolists.json"
    headers = {
        "Authorization": f"Bearer {BASECAMP_ACCESS_TOKEN}",
        "User-Agent": "RedTeamBot (redteam@example.com)"
    }
    response = requests.get(url, headers=headers)
    return response.json()

def get_todos(project_id, todolist_id):
    url = f"https://3.basecampapi.com/{BASECAMP_ACCOUNT_ID}/buckets/{project_id}/todolists/{todolist_id}/todos.json"
    headers = {
        "Authorization": f"Bearer {BASECAMP_ACCESS_TOKEN}",
        "User-Agent": "RedTeamBot (redteam@example.com)"
    }
    response = requests.get(url, headers=headers)
    return response.json()

def get_comments(project_id, task_id):
    url = f"https://3.basecampapi.com/{BASECAMP_ACCOUNT_ID}/buckets/{project_id}/todos/{task_id}/comments.json"
    headers = {
        "Authorization": f"Bearer {BASECAMP_ACCESS_TOKEN}",
        "User-Agent": "RedTeamBot (redteam@example.com)"
    }
    response = requests.get(url, headers=headers)
    return response.json()

async def send_message(text):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)

async def check_new_tasks_and_comments():
    global seen_tasks, seen_comments, monitoring_enabled
    if not monitoring_enabled:
        return

    for project in get_projects():
        project_id = project["id"]
        todolists = get_todolists(project_id)
        for todolist in todolists:
            todos = get_todos(project_id, todolist["id"])
            for task in todos:
                task_id = task["id"]
                task_url = task["app_url"]
                task_title = task["title"]
                due_on = task.get("due_on", "Не указан")
                assignees = task.get("assignees", [])

                if task_id not in seen_tasks:
                    for person in assignees:
                        name = person.get("name", "")
                        if name in TEAM:
                            mention = TEAM[name]
                            message = f"{mention}, новая задача в проекте:\n📌 *{task_title}*\n🗓 {due_on}\n🔗 {task_url}"
                            await send_message(message)
                    seen_tasks.add(task_id)

                comments = get_comments(project_id, task_id)
                for comment in comments:
                    comment_id = comment["id"]
                    commenter = comment["creator"]["name"]
                    content = comment["content"]
                    created_at = comment["created_at"]

                    if comment_id not in seen_comments:
                        for name, mention in TEAM.items():
                            if name in content:
                                message = f"{mention}, апдейт в задаче *{task_title}*\n🔗 {task_url}"
                                await send_message(message)
                        seen_comments.add(comment_id)

async def morning_report():
    today = datetime.date.today().isoformat()
    message = "Привет, красная команда!\nСегодня у нас:"
    for project in get_projects():
        project_id = project["id"]
        todolists = get_todolists(project_id)
        for todolist in todolists:
            todos = get_todos(project_id, todolist["id"])
            for name, mention in TEAM.items():
                user_tasks = [t for t in todos if any(p["name"] == name and t.get("due_on") == today for p in t.get("assignees", []))]
                if user_tasks:
                    message += f"\n\n*{name}*\nУ тебя сегодня {len(user_tasks)} задач:"
                    for i, task in enumerate(user_tasks, 1):
                        message += f"\n{i}. {task['app_url']}"
    await send_message(message)

async def task_monitor_loop():
    while True:
        now = datetime.datetime.now().time()
        if datetime.time(10, 0) <= now <= datetime.time(21, 0):
            await check_new_tasks_and_comments()
        await asyncio.sleep(600)

async def daily_report_loop():
    while True:
        now = datetime.datetime.now()
        if now.hour == 11 and now.minute == 0:
            await morning_report()
        await asyncio.sleep(60)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitoring_enabled
    monitoring_enabled = True
    await update.message.reply_text("🔴 Мониторинг включен!")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitoring_enabled
    monitoring_enabled = False
    await update.message.reply_text("🟡 Мониторинг приостановлен.")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3:
        await update.message.reply_text("Используй: /add Имя Фамилия @ник")
        return
    full_name = f"{context.args[0]} {context.args[1]}"
    mention = context.args[2]
    TEAM[full_name] = mention
    await update.message.reply_text(f"✅ Добавлен: {full_name} ({mention})")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Используй: /remove Имя Фамилия")
        return
    full_name = f"{context.args[0]} {context.args[1]}"
    if full_name in TEAM:
        del TEAM[full_name]
        await update.message.reply_text(f"🗑 Удалён: {full_name}")
    else:
        await update.message.reply_text(f"Не найден: {full_name}")

async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("remove", remove_command))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    await asyncio.gather(
        task_monitor_loop(),
        daily_report_loop()
    )

    await app.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())