from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta # Import timedelta for session lifetime
import json
import secrets 
import functools # <--- CRITICAL FIX: ADDED THIS IMPORT

# --- Flask Application Setup ---
app = Flask(__name__)

# CRITICAL FIX: Use a fixed secret key for development.
# DO NOT USE THIS HARDCODED KEY IN PRODUCTION! Use a proper environment variable.
# For production, set FLASK_SECRET_KEY as an environment variable (e.g., export FLASK_SECRET_KEY="<your_long_random_string>")
app.secret_key = 'your_strong_and_static_secret_key_here_for_dev_only_12345' # <-- IMPORTANT CHANGE!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///baba_milk.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure session to be permanent and set its lifetime
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7) # Session lasts for 7 days

db = SQLAlchemy(app)

# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100))
    phone = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<User {self.phone}>"

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_path = db.Column(db.String(200)) # This path will now store ONLY the filename (e.g., 'product1.png')
    description = db.Column(db.Text)

    def __repr__(self):
        return f"<Product {self.name}>"

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='placed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    delivery_address = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    payment_details = db.Column(db.Text)
    items = db.relationship('OrderItem', backref='order', lazy=True)

    def __repr__(self):
        return f"<Order {self.id} by User {self.user_id}>"

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

    def __repr__(self):
        return f"<OrderItem {self.id} for Order {self.order_id}>"

# --- Predefined Products Data ---
products_data = [
    {"name": "1 Cup Fresh Cow Milk", "price": 20.00, "category": "milk", "image_suffix": "1", "description": "Fresh and healthy cow milk in a convenient cup."},
    {"name": "1L Fresh Cow Milk", "price": 55.00, "category": "milk", "image_suffix": "2", "description": "Pure, pasteurized 1-liter fresh cow milk."},
    {"name": "5L Fresh Cow Milk", "price": 250.00, "category": "milk", "image_suffix": "3", "description": "Economical 5-liter pack of fresh cow milk."},
    {"name": "25L Fresh Cow Milk", "price": 500.00, "category": "milk", "image_suffix": "4", "description": "Bulk 25-liter container, ideal for larger needs."},
    {"name": "Plain Yogurt", "price": 70.00, "category": "yogurt", "image_suffix": "5", "description": "Creamy and delicious plain yogurt, great for health."},
    {"name": "Cup Yogurt", "price": 40.00, "category": "yogurt", "image_suffix": "6", "description": "Single-serving cup of refreshing yogurt."},
    {"name": "Glass Yogurt", "price": 80.00, "category": "yogurt", "image_suffix": "7", "description": "Thick yogurt in a reusable glass container."},
    {"name": "Plate Yogurt", "price": 100.00, "category": "yogurt", "image_suffix": "8", "description": "A larger serving of traditional plate-style yogurt."},
    {"name": "Ethiopian Ayib", "price": 160.00, "category": "cheese", "image_suffix": "9", "description": "Authentic Ethiopian Ayib (cottage cheese)."},
    {"name": "Ethiopian Nechi Ayib", "price": 170.00, "category": "cheese", "image_suffix": "10", "description": "White Ayib, a staple in Ethiopian cuisine."},
    {"name": "Ethiopian Sahen Ayib", "price": 180.00, "category": "cheese", "image_suffix": "11", "description": "Plate-style Ayib, rich and fresh."},
    {"name": "Ethiopian Home Made Ayib", "price": 100.00, "category": "cheese", "image_suffix": "12", "description": "Traditional homemade Ayib, full of natural goodness."},
    {"name": "Organic Butter", "price": 100.00, "category": "butter", "image_suffix": "13", "description": "Pure organic butter, churned from fresh cream."},
    {"name": "Traditional Ethiopian Butter", "price": 120.00, "category": "butter", "image_suffix": "14", "description": "Authentic Ethiopian Kibe (clarified butter), rich in flavor."},
    {"name": "Ethiopian Laga Butter", "price": 170.00, "category": "butter", "image_suffix": "15", "description": "Premium Ethiopian Laga butter, for special dishes."},
    {"name": "Ethiopian Gebeta Butter", "price": 200.00, "category": "butter", "image_suffix": "16", "description": "High-quality Gebeta butter, a culinary delight."}
]

