from .db import get_connection
from datetime import datetime
import pytz
import json

def get_service_categories_limited(limit=6):
    conn = get_connection()
    if conn is None:
        return {"message": "Erreur de connexion à la base de données."}

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name FROM service_categories LIMIT %s;", (limit,))
        categories = cursor.fetchall()
        return {
            "message": f"Voici les {len(categories)} premières catégories de services disponibles :",
            "categories": categories
        }
    except Exception as e:
        return {"message": f"Erreur SQL : {str(e)}"}
    finally:
        conn.close()

def get_filtered_health_services(patient_id, selected_category_id):
    conn = get_connection()
    if conn is None:
        return {"message": "Erreur de connexion à la base de données."}

    try:
        cursor = conn.cursor(dictionary=True)

        # 1. Récupérer les informations du patient, y compris sa ville et sa région
        cursor.execute("SELECT p.first_name, p.city_id, c.region_id FROM patients p JOIN cities c ON p.city_id = c.id WHERE p.user_id = %s;", (patient_id,))
        patient = cursor.fetchone()

        if not patient:
            return {"message": "Aucun patient trouvé avec cet ID utilisateur."}
        
        patient_first_name = patient['first_name']
        patient_city_id = patient.get("city_id")
        patient_region_id = patient.get("region_id")

        if not patient_city_id:
            return {"message": f" {patient_first_name} ,votre ville n’est pas renseignée, impossible de filtrer les services. Veuillez remplir votre profil ou nous contacter pour plus d'informations."}

        services_to_return = []

        # 2. Chercher les services dans la ville du patient
        cursor.execute("""
            SELECT hs.id, hs.establishment_name AS name, hs.category_id, hs.city_id, ci.name AS city_name
            FROM health_services hs
            JOIN cities ci ON hs.city_id = ci.id
            WHERE hs.category_id = %s AND hs.city_id = %s
            LIMIT 6;
        """, (selected_category_id, patient_city_id))
        services_in_city = cursor.fetchall()

        for service in services_in_city:
            services_to_return.append({
                "id": service['id'],
                "name": service['name'],
                "location_type": "Votre ville",
                "category_id": service['category_id'],
                "city_id": service['city_id'],
                "city_name": service['city_name']
            })

        # 3. Si moins de 6 services trouvés dans la ville, chercher dans la région
        if len(services_to_return) < 6 and patient_region_id:
            # Récupérer toutes les villes de la région (sauf la ville du patient déjà traitée)
            cursor.execute("SELECT id, name FROM cities WHERE region_id = %s AND id != %s;", (patient_region_id, patient_city_id))
            other_city_ids_in_region = [row["id"] for row in cursor.fetchall()]

            if other_city_ids_in_region:
                # Créer une chaîne de placeholders pour la clause IN
                placeholders = ','.join(['%s'] * len(other_city_ids_in_region))
                query_params = [selected_category_id] + other_city_ids_in_region + [6 - len(services_to_return)] # Limiter le nombre de résultats supplémentaires

                cursor.execute(f"""
                    SELECT hs.id, hs.establishment_name AS name, hs.category_id, hs.city_id, ci.name AS city_name
                    FROM health_services hs
                    JOIN cities ci ON hs.city_id = ci.id
                    WHERE hs.category_id = %s AND hs.city_id IN ({placeholders})
                    LIMIT %s;
                """, query_params)
                services_in_region = cursor.fetchall()

                for service in services_in_region:
                    # S'assurer de ne pas dépasser la limite totale de 6 services
                    if len(services_to_return) < 6:
                        services_to_return.append({
                            "id": service['id'],
                            "name": service['name'],
                            "location_type": "Votre région",
                            "category_id": service['category_id'],
                            "city_id": service['city_id'],
                            "city_name": service['city_name']
                        })

        if services_to_return:
            message = f"Voici les services disponibles pour la catégorie sélectionnée, près de {patient_first_name} :"
            return {
                "message": message,
                "services": services_to_return
            }
        else:
            return {
                "message": "Aucun service trouvé pour cette catégorie dans votre ville ni dans votre région.",
                "services": []
            }

    except Exception as e:
        print(f"Erreur dans get_filtered_health_services: {e}")
        return {"message": f"Erreur interne du serveur lors de la récupération des services : {str(e)}", "services": []}
    finally:
        conn.close()

