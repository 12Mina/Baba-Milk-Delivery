from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
import json
import secrets
import functools
from flask_migrate import Migrate
import random # Import random for OTP generation

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
    yogurt_products = Product.query.filter_by(category='yogurt').all()
    cheese_products = Product.query.filter_by(category='cheese').all()
    butter_products = Product.query.filter_by(category='butter').all()
    return render_template('home.html',
                           milk_products=milk_products,
                           yogurt_products=yogurt_products,
                           cheese_products=cheese_products,
                           butter_products=butter_products,
                           datetime=datetime) # Ensure datetime is passed

@app.route('/account', methods=['GET']) # Only GET is needed now for rendering the form
def account():
    # Pass datetime to the template for the copyright year in base.html
    return render_template('account.html', datetime=datetime) # Ensure datetime is passed


@app.route('/send_otp', methods=['POST'])
def send_otp():
    phone = request.form.get('phone')
    name = request.form.get('name') # name will be provided for signup

    if not phone:
        flash("Phone number is required.", 'danger')
        return redirect(url_for('account'))

    # Validate phone format
    if not phone.isdigit() or len(phone) < 9:
        flash("Please enter a valid phone number (digits only, at least 9 digits).", 'danger')
        return redirect(url_for('account'))

    user = User.query.filter_by(phone=phone).first()

    action_type = ''
    if user:
        action_type = 'login'
        # If logging in, name is optional, so we don't strictly require it.
        # But if provided, it's ignored for login.
        flash("Account found. Sending OTP for login.", 'info')
    else:
        action_type = 'signup'
        if not name:
            flash("Full name is required for new accounts (signup).", 'danger')
            return redirect(url_for('account'))
        session['signup_name'] = name # Store name for later account creation
        flash("No account found. Sending OTP for signup.", 'info')

    otp = str(random.randint(100000, 999999)) # 6-digit OTP
    session['otp'] = otp
    session['otp_phone'] = phone # Store phone number associated with this OTP
    session['otp_timestamp'] = datetime.now().timestamp() # Store timestamp for OTP expiry
    session['action_type'] = action_type # Store 'login' or 'signup'


    # SIMULATED SMS SENDING: In a real app, integrate with Twilio/other SMS API here
    print(f"--- OTP for {phone} is: {otp} (Action: {session['action_type']}) ---")
    flash(f"An OTP has been sent to {phone}. Please check your console (for simulation).", 'info')

    return render_template('verify_otp.html', phone=phone, datetime=datetime) # Ensure datetime is passed

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    user_otp = request.form.get('otp')
    phone = session.get('otp_phone')
    stored_otp = session.get('otp')
    otp_timestamp = session.get('otp_timestamp')
    action_type = session.get('action_type')
    
    # OTP Expiry check (e.g., 5 minutes)
    if otp_timestamp and (datetime.now().timestamp() - otp_timestamp > 300): # 300 seconds = 5 minutes
        flash("OTP has expired. Please request a new one.", 'danger')
        # Clear OTP session data
        session.pop('otp', None)
        session.pop('otp_phone', None)
        session.pop('otp_timestamp', None)
        session.pop('signup_name', None)
        session.pop('action_type', None)
        return redirect(url_for('account'))

    if not all([user_otp, phone, stored_otp, action_type]):
        flash("Missing verification data. Please try again from the account page.", 'danger')
        return redirect(url_for('account'))

    if user_otp == stored_otp:
        user = User.query.filter_by(phone=phone).first()

        if action_type == 'signup':
            name = session.get('signup_name')
            if user: # Double check if user was created while OTP was pending
                flash("An account with this phone number already exists. Please log in.", 'warning')
                # Clear OTP session data
                session.pop('otp', None)
                session.pop('otp_phone', None)
                session.pop('otp_timestamp', None)
                session.pop('signup_name', None)
                session.pop('action_type', None)
                return redirect(url_for('account'))
            if not name:
                flash("Signup failed: Name not found in session. Please start over.", 'danger')
                # Clear OTP session data
                session.pop('otp', None)
                session.pop('otp_phone', None)
                session.pop('otp_timestamp', None)
                session.pop('signup_name', None)
                session.pop('action_type', None)
                return redirect(url_for('account'))

            # Create new user
            new_user = User(
                name=name,
                phone=phone,
                # For simplicity, using OTP as a placeholder for password.
                # In a real app, you might consider an initial password or password reset flow.
                password=generate_password_hash(stored_otp)
            )
            db.session.add(new_user)
            db.session.commit()
            flash("Account created successfully!", 'success')
            session['user_id'] = new_user.id
            session['user_name'] = new_user.name
            session['is_admin'] = new_user.is_admin
            print(f"User {new_user.name} ({new_user.phone}) signed up and logged in.")

        elif action_type == 'login':
            if not user:
                flash("Login failed: No account found with this phone number.", 'danger')
                return redirect(url_for('account'))
            # Log in the existing user
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['is_admin'] = user.is_admin
            flash(f"Welcome back, {user.name}!", 'success')
            print(f"User {user.name} ({user.phone}) logged in.")

        # Clear OTP session data after successful verification
        session.pop('otp', None)
        session.pop('otp_phone', None)
        session.pop('otp_timestamp', None)
        session.pop('signup_name', None)
        session.pop('action_type', None)

        return redirect(url_for('home'))
    else:
        flash("Invalid OTP. Please try again.", 'danger')
        # Do NOT clear OTP data yet, allow retry on the same phone/OTP
        return render_template('verify_otp.html', phone=phone, datetime=datetime) # Render verify page again with error

