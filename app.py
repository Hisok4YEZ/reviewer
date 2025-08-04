from flask import Flask, redirect, request, session, url_for, render_template
from dotenv import load_dotenv
import os
import requests
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from flask_sqlalchemy import SQLAlchemy
from models import db, User, Review, DemoReview, RedemptionCode
import json
import google.generativeai as genai

# === Fonctions utilitaires JSON pour profil établissement ===
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

# === Config Flask & DB ===
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
print("🧪 DATABASE_URL = ", os.environ.get("DATABASE_URL"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
app.secret_key = "yunes_secret_key"
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# === Google OAuth Config ===
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")
SCOPES = [
    "https://www.googleapis.com/auth/business.manage",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

# === Page d'accueil ===
@app.route("/")
def index():
    return render_template("index.html")

# === Callback OAuth ===
@app.route("/callback")
def callback():
    print("➡️ URL callback appelée :", request.url)

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

    # ✅ Vérifie et décode l'id_token
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    idinfo = id_token.verify_oauth2_token(
        credentials.id_token,
        google_requests.Request(),
        GOOGLE_CLIENT_ID
    )
    google_id = idinfo["sub"]
    email = idinfo["email"]

    # 💾 Enregistrement des tokens dans la session
    session["token"] = credentials.token
    session["refresh_token"] = credentials.refresh_token
    session["token_uri"] = credentials.token_uri
    session["client_id"] = credentials.client_id
    session["client_secret"] = credentials.client_secret
    session["user_email"] = email

    # 📦 Création utilisateur si nouveau
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, google_id=google_id)
        db.session.add(user)
        db.session.commit()

    # 📁 Chargement du profil s’il existe
    profil = charger_profil_utilisateur(email)
    if profil:
        session["profil_etablissement"] = profil

    return redirect(url_for("dashboard"))


# === Login OAuth ===
@app.route("/login")
def login():
    flow = Flow.from_client_config({
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }, scopes=SCOPES, redirect_uri=REDIRECT_URI)

    auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')
    session["flow_state"] = state
    print("👉 redirect_uri utilisé :", flow.redirect_uri)
    return redirect(auth_url)

from models import db, User, Review, DemoReview
from datetime import datetime, timezone

@app.route("/add_demo_review", methods=["POST"])
def add_demo_review():
    if "user_email" not in session:
        return redirect(url_for("login"))

    auteur = request.form.get("auteur")
    note = request.form.get("note")
    texte = request.form.get("texte")

    user = User.query.filter_by(email=session["user_email"]).first()
    review = DemoReview(
        auteur=auteur,
        note=note,
        texte=texte,
        date=datetime.now(timezone.utc).isoformat(),
        user_id=user.id
    )
    db.session.add(review)
    db.session.commit()
    return redirect(url_for("dashboard"))

# === Fallback / Données démo ===
def get_reviews_data(token, refresh_token, token_uri, client_id, client_secret):
    print("ℹ️ Mode démo forcé activé (aucun appel à l’API Google Business).")

    # Données d’établissement fictives
    locations = [{
        'title': 'Établissement Démo',
        'locationName': '123 Rue de l’Exemple, Paris',
        'name': 'accounts/000000000/locations/000000000'
    }]

    # Avis fictifs pré-remplis
    reviews = [
        {"id": "demo_alice", "reviewer": {"displayName": "Alice", "profilePhotoUrl": "https://i.pravatar.cc/50?img=1"}, "starRating": "FIVE", "comment": "Great service ! thanks.", "createTime": "2025-06-30T14:00:00Z", "response": None},
        {"id": "demo_bob", "reviewer": {"displayName": "Bob", "profilePhotoUrl": "https://i.pravatar.cc/50?img=2"}, "starRating": "THREE", "comment": "Correct mais un peu long.", "createTime": "2025-06-29T12:00:00Z", "response": None},
        {"id": "demo_claire", "reviewer": {"displayName": "Claire", "profilePhotoUrl": "https://i.pravatar.cc/50?img=3"}, "starRating": "ONE", "comment": "Très mauvaise expérience.", "createTime": "2025-06-28T10:45:00Z", "response": None},
        {"id": "demo_david", "reviewer": {"displayName": "David", "profilePhotoUrl": "https://i.pravatar.cc/50?img=4"}, "starRating": "FOUR", "comment": "Personnel agréable. Bruyant.", "createTime": "2025-06-27T18:30:00Z", "response": None}
    ]

    # 🔁 Ajouter les avis personnalisés persistés en BDD
    user = User.query.filter_by(email=session["user_email"]).first()
    custom_reviews = DemoReview.query.filter_by(user_id=user.id).all()

    for r in custom_reviews:
        reviews.append({
            "id": f"demo_{r.id}",
            "reviewer": {
                "displayName": r.auteur,
                "profilePhotoUrl": "https://i.pravatar.cc/50?" + r.auteur.replace(" ", "_")
            },
            "starRating": r.note,
            "comment": r.texte,
            "createTime": r.date,
            "response": r.reponse
        })

    return locations, reviews


# === Dashboard ===
@app.route("/dashboard")
def dashboard():
    if "token" not in session:
        return redirect(url_for("index"))

    locations, reviews = get_reviews_data(
        token=session["token"],
        refresh_token=session["refresh_token"],
        token_uri=session["token_uri"],
        client_id=session["client_id"],
        client_secret=session["client_secret"]
    )
    user = User.query.filter_by(email=session["user_email"]).first()
    return render_template("dashboard.html", locations=locations, reviews=reviews, credits=user.credits)

# === Sauvegarde du profil ===
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
    if session.get("user_email"):
        sauvegarder_profil_utilisateur(session["user_email"], profil)
    return redirect(url_for("dashboard"))

# === IA - génération de réponse ===
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def generer_reponse_avis(profil, avis):
    prompt = f"""
Tu es le gérant de l’établissement suivant : {profil['nom']}, un {profil['type']} situé à {profil['ville']}.
---
📝 Voici un avis client reçu (écrit dans sa langue d'origine) :
"{avis}"
---
🎯 Ta tâche est de rédiger une réponse dans la **même langue que l'avis**, en respectant le ton défini ci-dessous :
🎙️ Ton attendu : **{profil['ton']}**
- La réponse doit être polie, empathique et adaptée au contenu de l’avis.
- Reste professionnel tout en respectant le ton indiqué.
- Sois concis : 3 à 5 phrases maximum.
❌ Évite les formules génériques, les répétitions, les emojis, les flatteries exagérées.
✅ Termine toujours par cette signature : "{profil['signature']}"
---
🧾 Règles :
- Ne traduis pas l’avis
- Réponds uniquement dans la langue d’origine
- Aucune balise HTML ou Markdown
- Pas d’intro type "Cher client" ou "Bonjour"
- Aère avec des retours à la ligne entre les phrases.
"""
    try:
        model = genai.GenerativeModel("models/gemini-1.5-pro-latest")
        response = model.generate_content([prompt])
        return response.text.strip()
    except Exception as e:
        return f"[Erreur Gemini] {e}"

@app.route("/generate_response", methods=["POST"])
def generate_response():
    avis = request.form.get("avis")
    review_id = request.form.get("review_id")  # Optionnel : pour savoir à quel avis associer la réponse
    profil = session.get("profil_etablissement")

    if not avis or not profil:
        return "Erreur : informations manquantes, veuillez remplir le formulaire en bas de la page", 400

    user = User.query.filter_by(email=session["user_email"]).first()
    
    if user.credits <= 0:
        return "Crédits épuisés", 402
    user.credits -= 1


    reponse = generer_reponse_avis(profil, avis)
    user.credits -= 1

    # 🧠 Si l'ID de l'avis est fourni et correspond à un avis personnalisé, on sauvegarde la réponse
    if review_id and review_id.startswith("demo_"):
        try:
            demo_id = int(review_id.replace("demo_", ""))
            demo_review = DemoReview.query.get(demo_id)
            if demo_review and demo_review.user_id == user.id:
                demo_review.reponse = reponse
        except Exception as e:
            print("⚠️ Impossible de mettre à jour la réponse de l'avis :", e)

    db.session.commit()
    return reponse

@app.route("/contact")
def contact():
    return render_template("contact.html")


# === Logout ===
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/pricing")
def pricing():
    return render_template("pricing.html")

@app.route("/redeem", methods=["POST"])
def redeem():
    code = request.form.get("code")
    user_email = session.get("user_email")
    # Validation + ajout crédits...
    return redirect("/dashboard")

    if request.method == "POST":
        code_input = request.form.get("code").strip()
        if not code_input or "user_email" not in session:
            return "Erreur : code invalide ou utilisateur non connecté."

        user_email = session["user_email"]
        user = User.query.filter_by(email=user_email).first()
        code = RedemptionCode.query.filter_by(code=code_input).first()

        if not code:
            return "❌ Code introuvable."
        if code.is_used:
            return f"❌ Ce code a déjà été utilisé par {code.used_by}."
        
        # Appliquer les crédits illimités
        user.code_reduction = "APP_SUMO_UNLIMITED"
        user.credits = 999999

        # Marquer le code comme utilisé
        code.is_used = True
        code.used_by = user_email

        db.session.commit()
        return redirect(url_for("dashboard"))

    return render_template("redeem.html")

@app.route("/admin/generate-codes")
def generate_codes_route():
    from models import RedemptionCode
    import random, string

    def generate_code(length=12):
        return "APP-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

    existing = {c.code for c in RedemptionCode.query.all()}
    codes = []
    while len(codes) < 1000:
        code = generate_code()
        if code not in existing:
            codes.append(RedemptionCode(code=code))
            existing.add(code)

    db.session.bulk_save_objects(codes)
    db.session.commit()
    return f"{len(codes)} codes générés ! ✅"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
