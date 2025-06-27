from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
import json
import random
import string
from functools import wraps
from flask_migrate import Migrate
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import re

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_baba_milk_very_secret_and_long")
app.config['SESSION_COOKIE_NAME'] = 'baba_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Database Configuration
db_url = os.environ.get("DATABASE_URL", "sqlite:///baba_milk.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://")
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # ✅ Add this line
    is_admin = db.Column(db.Boolean, default=False)
    address = db.Column(db.String(200), nullable=True)
    orders = db.relationship('Order', backref='customer', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_path = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    user = db.relationship('User', backref='cart_items')
    product = db.relationship('Product')
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='_user_product_uc'),)

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
        return ", ".join(f"{item.product.name} (x{item.quantity})" for item in self.order_items)

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

# Context Processor
@app.context_processor
def utility_processor():
    return dict(current_year=datetime.now().year)

# Before Request Hook
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = None
    otp_timestamp = session.get('otp_timestamp')
    if otp_timestamp and (datetime.now().timestamp() - otp_timestamp > 300):
        for key in ['otp_code', 'otp_phone', 'otp_timestamp', 'signup_name', 'action_type']:
            session.pop(key, None)
        session.modified = True
        if request.path in ['/verify_otp', '/resend_otp']:
            flash("Your OTP has expired. Please request a new one.", 'warning')
    if user_id:
        try:
            g.user = User.query.get(user_id)
            if g.user:
                session['user_name'] = g.user.name
                session['is_admin'] = g.user.is_admin
                session.permanent = True
                session.modified = True
            else:
                session.pop('user_id', None)
                session.pop('user_name', None)
                session.pop('is_admin', None)
                session.modified = True
                db.session.rollback()
        except Exception as e:
            session.pop('user_id', None)
            session.pop('user_name', None)
            session.pop('is_admin', None)
            session.modified = True
            db.session.rollback()

# Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            session['next'] = request.url
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('account'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            if 'user_id' in session:
                flash('Access denied. You are not authorized to view this page.', 'danger')
                return redirect(url_for('dashboard'))
            else:
                flash('Please login as an admin to access this page.', 'warning')
                session['next'] = request.url
                return redirect(url_for('account'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@app.route('/home')
def home():
    all_products = Product.query.all()
    return render_template('home.html', all_products=all_products)

@app.route('/account', methods=['GET'])
def account():
    return render_template('account.html')

@app.route('/send_otp', methods=['POST'])
def send_otp():
    print("=== Received POST to /send_otp ===")
    phone_raw = request.form.get('phone')
    name = request.form.get('name').strip() if request.form.get('name') else None
    next_url = request.form.get('next', session.get('next', url_for('home')))
    print(f"Input: phone_raw={phone_raw}, name={name}, next_url={next_url}")
    
    if not phone_raw:
        flash("Phone number is required.", 'danger')
        print("Error: Phone number missing")
        return redirect(url_for('account'))
    
    phone_regex = r'^\+\d{10,15}$'
    if not re.match(phone_regex, phone_raw):
        flash("Please enter a valid international phone number (e.g., +12025550123 or +251912345678).", 'danger')
        print(f"Error: Invalid phone number format: {phone_raw}")
        return redirect(url_for('account'))
    
    phone = phone_raw
    print(f"Normalized phone: {phone}")
    
    user_exists = User.query.filter_by(phone=phone).first()
    if not user_exists and not name:
        flash("Full name is required for signup.", 'danger')
        print("Error: Name missing for signup")
        return redirect(url_for('account') + '#name-field')
    
    otp = ''.join(random.choices(string.digits, k=6))
    session['otp_code'] = otp
    session['otp_phone'] = phone
    session['otp_timestamp'] = datetime.now().timestamp()
    session['action_type'] = 'login' if user_exists else 'signup'
    session['signup_name'] = name if name else None
    session['next'] = next_url
    session.modified = True
    print(f"Session set: OTP={otp}, Phone={phone}, Action={session['action_type']}, Name={name}")
    
    if twilio_client and TWILIO_PHONE_NUMBER:
        print(f"Attempting Twilio SMS to {phone} from {TWILIO_PHONE_NUMBER}")
        try:
            message = twilio_client.messages.create(
                to=phone,
                from_=TWILIO_PHONE_NUMBER,
                body=f"Your Baba Milk App verification code is: {otp}"
            )
            print(f"Twilio success: SID={message.sid}")
            flash(f"An OTP has been sent to {phone}.", 'info')
        except TwilioRestException as e:
            print(f"Twilio error sending OTP to {phone}: {e}")
            flash(f"Failed to send OTP: {str(e)}. Please check your phone number or use console OTP.", 'danger')
            print(f"🔐 OTP for {phone}: {otp} (Twilio failed, using console fallback)")
        except Exception as e:
            print(f"General error sending OTP to {phone}: {e}")
            flash("An unexpected error occurred while sending OTP. Please try again.", 'danger')
            return redirect(url_for('account'))
    else:
        print(f"🔐 OTP for {phone}: {otp} (No Twilio client, using console)")
        flash(f"OTP simulation: {otp}. Please check your console.", 'info')
    
    print(f"Redirecting to verify_otp with phone={phone}")
    return redirect(url_for('verify_otp', phone=phone))

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    phone = session.get('otp_phone')
    if not phone:
        flash("Session expired or no OTP request found. Please start again.", 'danger')
        return redirect(url_for('account'))

    if request.method == 'POST':
        user_otp = request.form.get('otp', '').strip()
        stored_otp = session.get('otp_code')
        otp_timestamp = session.get('otp_timestamp')
        action_type = session.get('action_type')

        if not all([user_otp, stored_otp, action_type, otp_timestamp]):
            flash("Missing verification data. Please try again.", 'danger')
            session.clear()
            session.modified = True
            return redirect(url_for('account'))

        # Check OTP expiry (5 min = 300 sec)
        if datetime.now().timestamp() > otp_timestamp + 300:
            flash("OTP has expired. Please request a new one.", 'danger')
            session.clear()
            session.modified = True
            return redirect(url_for('account'))

        if user_otp != stored_otp:
            flash("Invalid OTP. Please try again.", 'danger')
            return redirect(url_for('verify_otp', phone=phone))

        user = User.query.filter_by(phone=phone).first()

        if action_type == 'signup':
            name = session.get('signup_name')  # ✅ FIXED: correct key for name
            if user:
                flash("Account already exists. Please log in.", 'warning')
                session.clear()
                session.modified = True
                return redirect(url_for('account'))

            if not name:
                flash("Signup failed. Missing name.", 'danger')
                session.clear()
                session.modified = True
                return redirect(url_for('account'))

            hashed_password = generate_password_hash(stored_otp)
            user = User(name=name, phone=phone, password=hashed_password)
            db.session.add(user)
            db.session.commit()
            flash("Account created successfully!", 'success')

        elif action_type == 'login':
            if not user:
                flash("No account found for this phone number.", 'danger')
                session.clear()
                session.modified = True
                return redirect(url_for('account'))
            flash(f"Welcome back, {user.name}!", 'success')

        # ✅ Set user session
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['is_admin'] = user.is_admin
        session.permanent = True

        # ✅ Merge guest cart to user cart
        guest_cart = session.pop('cart', {})
        if guest_cart:
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
                db.session.rollback()
                flash("Unable to merge cart items. Please review your cart.", 'warning')

        # ✅ Clean up OTP-related session keys
        for key in ['otp_code', 'otp_phone', 'otp_timestamp', 'signup_name', 'action_type']:
            session.pop(key, None)
        session.modified = True

        next_url = session.pop('next', url_for('dashboard'))
        return redirect(next_url)

    # GET method fallback
    return render_template('verify_otp.html', phone=phone)

@app.route('/resend_otp', methods=['POST'])
def resend_otp():
    phone = session.get('otp_phone')
    action_type = session.get('action_type')
    if not phone or not action_type:
        flash("No active OTP request found. Please start from the account page.", 'danger')
        return redirect(url_for('account'))
    otp = ''.join(random.choices(string.digits, k=6))
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
            print(f"Twilio error resending OTP to {phone}: {e}")
            flash("Failed to resend OTP. Please try again or check your phone number.", 'danger')
            return redirect(url_for('account'))
        except Exception as e:
            print(f"General error resending OTP to {phone}: {e}")
            flash("An error occurred while resending OTP. Please try again.", 'danger')
            return redirect(url_for('account'))
    else:
        print(f"Resent OTP for {phone}: {otp}")
        flash(f"A new OTP has been sent to {phone}. Check your console.", 'info')
    return redirect(url_for('verify_otp', phone=phone))

@app.route('/cart', methods=['GET', 'POST'])
@login_required
def cart():
    user_address = g.user.address if g.user and g.user.address else ''
    user_phone = g.user.phone if g.user and g.user.phone else ''
    if request.method == 'POST':
        delivery_name = request.form.get('delivery_name')
        delivery_phone = request.form.get('delivery_phone')
        delivery_address = request.form.get('delivery_address')
        errors = []
        if not delivery_phone:
            errors.append("Please provide a delivery phone number.")
        if not delivery_address:
            errors.append("Please provide a delivery address.")
        if delivery_phone and (not delivery_phone.replace('+', '').isdigit() or len(delivery_phone.replace('+', '')) < 9):
            errors.append("Please enter a valid phone number (digits only, at least 9 digits, optional '+').")
        if errors:
            for error in errors:
                flash(error, 'danger')
            session['delivery_info'] = {
                'name': delivery_name or '',
                'phone': delivery_phone or '',
                'address': delivery_address or ''
            }
            session.modified = True
            return redirect(url_for('cart'))
        if delivery_phone.startswith('09') and len(delivery_phone) == 10:
            delivery_phone = '+251' + delivery_phone[1:]
        elif not delivery_phone.startswith('+'):
            delivery_phone = '+251' + delivery_phone
        cart = session.get('cart', {})
        if not cart:
            flash("Your cart is empty. Please add items before checking out.", 'warning')
            session['delivery_info'] = {
                'name': delivery_name or '',
                'phone': delivery_phone,
                'address': delivery_address
            }
            session.modified = True
            return redirect(url_for('cart'))
        total_amount = sum(float(item['price']) * item['quantity'] for item in cart.values())
        session['delivery_info'] = {
            'name': delivery_name or '',
            'phone': delivery_phone,
            'address': delivery_address,
            'total_amount': total_amount,
            'cart_items': list(cart.values())
        }
        session.modified = True
        return redirect(url_for('payment'))
    return render_template('cart.html', user_address=user_address, user_phone=user_phone, delivery_info=session.get('delivery_info', {}))

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))
        quantity = int(data.get('quantity', 1))
        product = Product.query.get(int(product_id))
        if not product:
            return jsonify({'success': False, 'message': 'Product not found.'}), 404
        cart = session.get('cart', {})
        if product_id in cart:
            cart[product_id]['quantity'] += quantity
        else:
            cart[product_id] = {
                'name': product.name,
                'price': float(product.price),
                'image_path': product.image_path or 'default.png',
                'quantity': quantity
            }
        session['cart'] = cart
        session.modified = True
        return jsonify({'success': True, 'cart_count': sum(item['quantity'] for item in cart.values())})
    except Exception as e:
        print(f"Error adding to cart: {e}")
        return jsonify({'success': False, 'message': 'Error adding to cart.'}), 500

@app.route('/get_cart_count')
def get_cart_count():
    try:
        total_quantity = sum(item['quantity'] for item in session.get('cart', {}).values() if isinstance(item, dict))
        return jsonify({'count': total_quantity}), 200
    except Exception:
        return jsonify({'count': 0}), 200

@app.route('/get_cart_items')
def get_cart_items():
    try:
        cart_data = session.get('cart', {})
        items_list = [
            {
                'id': pid,
                'name': item.get('name', 'Unknown'),
                'price': item.get('price', 0.0),
                'image_url': url_for('static', filename='images/' + item.get('image_path', 'default.png')),
                'quantity': item.get('quantity', 1)
            }
            for pid, item in cart_data.items() if isinstance(item, dict)
        ]
        return jsonify({'cart_items': items_list}), 200
    except Exception:
        return jsonify({'cart_items': []}), 200

@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))
        new_quantity = data.get('quantity')
        if new_quantity is None or not isinstance(new_quantity, int) or new_quantity < 0:
            return jsonify({'success': False, 'message': 'Invalid quantity.'}), 400
        cart = session.get('cart', {})
        if product_id not in cart:
            return jsonify({'success': False, 'message': 'Item not in cart.'}), 404
        if new_quantity == 0:
            item_name = cart[product_id]['name']
            del cart[product_id]
            message = f"Removed {item_name} from cart."
        else:
            cart[product_id]['quantity'] = new_quantity
            message = f"Updated {cart[product_id]['name']} to {new_quantity}."
        session['cart'] = cart
        session.modified = True
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        print(f"Error updating cart quantity: {e}")
        return jsonify({'success': False, 'message': 'Error updating cart.'}), 500

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))
        cart = session.get('cart', {})
        if product_id not in cart:
            return jsonify({'success': False, 'message': 'Item not in cart.'}), 404
        item_name = cart[product_id]['name']
        del cart[product_id]
        session['cart'] = cart
        session.modified = True
        return jsonify({'success': True, 'message': f'{item_name} removed from cart.'})
    except Exception as e:
        print(f"Error removing item from cart: {e}")
        return jsonify({'success': False, 'message': 'Error removing item.'}), 500

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    delivery_info = session.get('delivery_info')
    if not delivery_info:
        flash("Checkout session expired. Please order again.", 'warning')
        return redirect(url_for('dashboard'))
    total_amount = delivery_info.get('total_amount', 0)
    cart_items = delivery_info.get('cart_items', [])
    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        payment_details = {}
        if payment_method in ['telebirr', 'cbebirr']:
            payment_phone = request.form.get(f'{payment_method}_phone')
            if not payment_phone or not payment_phone.replace('+', '').isdigit():
                flash(f'Please provide a valid {payment_method.title()} phone number.', 'danger')
                return redirect(url_for('payment'))
            if payment_phone.startswith('09') and len(payment_phone) == 10:
                payment_phone = '+251' + payment_phone[1:]
            elif not payment_phone.startswith('+'):
                payment_phone = '+251' + payment_phone
            payment_details['phone'] = payment_phone
        elif payment_method != 'cash_on_delivery':
            flash('Please select a valid payment method.', 'danger')
            return redirect(url_for('payment'))
        session['payment_info'] = {
            'method': payment_method,
            'details': payment_details
        }
        session.modified = True
        return redirect(url_for('finalize_order'))
    return render_template('payment.html', total_amount=total_amount, cart_items=cart_items)

