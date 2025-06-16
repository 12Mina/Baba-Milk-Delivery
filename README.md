# Baba-Milk-Delivery

## Overview

Baba-Milk-Delivery is a full-featured web application designed to streamline the local milk delivery process. The platform offers an intuitive interface for customers to browse dairy products, place orders, and track deliveries—while allowing admins to manage orders and products efficiently.

## Features

- 🧑‍💼 User Authentication with OTP (SMS-based via Twilio)
- 🛒 Smart Cart: Add, update, or remove milk, yogurt, cheese, and butter products
- 📦 Order Management with delivery tracking stages (placed, confirmed, packed, out for delivery, delivered)
- 💸 Payment Options: Cash on Delivery, Telebirr, CBE Birr
- 🔐 Admin Panel: Update order status and manage orders
- 📨 Flash messaging and validation feedback
- 🌍 Multi-language support potential (Amharic/English)

## Technologies Used

- 🖥️ Frontend: HTML, CSS, JavaScript
- ⚙️ Backend: Python with Flask
- 🗃️ Database: SQLite (for development), PostgreSQL (for production)
- 🌐 APIs: Twilio (for sending OTP via SMS)

## Setup and Installation

Follow these steps to get a development environment up and running on your local machine.

### Prerequisites

- Python 3.x
- pip (Python package installer)

### Installation Steps

1. Clone the repository:

    ```bash
    git clone https://github.com/your-username/Baba-Milk-Delivery.git
    cd Baba-Milk-Delivery
    ```

2. Create a virtual environment (recommended):

    ```bash
    python -m venv venv
    ```

3. Activate the virtual environment:

- On Windows:

    ```bash
    .\venv\Scripts\activate
    ```

- On macOS/Linux:

    ```bash
    source venv/bin/activate
    ```

4. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

5. Set up environment variables:

Create a .env file in the root directory and add:

    ```env
    FLASK_SECRET_KEY=your_flask_secret_key
    DATABASE_URL=sqlite:///baba_milk.db
    TWILIO_ACCOUNT_SID=your_twilio_account_sid
    TWILIO_AUTH_TOKEN=your_twilio_auth_token
    TWILIO_PHONE_NUMBER=your_twilio_registered_number
    ```

6. Initialize the database and populate products (optional):

    ```bash
    flask init-db
    ```

7. Run the Flask app:

    ```bash
    python app.py
    ```

Visit http://127.0.0.1:5000 to access the application.

## Project Structure

Baba-Milk-Delivery/
├── app.py # Main Flask application file
├── templates/ # HTML templates
│ ├── base.html
│ ├── home.html
│ ├── cart.html
│ ├── account.html
│ ├── verify_otp.html
│ ├── dashboard.html
│ ├── payment.html
│ └── admin.html
├── static/ # CSS, JS, images
│ ├── css/
│ │ └── style.css
│ ├── js/
│ │ └── script.js
│ └── images/
├── requirements.txt # Python dependencies
├── .env # Local environment variables
└── README.md # This file

pgsql
Copy
Edit

## License

This project is open-source and free to use for educational and local business purposes. Feel free to contribute or suggest improve