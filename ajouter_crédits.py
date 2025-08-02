import sys
from app import app, db
from models import User

if len(sys.argv) != 2:
    print("Usage: python ajouter_credits.py <email>")
    sys.exit(1)

email = sys.argv[1]

with app.app_context():
    user = User.query.filter_by(email=email).first()
    if user:
        user.credits += 50
        db.session.commit()
        print(f"Nouveaux crédits pour {email} : {user.credits}")
    else:
        print("Utilisateur non trouvé.")
