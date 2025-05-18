import mysql.connector
from db_config import DB_CONFIG

def get_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"[Erreur] Connexion à la BDD : {err}")
        return None
