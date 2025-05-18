from flask import Flask, request, jsonify
from bot.logic import run_bot
from flask_cors import CORS


app = Flask(__name__)
CORS(app, resources={r"/chat": {"origins": "*"}})  # en dev tu peux ouvrir à tout

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    response = run_bot(data)
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
