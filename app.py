from flask import Flask, redirect, request, session, url_for, render_template
from dotenv import load_dotenv
import os
import requests
from google_auth_oauthlib.flow import Flow
import pathlib
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow



import json

def sauvegarder_profil_utilisateur(email, profil):
    with open("profils.json", "r+") as f:
        data = json.load(f)
        data[email] = profil
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

def charger_profil_utilisateur(email):
    if not os.path.exists("profils.json"):
        return None
    with open("profils.json", "r") as f:
        data = json.load(f)
        return data.get(email)




load_dotenv()
app = Flask(__name__)
app.secret_key = "yunes_secret_key"  # change en prod

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # pour le local

# === Configuration ===
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:5000/callback"

SCOPES = [
    "https://www.googleapis.com/auth/business.manage",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

# === Routes ===

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/callback")
def callback():
    print("➡️ URL callback appelée :", request.url)  # ajoute cette ligne

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials

    # 💾 Enregistrement des tokens dans la session
    session["token"] = credentials.token
    session["refresh_token"] = credentials.refresh_token
    session["token_uri"] = credentials.token_uri
    session["client_id"] = credentials.client_id
    session["client_secret"] = credentials.client_secret

    # 🔐 Récupération de l’email utilisateur
    user_info = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"}
    ).json()
    session["user_email"] = user_info["email"]

    # 📁 Chargement du profil existant s’il y en a un
    profil = charger_profil_utilisateur(user_info["email"])
    if profil:
        session["profil_etablissement"] = profil

    # ✅ Redirection vers /dashboard une fois les infos bien stockées
    return redirect(url_for("dashboard"))


@app.route("/login")
def login():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')
    session["flow_state"] = state
    print("👉 redirect_uri utilisé :", flow.redirect_uri)
    return redirect(auth_url)

"""
# Fonction pour récupérer les avis depuis l'API Google My Business
 
def get_reviews_data(token, refresh_token, token_uri, client_id, client_secret):
    # Authentification
    credentials = Credentials(
        token=token,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret
    )

    # 🔐 Étape 1 : récupérer le compte via l’API Account Management
    account_service = build("mybusinessaccountmanagement", "v1", credentials=credentials)
    accounts = account_service.accounts().list().execute()
    if "accounts" not in accounts or len(accounts["accounts"]) == 0:
        return [], []
    account_name = accounts["accounts"][0]["name"]  # ex: "accounts/123456789"

    # 🏢 Étape 2 : récupérer les établissements via l’API Business Info
    info_service = build("mybusinessbusinessinformation", "v1", credentials=credentials)
    locations_response = info_service.accounts().locations().list(parent=account_name).execute()
    locations = locations_response.get("locations", [])
    if not locations:
        return [], []

    first_location = locations[0]
    location_name = first_location["name"]  # ex: "accounts/123456789/locations/987654321"

    # ✨ Étape 3 : récupérer les avis via l’API My Business (v4)
    reviews_service = build("mybusiness", "v4", credentials=credentials)
    reviews_response = reviews_service.accounts().locations().reviews().list(parent=location_name).execute()
    reviews = reviews_response.get("reviews", [])

    # 🧽 Formatage pour dashboard.html
    avis_formatés = []
    for r in reviews:
        avis_formatés.append({
            "reviewer": {
                "displayName": r.get("reviewer", {}).get("displayName", "Client"),
                "profilePhotoUrl": r.get("reviewer", {}).get("profilePhotoUrl", "https://i.pravatar.cc/50")
            },
            "starRating": r.get("starRating", "UNSPECIFIED"),
            "comment": r.get("comment", ""),
            "createTime": r.get("createTime", "")
        })

    return [first_location], avis_formatés

"""

