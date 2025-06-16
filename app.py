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


# --- Context Processor (makes user available in all templates) ---
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            # For AJAX requests, return JSON error
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Please log in to perform this action.', 'error': 'Not logged in'}), 401
            # For regular requests, redirect to login page with a flash message
            flash('You need to be logged in to access this page.', 'warning')
            return redirect(url_for('account'))
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash('You need to be logged in to access this page.', 'warning')
            return redirect(url_for('account'))
        if not g.user.is_admin:
            flash('You do not have permission to access the admin panel.', 'danger')
            return redirect(url_for('home')) # Or redirect to dashboard/home
        return view(**kwargs)
    return wrapped_view

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
                           butter_products=butter_products)

@app.route('/account', methods=['GET', 'POST'])
def account():
    # This route will now primarily render the initial login/signup form
    # The OTP handling will be separate Flask routes
    return render_template('account.html')

@app.route('/send_otp', methods=['POST'])
def send_otp():
    phone = request.form.get('phone')
    name = request.form.get('name') # name will be provided for signup
    action = request.form.get('action') # 'signup' or 'login'

    if not phone:
        flash("Phone number is required.", 'danger')
        return redirect(url_for('account'))

    user = User.query.filter_by(phone=phone).first()

    if action == 'signup':
        if user:
            flash("An account with this phone number already exists. Please log in.", 'warning')
            return redirect(url_for('account'))
        if not name:
            flash("Full name is required for signup.", 'danger')
            return redirect(url_for('account'))
        session['signup_name'] = name # Store name for later account creation
        session['action_type'] = 'signup'
    elif action == 'login':
        if not user:
            flash("No account found with this phone number. Please sign up.", 'danger')
            return redirect(url_for('account'))
        session['action_type'] = 'login'
    else:
        flash("Invalid action.", 'danger')
        return redirect(url_for('account'))

    otp = str(random.randint(100000, 999999)) # 6-digit OTP
    session['otp'] = otp
    session['otp_phone'] = phone # Store phone number associated with this OTP
    session['otp_timestamp'] = datetime.now().timestamp() # Store timestamp for OTP expiry

    # SIMULATED SMS SENDING: In a real app, integrate with Twilio/other SMS API here
    print(f"--- OTP for {phone} is: {otp} (Action: {session['action_type']}) ---")
    flash(f"An OTP has been sent to {phone}. Please check your console (for simulation).", 'info')

    return render_template('verify_otp.html', phone=phone)

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
                return redirect(url_for('account'))
            if not name:
                flash("Signup failed: Name not found in session.", 'danger')
                return redirect(url_for('account'))

            # Create new user
            new_user = User(
                name=name,
                phone=phone,
                # For simplicity, using OTP as a placeholder for password.
                # In a real app, you'd prompt for a real password or hash a default one.
                password=generate_password_hash(otp)
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
        return render_template('verify_otp.html', phone=phone) # Render verify page again with error

@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('is_admin', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/add_to_cart', methods=['POST'])
@login_required # Ensure user is logged in
def add_to_cart():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    if not product_id or quantity < 1:
        return jsonify({'success': False, 'message': 'Invalid product or quantity'}), 400

    product = Product.query.get(product_id)
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'}), 404

    user_id = g.user.id # Get user_id from g.user (guaranteed by login_required)

    cart_item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()

    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(user_id=user_id, product_id=product_id, quantity=quantity)
        db.session.add(cart_item)

    db.session.commit()
    return jsonify({'success': True, 'message': f'{product.name} added to cart!'}), 200

@app.route('/get_cart_count')
@login_required
def get_cart_count():
    user_id = g.user.id
    total_quantity = db.session.query(db.func.sum(CartItem.quantity)).filter_by(user_id=user_id).scalar() or 0
    return jsonify({'cart_count': total_quantity}), 200

@app.route('/get_cart_items')
@login_required
def get_cart_items():
    user_id = g.user.id
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    items_data = []
    for item in cart_items:
        items_data.append({
            'id': item.product.id,
            'name': item.product.name,
            'price': item.product.price,
            'quantity': item.quantity,
            'image_url': url_for('static', filename='images/' + item.product.image_path)
        })
    return jsonify({'cart_items': items_data}), 200

@app.route('/update_cart_quantity', methods=['POST'])
@login_required
def update_cart_quantity():
    data = request.get_json()
    product_id = data.get('product_id')
    new_quantity = data.get('quantity')

    if not product_id or new_quantity is None or not isinstance(new_quantity, int) or new_quantity < 0:
        return jsonify({'success': False, 'message': 'Invalid product ID or quantity.'}), 400

    user_id = g.user.id
    cart_item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()

    if not cart_item:
        return jsonify({'success': False, 'message': 'Item not found in cart.'}), 404

    if new_quantity == 0:
        db.session.delete(cart_item)
        message = f"Removed {cart_item.product.name} from cart."
    else:
        cart_item.quantity = new_quantity
        message = f"Quantity of {cart_item.product.name} updated to {new_quantity}."

    db.session.commit()
    return jsonify({'success': True, 'message': message}), 200

@app.route('/remove_from_cart', methods=['POST'])
@login_required
def remove_from_cart():
    data = request.get_json()
    product_id = data.get('product_id')

    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID is required.'}), 400

    user_id = g.user.id
    cart_item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()

    if not cart_item:
        return jsonify({'success': False, 'message': 'Item not found in cart.'}), 404

    db.session.delete(cart_item)
    db.session.commit()
    return jsonify({'success': True, 'message': f'{cart_item.product.name} removed from cart.'}), 200


@app.route('/cart')
@login_required
def cart():
    # Fetch user's default delivery address for pre-filling
    user_address = g.user.address if g.user and g.user.address else ''
    user_phone = g.user.phone if g.user and g.user.phone else ''
    return render_template('cart.html', user_address=user_address, user_phone=user_phone)

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    # This route is hit from the cart page after confirming delivery details
    total_amount_str = request.form.get('total_amount_hidden')
    cart_data_json = request.form.get('cart_data_hidden')
    delivery_name = request.form.get('delivery_name') # New: delivery name
    delivery_phone = request.form.get('delivery_phone')
    delivery_address = request.form.get('delivery_address')

    if not all([total_amount_str, cart_data_json, delivery_name, delivery_phone, delivery_address]):
        flash("Missing cart or delivery details. Please fill all fields.", 'danger')
        return redirect(url_for('cart'))

    try:
        total_amount = float(total_amount_str)
        cart_items_data = json.loads(cart_data_json)
    except (ValueError, json.JSONDecodeError):
        flash("Invalid cart data. Please try again.", 'danger')
        return redirect(url_for('cart'))
    
    if not cart_items_data:
        flash("Your cart is empty. Please add items before checking out.", 'warning')
        return redirect(url_for('home'))

    # Store delivery info in session for use on the payment page
    session['delivery_info'] = {
        'name': delivery_name,
        'phone': delivery_phone,
        'address': delivery_address,
        'total_amount': total_amount,
        'cart_items': cart_items_data # Pass detailed cart items to payment if needed
    }

    # Redirect to payment page, passing total amount and cart items
    # Payment page will retrieve 'delivery_info' from session
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
    cart_items = delivery_info.get('cart_items') # Pass actual cart items for display/review if needed

    return render_template('payment.html', total_amount=total_amount, cart_items=cart_items)


@app.route('/finalize_order', methods=['POST'])
@login_required
def finalize_order():
    delivery_info = session.get('delivery_info')
    if not delivery_info:
        flash("Checkout information missing. Please start from cart.", 'danger')
        return redirect(url_for('cart'))

    payment_method = request.form.get('payment_method')
    telebirr_phone = request.form.get('telebirr_phone')
    cbebirr_phone = request.form.get('cbebirr_phone')

    # Basic validation for payment methods
    payment_details = {}
    order_status = 'placed'

    if payment_method == 'cash_on_delivery':
        pass # No extra details needed
    elif payment_method == 'telebirr':
        if not telebirr_phone:
            flash("Telebirr phone number is required.", 'danger')
            return redirect(url_for('payment'))
        payment_details['phone'] = telebirr_phone
        order_status = 'pending_payment_telebirr'
    elif payment_method == 'cbebirr':
        if not cbebirr_phone:
            flash("CBE Birr phone number is required.", 'danger')
            return redirect(url_for('payment'))
        payment_details['phone'] = cbebirr_phone
        order_status = 'pending_payment_cbebirr'
    else:
        flash("Invalid payment method selected.", 'danger')
        return redirect(url_for('payment'))

    try:
        new_order = Order(
            user_id=g.user.id,
            total_amount=delivery_info['total_amount'],
            delivery_address=delivery_info['address'],
            delivery_phone=delivery_info['phone'], # Use phone from delivery info
            payment_method=payment_method,
            payment_details=payment_details,
            status=order_status
        )
        db.session.add(new_order)
        db.session.flush() # Get ID before commit for order_items

        # Add items from cart to OrderItem table and clear cart
        for item_data in delivery_info['cart_items']:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item_data['id'],
                quantity=item_data['quantity'],
                price_at_purchase=item_data['price']
            )
            db.session.add(order_item)
            # Remove item from CartItem
            cart_item = CartItem.query.filter_by(user_id=g.user.id, product_id=item_data['id']).first()
            if cart_item:
                db.session.delete(cart_item)

        db.session.commit()
        session.pop('delivery_info', None) # Clear delivery info from session

        flash("Your order has been placed successfully!", 'success')
        # Update cart count in header after order finalization
        # (This will be triggered by re-rendering of the page or a JS call)
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
    return render_template('dashboard.html', orders=orders)

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
        })
    return render_template('admin.html', orders=orders_for_template)


