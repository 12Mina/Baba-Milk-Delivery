from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
import json
import secrets
import functools
from flask_migrate import Migrate
import random 
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException # Import Twilio exception for error handling
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER") # Your Twilio phone number (e.g., "+15017122661")

# Initialize Twilio client only if credentials are provided
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    twilio_client = None # Set to None if credentials are not found, so we can check later

# --- Flask App Setup ---
app = Flask(__name__)

# Secret key (you can set a secure one in production via environment variable)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_baba_milk_very_secret_and_long")

# --- Database Configuration ---
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://")
else:
    db_url = "sqlite:///baba_milk.db"  # force SQLite if not PostgreSQL

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

db = SQLAlchemy(app)

# --- Migration Setup ---
migrate = Migrate(app, db)

# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=True) # Optional lastname
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True) # Optional email
    password = db.Column(db.String(200), nullable=False) # Storing hashed OTP for simplicity as password
    is_admin = db.Column(db.Boolean, default=False)
    address = db.Column(db.String(200), nullable=True) # Default address

    orders = db.relationship('Order', backref='customer', lazy=True)

    def __repr__(self):
        return f"<User {self.phone}>"

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_path = db.Column(db.String(100), nullable=True) # Store only filename, not full path
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Product {self.name}>"

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    user = db.relationship('User', backref='cart_items')
    product = db.relationship('Product')

    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='_user_product_uc'),)

    def __repr__(self):
        return f"<CartItem User:{self.user_id} Product:{self.product_id} Qty:{self.quantity}>"

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    delivery_address = db.Column(db.String(255), nullable=False)
    delivery_phone = db.Column(db.String(20), nullable=False) # New field for delivery phone
    payment_method = db.Column(db.String(50), nullable=False) # e.g., 'cash_on_delivery', 'telebirr', 'cbebirr'
    payment_details = db.Column(db.JSON, nullable=True) # Stores JSON for telebirr/CBE Birr phone, transaction ID
    status = db.Column(db.String(50), default='placed') # placed, pending_payment_telebirr, confirmed, packed, out_for_delivery, delivered, cancelled

    # For displaying in admin panel and dashboard
    @property
    def items(self):
        # This will be a string representation for display in the admin panel/dashboard
        item_names = [f"{item.product.name} (x{item.quantity})" for item in self.order_items]
        return ", ".join(item_names)

    # For display in admin panel and dashboard
    @property
    def customer_name(self):
        return self.customer.name if self.customer else "N/A"
    
    @property
    def customer_phone(self):
        return self.customer.phone if self.customer else "N/A"
    
    @property
    def customer_email(self):
        return self.customer.email if self.customer else "N/A"

    @property
    def date(self):
        return self.order_date.strftime('%Y-%m-%d %H:%M')

    @property
    def tracker_statuses(self):
        # Define the full sequence of statuses for tracking display
        return ['placed', 'confirmed', 'packed', 'out_for_delivery', 'delivered']

    @property
    def current_status_index(self):
        # Get the index of the current status in the tracker sequence
        try:
            return self.tracker_statuses.index(self.status)
        except ValueError:
            return -1 # Status not in tracker list

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_purchase = db.Column(db.Float, nullable=False) # Price at the time of order

    order = db.relationship('Order', backref='order_items')
    product = db.relationship('Product')

    def __repr__(self):
        return f"<OrderItem Order:{self.order_id} Product:{self.product.name} Qty:{self.quantity}>"


# --- Context Processor (makes datetime available in all templates by default) ---
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# --- Context Processor (makes user available in all templates) ---
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = None
    print(f"\n--- BEFORE REQUEST HOOK ({datetime.now().strftime('%H:%M:%S')}) ---")
    print(f"  Request Method: {request.method}, Path: {request.path}")
    print(f"  Session content (on entry): {dict(session)}") # See full session on every request
    print(f"  Attempting to load user for session user_id: {user_id}")
    if user_id is not None:
        try:
            # Query the user using the session ID
            g.user = User.query.get(user_id)
            if g.user:
                print(f"  SUCCESS: g.user loaded: {g.user.name} (ID: {g.user.id}, Is Admin: {g.user.is_admin})")
                # Ensure user_name and is_admin are consistent with g.user
                session['user_name'] = g.user.name
                session['is_admin'] = g.user.is_admin
                session.permanent = True # Ensure session remains permanent
            else:
                print(f"  WARNING: No user found in DB for session user_id: {user_id}. Clearing session.")
                # If user_id is in session but not in DB (e.g., DB reset), clear session
                session.pop('user_id', None)
                session.pop('user_name', None)
                session.pop('is_admin', None)
                session.modified = True # Mark session modified
        except Exception as e:
            # Catch any database errors during user lookup
            print(f"  ERROR: Exception loading user for ID {user_id}: {e}. Clearing session and rolling back.")
            session.pop('user_id', None)
            session.pop('user_name', None)
            session.pop('is_admin', None)
            session.modified = True # Mark session modified
            db.session.rollback() # Rollback any half-baked transactions if an error occurred
    else:
        print("  INFO: No user_id found in session.")
    print(f"  Final g.user status (is not None): {g.user is not None}")
    print(f"--- END BEFORE REQUEST HOOK ---")


