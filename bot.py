
import os
import json
import openai
import gspread
import asyncio
from flask import Flask, request
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# 📌 Initialisation de l'application Flask
app = Flask(__name__)

# ✅ Données d'environnement
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_CREDS = os.environ.get("GOOGLE_CREDS")

# 🔐 Configuration des API
openai.api_key = OPENAI_API_KEY

# 🧠 OpenAI : générer une réponse personnalisée
def generate_response(contexte_patient, question):
    prompt = f"""Voici le contexte d’un patient en rééducation :
{contexte}

Le patient pose la question suivante :
{question}

Réponds de manière professionnelle, bienveillante et claire. Tu es un assistant kinésithérapeute."""

    )

    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return completion.choices[0].message["content"]

# 🔍 Lecture Google Sheet
def get_sheet_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_json = json.loads(GOOGLE_CREDS)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Patients").sheet1
    return sheet.get_all_records()

def find_patient(patient_input):
    data = get_sheet_data()
    for row in data:
        if (
            str(row.get("patient_id", "")).lower() == str(patient_input).lower()
            or row.get("prenom", "").lower() == str(patient_input).lower()
            or row.get("email", "").lower() == str(patient_input).lower()
        ):
            return row
    return None

# 🌐 Telegram bot
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if args:
        context.user_data["patient_input"] = args[0].lower()
    await update.message.reply_text(
        "Bonjour 👋 Je suis votre assistant kiné. Posez-moi une question ou parlez-moi de vos douleurs."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📩 [{update.effective_user.id}] Message reçu : {update.message.text}")
    user_input = update.message.text.strip()

    patient_input = context.user_data.get("patient_input", user_input)
    patient = find_patient(patient_input)

    if patient:
        contexte = (
            f"Prénom : {patient['prenom']}
"
            f"Exercice du jour : {patient['exercice_du_jour']}
"
            f"Remarques : {patient['remarques']}"
        )
        response = generate_response(contexte, user_input)
    else:
        response = (
            "Je ne trouve pas vos informations. Veuillez vérifier votre prénom ou ID, "
            "ou contacter directement votre kinésithérapeute."
        )

    await update.message.reply_text(response)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# 🌍 Webhook avec Flask
@app.route("/")
def index():
    return "Bot Webhook actif ✅"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(handle_update(update))
    return "OK"

async def handle_update(update: Update):
    await application.initialize()
    await application.process_update(update)

if __name__ == "__main__":
    print("✅ Bot démarré en mode Webhook.")
    app.run(host="0.0.0.0", port=10000)
