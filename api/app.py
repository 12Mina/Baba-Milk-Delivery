from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import json
from sqlalchemy import inspect, text
import secrets
import functools

# --- Flask Application Setup ---
app = Flask(__name__)

# IMPORTANT: Change this to a strong, random key in production!
# You can generate one with `secrets.token_hex(16)` for 32 characters or `os.urandom(24)` for 24 bytes (48 hex chars)
# For production, it's recommended to load this from an environment variable.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(16)) # Use environment variable or generate a secure one
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///baba_milk.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100))
    phone = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(120), unique=True, nullable=True) # Email can be optional
    password = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text) # This can be a default address for the user
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='user', lazy=True)
    is_admin = db.Column(db.Boolean, default=False) # Add for admin roles

    def __repr__(self):
        return f"<User {self.phone}>"

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # milk, yogurt, cheese, butter
    price = db.Column(db.Float, nullable=False)
    image_path = db.Column(db.String(200)) # Path relative to static/images
    description = db.Column(db.Text)

    def __repr__(self):
        return f"<Product {self.name}>"

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    # Statuses: placed, pending_payment_telebirr, pending_payment_cbebirr, confirmed, packed, out_for_delivery, delivered, cancelled
    status = db.Column(db.String(50), default='placed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    delivery_address = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(20), nullable=False) # Delivery contact phone
    payment_method = db.Column(db.String(50), nullable=False) # cash_on_delivery, telebirr, cbebirr
    payment_details = db.Column(db.Text) # JSON string for mobile money phone number, transaction ID etc.
    items = db.relationship('OrderItem', backref='order', lazy=True)

    def __repr__(self):
        return f"<Order {self.id} by User {self.user_id}>"

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False) # Price at the time of order
    product = db.relationship('Product')

    def __repr__(self):
        return f"<OrderItem {self.id} for Order {self.order_id}>"

# --- Predefined Products Data ---
# These will be added if not already present in the database.
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
# These messages are stored in the session and can be retrieved by JavaScript on the frontend.
def set_flash_message(message, category='info'):
    if 'flash_messages' not in session:
        session['flash_messages'] = []
    session['flash_messages'].append({'message': message, 'category': category})
    session.modified = True # Ensure session changes are saved immediately

# --- Context processor to make datetime available in all templates ---
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# --- before_request to load user into Flask's 'g' object ---
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)

