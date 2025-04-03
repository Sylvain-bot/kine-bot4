import os
import json
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from sheets_helper import find_patient
from openai_helper import generate_response
import nest_asyncio
import asyncio

nest_asyncio.apply()

TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

app = Flask(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bonjour 👋 Je suis votre assistant kiné. Envoyez-moi votre prénom ou ID patient.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    chat_id = update.message.chat.id
    print(f"📩 [{chat_id}] Message reçu : {user_input}")

    patient = find_patient(user_input)

    if patient:
        contexte = (
            f"Prénom : {patient['prenom']}\n"
            f"Exercice du jour : {patient['exercice_du_jour']}\n"
            f"Remarques : {patient['remarques']}"
        )
        response = generate_response(contexte, user_input)
    else:
        response = (
            "Je ne trouve pas vos informations dans la base de données. "
            "Merci de contacter directement votre kinésithérapeute."
        )

    await update.message.reply_text(response)

async def setup_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    return application

@app.route("/webhook", methods=["POST"])
def webhook():
    application = app.config.get("application")
    if application:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run(application.process_update(update))
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "Bot is live ✅"

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    app.config["application"] = loop.run_until_complete(setup_bot())
    print("✅ Bot démarré en mode Webhook.")
    app.run(host="0.0.0.0", port=10000)