@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('is_admin', None)
    session.pop('delivery_info', None)
    session.pop('cart', None) # Clear cart on logout
    session.modified = True # Explicitly mark session as modified
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    # Explicitly check for user_id for API calls. If not logged in, return JSON 401.
    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'error': 'Not logged in',
            'message': 'Authentication required. Please log in to proceed.'
        }), 401

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
    # This endpoint is designed to be accessible without login to show '0' in header
    total_quantity = 0
    if 'user_id' in session and 'cart' in session: # Only count if user is logged in AND cart exists
        total_quantity = sum(item['quantity'] for item in session['cart'].values())
    return jsonify({'cart_count': total_quantity}), 200

@app.route('/get_cart_items')
def get_cart_items():
    # Explicitly check for user_id for API calls. If not logged in, return JSON 401.
    if 'user_id' not in session:
        return jsonify({
            'cart_items': [], # Return empty array if not logged in
            'error': 'Not logged in',
            'message': 'Authentication required to view cart.'
        }), 401 # Return 401 for not logged in, consistent with other API errors

    cart_data = session.get('cart', {})
    items_list = []

    for product_id_str, item_data in cart_data.items():
        items_list.append({
            'id': product_id_str,
            'name': item_data['name'],
            'price': item_data['price'],
            'image_url': url_for('static', filename='images/' + item_data.get('image_path', 'default.png')), # Use item_data's image_path
            'quantity': item_data['quantity']
        })
    
    return jsonify({'cart_items': items_list}), 200

@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    # Explicitly check for user_id for API calls. If not logged in, return JSON 401.
    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'error': 'Not logged in',
            'message': 'Authentication required. Please log in to proceed.'
        }), 401

    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))
        new_quantity = data.get('quantity')

        if new_quantity is None or not isinstance(new_quantity, int) or new_quantity < 0:
            return jsonify({'success': False, 'message': 'Invalid product ID or quantity.'}), 400

        cart = session.get('cart', {})

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
    # Explicitly check for user_id for API calls. If not logged in, return JSON 401.
    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'error': 'Not logged in',
            'message': 'Authentication required. Please log in to proceed.'
        }), 401

    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))

        cart = session.get('cart', {})

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
@login_required
def cart():
    # Fetch user's default delivery address for pre-filling
    user_address = g.user.address if g.user and g.user.address else ''
    user_phone = g.user.phone if g.user and g.user.phone else ''
    return render_template('cart.html', user_address=user_address, user_phone=user_phone, datetime=datetime) # Ensure datetime is passed

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    # This route is hit from the cart page after confirming delivery details
    # No longer using hidden total_amount/cart_data from form, calculate on server-side
    delivery_name = request.form.get('delivery_name')
    delivery_phone = request.form.get('delivery_phone')
    delivery_address = request.form.get('delivery_address')

    if not all([delivery_name, delivery_phone, delivery_address]):
        flash("Missing delivery details. Please fill all fields.", 'danger')
        return redirect(url_for('cart'))

    if not delivery_phone.isdigit() or len(delivery_phone) < 9:
        flash("Please enter a valid phone number (digits only, at least 9 digits).", 'danger')
        return redirect(url_for('cart'))

    # Calculate total and get cart items from session (server-side for security)
    cart_items_session = session.get('cart', {})
    if not cart_items_session:
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
@login_required
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
@login_required
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
    
    for item_data in delivery_info['cart_items']:
        try:
            product_id = int(item_data['id'])
        except ValueError:
            flash(f"Invalid product ID in cart: {item_data['id']}", 'danger')
            return redirect(url_for('cart'))

        quantity = item_data.get('quantity')
        if not quantity or not isinstance(quantity, int) or quantity <= 0:
            flash('Invalid item quantity in cart.', 'danger')
            return redirect(url_for('cart'))

        product = Product.query.get(product_id)
        if not product:
            flash(f"Product '{item_data.get('name', 'Unknown')}' not found. Please refresh your cart.", 'danger')
            return redirect(url_for('cart'))

        item_total = product.price * quantity
        server_validated_total += item_total
        order_items_to_add.append({
            'product_id': product.id,
            'quantity': quantity,
            'price': product.price
        })

    payment_method = request.form.get('payment_method')
    payment_detail_info = {}
    status = 'placed'

    if payment_method == 'telebirr':
        payment_detail_info['phone'] = request.form.get('telebirr_phone')
        if not payment_detail_info['phone'] or not payment_detail_info['phone'].isdigit():
            flash('Valid Telebirr phone number is required.', 'danger')
            return redirect(url_for('payment'))
        status = 'pending_payment_telebirr'
    elif payment_method == 'cbebirr':
        payment_detail_info['phone'] = request.form.get('cbebirr_phone')
        if not payment_detail_info['phone'] or not payment_detail_info['phone'].isdigit():
            flash('Valid CBE Birr phone number is required.', 'danger')
            return redirect(url_for('payment'))
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
            
        # Clear the user's cart in session
        session.pop('cart', None)
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
@login_required
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