# --- Helper functions for flash messages ---
def set_flash_message(message, category='info'):
    if 'flash_messages' not in session:
        session['flash_messages'] = []
    session['flash_messages'].append({'message': message, 'category': category})
    session.modified = True # Crucial for mutable session objects

# --- Context processor and before_request ---
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

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
            set_flash_message('Please login to access this page.', 'warning')
            return redirect(url_for('account'))
        print("  SUCCESS: User ID found in session. Proceeding with route function.")
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to check if a user is logged in and is an admin. Redirects if not authorized."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            set_flash_message('Access denied. You are not authorized to view this page.', 'danger')
            if request.accept_mimetypes.accept_json and \
               not request.accept_mimetypes.accept_html:
                return jsonify(success=False, message="Authorization required (Admin access)."), 403
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/')
def home():
    milk_products = Product.query.filter_by(category='milk').all()
    yogurt_products = Product.query.filter_by(category='yogurt').all()
    cheese_products = Product.query.filter_by(category='cheese').all()
    butter_products = Product.query.filter_by(category='butter').all()
    return render_template('home.html',
                           milk_products=milk_products,
                           yogurt_products=yogurt_products,
                           cheese_products=cheese_products,
                           butter_products=butter_products)

@app.route('/account', methods=['GET', 'POST'])
def account():
    if request.method == 'POST':
        if 'login_submit' in request.form:
            phone = request.form['phone']
            password = request.form['password']
            
            print(f"\n--- LOGIN ATTEMPT (Route Handler {datetime.now().strftime('%H:%M:%S')}) ---")
            print(f"  Attempting login for phone: {phone}")

            user = User.query.filter_by(phone=phone).first()
            
            print(f"  User found by phone: {user}")
            if user:
                password_check_result = check_password_hash(user.password, password)
                print(f"  Password check result: {password_check_result}")
            else:
                password_check_result = False # Ensure it's false if no user
            
            if user and password_check_result:
                session['user_id'] = user.id
                session['user_name'] = user.name
                session['is_admin'] = user.is_admin
                session.permanent = True # Make the session permanent
                session.modified = True # Explicitly mark session as modified

                print(f"\n--- LOGIN SUCCESS (Route Handler {datetime.now().strftime('%H:%M:%S')}) ---")
                print(f"  User ID set in session: {session.get('user_id')}")
                print(f"  Session content (after setting): {dict(session)}") # Print full session for debugging
                print(f"--- END LOGIN SUCCESS ---")

                set_flash_message('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                print(f"  LOGIN FAILED: Invalid phone number or password for phone: {phone}")
                set_flash_message('Invalid phone number or password', 'danger')
    return render_template('account.html')

@app.route('/signup', methods=['POST'])
def signup():
    name = request.form['name']
    lastname = request.form.get('lastname')
    phone = request.form['phone']
    email = request.form.get('email')
    password = request.form['psw']
    confirm_password = request.form['psw-repeat']

    print(f"\n--- SIGNUP ATTEMPT (Route Handler {datetime.now().strftime('%H:%M:%S')}) ---")
    print(f"  Attempting signup for phone: {phone}, email: {email}")

    if password != confirm_password:
        set_flash_message('Passwords do not match!', 'danger')
        print("  SIGNUP FAILED: Passwords do not match.")
        return redirect(url_for('account'))

    if not phone.isdigit() or len(phone) < 9:
        set_flash_message('Please enter a valid phone number (digits only, at least 9 digits).', 'danger')
        print("  SIGNUP FAILED: Invalid phone number format.")
        return redirect(url_for('account'))

    if User.query.filter_by(phone=phone).first():
        set_flash_message('Phone number already registered', 'danger')
        print(f"  SIGNUP FAILED: Phone number {phone} already registered.")
        return redirect(url_for('account'))

    if email and User.query.filter_by(email=email).first():
        set_flash_message('Email already registered', 'danger')
        print(f"  SIGNUP FAILED: Email {email} already registered.")
        return redirect(url_for('account'))

    hashed_password = generate_password_hash(password)

    new_user = User(
        name=name,
        lastname=lastname,
        phone=phone,
        email=email if email else None,
        password=hashed_password,
        is_admin=False
    )

    try:
        db.session.add(new_user)
        db.session.commit() # Commit new user to get ID

        session['user_id'] = new_user.id
        session['user_name'] = new_user.name
        session['is_admin'] = new_user.is_admin
        session.permanent = True # Make the session permanent
        session.modified = True # Explicitly mark session as modified

        print(f"\n--- SIGNUP SUCCESS (Route Handler {datetime.now().strftime('%H:%M:%S')}) ---")
        print(f"  User ID set in session: {session.get('user_id')}")
        print(f"  Session content: {dict(session)}") # Print full session for debugging
        print(f"--- END SIGNUP SUCCESS ---")

        set_flash_message('Account created successfully! You are now logged in.', 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        db.session.rollback()
        set_flash_message(f'An error occurred during registration: {e}', 'danger')
        app.logger.error(f"Signup error: {e}") # Log the specific error
        print(f"  SIGNUP ERROR: {e}")
        return redirect(url_for('account'))

@app.route('/dashboard')
@login_required # This is an HTML page, requires redirect if not logged in
def dashboard():
    user_id = session['user_id'] # This should be safe because @login_required passed
    orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()

    order_details = []
    tracker_statuses = ['placed', 'confirmed', 'out_for_delivery', 'delivered']
    for order in orders:
        items = []
        for item in order.items:
            items.append(f"{item.product.name} x {item.quantity}")

        current_status_index = -1
        if order.status.startswith('pending_payment'):
            current_status_index = 0
        elif order.status in tracker_statuses:
            current_status_index = tracker_statuses.index(order.status)
        elif order.status == 'packed':
            current_status_index = tracker_statuses.index('confirmed')

        payment_details_dict = {}
        try:
            if order.payment_details:
                payment_details_dict = json.loads(order.payment_details)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode payment_details for order {order.id}: {order.payment_details}")

        order_details.append({
            'id': order.id,
            'date': order.created_at.strftime('%B %d, %Y %I:%M %p'),
            'items': ', '.join(items) if items else 'No items listed',
            'total': order.total,
            'status': order.status,
            'payment_method': order.payment_method,
            'payment_details': payment_details_dict,
            'delivery_address': order.delivery_address,
            'delivery_phone': order.phone,
            'current_status_index': current_status_index,
            'tracker_statuses': tracker_statuses
        })

    return render_template('dashboard.html', orders=order_details)

@app.route('/logout')
def logout():
    print(f"\n--- LOGOUT ({datetime.now().strftime('%H:%M:%S')}) ---")
    print(f"  Before logout session: {dict(session)}")
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('is_admin', None)
    session.pop('delivery_info', None)
    session.pop('cart', None)
    session.modified = True # Explicitly mark session as modified
    print(f"  After logout session: {dict(session)}")
    print(f"--- END LOGOUT ---")
    set_flash_message('You have been logged out', 'info')
    return redirect(url_for('home'))

@app.route('/cart')
def cart():
    # Pass user's default phone and address to cart.html if available
    user_phone = None
    user_address = None
    if g.user:
        user_phone = g.user.phone
        user_address = g.user.address
    return render_template('cart.html', user_phone=user_phone, user_address=user_address)

# --- Cart Management API Endpoints (Explicit JSON Authentication) ---
# Removed @login_required decorator from these API endpoints
# as they handle auth check and JSON response internally.

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    # Explicitly check for user_id for API calls. If not logged in, return JSON 401.
    if 'user_id' not in session:
        print(f"  AUTH FAIL: /add_to_cart - No user_id in session. Returning 401.")
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
            return jsonify({'success': False, 'message': 'Product not found.'}), 404

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
                # Store ONLY the filename in cart session data for image_path
                'image_path': product.image_path, # This is just the filename now
                'quantity': 1
            }

        session['cart'] = cart
        session.modified = True # Mark session modified

        total_quantity = sum(item['quantity'] for item in cart.values())
        print(f"  CART: Item {product_id_str} added. Total quantity: {total_quantity}. Session Cart: {dict(session.get('cart', {}))}")
        return jsonify({'success': True, 'message': f'{product.name} added to cart!', 'total_quantity': total_quantity})

    except Exception as e:
        app.logger.error(f"Error adding to cart: {e}")
        db.session.rollback() # Ensure rollback on error
        return jsonify({'success': False, 'message': 'An error occurred while adding to cart.'}), 500

@app.route('/cart/update_quantity', methods=['POST'])
def update_cart_quantity():
    # Explicitly check for user_id for API calls. If not logged in, return JSON 401.
    if 'user_id' not in session:
        print(f"  AUTH FAIL: /cart/update_quantity - No user_id in session. Returning 401.")
        return jsonify({
            'success': False,
            'error': 'Not logged in',
            'message': 'Authentication required. Please log in to proceed.'
        }), 401

    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))
        delta = int(data.get('delta'))

        cart = session.get('cart', {})

        if product_id not in cart:
            return jsonify({'success': False, 'message': 'Item not in cart.'}), 404

        current_quantity = cart[product_id]['quantity']
        new_quantity = current_quantity + delta

        if new_quantity <= 0:
            item_name = cart[product_id]['name']
            del cart[product_id]
            message = f"{item_name} removed from cart."
        else:
            cart[product_id]['quantity'] = new_quantity
            message = f"{cart[product_id]['name']} quantity updated to {new_quantity}."

        session['cart'] = cart
        session.modified = True # Mark session modified
        
        total_quantity = sum(item['quantity'] for item in cart.values())
        print(f"  CART: Item {product_id} quantity updated to {new_quantity}. Total quantity: {total_quantity}. Session Cart: {dict(session.get('cart', {}))}")
        return jsonify({'success': True, 'message': message, 'total_quantity': total_quantity})

    except Exception as e:
        app.logger.error(f"Error updating cart quantity: {e}")
        db.session.rollback() # Ensure rollback on error
        return jsonify({'success': False, 'message': 'An error occurred while updating quantity.'}), 500