def get_health_service_details(service_id):
    conn = get_connection()
    if conn is None:
        return {"message": "Erreur de connexion à la base de données."}

    try:
        cursor = conn.cursor(dictionary=True)

        # 1. Récupérer les informations de base du service
        cursor.execute("""
            SELECT hs.id, hs.establishment_name, hs.presentation, hs.profile_photo_path,
                   sc.name AS category_name, hs.public_received
            FROM health_services hs
            JOIN service_categories sc ON hs.category_id = sc.id
            WHERE hs.id = %s;
        """, (service_id,))
        service = cursor.fetchone()

        if not service:
            return {"message": "Service de santé non trouvé."}

        # 2. Récupérer les langues du service
        cursor.execute("""
            SELECT l.name
            FROM service_languages sl
            JOIN languages l ON sl.language_id = l.id
            WHERE sl.health_service_id = %s;
        """, (service_id,))
        languages = [lang['name'] for lang in cursor.fetchall()]

        # 3. Récupérer les détails de fonctionnement (modes de consultation, paiement, horaires)
        cursor.execute("""
            SELECT consultation_modes, payment_methods, working_hours
            FROM service_working_details
            WHERE health_service_id = %s;
        """, (service_id,))
        working_details = cursor.fetchone()

        consultation_modes = []
        payment_methods = []
        working_hours_info = "Non spécifié"
        age_required = "Tout âge"

        if working_details:
            # Traitement de consultation_modes
            if working_details.get('consultation_modes'):
                if isinstance(working_details['consultation_modes'], str):
                    try:
                        consultation_modes = json.loads(working_details['consultation_modes'])
                    except json.JSONDecodeError:
                        consultation_modes = ["Erreur de format JSON"]
                else:
                    consultation_modes = working_details['consultation_modes']

            # Traitement de payment_methods
            if working_details.get('payment_methods'):
                if isinstance(working_details['payment_methods'], str):
                    try:
                        payment_methods = json.loads(working_details['payment_methods'])
                    except json.JSONDecodeError:
                        payment_methods = ["Erreur de format JSON"]
                else:
                    payment_methods = working_details['payment_methods']
            
            # Traitement de working_hours
            if working_details.get('working_hours'):
                if isinstance(working_details['working_hours'], str):
                    try:
                        working_hours_info = json.loads(working_details['working_hours'])
                    except json.JSONDecodeError:
                        working_hours_info = "Erreur de format JSON pour les horaires"
                else:
                    working_hours_info = working_details['working_hours']

        # Gérer la "Disponibilité"
        now = datetime.now(pytz.timezone("Africa/Abidjan"))
        current_day_of_week = now.strftime('%A').lower() # ex: 'monday'

        disponibility_message = "Vérifier la disponibilité pour les horaires précis."
        
        # Si working_hours_info est un dictionnaire et contient le jour actuel
        if isinstance(working_hours_info, dict) and current_day_of_week in working_hours_info:
            disponibility_message = f"Disponible aujourd'hui: {working_hours_info[current_day_of_week]}"
        elif isinstance(working_details, dict) and working_details.get('working_hours') and isinstance(working_details['working_hours'], str):
             # Si working_hours était une chaîne JSON non encore parsée pour ce bloc
            try:
                temp_hours = json.loads(working_details['working_hours'])
                if isinstance(temp_hours, dict) and current_day_of_week in temp_hours:
                    disponibility_message = f"Disponible aujourd'hui: {temp_hours[current_day_of_week]}"
            except json.JSONDecodeError:
                pass # Ne rien faire, le message par défaut est déjà là

        return {
            "message": f"Détails du service {service['establishment_name']} :",
            "service_details": {
                "id": service['id'],
                "name": service['establishment_name'],
                "type": service['category_name'],
                "age_required": age_required,
                "languages": languages if languages else ["Non spécifié"],
                "payment_modes": payment_methods if payment_methods else ["Non spécifié"],
                "consultation_modes": consultation_modes if consultation_modes else ["Non spécifié"],
                "availability": disponibility_message,
                "photo_url": service['profile_photo_path'] if service['profile_photo_path'] else None,
                "presentation": service['presentation']
            },
            "next_step": "confirm_appointment"
        }

    except Exception as e:
        print(f"Erreur dans get_health_service_details: {e}")
        # Retourne le message d'erreur SQL complet pour le débogage
        return {"message": f"Erreur interne du serveur lors de la récupération des détails du service : {str(e)}", "service_details": None}
    finally:
        conn.close()

