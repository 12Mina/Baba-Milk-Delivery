from waitress import serve
from app import app  # Make sure your main Flask app is in app.py

if __name__ == "__main__":
    print("🚀 Starting Baba Milk Delivery app with Waitress...")
    serve(app, host="0.0.0.0", port=8000)