@app.route('/cart/remove_item', methods=['POST'])
def remove_item_from_cart():
    # Explicitly check for user_id for API calls. If not logged in, return JSON 401.
    if 'user_id' not in session:
        print(f"  AUTH FAIL: /cart/remove_item - No user_id in session. Returning 401.")
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

        total_quantity = sum(item['quantity'] for item in cart.values())
        print(f"  CART: Item {product_id} removed. Total quantity: {total_quantity}. Session Cart: {dict(session.get('cart', {}))}")
        return jsonify({'success': True, 'message': f'{item_name} removed from cart.', 'total_quantity': total_quantity})

    except Exception as e:
        app.logger.error(f"Error removing item from cart: {e}")
        db.session.rollback() # Ensure rollback on error
        return jsonify({'success': False, 'message': 'An error occurred while removing item.'}), 500

@app.route('/cart/items')
def get_cart_items():
    # Explicitly check for user_id for API calls. If not logged in, return JSON 401.
    if 'user_id' not in session:
        print(f"  AUTH FAIL: /cart/items - No user_id in session. Returning 401.")
        return jsonify({
            'items': [],
            'total_quantity': 0,
            'error': 'Not logged in',
            'message': 'Authentication required to view cart.'
        }), 401 # Return 401 for not logged in, consistent with other API errors

    cart_data = session.get('cart', {})
    items_list = []

    # Iterate through cart items and build the list, ensuring 'image_path' is included
    for product_id_str, item_data in cart_data.items():
        # Use item_data.get('image_path') as it should have been stored when added to cart
        items_list.append({
            'id': product_id_str, # Use string ID for consistency with JS
            'name': item_data['name'],
            'price': item_data['price'],
            'image_path': item_data.get('image_path', 'default_product.png'), # Fallback image name only
            'quantity': item_data['quantity']
        })
    
    total_quantity = sum(item['quantity'] for item in cart_data.values())
    print(f"  CART: Fetching items. Total quantity: {total_quantity}. Items count: {len(items_list)}. Session Cart: {dict(session.get('cart', {}))}")
    return jsonify({'items': items_list, 'total_quantity': total_quantity})