@app.route('/finalize_order', methods=['POST'])
def finalize_order():
    user_id = session.get('user_id')  # Might be None (guest)
    delivery_info = session.get('delivery_info')
    payment_info = session.get('payment_info')
    cart = session.get('cart', {})

    if not delivery_info or not payment_info or not cart:
        flash("Checkout information incomplete. Please start from the cart.", 'danger')
        session['delivery_info'] = delivery_info or {}
        session.modified = True
        return redirect(url_for('cart'))

    try:
        total_amount = sum(float(item['price']) * item['quantity'] for item in cart.values())

        new_order = Order(
            user_id=user_id,  # ✅ None if guest
            total_amount=total_amount,
            delivery_address=delivery_info['address'],
            delivery_phone=delivery_info['phone'],
            payment_method=payment_info['method'],
            payment_details=json.dumps(payment_info['details']),
            status='placed' if payment_info['method'] == 'cash_on_delivery' else f'pending_payment_{payment_info["method"]}'
        )
        db.session.add(new_order)
        db.session.flush()

        for pid, item in cart.items():
            product = Product.query.get(int(pid))
            if not product:
                flash(f"Product {item['name']} is no longer available.", 'danger')
                session['delivery_info'] = delivery_info
                session.modified = True
                return redirect(url_for('cart'))

            order_item = OrderItem(
                order_id=new_order.id,
                product_id=product.id,
                quantity=item['quantity'],
                price_at_purchase=item['price']
            )
            db.session.add(order_item)

        # Only clear database cart if logged in
        if user_id:
            CartItem.query.filter_by(user_id=user_id).delete()

        # Cleanup session
        session.pop('cart', None)
        session.pop('delivery_info', None)
        session.pop('payment_info', None)
        session.modified = True

        db.session.commit()
        flash("Order placed successfully! Check your dashboard for details.", 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        db.session.rollback()
        print(f"Error finalizing order: {e}")
        flash("An error occurred while placing your order. Please try again.", 'danger')
        session['delivery_info'] = delivery_info
        session.modified = True
        return redirect(url_for('cart'))

@app.route('/dashboard')
@login_required
def dashboard():
    orders = Order.query.filter_by(user_id=g.user.id).order_by(Order.order_date.desc()).all()
    return render_template('dashboard.html', orders=orders)

@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        new_status = request.form.get('status')
        valid_statuses = ['placed', 'pending_payment_telebirr', 'pending_payment_cbebirr', 'confirmed', 'packed', 'out_for_delivery', 'delivered', 'cancelled']
        if not order_id or not new_status or new_status not in valid_statuses:
            flash('Invalid order ID or status.', 'danger')
            return redirect(url_for('admin'))
        order = Order.query.get(order_id)
        if order:
            order.status = new_status
            try:
                db.session.commit()
                flash(f'Order {order_id} status updated to {new_status.replace("_", " ").capitalize()}.', 'success')
            except Exception as e:
                db.session.rollback()
                print(f"Error updating order status: {e}")
                flash('Error updating order status.', 'danger')
        else:
            flash('Order not found.', 'danger')
    orders = Order.query.order_by(Order.order_date.desc()).all()
    orders_for_template = [
        {
            'id': order.id,
            'customer': order.customer.name,
            'customer_phone': order.customer.phone,
            'delivery_address': order.delivery_address,
            'items': order.items,
            'date': order.date,
            'total': order.total_amount,
            'payment_method': order.payment_method,
            'payment_details': order.payment_details,
            'status': order.status,
            'current_status_index': order.current_status_index,
            'tracker_statuses': order.tracker_statuses
        }
        for order in orders
    ]
    return render_template('admin.html', orders=orders_for_template)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('account'))

@app.route('/about_us')
def about_us():
     return render_template('about_us.html', datetime=datetime)

@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms_of_service')
def terms_of_service():
    return render_template('terms_of_service.html')

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
    search_results = [
        {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'image_path': url_for('static', filename='images/' + product.image_path),
            'description': product.description,
            'category': product.category
        }
        for product in products
    ]
    return jsonify(products=search_results), 200

# Data Population
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
        Product.query.delete()
        db.session.commit()
        print("Existing products deleted.")
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
                phone="+251911223344",
                is_admin=True,
                address="Admin Office, Addis Ababa"
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin user created (phone: +251911223344).")
        else:
            print("Admin user already exists. Skipping creation.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)