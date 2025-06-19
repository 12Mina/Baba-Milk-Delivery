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
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("+919034653116")

if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    twilio_client = None

app = Flask(__name__)

# --- Session & Cookie Config ---
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_baba_milk_very_secret_and_long")
app.config['SESSION_COOKIE_NAME'] = 'baba_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Only for local testing
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# --- Database Configuration ---
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://")
else:
    db_url = "sqlite:///baba_milk.db"

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    address = db.Column(db.String(200), nullable=True)

    orders = db.relationship('Order', backref='customer', lazy=True)

    def __repr__(self):
        return f"<User {self.phone}>"

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_path = db.Column(db.String(100), nullable=True)
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
        return f"<CartItem User:{self.user_id} Product:{self.product.id} Qty:{self.quantity}>"

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    delivery_address = db.Column(db.String(255), nullable=False)
    delivery_phone = db.Column(db.String(20), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    payment_details = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(50), default='placed')

    @property
    def items(self):
        item_names = [f"{item.product.name} (x{item.quantity})" for item in self.order_items]
        return ", ".join(item_names)

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
        return ['placed', 'confirmed', 'packed', 'out_for_delivery', 'delivered']

    @property
    def current_status_index(self):
        try:
            return self.tracker_statuses.index(self.status)
        except ValueError:
            return -1

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_purchase = db.Column(db.Float, nullable=False)

    order = db.relationship('Order', backref='order_items')
    product = db.relationship('Product')

    def __repr__(self):
        return f"<OrderItem Order:{self.order_id} Product:{self.product.name} Qty:{self.quantity}>"

# --- Context Processor ---
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# --- Before Request ---
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = None
    print(f"\n--- BEFORE REQUEST HOOK ({datetime.now().strftime('%H:%M:%S')}) ---")
    print(f"  Request Method: {request.method}, Path: {request.path}")
    print(f"  Session content (on entry): {dict(session)}")
    print(f"  Attempting to load user for session user_id: {user_id}")

    # Check for expired OTP and clean up session
    otp_timestamp = session.get('otp_timestamp')
    if otp_timestamp and (datetime.now().timestamp() - otp_timestamp > 300):
        print("  WARNING: OTP expired. Clearing OTP-related session data.")
        for key in ['otp_code', 'otp_phone', 'otp_timestamp', 'signup_name', 'action_type']:
            session.pop(key, None)
        session.modified = True
        if request.path in ['/verify_otp', '/resend_otp']:
            flash("Your OTP has expired. Please request a new one.", 'warning')

    if user_id is not None:
        try:
            g.user = User.query.get(user_id)
            if g.user:
                print(f"  SUCCESS: g.user loaded: {g.user.name} (ID: {g.user.id}, Is Admin: {g.user.is_admin})")
                session['user_name'] = g.user.name
                session['is_admin'] = g.user.is_admin
                session.permanent = True
                session.modified = True
                print(f"  Session after g.user load and modification: {dict(session)}")
            else:
                print(f"  WARNING: No user found in DB for session user_id: {user_id}. Clearing session.")
                session.pop('user_id', None)
                session.pop('user_name', None)
                session.pop('is_admin', None)
                session.modified = True
                print(f"  Session after clear: {dict(session)}")
        except Exception as e:
            print(f"  ERROR: Exception loading user for ID {user_id}: {e}. Clearing session and rolling back.")
            session.pop('user_id', None)
            session.pop('user_name', None)
            session.pop('is_admin', None)
            session.modified = True
            db.session.rollback()
    else:
        print("  INFO: No user_id found in session.")
    print(f"  Final g.user status (is not None): {g.user is not None}")
    print(f"--- END BEFORE REQUEST HOOK ---")

