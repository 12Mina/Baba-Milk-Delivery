import os
from waitress import serve
from app import app, db
from flask_migrate import upgrade

DB_PATH = os.path.join(os.path.dirname(__file__), 'baba_milk.db')

if __name__ == "__main__":
    print("📦 Running database migrations on startup...")

    with app.app_context():
        try:
            if not os.path.exists(DB_PATH):
                print("⚠️ Database not found. Creating new one with db.create_all()")
                db.create_all()
            upgrade()
            print("✅ Migrations applied successfully.")
        except Exception as e:
            print("❌ Failed to apply migrations:", e)

    print("🚀 Starting Baba Milk Delivery app with Waitress on port 10000...")
    serve(app, host="0.0.0.0", port=10000)