def get_reviews_data(token, refresh_token, token_uri, client_id, client_secret):
    try:
        # Authentification
        credentials = Credentials(
            token=token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret
        )

        # Étape 1 : récupérer le compte
        account_service = build("mybusinessaccountmanagement", "v1", credentials=credentials)
        accounts = account_service.accounts().list().execute()
        if "accounts" not in accounts or not accounts["accounts"]:
            raise Exception("Aucun compte trouvé.")

        account_name = accounts["accounts"][0]["name"]  # "accounts/123..."

        # Étape 2 : récupérer les établissements
        info_service = build("mybusinessbusinessinformation", "v1", credentials=credentials)
        locations_response = info_service.accounts().locations().list(parent=account_name).execute()
        locations = locations_response.get("locations", [])
        if not locations:
            raise Exception("Aucun établissement trouvé.")

        first_location = locations[0]
        location_name = first_location["name"]

        # Étape 3 : récupérer les avis
        reviews_service = build("mybusiness", "v4", credentials=credentials)
        reviews_response = reviews_service.accounts().locations().reviews().list(parent=location_name).execute()
        reviews = reviews_response.get("reviews", [])

        # Formatage
        avis_formatés = []
        for r in reviews:
            avis_formatés.append({
                "reviewer": {
                    "displayName": r.get("reviewer", {}).get("displayName", "Client"),
                    "profilePhotoUrl": r.get("reviewer", {}).get("profilePhotoUrl", "https://i.pravatar.cc/50")
                },
                "starRating": r.get("starRating", "UNSPECIFIED"),
                "comment": r.get("comment", ""),
                "createTime": r.get("createTime", "")
            })

        return [first_location], avis_formatés

    except Exception as e:
        print("⚠️ Erreur API Google : fallback en mode démo :", e)

        # MODE DÉMO — Fallback avec avis simulés
        locations = [{
            'title': 'Établissement Démo',
            'locationName': '123 Rue de l’Exemple, Paris',
            'name': 'accounts/000000000/locations/000000000'
        }]
        reviews = [
            {
                'reviewer': {'displayName': 'Alice', 'profilePhotoUrl': 'https://i.pravatar.cc/50?img=1'},
                'starRating': 'FIVE',
                'comment': 'Super service ! Merci beaucoup.',
                'createTime': '2025-06-30T14:00:00Z'
            },
            {
                'reviewer': {'displayName': 'Bob', 'profilePhotoUrl': 'https://i.pravatar.cc/50?img=2'},
                'starRating': 'THREE',
                'comment': 'Correct mais un peu long.',
                'createTime': '2025-06-29T12:00:00Z'
            }
        ]
        return locations, reviews



@app.route("/dashboard")
@app.route("/dashboard")
def dashboard():
    if "token" not in session:
        return redirect(url_for("index"))

    # ✅ Appel correct avec les 5 arguments stockés en session
    locations, reviews = get_reviews_data(
        token=session["token"],
        refresh_token=session["refresh_token"],
        token_uri=session["token_uri"],
        client_id=session["client_id"],
        client_secret=session["client_secret"]
    )

    return render_template("dashboard.html", locations=locations, reviews=reviews)



@app.route("/save_profile", methods=["POST"])
def save_profile():
    profil = {
        "nom": request.form["nom"],
        "type": request.form["type"],
        "ville": request.form["ville"],
        "ton": request.form["ton"],
        "signature": request.form["signature"]
    }
    session["profil_etablissement"] = profil

    email = session.get("user_email")
    if email:
        sauvegarder_profil_utilisateur(email, profil)

    return redirect(url_for("dashboard"))





import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def generer_reponse_avis(profil, avis):
    prompt = f"""
Tu es le gérant de {profil['nom']}, un {profil['type']} situé à {profil['ville']}.
Voici un avis client :
"{avis}"

Génère une réponse {profil['ton']}, professionnelle, polie et efficace, en 3 à 5 phrases.
Termine par cette signature : "{profil['signature']}".
Merci de rester concis."""


    try:
        # 🔥 modèle validé et dispo pour la génération de texte
        model = genai.GenerativeModel("models/gemini-1.5-pro-latest")

        response = model.generate_content([prompt])
        return response.text.strip()
    except Exception as e:
        return f"[Erreur Gemini] {e}"   


@app.route("/generate_response", methods=["POST"])
def generate_response():
    avis = request.form.get("avis")  # récupère l'avis du formulaire
    profil = session.get("profil_etablissement", )  # récupère le profil depuis la session

    if not avis or not profil:
        return "Erreur : informations manquantes", 400

    # ✅ on passe bien les 2 arguments attendus ici
    reponse = generer_reponse_avis(profil, avis)
    return reponse


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)

    