# --- Route Decorators ---
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"\n--- LOGIN REQUIRED DECORATOR INVOKED for {request.path} ({datetime.now().strftime('%H:%M:%S')}) ---")
        print(f"  Current session state at decorator entry: {dict(session)}")
        print(f"  Checking for 'user_id' in session: {'user_id' in session}")
        if 'user_id' not in session:
            print("  FAIL: User ID NOT found in session. Redirecting to /account.")
            session['next'] = request.url
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('account'))
        print("  SUCCESS: User ID found in session. Proceeding with route function.")
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Access denied. You are not authorized to view this page.', 'danger')
            if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
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
    all_products = Product.query.all()
    return render_template('home.html',
                           milk_products=milk_products,
                           cheese_products=cheese_products,
                           butter_products=butter_products,
                           all_products=all_products,
                           datetime=datetime)

@app.route('/account', methods=['GET'])
def account():
    return render_template('account.html', datetime=datetime)

@app.route('/send_otp', methods=['POST'])
def send_otp():
    phone_raw = request.form.get('phone')
    name = request.form.get('name')
    session['next'] = request.form.get('next', session.get('next', url_for('home')))

    if not phone_raw or not phone_raw.replace('+', '').isdigit() or len(phone_raw.replace('+', '')) < 9:
        flash("Please enter a valid phone number (digits only, at least 9 digits, optional '+').", 'danger')
        return redirect(url_for('account'))

    if phone_raw.startswith('09') and len(phone_raw) == 10:
        phone = '+251' + phone_raw[1:]
    elif not phone_raw.startswith('+'):
        phone = '+251' + phone_raw
    else:
        phone = phone_raw

    otp = str(random.randint(100000, 999999))
    session['otp_code'] = otp
    session['otp_phone'] = phone
    session['otp_timestamp'] = datetime.now().timestamp()
    session['action_type'] = 'login' if User.query.filter_by(phone=phone).first() else 'signup'
    if session['action_type'] == 'signup' and not name:
        flash("Full name is required for signup.", 'danger')
        return redirect(url_for('account'))
    if name:
        session['signup_name'] = name
    session.modified = True

    print(f"🔐 OTP for {phone} is: {otp}")

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
            return redirect(url_for('account'))
        except Exception as e:
            app.logger.error(f"General error sending OTP to {phone}: {e}")
            flash("An unexpected error occurred while sending OTP. Please try again.", 'danger')
            return redirect(url_for('account'))
    else:
        flash(f"OTP simulation: {otp}. Please check your console.", 'info')

    return redirect(url_for('verify_otp_page', phone=phone))

@app.route('/resend_otp', methods=['POST'])
def resend_otp():
    phone = session.get('otp_phone')
    action_type = session.get('action_type')

    if not phone or not action_type:
        flash("No active OTP request found. Please start from the account page.", 'danger')
        return redirect(url_for('account'))

    otp = str(random.randint(100000, 999999))
    session['otp_code'] = otp
    session['otp_timestamp'] = datetime.now().timestamp()
    session.modified = True

    if twilio_client and TWILIO_PHONE_NUMBER:
        try:
            message = twilio_client.messages.create(
                to=phone,
                from_=TWILIO_PHONE_NUMBER,
                body=f"Your new OTP is: {otp} for Baba Milk App verification."
            )
            print(f"Twilio message SID (resend): {message.sid}")
            flash(f"A new OTP has been sent to {phone}.", 'info')
        except TwilioRestException as e:
            app.logger.error(f"Twilio error resending OTP to {phone}: {e}")
            flash("Failed to resend OTP. Please try again or check your phone number.", 'danger')
            return redirect(url_for('account'))
        except Exception as e:
            app.logger.error(f"General error resending OTP to {phone}: {e}")
            flash("An error occurred while resending OTP. Please try again.", 'danger')
            return redirect(url_for('account'))
    else:
        print(f"\n--- RESENT OTP for {phone} is: {otp} (Action: {action_type}) ---\n")
        flash(f"A new OTP has been sent to {phone}. Check your console.", 'info')

    return redirect(url_for('verify_otp_page', phone=phone))

