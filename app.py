from flask import Flask, request, jsonify
from bot.logic import run_bot
from bot.logic_meta import run_bot_whatsapp, send_to_whatsapp
from bot.logic2 import get_service_categories_limited, get_filtered_health_services, get_health_service_details, get_user_details, confirm_appointment
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
# Mettez à jour la configuration CORS pour toutes les routes nécessaires
CORS(app, resources={
    r"/chat": {"origins": "*"},
    r"/categories": {"origins": "*"},
    r"/services": {"origins": "*", "methods": ["POST"]},
    r"/service_details": {"origins": "*", "methods": ["POST"]},
    r"/user_details": {"origins": "*", "methods": ["POST"]}, # Nouvelle route
    r"/confirm_appointment": {"origins": "*", "methods": ["POST"]} # Nouvelle route
})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    response = run_bot(data)
    return jsonify(response)

@app.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    incoming = request.get_json()
    message_payload = run_bot_whatsapp(incoming)
    result = send_to_whatsapp(message_payload)
    return jsonify({"status": "sent", "whatsapp_response": result})

@app.route('/categories', methods=['GET'])
def get_categories():
    response = get_service_categories_limited()
    return jsonify(response)

@app.route('/services', methods=['POST'])
def get_services():
    data = request.get_json()

    user_id = data.get('user_id')
    category_id = data.get('category_id')

    if user_id is None:
        return jsonify({"message": "Paramètre 'user_id' manquant dans le corps de la requête."}), 400
    if category_id is None:
        return jsonify({"message": "Paramètre 'category_id' manquant dans le corps de la requête."}), 400

    try:
        user_id = int(user_id)
        category_id = int(category_id)
    except ValueError:
        return jsonify({"message": "Les paramètres 'user_id' et 'category_id' doivent être des nombres entiers."}), 400

    response = get_filtered_health_services(user_id, category_id)
    return jsonify(response)

@app.route('/service_details', methods=['POST'])
def get_service_details():
    data = request.get_json()
    service_id = data.get('service_id')

    if service_id is None:
        return jsonify({"message": "Paramètre 'service_id' manquant dans le corps de la requête."}), 400

    try:
        service_id = int(service_id)
    except ValueError:
        return jsonify({"message": "Le paramètre 'service_id' doit être un nombre entier."}), 400

    response = get_health_service_details(service_id)
    return jsonify(response)

@app.route('/user_details', methods=['POST'])
def user_details_route():
    data = request.get_json()
    user_id = data.get('user_id')

    if user_id is None:
        return jsonify({"message": "Paramètre 'user_id' manquant dans le corps de la requête."}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"message": "Le paramètre 'user_id' doit être un nombre entier."}), 400

    response = get_user_details(user_id)
    return jsonify(response)

@app.route('/confirm_appointment', methods=['POST'])
def confirm_appointment_route():
    data = request.get_json()
    
    patient_user_id = data.get('user_id')
    service_id = data.get('service_id')
    reason = data.get('reason')
    consultation_mode = data.get('consultation_mode')
    appointment_date = data.get('appointment_date') # Format 'YYYY-MM-DD'
    start_time = data.get('start_time')             # Format 'HH:MM:SS'
    end_time = data.get('end_time')                 # Format 'HH:MM:SS'
    attachment_path = data.get('attachment_path') # Optionnel

    # Validations des paramètres nécessaires
    if any(param is None for param in [patient_user_id, service_id, reason, consultation_mode, appointment_date, start_time, end_time]):
        return jsonify({"message": "Paramètres manquants : user_id, service_id, reason, consultation_mode, appointment_date, start_time, end_time sont requis."}), 400

    try:
        patient_user_id = int(patient_user_id)
        service_id = int(service_id)
        # Validation de la date et de l'heure 
        datetime.strptime(appointment_date, '%Y-%m-%d')
        datetime.strptime(start_time, '%H:%M:%S')
        datetime.strptime(end_time, '%H:%M:%S')
    except ValueError as e:
        return jsonify({"message": f"Erreur de format de paramètre : {e}. Assurez-vous que les IDs sont des entiers, la date est YYYY-MM-DD et les heures HH:MM:SS."}), 400

    response = confirm_appointment(
        patient_user_id, service_id, reason, consultation_mode, 
        appointment_date, start_time, end_time, attachment_path
    )
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)