# --- Route Decorators for Authentication and Authorization (ONLY for HTML routes) ---
def login_required(f):
    """Decorator to check if a user is logged in. Redirects to account page if not."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"\n--- LOGIN REQUIRED DECORATOR INVOKED for {request.path} ({datetime.now().strftime('%H:%M:%S')}) ---")
        print(f"  Session user_id within decorator: {session.get('user_id')}")
        if 'user_id' not in session:
            print("  FAIL: User ID NOT found in session. Redirecting to /account.")
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('account'))
        print("  SUCCESS: User ID found in session. Proceeding with route function.")
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to check if a user is logged in and is an admin. Redirects if not authorized."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Access denied. You are not authorized to view this page.', 'danger')
            if request.accept_mimetypes.accept_json and \
               not request.accept_mimetypes.accept_html:
                return jsonify(success=False, message="Authorization required (Admin access)."), 403
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---
@app.route('/')
@app.route('/home')
def home():
    milk_products = Product.query.filter_by(category='milk').all()
    cheese_products = Product.query.filter_by(category='cheese').all()
    butter_products = Product.query.filter_by(category='butter').all()
    all_products = Product.query.all() # Fetch all products to display in a single grid
    return render_template('home.html',
                           milk_products=milk_products, # Still passed, but not explicitly used in template now
                           cheese_products=cheese_products, # Still passed, but not explicitly used in template now
                           butter_products=butter_products, # Still passed, but not explicitly used in template now
                           all_products=all_products, # This will be used to display all products
                           datetime=datetime)

@app.route('/account', methods=['GET'])
def account():
    return render_template('account.html', datetime=datetime)


@app.route('/send_otp', methods=['POST'])
def send_otp():
    phone_raw = request.form.get('phone')
    name = request.form.get('name')

    if not phone_raw or not phone_raw.replace('+', '').isdigit() or len(phone_raw.replace('+', '')) < 9:
        flash("Enter a valid phone number. It should contain only digits and optional '+' and be at least 9 digits long.", 'danger')
        return redirect(url_for('account'))

    # Ensure phone number is in E.164 format (e.g., +251912345678).
    # If it starts with 09 and is 10 digits (common for local Ethiopian numbers), prepend +251
    # Otherwise, assume it's already an international format if it starts with '+'
    # or requires a default country code if it doesn't start with 0 or +
    if phone_raw.startswith('09') and len(phone_raw) == 10:
        phone = '+251' + phone_raw[1:] # Convert 09xxxxxxxx to +2519xxxxxxxx
    elif not phone_raw.startswith('+'):
        # Fallback for non-Ethiopian numbers or other formats: assume a default country code
        # You might need a more sophisticated library for real-world international number parsing.
        phone = '+251' + phone_raw # Default to Ethiopia if no '+' provided
    else:
        phone = phone_raw # Already in a proper international format

    otp = str(random.randint(100000, 999999))
    session['otp_code'] = otp # CORRECTED: Store as 'otp_code' for verification
    session['otp_phone'] = phone
    session['otp_timestamp'] = datetime.now().timestamp()

    user = User.query.filter_by(phone=phone).first()
    session['action_type'] = 'login' if user else 'signup'
    if not user and not name:
        flash("Full name required for signup.", 'danger')
        return redirect(url_for('account'))
    if name:
        session['signup_name'] = name

    print(f"🔐 OTP for {phone} is: {otp}")  # SIMULATED / DEBUGGING

    # --- Twilio SMS Sending (Uncomment and configure if live Twilio is used) ---
    if twilio_client and TWILIO_PHONE_NUMBER:
        try:
            message = twilio_client.messages.create(
                to=phone,
                from_=TWILIO_PHONE_NUMBER,
                body=f"Your Baba Milk App verification code is: {otp}"
            )
            print(f"Twilio message SID: {message.sid}")
            flash(f"An OTP has been sent to {phone}.", 'info')
        except TwilioRestException as e:
            app.logger.error(f"Twilio error sending OTP to {phone}: {e}")
            flash("Failed to send OTP. Please try again or check your phone number.", 'danger')
        except Exception as e:
            app.logger.error(f"General error sending OTP to {phone}: {e}")
            flash("An unexpected error occurred while sending OTP. Please try again.", 'danger')
    else:
        flash(f"OTP simulation: {otp}. Please check your console. (Twilio not configured)", 'info')

    return render_template('verify_otp.html', phone=phone)

@app.route('/resend_otp', methods=['POST'])
def resend_otp():
    phone = session.get('otp_phone')
    action_type = session.get('action_type') # Preserve action type (login/signup)

    if not phone:
        flash("No active OTP request found. Please start from the account page.", 'danger')
        return redirect(url_for('account'))

    # Generate a new OTP
    otp = str(random.randint(100000, 999999))
    session['otp_code'] = otp # CORRECTED: Store as 'otp_code' for consistency
    session['otp_timestamp'] = datetime.now().timestamp() # Update timestamp for new OTP

    # --- Twilio SMS Sending (Uncomment and configure if live Twilio is used) ---
    if twilio_client and TWILIO_PHONE_NUMBER:
        try:
            message = twilio_client.messages.create(
                to=phone,
                from_=TWILIO_PHONE_NUMBER,
                body=f"Your new Baba Milk App verification code is: {otp}"
            )
            print(f"Twilio message SID (resend): {message.sid}")
            flash(f"A new OTP has been sent to {phone}.", 'info')
        except TwilioRestException as e:
            app.logger.error(f"Twilio error resending OTP to {phone}: {e}")
            flash("Failed to resend OTP. Please try again or check your phone number.", 'danger')
        except Exception as e:
            app.logger.error(f"General error resending OTP to {phone}: {e}")
            flash("An unexpected error occurred while resending OTP. Please try again.", 'danger')
    else:
        print(f"\n--- RESENT OTP for {phone} is: {otp} (Action: {action_type}) ---\n")
        flash(f"A new OTP has been sent to {phone}. Check your **console**.", 'info')
        
    return render_template('verify_otp.html', phone=phone, datetime=datetime)

@app.route('/verify_otp', methods=['GET'])
def verify_otp_page():
    phone = session.get('otp_phone')
    if not phone:
        flash("Session expired. Please start again.", 'danger')
        return redirect(url_for('account'))
    return render_template('verify_otp.html', phone=phone, datetime=datetime)

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    user_otp = request.form.get('otp')
    phone = session.get('otp_phone')
    stored_otp = session.get('otp_code') # This is now correctly matching where it's stored
    otp_timestamp = session.get('otp_timestamp')
    action_type = session.get('action_type')

    if not all([user_otp, phone, stored_otp, action_type]):
        flash("Missing verification data. Please try again from the account page.", 'danger')
        return redirect(url_for('account'))

    # Expiry check (5 min)
    if otp_timestamp and (datetime.now().timestamp() - otp_timestamp > 300): # Use datetime.now() for consistency
        flash("OTP has expired. Please request a new one.", 'danger')
        session.clear()
        return redirect(url_for('account'))

    if user_otp == stored_otp:
        user = User.query.filter_by(phone=phone).first()

        if action_type == 'signup':
            name = session.get('signup_name')
            if user:
                flash("Account already exists. Please log in.", 'warning')
                session.clear()
                return redirect(url_for('account'))
            if not name:
                flash("Signup failed. Missing name in session.", 'danger')
                session.clear()
                return redirect(url_for('account'))

            new_user = User(
                name=name,
                phone=phone,
                password=generate_password_hash(stored_otp) # Store hashed OTP
            )
            db.session.add(new_user)
            db.session.commit()
            session['user_id'] = new_user.id
            session['user_name'] = new_user.name
            session['is_admin'] = new_user.is_admin
            flash("Account created successfully!", 'success')

        elif action_type == 'login':
            if not user:
                flash("Login failed. No account found for this phone number.", 'danger')
                return redirect(url_for('account'))
            # For login, we are checking the entered OTP against the one sent.
            # No password hash comparison needed if OTP is the only login mechanism.
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['is_admin'] = user.is_admin
            flash(f"Welcome back, {user.name}!", 'success')

        # --- Cart Merging Logic ---
        # If there's a guest cart in session, merge it with the newly logged-in user's cart in the DB.
        current_session_cart = session.get('cart', {})
        if current_session_cart and session.get('user_id'): # Only merge if there's a cart and a user is now logged in
            logged_in_user_id = session['user_id']
            for product_id_str, item_data in current_session_cart.items():
                product_id = int(product_id_str)
                quantity = item_data['quantity']

                existing_cart_item = CartItem.query.filter_by(
                    user_id=logged_in_user_id,
                    product_id=product_id
                ).first()

                if existing_cart_item:
                    existing_cart_item.quantity += quantity
                else:
                    new_cart_item_db = CartItem(
                        user_id=logged_in_user_id,
                        product_id=product_id,
                        quantity=quantity
                    )
                    db.session.add(new_cart_item_db)
            
            db.session.commit() # Commit all merged cart items to the database
            session.pop('cart', None) # Clear the session cart after it's persisted to DB
            session.modified = True
            print(f"Cart merged and persisted for user {logged_in_user_id}. Session cart cleared.")
        # --- End Cart Merging Logic ---


        # Clear OTP session data after success
        for key in ['otp_code', 'otp_phone', 'otp_timestamp', 'signup_name', 'action_type']:
            session.pop(key, None)

        return redirect(url_for('home'))

    else:
        flash("Invalid OTP. Please try again.", 'danger')
        # Do not clear session here so user can retry OTP
        return redirect(url_for('verify_otp_page'))

@app.route('/logout')
@login_required
def logout():
    # If a user logs out, their cart in the DB remains.
    # The session cart is simply cleared as it's no longer associated with a logged-in user.
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('is_admin', None)
    session.pop('delivery_info', None) # Clear delivery info if any
    session.pop('cart', None) # This clears the in-memory session cart. The DB cart persists.
    session.modified = True # Explicitly mark session as modified
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    try:
        data = request.get_json()
        product_id_str = str(data.get('product_id'))
        
        try:
            product_id_int = int(product_id_str)
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid product ID format.'}), 400

        product = Product.query.get(product_id_int)
        if not product:
            return jsonify({'success': False, 'message': 'Product not found'}), 404

        # Initialize cart in session if it doesn't exist (for guests or logged-in)
        if 'cart' not in session:
            session['cart'] = {}

        cart = session['cart']

        if product_id_str in cart:
            cart[product_id_str]['quantity'] += 1
        else:
            cart[product_id_str] = {
                'id': product_id_str,
                'name': product.name,
                'price': float(product.price),
                'image_path': product.image_path, # This is just the filename now
                'quantity': 1
            }

        session['cart'] = cart
        session.modified = True # Mark session modified

        total_quantity = sum(item['quantity'] for item in cart.values())
        return jsonify({'success': True, 'message': f'{product.name} added to cart!', 'total_quantity': total_quantity})

    except Exception as e:
        app.logger.error(f"Error adding to cart: {e}")
        db.session.rollback() # Ensure rollback on error
        return jsonify({'success': False, 'message': 'An error occurred while adding to cart.'}), 500

@app.route('/get_cart_count')
def get_cart_count():
    # Always return cart count from session, regardless of login status
    total_quantity = 0
    if 'cart' in session:
        total_quantity = sum(item['quantity'] for item in session['cart'].values())
    return jsonify({'cart_count': total_quantity}), 200

@app.route('/get_cart_items')
def get_cart_items():
    # Always return cart items from session, regardless of login status
    cart_data = session.get('cart', {})
    items_list = []

    for product_id_str, item_data in cart_data.items():
        items_list.append({
            'id': product_id_str,
            'name': item_data['name'],
            'price': item_data['price'],
            'image_url': url_for('static', filename='images/' + item_data.get('image_path', 'default.png')),
            'quantity': item_data['quantity']
        })
    
    return jsonify({'cart_items': items_list}), 200

@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))
        new_quantity = data.get('quantity')

        if new_quantity is None or not isinstance(new_quantity, int) or new_quantity < 0:
            return jsonify({'success': False, 'message': 'Invalid product ID or quantity.'}), 400

        cart = session.get('cart', {}) # Use session cart

        if product_id not in cart:
            return jsonify({'success': False, 'message': 'Item not found in cart.'}), 404

        if new_quantity == 0:
            item_name = cart[product_id]['name']
            del cart[product_id]
            message = f"Removed {item_name} from cart."
        else:
            cart[product_id]['quantity'] = new_quantity
            message = f"Quantity of {cart[product_id]['name']} updated to {new_quantity}."

        session['cart'] = cart
        session.modified = True # Mark session modified
        
        return jsonify({'success': True, 'message': message})

    except Exception as e:
        app.logger.error(f"Error updating cart quantity: {e}")
        db.session.rollback() # Ensure rollback on error
        return jsonify({'success': False, 'message': 'An error occurred while updating quantity.'}), 500

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))

        cart = session.get('cart', {}) # Use session cart

        if product_id not in cart:
            return jsonify({'success': False, 'message': 'Item not found in cart.'}), 404

        item_name = cart[product_id]['name']
        del cart[product_id]
        session['cart'] = cart
        session.modified = True # Mark session modified

        return jsonify({'success': True, 'message': f'{item_name} removed from cart.'})

    except Exception as e:
        app.logger.error(f"Error removing item from cart: {e}")
        db.session.rollback() # Ensure rollback on error
        return jsonify({'success': False, 'message': 'An error occurred while removing item.'}), 500


@app.route('/cart')
# Removed @login_required decorator to allow guest access
def cart():
    # Only try to get user's default delivery address/phone if logged in
    user_address = g.user.address if g.user and g.user.address else ''
    user_phone = g.user.phone if g.user and g.user.phone else ''
    return render_template('cart.html', user_address=user_address, user_phone=user_phone, datetime=datetime) # Ensure datetime is passed

@app.route('/checkout', methods=['POST'])
@login_required # This route still requires login to proceed to payment
def checkout():
    # This route is hit from the cart page after confirming delivery details
    # The login_required decorator ensures user is logged in here.
    delivery_name = request.form.get('delivery_name', session.get('user_name', '')) 
    delivery_phone = request.form.get('delivery_phone')
    delivery_address = request.form.get('delivery_address')

    if not all([delivery_phone, delivery_address]): 
        flash("Missing delivery phone or address. Please fill all fields.", 'danger')
        return redirect(url_for('cart'))

    if not delivery_phone.replace('+', '').isdigit() or len(delivery_phone.replace('+', '')) < 9:
        flash("Please enter a valid phone number (digits only, at least 9 digits, optional leading '+').", 'danger')
        return redirect(url_for('cart'))
        
    # Ensure delivery phone is in E.164 format here as well
    if delivery_phone.startswith('09') and len(delivery_phone) == 10:
        delivery_phone = '+251' + delivery_phone[1:] # Convert 09xxxxxxxx to +2519xxxxxxxx
    elif not delivery_phone.startswith('+'):
        delivery_phone = '+251' + delivery_phone # Default to Ethiopia if no '+' provided

    # Calculate total and get cart items from session (server-side for security)
    cart_items_session = session.get('cart', {})
    if not cart_items_session:
        # If cart is empty here, it means it was just merged, or user logged out and back in
        # We need to load user's actual DB cart if session cart is empty but user is logged in.
        if g.user:
            user_db_cart_items = CartItem.query.filter_by(user_id=g.user.id).all()
            if user_db_cart_items:
                # Reconstruct session cart from DB cart items
                for db_item in user_db_cart_items:
                    cart_items_session[str(db_item.product_id)] = {
                        'id': str(db_item.product_id),
                        'name': db_item.product.name,
                        'price': float(db_item.product.price),
                        'image_path': db_item.product.image_path,
                        'quantity': db_item.quantity
                    }
                session['cart'] = cart_items_session
                session.modified = True
            else:
                flash("Your cart is empty. Please add items before checking out.", 'warning')
                return redirect(url_for('home'))
        else: # Should not happen if @login_required is working
            flash("Your cart is empty. Please add items before checking out.", 'warning')
            return redirect(url_for('home'))

    total_amount = sum(item['price'] * item['quantity'] for item in cart_items_session.values())

    # Store delivery info and actual cart items in session for use on the payment page
    session['delivery_info'] = {
        'name': delivery_name,
        'phone': delivery_phone,
        'address': delivery_address,
        'total_amount': total_amount,
        'cart_items': list(cart_items_session.values()) # Convert dict_values to list for storage
    }
    session.modified = True # Mark session modified

    # Redirect to payment page
    return redirect(url_for('payment'))

@app.route('/payment')
@login_required # This route still requires login
def payment():
    # Retrieve delivery info and total from session
    delivery_info = session.get('delivery_info')
    if not delivery_info:
        flash("No checkout information found. Please proceed from your cart.", 'warning')
        return redirect(url_for('cart'))

    total_amount = delivery_info.get('total_amount')
    cart_items = delivery_info.get('cart_items') # Detailed cart items passed for review

    return render_template('payment.html', total_amount=total_amount, cart_items=cart_items, datetime=datetime) # Ensure datetime is passed


@app.route('/finalize_order', methods=['POST'])
@login_required # This route still requires login
def finalize_order():
    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        flash('User not found. Please log in again.', 'danger')
        return redirect(url_for('account'))

    delivery_info = session.get('delivery_info')
    if not delivery_info or not delivery_info.get('address') or not delivery_info.get('phone') or not delivery_info.get('cart_items'):
        flash("Checkout information missing. Please start from cart.", 'danger')
        return redirect(url_for('cart'))

    # Re-calculate total and validate cart items from session for security
    server_validated_total = 0.0
    order_items_to_add = []
    
    # After login, the session['cart'] might be empty if it was just merged to DB.
    # So, we should ensure the items are fetched from the DB for the final order creation.
    # This ensures consistency even if session was cleared or user navigated away then back.
    user_db_cart_items = CartItem.query.filter_by(user_id=user_id).all()
    if not user_db_cart_items:
        flash("Your cart is empty. Please add items before checking out.", 'warning')
        return redirect(url_for('home'))

    for db_item in user_db_cart_items:
        product = Product.query.get(db_item.product_id)
        if not product:
            # Handle case where product might have been deleted after adding to cart
            flash(f"One of the products in your cart ({db_item.product.name if db_item.product else 'Unknown'}) is no longer available. Please review your cart.", 'danger')
            return redirect(url_for('cart'))

        item_total = product.price * db_item.quantity
        server_validated_total += item_total
        order_items_to_add.append({
            'product_id': product.id,
            'quantity': db_item.quantity,
            'price': product.price # Store current price for historical accuracy
        })

    payment_method = request.form.get('payment_method')
    payment_detail_info = {}
    status = 'placed'

    if payment_method == 'telebirr':
        payment_detail_info['phone'] = request.form.get('telebirr_phone')
        # Validate and format phone number for payment details
        if not payment_detail_info['phone'] or not payment_detail_info['phone'].replace('+', '').isdigit():
            flash('Valid Telebirr phone number is required.', 'danger')
            return redirect(url_for('payment'))
        if payment_detail_info['phone'].startswith('09') and len(payment_detail_info['phone']) == 10:
            payment_detail_info['phone'] = '+251' + payment_detail_info['phone'][1:]
        elif not payment_detail_info['phone'].startswith('+'):
            payment_detail_info['phone'] = '+251' + payment_detail_info['phone']

        status = 'pending_payment_telebirr'
    elif payment_method == 'cbebirr':
        payment_detail_info['phone'] = request.form.get('cbebirr_phone')
        # Validate and format phone number for payment details
        if not payment_detail_info['phone'] or not payment_detail_info['phone'].replace('+', '').isdigit():
            flash('Valid CBE Birr phone number is required.', 'danger')
            return redirect(url_for('payment'))
        if payment_detail_info['phone'].startswith('09') and len(payment_detail_info['phone']) == 10:
            payment_detail_info['phone'] = '+251' + payment_detail_info['phone'][1:]
        elif not payment_detail_info['phone'].startswith('+'):
            payment_detail_info['phone'] = '+251' + payment_detail_info['phone']

        status = 'pending_payment_cbebirr'
    elif payment_method != 'cash_on_delivery':
        flash('Invalid payment method selected.', 'danger')
        return redirect(url_for('payment'))

    try:
        new_order = Order(
            user_id=g.user.id,
            total_amount=server_validated_total, # Use server-validated total
            delivery_address=delivery_info['address'],
            delivery_phone=delivery_info['phone'],
            payment_method=payment_method,
            payment_details=json.dumps(payment_detail_info),
            status=status
        )
        db.session.add(new_order)
        db.session.flush() # Get ID before commit for order_items

        # Add items from stored delivery_info['cart_items'] to OrderItem table
        for item_data in order_items_to_add:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item_data['product_id'],
                quantity=item_data['quantity'],
                price_at_purchase=item_data['price']
            )
            db.session.add(order_item)
            
        # Clear the user's cart from the database after order is finalized
        CartItem.query.filter_by(user_id=user_id).delete()
        
        session.pop('cart', None) # Clear the session cart (it should be empty anyway after merge)
        session.modified = True # Mark session modified

        db.session.commit()
        session.pop('delivery_info', None) # Clear delivery info from session
        session.modified = True # Mark session modified

        flash("Your order has been placed successfully!", 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        db.session.rollback()
        print(f"Error finalizing order: {e}")
        flash("An error occurred while placing your order. Please try again.", 'danger')
        return redirect(url_for('cart'))

@app.route('/dashboard')
@login_required # Dashboard still requires login
def dashboard():
    orders = Order.query.filter_by(user_id=g.user.id).order_by(Order.order_date.desc()).all()
    return render_template('dashboard.html', orders=orders, datetime=datetime) # Ensure datetime is passed

@app.route('/admin')
@admin_required
def admin():
    orders = Order.query.order_by(Order.order_date.desc()).all()
    # Prepare orders to pass to the template, including customer name, phone, email, and detailed items
    orders_for_template = []
    for order in orders:
        items_detail = []
        for item in order.order_items:
            items_detail.append(f"{item.product.name} (x{item.quantity})")
        
        # Determine current status index for tracker display in admin panel too
        current_status_index = -1
        tracker_statuses_admin = ['placed', 'confirmed', 'packed', 'out_for_delivery', 'delivered'] # Admin might see 'packed'
        if order.status.startswith('pending_payment'):
            current_status_index = 0 # Consider pending payment as "placed" for tracker visual
        elif order.status in tracker_statuses_admin:
            current_status_index = tracker_statuses_admin.index(order.status)

        orders_for_template.append({
            'id': order.id,
            'customer': order.customer_name,
            'customer_phone': order.customer_phone,
            'customer_email': order.customer_email,
            'delivery_address': order.delivery_address,
            'items': ', '.join(items_detail),
            'date': order.date,
            'total': order.total_amount,
            'payment_method': order.payment_method,
            'payment_details': order.payment_details,
            'status': order.status,
            'current_status_index': current_status_index,
            'tracker_statuses': tracker_statuses_admin # Pass for admin panel too
        })
    return render_template('admin.html', orders=orders_for_template, datetime=datetime) # Ensure datetime is passed


@app.route('/update_order_status', methods=['POST'])
@admin_required
def update_order_status():
    # This route is called by an HTML form, so it expects form data
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')

    valid_statuses = [
        'placed', 'pending_payment_telebirr', 'pending_payment_cbebirr',
        'confirmed', 'packed', 'out_for_delivery', 'delivered', 'cancelled'
    ]

    if not order_id or not new_status:
        flash('Missing order ID or status.', 'danger')
        return redirect(url_for('admin'))

    if new_status not in valid_statuses:
        flash(f'Invalid status: {new_status}', 'danger')
        return redirect(url_for('admin'))

    order = Order.query.get(order_id)
    if order:
        order.status = new_status
        try:
            db.session.commit()
            flash(f'Order {order_id} status updated to {new_status.replace("_", " ").capitalize()}', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating order status: {e}', 'danger')
            app.logger.error(f"Order status update error: {e}")
    else:
        flash('Order not found', 'danger')

    return redirect(url_for('admin'))

# --- New Search Route ---
@app.route('/search_products', methods=['GET'])
def search_products():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify(products=[]), 200 # Return empty if no query

    # Perform a case-insensitive search on product name or description
    search_pattern = f"%{query}%"
    products = Product.query.filter(
        (Product.name.ilike(search_pattern)) |
        (Product.description.ilike(search_pattern))
    ).all()

    # Format products for JSON response
    search_results = []
    for product in products:
        search_results.append({
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'image_path': url_for('static', filename='images/' + product.image_path),
            'description': product.description,
            'category': product.category
        })
    
    return jsonify(products=search_results), 200

# --- New About Us Route ---
@app.route('/about_us')
def about_us():
    return render_template('about_us.html', datetime=datetime)


# --- Data Population (for initial setup) ---
# NOTE: Ensure you have corresponding image files (e.g., product1.png to product40.png)
# in your 'static/images/' directory for these products to display correctly.
products_data = [
    # Milk (image_suffix 1-10)
    {"name": "Fresh Cow Milk (1L)", "category": "milk", "price": 80.00, "image_suffix": 1, "description": "Pure, pasteurized cow milk, delivered fresh daily."},
    {"name": "Organic Whole Milk (1L)", "category": "milk", "price": 95.00, "image_suffix": 2, "description": "Sourced from organic farms, rich in nutrients and flavor."},
    {"name": "Low-Fat Milk (1L)", "category": "milk", "price": 70.00, "image_suffix": 3, "description": "A healthy choice with reduced fat content, perfect for everyday use."},
    {"name": "Lactose-Free Milk (1L)", "category": "milk", "price": 110.00, "image_suffix": 4, "description": "Easy to digest, all the goodness of milk without lactose."},
    {"name": "Skim Milk (1L)", "category": "milk", "price": 65.00, "image_suffix": 5, "description": "Virtually fat-free, ideal for health-conscious individuals."},
    {"name": "Goat Milk (500ml)", "category": "milk", "price": 120.00, "image_suffix": 6, "description": "Nutrient-rich goat milk, a great alternative for sensitive stomachs."},
    {"name": "Almond Milk (1L)", "category": "milk", "price": 100.00, "image_suffix": 7, "description": "Dairy-free almond milk, perfect for vegans and those with intolerances."},
    {"name": "Soy Milk (1L)", "category": "milk", "price": 90.00, "image_suffix": 8, "description": "Plant-based soy milk, high in protein and versatility."},
    {"name": "Chocolate Milk (500ml)", "category": "milk", "price": 95.00, "image_suffix": 9, "description": "Rich and delicious chocolate milk, a treat for all ages."},
    {"name": "Strawberry Milk (500ml)", "category": "milk", "price": 95.00, "image_suffix": 10, "description": "Sweet strawberry-flavored milk, a fun drink for kids."},

    # Cheese (image_suffix 11-20)
    {"name": "Cheddar Cheese (200g)", "category": "cheese", "price": 150.00, "image_suffix": 11, "description": "Classic sharp cheddar cheese block, aged to perfection."},
    {"name": "Mozzarella Cheese (200g)", "category": "cheese", "price": 130.00, "image_suffix": 12, "description": "Perfect for pizzas and pastas, melts beautifully and stretches."},
    {"name": "Feta Cheese (150g)", "category": "cheese", "price": 120.00, "image_suffix": 13, "description": "Tangy and salty, ideal for salads and Mediterranean dishes."},
    {"name": "Gouda Cheese (200g)", "category": "cheese", "price": 160.00, "image_suffix": 14, "description": "Semi-hard cheese with a mild, nutty flavor."},
    {"name": "Cream Cheese (250g)", "category": "cheese", "price": 100.00, "image_suffix": 15, "description": "Smooth and spreadable, great for bagels and cooking."},
    {"name": "Parmesan Cheese (100g)", "category": "cheese", "price": 180.00, "image_suffix": 16, "description": "Hard, granular cheese perfect for grating over pasta."},
    {"name": "Ricotta Cheese (250g)", "category": "cheese", "price": 90.00, "image_suffix": 17, "description": "Soft and creamy, ideal for Italian desserts and savory dishes."},
    {"name": "Cottage Cheese (250g)", "category": "cheese", "price": 80.00, "image_suffix": 18, "description": "High in protein, a versatile and healthy snack."},
    {"name": "Swiss Cheese (200g)", "category": "cheese", "price": 140.00, "image_suffix": 19, "description": "Distinctive holes and a mild, nutty taste."},
    {"name": "Provolone Cheese (200g)", "category": "cheese", "price": 135.00, "image_suffix": 20, "description": "Versatile cheese, great for sandwiches and melting."},

    # Yogurt (image_suffix 21-30) - New entries based on user request
    {"name": "Plain Yogurt (500g)", "category": "yogurt", "price": 70.00, "image_suffix": 21, "description": "Creamy and natural plain yogurt, great for breakfast or cooking."},
    {"name": "Strawberry Yogurt (200g)", "category": "yogurt", "price": 55.00, "image_suffix": 22, "description": "Sweet strawberry-flavored yogurt, a delightful snack."},
    {"name": "Vanilla Bean Yogurt (200g)", "category": "yogurt", "price": 60.00, "image_suffix": 23, "description": "Smooth vanilla yogurt with real bean specks."},
    {"name": "Greek Yogurt (250g)", "category": "yogurt", "price": 85.00, "image_suffix": 24, "description": "Thick and protein-rich Greek yogurt."},
    {"name": "Blueberry Yogurt (200g)", "category": "yogurt", "price": 58.00, "image_suffix": 25, "description": "Fruity yogurt with juicy blueberries."},
    {"name": "Mango Yogurt (200g)", "category": "yogurt", "price": 58.00, "image_suffix": 26, "description": "Tropical mango-flavored yogurt."},
    {"name": "Honey Yogurt (200g)", "category": "yogurt", "price": 62.00, "image_suffix": 27, "description": "Naturally sweetened with pure honey."},
    {"name": "Peach Yogurt (200g)", "category": "yogurt", "price": 55.00, "image_suffix": 28, "description": "Refreshing peach-flavored yogurt."},
    {"name": "Low-Fat Yogurt (500g)", "category": "yogurt", "price": 65.00, "image_suffix": 29, "description": "Healthy low-fat option for everyday consumption."},
    {"name": "Probiotic Yogurt (200g)", "category": "yogurt", "price": 75.00, "image_suffix": 30, "description": "Contains live cultures for digestive health."},

    # Butter (image_suffix 31-40) - Adjusted existing and added new ones
    {"name": "Salted Butter (250g)", "category": "butter", "price": 90.00, "image_suffix": 31, "description": "Rich and creamy salted butter, perfect for spreading."},
    {"name": "Unsalted Butter (250g)", "category": "butter", "price": 90.00, "image_suffix": 32, "description": "Pure, unsalted butter for baking and cooking, allows flavor control."},
    {"name": "Ghee (Clarified Butter, 500g)", "category": "butter", "price": 200.00, "image_suffix": 33, "description": "Traditional clarified butter, rich flavor and high smoke point."},
    {"name": "Garlic Herb Butter (150g)", "category": "butter", "price": 110.00, "image_suffix": 34, "description": "Infused with garlic and herbs, perfect for steaks or bread."},
    {"name": "Whipped Butter (200g)", "category": "butter", "price": 85.00, "image_suffix": 35, "description": "Light and airy whipped butter, easy to spread."},
    {"name": "Cultured Butter (250g)", "category": "butter", "price": 105.00, "image_suffix": 36, "description": "Tangy and flavorful, made from cultured cream."},
    {"name": "European Style Butter (250g)", "category": "butter", "price": 115.00, "image_suffix": 37, "description": "Higher fat content for richer taste and texture."},
    {"name": "Light Butter (250g)", "category": "butter", "price": 75.00, "image_suffix": 38, "description": "Reduced-fat butter alternative."},
    {"name": "Brown Butter (Homemade, 100g)", "category": "butter", "price": 130.00, "image_suffix": 39, "description": "Nutty and aromatic, great for desserts and savory dishes."},
    {"name": "Avocado Oil Butter (250g)", "category": "butter", "price": 125.00, "image_suffix": 40, "description": "Blend of butter and healthy avocado oil."},
]


@app.cli.command('init-db')
def init_db_command():
    """Initializes the database and populates with sample data.
    This command will first delete all existing products and then repopulate.
    Use with caution in production environments as it clears product data."""
    with app.app_context():
        db.create_all()
        print("Database initialized.")
        
        # Always delete existing products before populating to ensure consistency with new mapping
        # This is especially important when changing product data structure or ranges.
        print("Deleting all existing products...")
        Product.query.delete()
        db.session.commit()
        print("Existing products deleted.")

        print("Populating products with new data...")
        for p_data in products_data:
            # Construct image path using the explicit image_suffix
            image_name = f"product{p_data['image_suffix']}.png" 
            new_product = Product(
                name=p_data['name'],
                category=p_data['category'],
                price=p_data['price'],
                image_path=image_name,
                description=p_data['description']
            )
            db.session.add(new_product)
        db.session.commit()
        print(f"Products populated. Total {len(products_data)} products added.")

        # Create admin user if not exists
        if not User.query.filter_by(is_admin=True).first():
            print("Admin user missing. Creating...")
            admin_user = User(
                name="Admin",
                lastname="User",
                phone="+251911223344",
                email="admin@example.com",
                password=generate_password_hash("adminpass"),
                is_admin=True,
                address="Admin Office, Addis Ababa"
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin user created (phone: +251911223344, pass: adminpass).")
        else:
            print("Admin user already exists. Skipping creation.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Ensure tables are created when running directly
        # To populate or re-populate your database with the new product data, run:
        # flask init-db
        # from your terminal.
    app.run(debug=True)