@app.route('/verify_otp', methods=['GET'])
def verify_otp_page():
    phone = session.get('otp_phone')
    if not phone:
        flash("Session expired or no OTP request found. Please start again.", 'danger')
        return redirect(url_for('account'))
    return render_template('verify_otp.html', phone=phone, datetime=datetime)

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    user_otp = request.form.get('otp')
    phone = session.get('otp_phone')
    stored_otp = session.get('otp_code')
    otp_timestamp = session.get('otp_timestamp')
    action_type = session.get('action_type')

    if not all([user_otp, phone, stored_otp, action_type, otp_timestamp]):
        flash("Missing OTP verification data. Please try again from the account page.", 'danger')
        session.clear()
        session.modified = True
        return redirect(url_for('account'))

    if datetime.now().timestamp() > otp_timestamp + 300:
        flash("OTP has expired. Please request a new one.", 'danger')
        session.clear()
        session.modified = True
        return redirect(url_for('account'))

    if user_otp != stored_otp:
        flash("Invalid OTP. Please try again.", 'danger')
        return redirect(url_for('verify_otp_page', phone=phone))

    user = User.query.filter_by(phone=phone).first()

    if action_type == 'signup':
        name = session.get('signup_name')
        if user:
            flash("Account already exists. Please log in.", 'warning')
            session.clear()
            session.modified = True
            return redirect(url_for('account'))
        if not name:
            flash("Signup failed. Missing name required for signup.", 'danger')
            session.clear()
            session.modified = True
            return redirect(url_for('account'))

        user = User(name=name, phone=phone, password=generate_password_hash(stored_otp))
        db.session.add(user)
        db.session.commit()
        flash("Account created successfully!", 'success')

    elif action_type == 'login':
        if not user:
            flash("Login failed. No account found for this phone number.", 'danger')
            session.clear()
            session.modified = True
            return redirect(url_for('account'))
        flash(f"Welcome back, {user.name}!", 'success')

    session['user_id'] = user.id
    session['user_name'] = user.name
    session['is_admin'] = user.is_admin
    session.permanent = True

    guest_cart = session.pop('cart', {})
    if guest_cart and user.id:
        try:
            for pid_str, item in guest_cart.items():
                pid = int(pid_str)
                qty = int(item.get('quantity', 1))
                existing_item = CartItem.query.filter_by(user_id=user.id, product_id=pid).first()
                if existing_item:
                    existing_item.quantity += qty
                else:
                    db.session.add(CartItem(user_id=user.id, product_id=pid, quantity=qty))
            db.session.commit()
        except Exception as e:
            app.logger.error(f"Error merging cart for user {user.id}: {e}")
            db.session.rollback()
            flash("Unable to merge your cart items. Please review your cart.", 'warning')

    for key in ['otp_code', 'otp_phone', 'otp_timestamp', 'signup_name', 'action_type']:
        session.pop(key, None)
    session.modified = True

    next_url = session.pop('next', url_for('dashboard' if user else 'home'))
    return redirect(next_url)

