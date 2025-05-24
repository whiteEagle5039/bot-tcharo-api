import requests
from config import ACCESS_TOKEN, PHONE_NUMBER_ID

from bot.logic import run_bot

# Simulation de la base de donnée
context_map = {}

def run_bot_whatsapp(data):
    # 🔍 Extraire infos depuis webhook Meta
    try:
        entry = data["entry"][0]
        message = entry["changes"][0]["value"]["messages"][0]
        wa_id = message["from"]
        text = message["text"]["body"]
    except Exception as e:
        return {"error": f"Format invalide: {str(e)}"}

    # Étape actuelle de l’utilisateur
    context = context_map.get(wa_id, {"step": 1, "user_id": wa_id})

    # Mise à jour du contexte avec l'input utilisateur
    if context["step"] == 1:
        context["selected_category_id"] = text  # à adapter si bouton
    elif context["step"] == 2:
        context["selected_service_id"] = text

    # Appeler la logique commune
    response = run_bot(context)

    # Mémoriser l'étape suivante
    context["step"] = response.get("next_step", 1)
    context_map[wa_id] = context

    # Retourner un texte simple (tu pourras le formater WhatsApp plus tard)
    return {
        "recipient_type": "individual",
        "to": wa_id,
        "type": "text",
        "text": {
            "body": response.get("message", "Erreur inconnue.")
        }
    }

def send_to_whatsapp(payload):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()