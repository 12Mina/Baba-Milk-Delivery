import os
from waitress import serve
from app import app, db
from flask_migrate import upgrade
from sqlalchemy.exc import OperationalError

# Optional: Only for local SQLite fallback
DB_PATH = os.path.join(os.path.dirname(__file__), 'baba_milk.db')

if __name__ == "__main__":
    print("📦 Running database migrations on startup...")

    with app.app_context():
        try:
            # If using SQLite and DB file not found (local dev)
            if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI'] and not os.path.exists(DB_PATH):
                print("⚠️ No SQLite DB found. Creating tables locally...")
                db.create_all()
            else:
                # Run migrations (works for PostgreSQL on Render)
                upgrade()
            print("✅ Database ready.")
        except OperationalError as oe:
            print("⚠️ OperationalError during upgrade:", oe)
            print("⛑️ Trying db.create_all() as fallback...")
            db.create_all()
        except Exception as e:
            print("❌ Migration failed:", e)

    print("🚀 Launching Baba Milk Delivery with Waitress on port 10000...")
    serve(app, host="0.0.0.0", port=10000)
