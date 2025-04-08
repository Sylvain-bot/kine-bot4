import os
import json
import gspread
import logging
from flask import Flask, request
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from openai import OpenAI
from pprint import pformat

# ✅ Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 📌 Flask app
app = Flask(__name__)

# 🔐 Tokens
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# 🤖 OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# 📊 Google Sheets
def get_sheet_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    with open("google-creds.json") as f:
        creds_dict = json.load(f)

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client_gs = gspread.authorize(creds)
    sheet = client_gs.open("Patients").sheet1
    return sheet.get_all_records()

# 🔍 Recherche du patient
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

# 🧠 Génération de réponse GPT
def generate_response(contexte_patient, question):
    prompt = f"""Voici le contexte d’un patient en rééducation :
{contexte_patient}

Le patient pose la question suivante :
{question}

Réponds de manière professionnelle, bienveillante et claire. Tu es un assistant kinésithérapeute."""

    chat_completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return chat_completion.choices[0].message.content

# 🤖 Commande /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("➡️ /start appelé")
    args = context.args
    if args:
        logger.info(f"🆔 Argument reçu : {args[0]}")
        context.user_data["patient_input"] = args[0].lower()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Bonjour 👋 Je suis votre assistant kiné. Posez-moi une question ou parlez-moi de vos douleurs."
    )

# 🤖 Message libre
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info("➡️ Entrée dans handle_message")
        logger.info(f"📩 Message reçu : {update.message.text}")

        user_input = update.message.text.strip()
        patient_input = context.user_data.get("patient_input", user_input)
        logger.info(f"🔍 patient_input = {patient_input}")

        patient = find_patient(patient_input)
        logger.info(f"🔍 patient trouvé ? {patient is not None}")

        if patient:
            contexte = (
                f"Prénom : {patient.get('prenom', 'Inconnu')}\n"
                f"Exercice du jour : {patient.get('exercice_du_jour', 'Non spécifié')}\n"
                f"Remarques : {patient.get('remarques', 'Aucune')}"
            )
            logger.info("🧠 Envoi à OpenAI...")
            response = generate_response(contexte, user_input)
        else:
            response = (
                "Je ne trouve pas vos informations. Veuillez vérifier votre prénom ou ID, "
                "ou contacter directement votre kinésithérapeute."
            )

        logger.info(f"💬 Réponse envoyée : {response}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

    except Exception as e:
        logger.error(f"❌ Erreur : {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Une erreur est survenue. Merci de réessayer plus tard."
        )

# 🤖 Application Telegram
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# 🌍 Webhook route pour Telegram
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        logger.info("🔥 Webhook reçu")
        logger.info("📨 Données reçues :\n%s", pformat(data))
        update = Update.de_json(data, application.bot)
        application.update_queue.put_nowait(update)
        return "OK"
    except Exception as e:
        logger.error(f"❌ Erreur dans webhook : {e}")
        return "Erreur", 500

# ▶️ Démarrage local
if __name__ == "__main__":
    logger.info("✅ Lancement du bot en mode webhook intégré")
    application.run_webhook(
        listen="0.0.0.0",
        port=10000,
        webhook_url="https://kine-bot4.onrender.com/webhook"
    )
