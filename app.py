from flask import Flask, request, jsonify
from bot.logic import run_bot
from bot.logic_meta import run_bot_whatsapp, send_to_whatsapp
from flask_cors import CORS


app = Flask(__name__)
CORS(app, resources={r"/chat": {"origins": "*"}})  # en dev tu peux ouvrir à tout

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

if __name__ == '__main__':
    app.run(debug=True)
