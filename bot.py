import os
import json
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from sheets_helper import find_patient
from openai_helper import generate_response

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = Flask(__name__)
application = ApplicationBuilder().token(TOKEN).build()


# === Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Bonjour ! Je suis ton assistant kiné virtuel. Pose-moi une question ou dis-moi ton prénom pour retrouver tes exercices.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    user_id = update.effective_user.id
    print(f"📩 [{user_id}] Message reçu : {user_input}")

    patient = find_patient(user_input)

    if patient:
        contexte = (
            f"Prénom : {patient['prenom']}\n"
            f"Exercice du jour : {patient['exercice_du_jour']}\n"
            f"Remarques : {patient['remarques']}"
        )
        response = generate_response(contexte, "Peux-tu me rappeler mes consignes ?")
    else:
        response = generate_response("Pas d'infos patient", user_input)

    await update.message.reply_text(response)


# === Routes Flask ===

@app.route('/')
def home():
    return '🤖 Webhook du bot Telegram est en ligne !'

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run(handle_update(update))
        return "ok", 200


async def handle_update(update: Update):
    if not application.ready:
        await application.initialize()
    await application.process_update(update)


# === Lancement du bot en Webhook ===

if __name__ == '__main__':
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot démarré en mode Webhook.")
    app.run(host="0.0.0.0", port=10000)
