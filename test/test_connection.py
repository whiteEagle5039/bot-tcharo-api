import mysql.connector
from config import DB_CONFIG

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    print("✅ Connexion réussie à la base de données !")
    conn.close()
except Exception as e:
    print("❌ Erreur :", e)
