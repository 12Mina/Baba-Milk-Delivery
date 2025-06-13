from waitress import serve
from flask_migrate import upgrade
from app import app, db

if __name__ == "__main__":
    print("📦 Applying database migrations...")
    with app.app_context():
        upgrade()
        print("✅ Database upgraded!")

    print("🚀 Starting Baba Milk Delivery app with Waitress on port 10000...")
    serve(app, host="0.0.0.0", port=10000)