@app.route('/cart/total_quantity')
def get_cart_total_quantity():
    # This endpoint is designed to be accessible without login to show '0' in header
    # No authentication check here, as it's meant to work anonymously.
    total_quantity = 0
    if 'user_id' in session:
        total_quantity = sum(item['quantity'] for item in session.get('cart', {}).values())
    print(f"  CART: Fetching total quantity. Current: {total_quantity}")
    return jsonify({'total_quantity': total_quantity})


@app.route('/checkout_delivery', methods=['POST'])
@login_required # This is an HTML form submission, so the decorator handles redirection
def checkout_delivery():
    delivery_phone = request.form.get('delivery_phone')
    delivery_address = request.form.get('delivery_address')

    if not delivery_phone or not delivery_address:
        set_flash_message('Please provide both your phone number and delivery address.', 'danger')
        return redirect(url_for('cart'))

    if not delivery_phone.isdigit() or len(delivery_phone) < 9:
        set_flash_message('Please enter a valid phone number (digits only, at least 9 digits).', 'danger')
        return redirect(url_for('cart'))

    session['delivery_info'] = {
        'phone': delivery_phone,
        'address': delivery_address
    }
    session.modified = True # Mark session modified

    return redirect(url_for('payment'))

@app.route('/payment')
@login_required # This is an HTML page, requires redirect if not logged in
def payment():
    if 'delivery_info' not in session:
        set_flash_message('Please provide delivery details first.', 'warning')
        return redirect(url_for('cart'))
    
    cart_items = session.get('cart', {}).values()
    total_amount = sum(item['price'] * item['quantity'] for item in cart_items)

    return render_template('payment.html', cart_items=list(cart_items), total_amount=total_amount)

