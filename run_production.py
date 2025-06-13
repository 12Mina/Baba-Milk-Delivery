from waitress import serve
from app import app, db
from flask_migrate import upgrade

if __name__ == "__main__":
    print("📦 Applying database migrations...")
    with app.app_context():
        upgrade()

    print("🚀 Starting Baba Milk Delivery app with Waitress on port 8000...")
    serve(app, host="0.0.0.0", port=8000)