@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('is_admin', None)
    session.pop('delivery_info', None)
    session.pop('cart', None)
    session.modified = True
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home'))

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    try:
        data = request.get_json()
        if not data or not isinstance(data.get('product_id'), str):
            return jsonify({'success': False, 'message': 'Invalid product ID format.'}), 400

        product_id_str = str(data['product_id'])
        try:
            product_id_int = int(product_id_str)
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid product ID format.'}), 400

        product = Product.query.get(product_id_int)
        if not product:
            return jsonify({'success': False, 'message': 'Product not found'}), 404

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
                'image_path': product.image_path or 'default.png',
                'quantity': 1
            }

        session['cart'] = cart
        session.modified = True

        total_quantity = sum(item['quantity'] for item in cart.values())
        return jsonify({'success': True, 'message': f'{product.name} added to cart!', 'total_quantity': total_quantity})

    except Exception as e:
        app.logger.error(f"Error adding to cart: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred while adding to cart.'}), 500

@app.route('/get_cart_count')
def get_cart_count():
    try:
        total_quantity = 0
        if 'cart' in session:
            cart = session['cart']
            if not isinstance(cart, dict):
                app.logger.error(f"Invalid cart format in session: {cart}")
                session.pop('cart', None)
                session.modified = True
                return jsonify({'cart_count': 0}), 200
            total_quantity = sum(item.get('quantity', 0) for item in cart.values() if isinstance(item, dict))
        return jsonify({'cart_count': total_quantity}), 200
    except Exception as e:
        app.logger.error(f"Error in get_cart_count: {e}")
        return jsonify({'cart_count': 0}), 200

@app.route('/get_cart_items')
def get_cart_items():
    try:
        cart_data = session.get('cart', {})
        if not isinstance(cart_data, dict):
            app.logger.error(f"Invalid cart format in session: {cart_data}")
            session.pop('cart', None)
            session.modified = True
            return jsonify({'cart_items': []}), 200

        items_list = []
        for product_id_str, item_data in cart_data.items():
            if not isinstance(item_data, dict):
                continue
            items_list.append({
                'id': product_id_str,
                'name': item_data.get('name', 'Unknown'),
                'price': item_data.get('price', 0.0),
                'image_url': url_for('static', filename='images/' + item_data.get('image_path', 'default.png')),
                'quantity': item_data.get('quantity', 1)
            })
        return jsonify({'cart_items': items_list}), 200
    except Exception as e:
        app.logger.error(f"Error in get_cart_items: {e}")
        return jsonify({'cart_items': []}), 200

@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))
        new_quantity = data.get('quantity')

        if new_quantity is None or not isinstance(new_quantity, int) or new_quantity < 0:
            return jsonify({'success': False, 'message': 'Invalid product ID or quantity.'}), 400

        cart = session.get('cart', {})
        if not isinstance(cart, dict):
            app.logger.error(f"Invalid cart format in session: {cart}")
            session.pop('cart', None)
            session.modified = True
            return jsonify({'success': False, 'message': 'Cart data corrupted. Please add items again.'}), 500

        if product_id not in cart:
            return jsonify({'success': False, 'message': 'Item not found in cart.'}), 404

        if new_quantity == 0:
            item_name = cart[product_id].get('name', 'Item')
            del cart[product_id]
            message = f"Removed {item_name} from cart."
        else:
            cart[product_id]['quantity'] = new_quantity
            message = f"Quantity of {cart[product_id].get('name', 'Item')} updated to {new_quantity}."

        session['cart'] = cart
        session.modified = True
        
        return jsonify({'success': True, 'message': message})

    except Exception as e:
        app.logger.error(f"Error updating cart quantity: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred while updating quantity.'}), 500

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))

        cart = session.get('cart', {})
        if not isinstance(cart, dict):
            app.logger.error(f"Invalid cart format in session: {cart}")
            session.pop('cart', None)
            session.modified = True
            return jsonify({'success': False, 'message': 'Cart data corrupted. Please add items again.'}), 500

        if product_id not in cart:
            return jsonify({'success': False, 'message': 'Item not found in cart.'}), 404

        item_name = cart[product_id].get('name', 'Item')
        del cart[product_id]
        session['cart'] = cart
        session.modified = True

        return jsonify({'success': True, 'message': f'{item_name} removed from cart.'})

    except Exception as e:
        app.logger.error(f"Error removing item from cart: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred while removing item.'}), 500

@app.route('/cart')
def cart():
    user_address = g.user.address if g.user and g.user.address else ''
    user_phone = g.user.phone if g.user and g.user.phone else ''
    return render_template('cart.html', user_address=user_address, user_phone=user_phone, datetime=datetime)

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    session['next'] = url_for('payment')
    delivery_name = request.form.get('delivery_name', session.get('user_name', '')) 
    delivery_phone = request.form.get('delivery_phone')
    delivery_address = request.form.get('delivery_address')

    if not all([delivery_phone, delivery_address]): 
        flash("Please provide both delivery phone and address.", 'danger')
        return redirect(url_for('cart'))

    if not delivery_phone.replace('+', '').isdigit() or len(delivery_phone.replace('+', '')) < 9:
        flash("Please enter a valid phone number (digits only, at least 9 digits, optional '+').", 'danger')
        return redirect(url_for('cart'))
        
    if delivery_phone.startswith('09') and len(delivery_phone) == 10:
        delivery_phone = '+251' + delivery_phone[1:]
    elif not delivery_phone.startswith('+'):
        delivery_phone = '+251' + delivery_phone

    cart_items_session = session.get('cart', {})
    if not cart_items_session:
        if g.user:
            user_db_cart_items = CartItem.query.filter_by(user_id=g.user.id).all()
            if user_db_cart_items:
                for db_item in user_db_cart_items:
                    cart_items_session[str(db_item.product_id)] = {
                        'id': str(db_item.product_id),
                        'name': db_item.product.name,
                        'price': float(db_item.product.price),
                        'image_path': db_item.product.image_path or 'default.png',
                        'quantity': db_item.quantity
                    }
                session['cart'] = cart_items_session
                session.modified = True
            else:
                flash("Your cart is empty. Please add items before checking out.", 'warning')
                return redirect(url_for('cart'))
        else:
            flash("Your cart is empty. Please add items before checking out.", 'warning')
            return redirect(url_for('cart'))

    total_amount = sum(item['price'] * item['quantity'] for item in cart_items_session.values())

    session['delivery_info'] = {
        'name': delivery_name,
        'phone': delivery_phone,
        'address': delivery_address,
        'total_amount': total_amount,
        'cart_items': list(cart_items_session.values())
    }
    session.modified = True

    return redirect(url_for('payment'))

@app.route('/payment')
@login_required
def payment():
    delivery_info = session.get('delivery_info')
    if not delivery_info:
        flash("Please complete checkout details from the cart page.", 'warning')
        session['next'] = url_for('payment')
        return redirect(url_for('cart'))

    total_amount = delivery_info.get('total_amount')
    cart_items = delivery_info.get('cart_items')

    return render_template('payment.html', total_amount=total_amount, cart_items=cart_items, datetime=datetime)

@app.route('/finalize_order', methods=['POST'])
@login_required
def finalize_order():
    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        flash('User session invalid. Please log in again.', 'danger')
        session['next'] = url_for('payment')
        return redirect(url_for('account'))

    delivery_info = session.get('delivery_info')
    if not delivery_info or not delivery_info.get('address') or not delivery_info.get('phone') or not delivery_info.get('cart_items'):
        flash("Checkout information incomplete. Please start from cart.", 'danger')
        return redirect(url_for('cart'))

    user_db_cart_items = CartItem.query.filter_by(user_id=user_id).all()
    if not user_db_cart_items:
        flash("Your cart is empty. Please add items before checking out.", 'warning')
        return redirect(url_for('cart'))

    server_validated_total = 0.0
    order_items_to_add = []
    
    for db_item in user_db_cart_items:
        product = Product.query.get(db_item.product_id)
        if not product:
            flash(f"One of the products in your cart ({db_item.product.name if db_item.product else 'Unknown'}) is no longer available. Please review your cart.", 'danger')
            return redirect(url_for('cart'))

        item_total = product.price * db_item.quantity
        server_validated_total += item_total
        order_items_to_add.append({
            'product_id': product.id,
            'quantity': db_item.quantity,
            'price': product.price
        })

    payment_method = request.form.get('payment_method')
    payment_detail_info = {}
    status = 'placed'

    if payment_method == 'telebirr':
        payment_detail_info['phone'] = request.form.get('telebirr_phone')
        if not payment_detail_info['phone'] or not payment_detail_info['phone'].replace('+', '').isdigit():
            flash('Please provide a valid Telebirr phone number.', 'danger')
            return redirect(url_for('payment'))
        if payment_detail_info['phone'].startswith('09') and len(payment_detail_info['phone']) == 10:
            payment_detail_info['phone'] = '+251' + payment_detail_info['phone'][1:]
        elif not payment_detail_info['phone'].startswith('+'):
            payment_detail_info['phone'] = '+251' + payment_detail_info['phone']
        status = 'pending_payment_telebirr'
    elif payment_method == 'cbebirr':
        payment_detail_info['phone'] = request.form.get('cbebirr_phone')
        if not payment_detail_info['phone'] or not payment_detail_info['phone'].replace('+', '').isdigit():
            flash('Please provide a valid CBE Birr phone number.', 'danger')
            return redirect(url_for('payment'))
        if payment_detail_info['phone'].startswith('09') and len(payment_detail_info['phone']) == 10:
            payment_detail_info['phone'] = '+251' + payment_detail_info['phone'][1:]
        elif not payment_detail_info['phone'].startswith('+'):
            payment_detail_info['phone'] = '+251' + payment_detail_info['phone']
        status = 'pending_payment_cbebirr'
    elif payment_method != 'cash_on_delivery':
        flash('Please select a valid payment method.', 'danger')
        return redirect(url_for('payment'))

    try:
        new_order = Order(
            user_id=g.user.id,
            total_amount=server_validated_total,
            delivery_address=delivery_info['address'],
            delivery_phone=delivery_info['phone'],
            payment_method=payment_method,
            payment_details=json.dumps(payment_detail_info),
            status=status
        )
        db.session.add(new_order)
        db.session.flush()

        for item_data in order_items_to_add:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item_data['product_id'],
                quantity=item_data['quantity'],
                price_at_purchase=item_data['price']
            )
            db.session.add(order_item)
            
        CartItem.query.filter_by(user_id=user_id).delete()
        
        session.pop('cart', None)
        session.pop('delivery_info', None)
        session.modified = True

        db.session.commit()
        flash("Your order has been placed successfully! Check your dashboard for details.", 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        db.session.rollback()
        print(f"Error finalizing order: {e}")
        flash("An error occurred while placing your order. Please try again.", 'danger')
        return redirect(url_for('cart'))

@app.route('/dashboard')
@login_required
def dashboard():
    orders = Order.query.filter_by(user_id=g.user.id).order_by(Order.order_date.desc()).all()
    return render_template('dashboard.html', orders=orders, datetime=datetime)

@app.route('/admin')
@admin_required
def admin():
    orders = Order.query.order_by(Order.order_date.desc()).all()
    orders_for_template = []
    for order in orders:
        items_detail = []
        for item in order.order_items:
            items_detail.append(f"{item.product.name} (x{item.quantity})")
        
        current_status_index = -1
        tracker_statuses_admin = ['placed', 'confirmed', 'packed', 'out_for_delivery', 'delivered']
        if order.status.startswith('pending_payment'):
            current_status_index = 0
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
            'tracker_statuses': tracker_statuses_admin
        })
    return render_template('admin.html', orders=orders_for_template, datetime=datetime)

