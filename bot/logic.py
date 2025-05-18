from .db import get_connection

def run_bot(data):
    conn = get_connection()
    step = data.get("step", 1)
    user_id = data.get("user_id")

    if conn is None:
        return {"message": "Erreur de connexion à la base de données."}

    try:
        cursor = conn.cursor(dictionary=True)

        # Étape 0 : Vérifier que l'utilisateur existe
        if not user_id:
            return {"message": "Veuillez fournir votre ID utilisateur."}

        cursor.execute("SELECT * FROM patients WHERE user_id = %s;", (user_id,))
        patient = cursor.fetchone()

        if not patient:
            return {"message": "Aucun patient trouvé avec cet ID utilisateur."}

        if step == 1:
            # Afficher les catégories
            cursor.execute("SELECT id, name FROM service_categories LIMIT 3;")
            categories = cursor.fetchall()
            return {
                "message": f"Bonjour {patient['first_name']}, je suis Tchoro, votre assistant pour vous aider à prendre rendez-vous! ! voici les catégories de services disponibles :",
                "options": categories,
                "next_step": 2
            }

        elif step == 2:
            selected_category_id = data.get("selected_category_id")
            if not selected_category_id:
                return {"message": "Veuillez sélectionner une catégorie de service."}

            # Récupérer la ville du patient
            patient_city_id = patient.get("city_id")
            if not patient_city_id:
                return {"message": f" {patient['first_name']} ,votre ville n’est pas renseignée, impossible de filtrer les services.  Veuillez remplir votre profil ou nous contacter pour plus d'informations."}

            # 1. Services dans la ville du patient
            cursor.execute("""
                SELECT id, establishment_name AS name
                FROM health_services
                WHERE category_id = %s AND city_id = %s
                LIMIT 3;
            """, (selected_category_id, patient_city_id))
            services = cursor.fetchall()

            if services:
                return {
                    "message": "Voici les services disponibles dans votre ville :",
                    "options": services,
                    "next_step": 3
                }

            # 2. Si aucun dans la ville → chercher la région
            cursor.execute("SELECT region_id FROM cities WHERE id = %s;", (patient_city_id,))
            city_data = cursor.fetchone()
            if not city_data:
                return {"message": "Impossible d’identifier la région associée à votre ville."}
            
            region_id = city_data['region_id']

            # Chercher toutes les villes de cette région
            cursor.execute("SELECT id FROM cities WHERE region_id = %s;", (region_id,))
            city_ids = [row["id"] for row in cursor.fetchall()]
            
            if not city_ids:
                return {"message": "Aucune autre ville trouvée dans votre région."}

            # Services disponibles dans d'autres villes de la même région
            query = """
                SELECT id, establishment_name AS name
                FROM health_services
                WHERE category_id = %s AND city_id IN (%s)
                LIMIT 3;
            """ % (selected_category_id, ','.join(['%s'] * len(city_ids)))

            cursor.execute(query, city_ids)
            region_services = cursor.fetchall()

            if region_services:
                return {
                    "message": "Aucun service trouvé dans votre ville. Voici ceux disponibles dans votre région :",
                    "options": region_services,
                    "next_step": 3
                }

            return {
                "message": "Aucun service trouvé dans votre ville ni dans votre région.",
                "next_step": 1
            }

        # elif step == 3:
        #     selected_service_id = data.get("selected_service_id")
        #     if not selected_service_id:
        #         return {"message": "Veuillez sélectionner un service pour continuer."}

        #     # 🔍 Étape A — Obtenir les langues du patient
        #     cursor.execute("""
        #         SELECT l.id, l.name
        #         FROM patient_languages pl
        #         JOIN languages l ON pl.language_id = l.id
        #         WHERE pl.patient_id = %s
        #     """, (patient["id"],))
        #     patient_languages = cursor.fetchall()
        #     patient_language_ids = [lang['id'] for lang in patient_languages]

        #     # 🔍 Étape B — Chercher les professionnels affiliés au service
        #     cursor.execute("""
        #         SELECT p.id, p.first_name, p.last_name, p.profile_photo_path
        #         FROM professional_service_affiliations a
        #         JOIN professionals p ON a.professional_id = p.id
        #         WHERE a.health_service_id = %s
        #     """, (selected_service_id,))
        #     professionals = cursor.fetchall()

        #     if not professionals:
        #         return {
        #             "message": "Aucun professionnel n'est affilié à ce service pour le moment.",
        #             "next_step": 1
        #         }

        #     # 🔍 Étape C — Filtrer ceux qui parlent une langue du patient
        #     matched_pros = []
        #     unmatched_pros = []

        #     for pro in professionals:
        #         cursor.execute("""
        #             SELECT l.id, l.name
        #             FROM professional_languages pl
        #             JOIN languages l ON pl.language_id = l.id
        #             WHERE pl.professional_id = %s
        #         """, (pro["id"],))
        #         pro_languages = cursor.fetchall()
        #         pro_language_ids = [lang["id"] for lang in pro_languages]
        #         language_names = [lang["name"] for lang in pro_languages]

        #         speaks_same_language = bool(set(pro_language_ids) & set(patient_language_ids))

        #         # 🔍 Étape D — Vérifier disponibilité actuelle
        #         from datetime import datetime
        #         import pytz

        #         now = datetime.now(pytz.timezone("Africa/Abidjan"))
        #         current_day = now.strftime('%A').lower()
        #         current_time = now.strftime('%H:%M:%S')

        #         cursor.execute("""
        #             SELECT start_time, end_time
        #             FROM appointment_availability
        #             WHERE professional_id = %s AND health_service_id = %s
        #             AND day_of_week = %s
        #             AND valid_from <= CURDATE()
        #             AND (valid_to IS NULL OR valid_to >= CURDATE())
        #         """, (pro["id"], selected_service_id, current_day))

        #         availability = cursor.fetchone()
        #         if availability:
        #             is_available_now = availability["start_time"] <= current_time <= availability["end_time"]
        #         else:
        #             is_available_now = False

        #         pro_data = {
        #             "id": pro["id"],
        #             "name": f"{pro['first_name']} {pro['last_name']}",
        #             "photo": pro["profile_photo_path"],
        #             "available_now": is_available_now,
        #             "availability": availability if availability else None,
        #             "languages": language_names
        #         }

        #         if speaks_same_language:
        #             matched_pros.append(pro_data)
        #         else:
        #             unmatched_pros.append(pro_data)

        #     # 🎯 Réponse personnalisée
        #     if matched_pros:
        #         return {
        #             "message": "Voici les professionnels qui parlent votre langue :",
        #             "professionals": matched_pros,
        #             "next_step": "end"
        #         }
        #     elif unmatched_pros:
        #         return {
        #             "message": "Aucun professionnel ne parle votre langue, mais voici ceux disponibles avec leurs langues :",
        #             "professionals": unmatched_pros,
        #             "next_step": "end"
        #         }
        #     else:
        #         return {
        #             "message": "Aucun professionnel disponible pour ce service actuellement.",
        #             "next_step": 1
        #         }
       
        elif step == 3:
            selected_service_id = data.get("selected_service_id")
            if not selected_service_id:
                return {"message": "Veuillez sélectionner un service pour continuer."}

            # Récupérer le service
            cursor.execute("SELECT establishment_name FROM health_services WHERE id = %s;", (selected_service_id,))
            service = cursor.fetchone()

            if not service:
                return {"message": "Service non trouvé."}

            # 🕒 Définir date et horaire (test statique pour l’instant)
            from datetime import datetime, timedelta
            today = datetime.today().strftime('%Y-%m-%d')
            start_time = "09:00:00"
            end_time = "10:00:00"
            consultation_mode = "in_person"
            reason = "Demande automatique via le bot"

            # 🔧 Créer le rendez-vous
            cursor.execute("""
                INSERT INTO appointments (
                    patient_id, health_service_id, date, start_time, end_time,
                    status, consultation_mode, payment_status, reason, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                patient["id"],
                selected_service_id,
                today,
                start_time,
                end_time,
                "pending",
                consultation_mode,
                "unpaid",
                reason
            ))
            conn.commit()

            return {
                "message": f"Parfait {patient['first_name']} 🎉 ! Votre rendez-vous dans le service {service['establishment_name']} est actuellement en attente de validation. Merci de patienter 🤗",
                "status": "pending",
                # "appointment": {
                #     "service": service['establishment_name'],
                #     "date": today,
                #     "start_time": start_time,
                #     "end_time": end_time,
                #     "consultation_mode": consultation_mode
                # },
                "next_step": "end"
            }

        else:
            return {
                "message": "Étape inconnue. Veuillez recommencer.",
                "next_step": 1
            }

    except Exception as e:
        return {"message": f"Erreur SQL : {str(e)}"}

    finally:
        conn.close()