# --- Route Decorators for Authentication and Authorization ---
def login_required(f):
    """Decorator to check if a user is logged in."""
    @functools.wraps(f) # Preserves original function metadata
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            set_flash_message('Please login to access this page.', 'warning')
            return redirect(url_for('account'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to check if a user is logged in and is an admin."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            set_flash_message('Access denied. You are not authorized to view this page.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/')
def home():
    """Renders the home page displaying products by category."""
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
    """Handles user login."""
    if request.method == 'POST':
        if 'login_submit' in request.form:
            phone = request.form['phone']
            password = request.form['password']
            user = User.query.filter_by(phone=phone).first()

            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['user_name'] = user.name
                session['is_admin'] = user.is_admin # Store admin status
                set_flash_message('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                set_flash_message('Invalid phone number or password', 'danger')
    return render_template('account.html')

@app.route('/signup', methods=['POST'])
def signup():
    """Handles user registration."""
    name = request.form['name']
    lastname = request.form.get('lastname') # Use .get for optional fields
    phone = request.form['phone']
    email = request.form.get('email')
    password = request.form['psw']
    confirm_password = request.form['psw-repeat']

    if password != confirm_password:
        set_flash_message('Passwords do not match!', 'danger')
        return redirect(url_for('account'))

    if not phone.isdigit() or len(phone) < 9:
        set_flash_message('Please enter a valid phone number (digits only, at least 9 digits).', 'danger')
        return redirect(url_for('account'))

    if User.query.filter_by(phone=phone).first():
        set_flash_message('Phone number already registered', 'danger')
        return redirect(url_for('account'))

    if email and User.query.filter_by(email=email).first():
        set_flash_message('Email already registered', 'danger')
        return redirect(url_for('account'))

    hashed_password = generate_password_hash(password)

    new_user = User(
        name=name,
        lastname=lastname,
        phone=phone,
        email=email if email else None,
        password=hashed_password,
        is_admin=False # Default to non-admin
    )

    try:
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        session['user_name'] = new_user.name
        session['is_admin'] = new_user.is_admin
        set_flash_message('Account created successfully! You are now logged in.', 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        db.session.rollback()
        set_flash_message(f'An error occurred during registration: {e}', 'danger')
        return redirect(url_for('account'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Displays the user's dashboard with their order history."""
    user_id = session['user_id']
    orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()

    order_details = []
    # These statuses are used for the order tracker visualization
    tracker_statuses = ['placed', 'confirmed', 'out_for_delivery', 'delivered']
    for order in orders:
        items = []
        for item in order.items:
            items.append(f"{item.product.name} x {item.quantity}")

        current_status_index = -1
        # Determine the current status for the tracker
        if order.status.startswith('pending_payment'):
            current_status_index = 0 # Consider pending payment orders at the 'placed' stage
        elif order.status in tracker_statuses:
            current_status_index = tracker_statuses.index(order.status)
        elif order.status == 'packed':
             # 'packed' usually means it's confirmed and being prepared for delivery
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
    """Logs out the current user by clearing session data."""
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('is_admin', None)
    session.pop('delivery_info', None) # Clear any pending delivery info
    session.pop('cart', None) # Clear the cart on logout
    set_flash_message('You have been logged out', 'info')
    return redirect(url_for('home'))

@app.route('/cart')
def cart():
    """Renders the shopping cart page."""
    return render_template('cart.html')

# --- Cart Management API Endpoints (using Flask Session) ---

@app.route('/add_to_cart', methods=['POST'])
@login_required # Ensure user is logged in to add to cart
def add_to_cart():
    """API endpoint to add a product to the session-based cart."""
    data = request.get_json()
    product_id = str(data.get('product_id')) # Ensure it's a string to match session keys
    name = data.get('name')
    # We will fetch the price and image_path from the database for security/consistency
    # price = data.get('price')
    # image_path = data.get('image_path')

    if not product_id:
        set_flash_message('Missing product ID for add to cart.', 'danger')
        return jsonify({'success': False, 'message': 'Invalid product data'}), 400

    # Ensure product_id actually exists in the database for security and to get true price/image
    product = Product.query.get(product_id)
    if not product:
        set_flash_message('Product not found.', 'danger')
        return jsonify({'success': False, 'message': 'Product not found.'}), 404
    
    # Use the price and image_path from the database to prevent client-side price manipulation
    actual_price = product.price
    actual_image_path = product.image_path
    actual_name = product.name # Use server-side name for consistency

    # Initialize cart in session if it doesn't exist
    if 'cart' not in session:
        session['cart'] = {}

    cart_item = session['cart'].get(product_id)
    if cart_item:
        cart_item['quantity'] += 1
    else:
        session['cart'][product_id] = {
            'id': product_id,
            'name': actual_name,
            'price': actual_price, # Use server-side price
            'image_path': actual_image_path,
            'quantity': 1
        }
    
    session.modified = True # Important: tell Flask the session has been updated

    total_quantity = sum(item['quantity'] for item in session['cart'].values())
    set_flash_message(f'{actual_name} added to cart!', 'success')
    return jsonify({'success': True, 'message': 'Product added to cart!', 'total_quantity': total_quantity})

@app.route('/remove_from_cart', methods=['POST'])
@login_required
def remove_from_cart():
    """API endpoint to remove a product from the session-based cart."""
    data = request.get_json()
    product_id = str(data.get('product_id')) # Ensure it's a string

    if 'cart' not in session or product_id not in session['cart']:
        set_flash_message('Item not found in cart.', 'warning')
        return jsonify({'success': False, 'message': 'Item not in cart'}), 404

    try:
        del session['cart'][product_id]
        session.modified = True
        total_quantity = sum(item['quantity'] for item in session['cart'].values())
        set_flash_message('Item removed from cart.', 'info')
        return jsonify({'success': True, 'message': 'Item removed.', 'total_quantity': total_quantity})
    except Exception as e:
        print(f"Error removing from cart: {e}")
        set_flash_message('Error removing item from cart.', 'danger')
        return jsonify({'success': False, 'message': 'Error removing item.'}), 500

@app.route('/update_cart_quantity', methods=['POST'])
@login_required
def update_cart_quantity():
    """API endpoint to update the quantity of a product in the session-based cart."""
    data = request.get_json()
    product_id = str(data.get('product_id'))
    change = int(data.get('change', 0)) # +1 for increment, -1 for decrement

    if 'cart' not in session or product_id not in session['cart']:
        set_flash_message('Item not found in cart.', 'warning')
        return jsonify({'success': False, 'message': 'Item not in cart'}), 404

    cart_item = session['cart'][product_id]
    new_quantity = cart_item['quantity'] + change

    if new_quantity <= 0:
        # If quantity drops to 0 or less, remove the item
        del session['cart'][product_id]
        message = 'Item removed from cart.'
        category = 'info'
    else:
        cart_item['quantity'] = new_quantity
        message = 'Cart quantity updated.'
        category = 'success'
    
    session.modified = True

    total_quantity = sum(item['quantity'] for item in session['cart'].values())
    set_flash_message(message, category)
    return jsonify({'success': True, 'message': message, 'total_quantity': total_quantity})

@app.route('/cart/items')
@login_required # Cart items are specific to the logged-in user
def get_cart_items():
    """API endpoint to get all items currently in the session cart."""
    # Return a copy of the cart to avoid modifying the session object directly outside requests
    return jsonify({'items': session.get('cart', {})})

@app.route('/cart/total_quantity')
def get_cart_total_quantity():
    """API endpoint to get the total number of items in the session cart for header display."""
    total_quantity = sum(item['quantity'] for item in session.get('cart', {}).values())
    return jsonify({'total_quantity': total_quantity})


@app.route('/checkout_delivery', methods=['POST'])
@login_required
def checkout_delivery():
    """Collects and validates delivery information before proceeding to payment."""
    delivery_phone = request.form.get('delivery_phone')
    delivery_address = request.form.get('delivery_address')

    if not delivery_phone or not delivery_address:
        set_flash_message('Please provide both your phone number and delivery address.', 'danger')
        return redirect(url_for('cart'))

    if not delivery_phone.isdigit() or len(delivery_phone) < 9: # Basic phone number validation
        set_flash_message('Please enter a valid phone number (digits only, at least 9 digits).', 'danger')
        return redirect(url_for('cart'))

    session['delivery_info'] = {
        'phone': delivery_phone,
        'address': delivery_address
    }
    session.modified = True # Mark session as modified to ensure changes are saved

    return redirect(url_for('payment'))

@app.route('/payment')
@login_required
def payment():
    """Renders the payment options page."""
    if 'delivery_info' not in session:
        set_flash_message('Please provide delivery details first.', 'warning')
        return redirect(url_for('cart'))
    
    # Pass cart items and total to the payment page for display
    cart_items = session.get('cart', {}).values()
    total_amount = sum(item['price'] * item['quantity'] for item in cart_items)

    return render_template('payment.html', cart_items=list(cart_items), total_amount=total_amount)

@app.route('/finalize_order', methods=['POST'])
@login_required
def finalize_order():
    """Finalizes the order by creating records in the database."""
    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        set_flash_message('User not found. Please log in again.', 'danger')
        return redirect(url_for('account'))

    # Get cart data from session, not from form (more secure)
    client_cart = session.get('cart', {})

    if not client_cart:
        set_flash_message('Your cart is empty. Nothing to pay for!', 'warning')
        return redirect(url_for('cart'))

    server_validated_total = 0.0
    order_items_to_add = []

    # Server-side validation of cart items and total using data from the database
    for product_id_str, item_data in client_cart.items():
        product_id = int(product_id_str) # Convert back to int for querying
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
            'price': product.price # Store price at time of order
        })
    
    # We remove the client_total from the form as it's now validated against server_validated_total
    # If you still want to compare, fetch it from request.form.get('total_amount')

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

    # Create the new order
    new_order = Order(
        user_id=user_id,
        total=server_validated_total, # Use server-validated total
        delivery_address=delivery_info['address'],
        phone=delivery_info['phone'],
        payment_method=payment_method,
        payment_details=json.dumps(payment_detail_info),
        status=status
    )
    db.session.add(new_order)
    db.session.flush() # Use flush to get new_order.id before committing

    # Add order items
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
        session.pop('delivery_info', None) # Clear delivery info from session after successful order
        session.pop('cart', None) # Clear the cart after successful order placement
        return redirect(url_for('dashboard'))
    except Exception as e:
        db.session.rollback()
        set_flash_message(f'An error occurred while placing your order: {e}', 'danger')
        return redirect(url_for('cart'))

@app.route('/admin')
@admin_required
def admin():
    """Displays the admin dashboard with all orders."""
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
@admin_required
def update_order_status():
    """Allows administrators to update the status of an order."""
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
    else:
        set_flash_message('Order not found', 'danger')

    return redirect(url_for('admin'))

# --- Application Initialization ---

if __name__ == '__main__':
    with app.app_context():
        # --- Database Migration Logic ---
        inspector = inspect(db.engine)

        # Check if 'user' table exists and if 'is_admin' column is missing
        if not inspector.has_table('user'):
            print("Creating all tables (user table does not exist)...")
            db.create_all()
        else:
            columns = [col['name'] for col in inspector.get_columns('user')]
            if 'is_admin' not in columns:
                print("Migrating 'user' table to add 'is_admin' column...")
                try:
                    # SQLite does not support ADD COLUMN with DEFAULT for existing tables directly in all cases
                    # A common robust migration strategy is to create a new table, copy data, drop old, rename new.
                    # This is more robust for SQLite specific quirks.
                    db.session.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
                    db.session.commit()
                    print("Migration complete. 'is_admin' column added to 'user' table with default FALSE.")
                except Exception as e:
                    db.session.rollback()
                    print(f"Error during 'is_admin' column migration: {e}")
                    print("Attempting a more robust migration (creating new table, copying data).")
                    try:
                        # Create a temporary new table with the correct schema
                        db.session.execute(text("""
                            CREATE TABLE user_new (
                                id INTEGER PRIMARY KEY,
                                name TEXT NOT NULL,
                                lastname TEXT,
                                phone TEXT NOT NULL UNIQUE,
                                email TEXT UNIQUE,
                                password TEXT NOT NULL,
                                address TEXT,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                is_admin BOOLEAN DEFAULT FALSE
                            )
                        """))
                        # Copy data from the old table to the new one, setting is_admin to FALSE
                        db.session.execute(text("""
                            INSERT INTO user_new (id, name, lastname, phone, email, password, address, created_at, is_admin)
                            SELECT id, name, lastname, phone, email, password, address, created_at, FALSE FROM user
                        """))
                        db.session.execute(text("DROP TABLE user")) # Drop the old table
                        db.session.execute(text("ALTER TABLE user_new RENAME TO user")) # Rename the new table
                        db.session.commit()
                        print("Robust migration complete. 'is_admin' column added and data transferred.")
                    except Exception as inner_e:
                        db.session.rollback()
                        print(f"Critical error during robust migration: {inner_e}")
                        print("Database migration failed. Please inspect your database schema manually.")
            else:
                print("'is_admin' column already exists in 'user' table. No migration needed.")
        # --- End of Database Migration Logic ---

        # Add predefined products if the database is empty or they don't exist
        for prod_data in products_data:
            if not Product.query.filter_by(name=prod_data['name']).first():
                new_product = Product(
                    name=prod_data['name'],
                    price=prod_data['price'],
                    category=prod_data['category'],
                    image_path=f"Product{prod_data['image_suffix']}.jpg",
                    description=prod_data['description']
                )
                db.session.add(new_product)
        db.session.commit()
        print("Predefined products checked/added.")

    # Run the Flask application
    app.run(debug=True)