# --- Data Population (for initial setup) ---
products_data = [
    {"name": "Fresh Cow Milk", "category": "milk", "price": 80.00, "image_suffix": 1, "description": "Pure, pasteurized cow milk."},
    {"name": "Organic Whole Milk", "category": "milk", "price": 95.00, "image_suffix": 2, "description": "Sourced from organic farms, rich in nutrients."},
    {"name": "Low-Fat Milk", "category": "milk", "price": 70.00, "image_suffix": 3, "description": "Healthy choice with reduced fat content."},
    {"name": "Lactose-Free Milk", "category": "milk", "price": 110.00, "image_suffix": 4, "description": "Easy to digest, all the goodness without lactose."},
    
    {"name": "Plain Yogurt", "category": "yogurt", "price": 50.00, "image_suffix": 5, "description": "Creamy and natural plain yogurt."},
    {"name": "Strawberry Yogurt", "category": "yogurt", "price": 65.00, "image_suffix": 6, "description": "Sweetened with real strawberries."},
    {"name": "Greek Yogurt", "category": "yogurt", "price": 85.00, "image_suffix": 7, "description": "Thick, high-protein Greek yogurt."},
    
    {"name": "Cheddar Cheese", "category": "cheese", "price": 150.00, "image_suffix": 8, "description": "Classic sharp cheddar cheese block."},
    {"name": "Mozzarella Cheese", "category": "cheese", "price": 130.00, "image_suffix": 9, "description": "Perfect for pizzas and pastas, melts beautifully."},
    {"name": "Feta Cheese", "category": "cheese", "price": 120.00, "image_suffix": 10, "description": "Tangy and salty, ideal for salads."},
    
    {"name": "Salted Butter", "category": "butter", "price": 90.00, "image_suffix": 11, "description": "Rich and creamy salted butter."},
    {"name": "Unsalted Butter", "category": "butter", "price": 90.00, "image_suffix": 12, "description": "Pure, unsalted butter for baking and cooking."},
]

@app.cli.command('init-db')
def init_db_command():
    """Initializes the database and populates with sample data."""
    with app.app_context():
        db.create_all()
        print("Database initialized.")
        
        # Check if products already exist before populating
        if not Product.query.first():
            print("Products missing. Populating...")
            for p_data in products_data:
                image_name = f"product{p_data['image_suffix']}.png" # Assuming images are named product1.png, product2.png etc.
                new_product = Product(
                    name=p_data['name'],
                    category=p_data['category'],
                    price=p_data['price'],
                    image_path=image_name,
                    description=p_data['description']
                )
                db.session.add(new_product)
            db.session.commit()
            print("Products populated.")
        else:
            print("Products already exist. Skipping population.")

        # Create admin user if not exists
        if not User.query.filter_by(is_admin=True).first():
            print("Admin user missing. Creating...")
            admin_user = User(
                name="Admin",
                lastname="User",
                phone="0911223344",
                email="admin@example.com",
                password=generate_password_hash("adminpass"), # You can set a default strong password or use OTP for admin too
                is_admin=True,
                address="Admin Office, Addis Ababa"
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin user created (phone: 0911223344, pass: adminpass).")
        else:
            print("Admin user already exists. Skipping creation.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Ensure tables are created when running directly
        # You can call init_db_command() here for initial setup if not using 'flask init-db'
        # init_db_command() # Uncomment to run population on every run for development
    app.run(debug=True)