@app.route('/update_order_status', methods=['POST'])
@admin_required
def update_order_status():
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')

    valid_statuses = [
        'placed', 'pending_payment_telebirr', 'pending_payment_cbebirr',
        'confirmed', 'packed', 'out_for_delivery', 'delivered', 'cancelled'
    ]

    if not order_id or not new_status:
        flash('Missing order ID or status. Please try again.', 'danger')
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

@app.route('/search_products', methods=['GET'])
def search_products():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify(products=[]), 200

    search_pattern = f"%{query}%"
    products = Product.query.filter(
        (Product.name.ilike(search_pattern)) |
        (Product.description.ilike(search_pattern))
    ).all()

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

@app.route('/about_us')
def about_us():
    return render_template('about_us.html', datetime=datetime)

# --- Data Population ---
products_data = [
    {"name": "Fresh Cow Milk (1L)", "category": "milk", "price": 80.00, "image_suffix": "1", "description": "Pure, pasteurized cow milk, delivered fresh daily."},
    {"name": "Organic Whole Milk (1L)", "category": "milk", "price": 95.00, "image_suffix": "2", "description": "Sourced from organic farms, rich in nutrients and flavor."},
    {"name": "Low-Fat Milk (1L)", "category": "milk", "price": 70.00, "image_suffix": "3", "description": "A healthy choice with reduced fat content, perfect for everyday use."},
    {"name": "Lactose-Free Milk (1L)", "category": "milk", "price": 110.00, "image_suffix": "4", "description": "Easy to digest, all the goodness of milk without lactose."},
    {"name": "Skim Milk (1L)", "category": "milk", "price": 65.00, "image_suffix": "5", "description": "Virtually fat-free, ideal for health-conscious individuals."},
    {"name": "Goat Milk (500ml)", "category": "milk", "price": 120.00, "image_suffix": "6", "description": "Nutrient-rich goat milk, a great alternative for sensitive stomachs."},
    {"name": "Almond Milk (1L)", "category": "milk", "price": 100.00, "image_suffix": "7", "description": "Dairy-free almond milk, perfect for vegans or those with intolerances."},
    {"name": "Soy Milk (1L)", "category": "milk", "price": 90.00, "image_suffix": "8", "description": "Plant-based soy milk, high in protein and versatile."},
    {"name": "Chocolate Milk (2L)", "category": "milk", "price": 95.00, "image_suffix": "9", "description": "Rich chocolate-flavored milk, a treat for all ages."},
    {"name": "Strawberry Milk (500ml)", "category": "milk", "price": 95.00, "image_suffix": "10", "description": "Sweet strawberry-flavored milk, a fun drink for kids."},
    {"name": "Cheddar Cheese (200g)", "category": "cheese", "price": 150.00, "image_suffix": "11", "description": "Classic sharp cheddar cheese block, aged to perfection."},
    {"name": "Mozzarella Cheese (200g)", "category": "cheese", "price": 130.00, "image_suffix": "12", "description": "Perfect for pizzas and pastas, melts beautifully and stretches."},
    {"name": "Feta Cheese (150g)", "category": "cheese", "price": 120.00, "image_suffix": "13", "description": "Tangy and salty, ideal for salads and Mediterranean dishes."},
    {"name": "Gouda Cheese (200g)", "category": "cheese", "price": 160.00, "image_suffix": "14", "description": "Semi-hard cheese with a mild, nutty flavor."},
    {"name": "Cream Cheese (250g)", "category": "cheese", "price": 100.00, "image_suffix": "15", "description": "Smooth and spreadable, great for bagels and cooking."},
    {"name": "Parmesan Cheese (100g)", "category": "cheese", "price": 180.00, "image_suffix": "16", "description": "Hard, granular cheese perfect for grating over pasta."},
    {"name": "Ricotta Cheese (250g)", "category": "cheese", "price": 90.00, "image_suffix": "17", "description": "Soft and creamy, ideal for Italian desserts and savory dishes."},
    {"name": "Cottage Cheese (250g)", "category": "cheese", "price": 80.00, "image_suffix": "18", "description": "High in protein, a versatile and healthy snack."},
    {"name": "Swiss Cheese (200g)", "category": "cheese", "price": 140.00, "image_suffix": "19", "description": "Distinctive holes and a mild, nutty taste."},
    {"name": "Provolone Cheese (200g)", "category": "cheese", "price": 135.00, "image_suffix": "20", "description": "Versatile cheese, great for sandwiches and melting."},
    {"name": "Plain Yogurt (500g)", "category": "yogurt", "price": 70.00, "image_suffix": "21", "description": "Creamy and natural plain yogurt, great for breakfast or cooking."},
    {"name": "Strawberry Yogurt (200g)", "category": "yogurt", "price": 55.00, "image_suffix": "22", "description": "Sweet strawberry-flavored yogurt, a delightful snack."},
    {"name": "Vanilla Bean Yogurt (200g)", "category": "yogurt", "price": 60.00, "image_suffix": "23", "description": "Smooth vanilla yogurt with real bean specks."},
    {"name": "Greek Yogurt (250g)", "category": "yogurt", "price": 85.00, "image_suffix": "24", "description": "Thick and protein-rich Greek yogurt."},
    {"name": "Blueberry Yogurt (200g)", "category": "yogurt", "price": 58.00, "image_suffix": "25", "description": "Fruity yogurt with juicy blueberries."},
    {"name": "Mango Yogurt (200g)", "category": "yogurt", "price": 58.00, "image_suffix": "26", "description": "Tropical mango-flavored yogurt."},
    {"name": "Honey Yogurt (200g)", "category": "yogurt", "price": 62.00, "image_suffix": "27", "description": "Naturally sweetened with pure honey."},
    {"name": "Peach Yogurt (200g)", "category": "yogurt", "price": 55.00, "image_suffix": "28", "description": "Refreshing peach-flavored yogurt."},
    {"name": "Low-Fat Yogurt (500g)", "category": "yogurt", "price": 65.00, "image_suffix": "29", "description": "Healthy low-fat option for everyday consumption."},
    {"name": "Probiotic Yogurt (200g)", "category": "yogurt", "price": 75.00, "image_suffix": "30", "description": "Contains live cultures for digestive health."},
    {"name": "Salted Butter (250g)", "category": "butter", "price": 90.00, "image_suffix": "31", "description": "Rich and creamy salted butter, perfect for spreading."},
    {"name": "Unsalted Butter (250g)", "category": "butter", "price": 90.00, "image_suffix": "32", "description": "Pure, unsalted butter for baking and cooking, allows flavor control."},
    {"name": "Ghee (Clarified Butter, 500g)", "category": "butter", "price": 200.00, "image_suffix": "33", "description": "Traditional clarified butter, rich flavor and high smoke point."},
    {"name": "Garlic Herb Butter (150g)", "category": "butter", "price": 110.00, "image_suffix": "34", "description": "Infused with garlic and herbs, perfect for steaks or bread."},
    {"name": "Whipped Butter (200g)", "category": "butter", "price": 85.00, "image_suffix": "35", "description": "Light and airy whipped butter, easy to spread."},
    {"name": "Cultured Butter (250g)", "category": "butter", "price": 105.00, "image_suffix": "36", "description": "Tangy and flavorful, made from cultured cream."},
    {"name": "European Style Butter (250g)", "category": "butter", "price": 115.00, "image_suffix": "37", "description": "Higher fat content for richer taste and texture."},
    {"name": "Light Butter (250g)", "category": "butter", "price": 75.00, "image_suffix": "38", "description": "Reduced-fat butter alternative."},
    {"name": "Brown Butter (100g)", "category": "butter", "price": 130.00, "image_suffix": "39", "description": "Nutty and aromatic, great for desserts and savory dishes."},
    {"name": "Avocado Oil Butter (250g)", "category": "butter", "price": 125.00, "image_suffix": "40", "description": "Blend of butter and healthy avocado oil."}
]

@app.cli.command('init-db')
def init_db_command():
    with app.app_context():
        db.create_all()
        print("Database initialized.")
        
        print("Deleting all existing products...")
        Product.query.delete()
        db.session.commit()
        print("Existing products deleted.")

        print("Populating products with new data...")
        for p_data in products_data:
            image_name = f"product{p_data['image_suffix']}.png"
            new_product = Product(
                name=p_data['name'],
                category=p_data['category'],
                price=p_data['price'],
                image_path=image_name,
                description=p_data.get('description')
            )
            db.session.add(new_product)
        db.session.commit()
        print(f"Total {len(products_data)} products added.")

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
        db.create_all()
    app.run(debug=True)