@app.route('/update_order_status', methods=['POST'])
@admin_required
def update_order_status():
    data = request.get_json()
    order_id = data.get('order_id')
    new_status = data.get('status')

    if not order_id or not new_status:
        return jsonify({'success': False, 'message': 'Missing order ID or status.'}), 400

    order = Order.query.get(order_id)
    if not order:
        return jsonify({'success': False, 'message': 'Order not found.'}), 404

    # Validate new status against allowed values (optional, but good practice)
    allowed_statuses = ['placed', 'pending_payment_telebirr', 'pending_payment_cbebirr', 'confirmed', 'packed', 'out_for_delivery', 'delivered', 'cancelled']
    if new_status not in allowed_statuses:
        return jsonify({'success': False, 'message': 'Invalid status provided.'}), 400

    order.status = new_status
    db.session.commit()
    flash(f"Order {order_id} status updated to {new_status.replace('_', ' ').capitalize()}", 'success')
    return jsonify({'success': True, 'message': 'Order status updated successfully.'}), 200


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
            print("Admin user created (phone: 0911223344, pass: adminpass).")
        else:
            print("Admin user already exists. Skipping creation.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Ensure tables are created when running directly
        # You can call init_db_command() here for initial setup if not using 'flask init-db'
        # init_db_command() # Uncomment to run population on every run for development
    app.run(debug=True)