@app.route('/finalize_order', methods=['POST'])
@login_required # This is an HTML form submission, requires redirect if not logged in
def finalize_order():
    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        set_flash_message('User not found. Please log in again.', 'danger')
        return redirect(url_for('account'))

    client_cart = session.get('cart', {})

    if not client_cart:
        set_flash_message('Your cart is empty. Nothing to pay for!', 'warning')
        return redirect(url_for('cart'))

    server_validated_total = 0.0
    order_items_to_add = []

    for product_id_str, item_data in client_cart.items():
        try:
            product_id = int(product_id_str)
        except ValueError:
            set_flash_message(f"Invalid product ID in cart: {product_id_str}", 'danger')
            return redirect(url_for('cart'))

        quantity = item_data.get('quantity')

        if not quantity or not isinstance(quantity, int) or quantity <= 0:
            set_flash_message('Invalid item quantity in cart.', 'danger')
            return redirect(url_for('cart'))

        product = Product.query.get(product_id)
        if not product:
            set_flash_message(f"Product '{item_data.get('name', 'Unknown')}' not found. Please refresh your cart.", 'danger')
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
            set_flash_message('Valid Telebirr phone number is required.', 'danger')
            return redirect(url_for('payment'))
        status = 'pending_payment_telebirr'
    elif payment_method == 'cbebirr':
        payment_detail_info['phone'] = request.form.get('cbebirr_phone')
        if not payment_detail_info['phone'] or not payment_detail_info['phone'].isdigit():
            set_flash_message('Valid CBE Birr phone number is required.', 'danger')
            return redirect(url_for('payment'))
        status = 'pending_payment_cbebirr'
    elif payment_method != 'cash_on_delivery':
        set_flash_message('Invalid payment method selected.', 'danger')
        return redirect(url_for('payment'))

    delivery_info = session.get('delivery_info')
    if not delivery_info or not delivery_info.get('address') or not delivery_info.get('phone'):
        set_flash_message('Delivery information not found. Please re-enter.', 'danger')
        return redirect(url_for('cart'))

    new_order = Order(
        user_id=user_id,
        total=server_validated_total,
        delivery_address=delivery_info['address'],
        phone=delivery_info['phone'],
        payment_method=payment_method,
        payment_details=json.dumps(payment_detail_info),
        status=status
    )
    db.session.add(new_order)
    db.session.flush() # Flush to get new_order.id before commit

    for item_data in order_items_to_add:
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item_data['product_id'],
            quantity=item_data['quantity'],
            price=item_data['price']
        )
        db.session.add(order_item)

    try:
        db.session.commit()
        set_flash_message('Order placed successfully! Please complete your payment if using mobile money. Your cart has been cleared.', 'success')
        session.pop('delivery_info', None)
        session.pop('cart', None)
        session.modified = True # Mark session modified
        return redirect(url_for('dashboard'))
    except Exception as e:
        db.session.rollback()
        set_flash_message(f'An error occurred while placing your order: {e}', 'danger')
        app.logger.error(f"Order finalization error: {e}") # Log the specific error
        return redirect(url_for('cart'))