def get_user_details(user_id):
    conn = get_connection()
    if conn is None:
        return {"message": "Erreur de connexion à la base de données."}

    try:
        cursor = conn.cursor(dictionary=True)

        # Récupérer les informations du patient
        cursor.execute("""
            SELECT p.first_name, p.last_name, p.birth_date, p.profession,
                   p.profile_photo_path, c.name AS city_name
            FROM patients p
            LEFT JOIN cities c ON p.city_id = c.id
            WHERE p.user_id = %s;
        """, (user_id,))
        patient_info = cursor.fetchone()

        if not patient_info:
            return {"message": "Patient non trouvé avec cet ID utilisateur."}
        
        # Récupérer les langues parlées par le patient
        cursor.execute("""
            SELECT l.name
            FROM patient_languages pl
            JOIN languages l ON pl.language_id = l.id
            WHERE pl.patient_id = (SELECT id FROM patients WHERE user_id = %s);
        """, (user_id,))
        patient_languages = [lang['name'] for lang in cursor.fetchall()]

        # Formater la date de naissance
        birth_date_formatted = None
        if patient_info['birth_date']:
            # Convertir l'objet date en format "jour mois année"
            # Exemple: 23 août 1998
            # Définir le locale pour les noms de mois si nécessaire, ou utiliser strftime avec %B pour le nom complet
            # Python utilise un comportement par défaut qui peut être anglais, donc forçons un format français si désiré.
            months_fr = {
                1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril', 5: 'mai', 6: 'juin',
                7: 'juillet', 8: 'août', 9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
            }
            birth_date_obj = patient_info['birth_date']
            birth_date_formatted = f"{birth_date_obj.day} {months_fr[birth_date_obj.month]} {birth_date_obj.year}"


        return {
            "message": "Voici vos informations pour la confirmation :",
            "user_details": {
                "user_id": user_id,
                "full_name": f"{patient_info['first_name']} {patient_info['last_name']}",
                "profession": patient_info['profession'] if patient_info['profession'] else "Non spécifié",
                "birth_date": birth_date_formatted,
                "languages": patient_languages if patient_languages else ["Non spécifié"],
                "city_of_residence": patient_info['city_name'] if patient_info['city_name'] else "Non spécifiée",
                "profile_photo_url": patient_info['profile_photo_path'] if patient_info['profile_photo_path'] else None
            },
            "next_step": "confirm_appointment_details_input" # Indique au front-end d'attendre le motif/document
        }

    except Exception as e:
        print(f"Erreur dans get_user_details: {e}")
        return {"message": f"Erreur interne du serveur lors de la récupération des informations utilisateur : {str(e)}", "user_details": None}
    finally:
        conn.close()
# La fonction confirm_appointment sera ajoutée plus tard, elle recevra le motif et le document.
def confirm_appointment(patient_user_id, service_id, reason, consultation_mode, appointment_date, start_time, end_time, attachment_path=None):
    conn = get_connection()
    if conn is None:
        return {"message": "Erreur de connexion à la base de données."}

    try:
        cursor = conn.cursor(dictionary=True)

        # 1. Récupérer l'ID réel du patient à partir de user_id
        cursor.execute("SELECT id FROM patients WHERE user_id = %s;", (patient_user_id,))
        patient = cursor.fetchone()
        if not patient:
            return {"message": "Patient non trouvé."}
        patient_id = patient['id']

        # 2. Récupérer le nom du service pour le message de confirmation
        cursor.execute("SELECT establishment_name FROM health_services WHERE id = %s;", (service_id,))
        service_name = cursor.fetchone()
        if not service_name:
            return {"message": "Service de santé non trouvé."}
        service_name = service_name['establishment_name']

        # Note: Pour l'instant, professional_id et affiliation_id sont NULL car la logique de sélection
        # du professionnel n'est pas encore complètement implémentée. Ils seront ajoutés plus tard.
        # Idéalement, consultation_mode, date, start_time, end_time devraient aussi être dynamiques,
        # venant du front-end après que l'utilisateur ait choisi un créneau.
        # Pour l'instant, on prend des valeurs statiques pour tester la création de l'appointment.

        # 3. Insérer le rendez-vous dans la base de données
        cursor.execute("""
            INSERT INTO appointments (
                patient_id, health_service_id, date, start_time, end_time,
                reason, status, consultation_mode, payment_status, attachment_path,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            patient_id,
            service_id,
            appointment_date, # Date fournie en argument
            start_time,       # Heure de début fournie en argument
            end_time,         # Heure de fin fournie en argument
            reason,
            "pending",        # Statut initial
            consultation_mode, # Mode de consultation fourni en argument
            "unpaid",         # Statut de paiement initial
            attachment_path
        ))
        conn.commit()

        return {
            "message": f"Parfait ! Votre rendez-vous chez {service_name} est en attente de validation. Nous vous contacterons bientôt pour confirmer.",
            "status": "pending",
            "appointment_details": {
                "service_name": service_name,
                "date": appointment_date,
                "start_time": start_time,
                "consultation_mode": consultation_mode,
                "reason": reason
            },
            "next_step": "end_conversation" # Fin de la conversation ou prochaine étape
        }

    except Exception as e:
        conn.rollback() # Annuler la transaction en cas d'erreur
        print(f"Erreur lors de la confirmation du rendez-vous : {e}")
        return {"message": f"Erreur interne du serveur lors de la confirmation du rendez-vous : {str(e)}"}
    finally:
        conn.close()