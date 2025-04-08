import os
import json
import gspread
import logging
import asyncio
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

# ✅ Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🌐 Flask app
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

# 🧠 Générer réponse GPT
def generate_response(contexte_patient, question):
    prompt = f"""Voici le contexte d’un patient en rééducation :
{contexte_patient}

Le patient pose la question suivante :
{question}

Réponds de manière professionnelle, bienveillante, claire, et tutoie le patient. Tu es un assistant kinésithérapeute."""

    chat_completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return chat_completion.choices[0].message.content

# ▶️ /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("➡️ /start appelé")
    args = context.args
    if args:
        logger.info(f"🆔 Argument reçu : {args[0]}")
        context.user_data["patient_input"] = args[0].lower()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "👋 Salut et bienvenue dans ton assistant kiné virtuel !\n\n"
            "Tu peux me poser une question à tout moment 🤔\n"
            "Ou taper la commande /exercice pour recevoir ton exercice du jour 🧘‍♂️\n\n"
            "Je suis là pour t’accompagner dans ta rééducation 💪"
        )
    )

# ▶️ /exercice
async def exercice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info("📥 Commande /exercice reçue")

        patient_input = context.user_data.get("patient_input")
        if not patient_input:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Tu dois d'abord lancer /start avec ton prénom. Exemple : /start?prenom=alice"
            )
            return

        patient = find_patient(patient_input)
        if patient:
            exercice = patient.get("exercice_du_jour", "Non spécifié")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"🧘 Ton exercice du jour :\n\n{exercice}"
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Je ne retrouve pas tes infos. Tu es sûr d'avoir bien écrit ton prénom ?"
            )
    except Exception as e:
        logger.error(f"❌ Erreur dans /exercice : {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Une erreur est survenue. Essaie encore ou contacte ton kiné."
        )

# ▶️ Message utilisateur libre
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
                "Je ne trouve pas tes informations. Vérifie bien ton prénom ou contacte ton kiné."
            )

        logger.info(f"💬 Réponse envoyée : {response}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

    except Exception as e:
        logger.error(f"❌ Erreur dans handle_message : {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Une erreur est survenue. Merci de réessayer plus tard."
        )

# 🤖 Application Telegram
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("exercice", exercice))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# 🌍 Route Webhook
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

# ▶️ Lancement serveur + démarrage bot Telegram
if __name__ == "__main__":
    logger.info("✅ Initialisation du bot et lancement Flask")

    async def start_bot():
        await application.initialize()
        await application.start()
        logger.info("✅ Bot Telegram démarré et prêt")

    asyncio.run(start_bot())

    app.run(host="0.0.0.0", port=10000)