@app.route('/admin')
@admin_required # This is an HTML page, requires redirect if not logged in
def admin():
    orders = Order.query.order_by(Order.created_at.desc()).all()

    order_details = []
    for order in orders:
        user = User.query.get(order.user_id)
        items_list = []
        for item in order.items:
            items_list.append(f"{item.product.name} x {item.quantity}")

        payment_details_dict = {}
        try:
            if order.payment_details:
                payment_details_dict = json.loads(order.payment_details)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode payment_details for order {order.id}: {order.payment_details}")

        order_details.append({
            'id': order.id,
            'customer': f"{user.name} {user.lastname}" if user else "Unknown",
            'customer_phone': user.phone if user else "N/A",
            'customer_email': user.email if user else "N/A",
            'delivery_address': order.delivery_address,
            'items': ', '.join(items_list),
            'date': order.created_at.strftime('%B %d, %Y %I:%M %p'),
            'total': order.total,
            'status': order.status,
            'payment_method': order.payment_method,
            'payment_details': payment_details_dict,
            'delivery_phone': order.phone
        })

    return render_template('admin.html', orders=order_details)

@app.route('/update_order_status', methods=['POST'])
@admin_required # This is an HTML form submission, requires redirect if not logged in
def update_order_status():
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')

    valid_statuses = [
        'placed', 'pending_payment_telebirr', 'pending_payment_cbebirr',
        'confirmed', 'packed', 'out_for_delivery', 'delivered', 'cancelled'
    ]

    if not order_id or not new_status:
        set_flash_message('Missing order ID or status.', 'danger')
        return redirect(url_for('admin'))

    if new_status not in valid_statuses:
        set_flash_message(f'Invalid status: {new_status}', 'danger')
        return redirect(url_for('admin'))

    order = Order.query.get(order_id)
    if order:
        order.status = new_status
        try:
            db.session.commit()
            set_flash_message(f'Order {order_id} status updated to {new_status}', 'success')
        except Exception as e:
            db.session.rollback()
            set_flash_message(f'Error updating order status: {e}', 'danger')
            app.logger.error(f"Order status update error: {e}") # Log the specific error
    else:
        set_flash_message('Order not found', 'danger')

    return redirect(url_for('admin'))

# --- Application Initialization ---
if __name__ == '__main__':
    with app.app_context():
        # Check if database exists, if not create and populate
        if not os.path.exists('baba_milk.db'):
            print("Database 'baba_milk.db' not found. Creating and populating...")
            db.create_all()

            print("Populating products table...")
            for p_data in products_data:
                # Store ONLY the filename in the database
                image_name = f"product{p_data['image_suffix']}.png"
                new_product = Product(
                    name=p_data['name'],
                    category=p_data['category'],
                    price=p_data['price'],
                    image_path=image_name, # <-- IMPORTANT CHANGE HERE! Store just the filename.
                    description=p_data['description']
                )
                db.session.add(new_product)
            db.session.commit()
            print("Products populated.")
            
            if not User.query.filter_by(is_admin=True).first():
                print("Creating a default admin user...")
                admin_user = User(
                    name="Admin",
                    lastname="User",
                    phone="0911223344",
                    email="admin@example.com",
                    password=generate_password_hash("adminpass"),
                    is_admin=True,
                    address="Admin Office"
                )
                db.session.add(admin_user)
                db.session.commit()
                print("Default admin user created (phone: 0911223344, pass: adminpass).")
        else:
            print("Database 'baba_milk.db' already exists. Checking for missing data...")
            # If DB exists but products/admin are missing, you might still want to add them
            with app.app_context():
                if not Product.query.first():
                    print("Products missing. Populating...")
                    for p_data in products_data:
                        image_name = f"product{p_data['image_suffix']}.png"
                        new_product = Product(
                            name=p_data['name'],
                            category=p_data['category'],
                            price=p_data['price'],
                            image_path=image_name, # <-- IMPORTANT CHANGE HERE! Store just the filename.
                            description=p_data['description']
                        )
                        db.session.add(new_product)
                    db.session.commit()
                    print("Products populated.")

                if not User.query.filter_by(is_admin=True).first():
                    print("Admin user missing. Creating...")
                    admin_user = User(
                        name="Admin",
                        lastname="User",
                        phone="0911223344",
                        email="admin@example.com",
                        password=generate_password_hash("adminpass"),
                        is_admin=True,
                        address="Admin Office"
                    )
                    db.session.add(admin_user)
                    db.session.commit()
                    print("Admin user created.")


    app.run(debug=True)
