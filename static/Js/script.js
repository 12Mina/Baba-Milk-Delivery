// ======================== 🚀 Initialize ========================
document.addEventListener('DOMContentLoaded', () => {
    if (typeof displayFlashMessages === 'function') displayFlashMessages();
    updateCartCountInHeader();
    initializeAddToCartButtons();

    const body = document.body;

    if (body.contains(document.getElementById('cart-page-container'))) {
        renderCartItems();
        initializeCartPageElements(); // ✅ This function is now defined below
    }

    if (body.contains(document.getElementById('payment-page-container'))) {
        initializePaymentOptions();
    }

    const accountContainer = document.getElementById('container');
    if (body.contains(accountContainer)) {
        initializeFlorinPopAccountPage(accountContainer);
    }

    if (body.contains(document.getElementById('admin-panel-container'))) {
        initializeAdminPanel();
    }

    const trackButton = document.querySelector('.track-button');
    if (trackButton) {
        trackButton.addEventListener('click', () => {
            displayFlashMessage('📦 Tracking feature is coming soon!', 'info');
        });
    }
});

// ======================== ✨ Flash Messages ========================
function displayFlashMessages() {
    const flashContainer = document.querySelector('.flash-messages');
    if (flashContainer) {
        flashContainer.style.display = 'block';
        setTimeout(() => {
            flashContainer.style.display = 'none';
        }, 4000);
    }
}

// ======================== 🛒 Cart Functions ========================
function updateCartCountInHeader() {
    const cartCount = localStorage.getItem('cartCount') || 0;
    const cartCounter = document.querySelector('.cart-count');
    if (cartCounter) cartCounter.textContent = cartCount;
}

function initializeAddToCartButtons() {
    const buttons = document.querySelectorAll('.add-to-cart-btn');
    buttons.forEach(button => {
        button.addEventListener('click', () => {
            const productId = button.getAttribute('data-product-id');
            addToCart(productId);
        });
    });
}

function addToCart(productId) {
    console.log(`🧺 Adding product ${productId} to cart...`);
    // Simulate cart update logic or send to Flask via fetch
    displayFlashMessage('🧺 Item added to cart!', 'success');
}

// ======================== 🧾 Cart Rendering ========================
async function renderCartItems() {
    const cartPageContainer = document.getElementById('cart-page-container');
    if (!cartPageContainer) return;

    const cartItemsList = document.getElementById('cart-items-list');
    const cartTotalElement = document.getElementById('cart-total');
    const emptyCartMessage = document.getElementById('empty-cart-message');
    const cartSummarySection = document.getElementById('cart-summary-section');
    const totalAmountHiddenInput = document.getElementById('total-amount-hidden');
    const cartDataHiddenInput = document.getElementById('cart-data-hidden');

    if (!cartItemsList || !cartTotalElement || !emptyCartMessage || !cartSummarySection || !totalAmountHiddenInput || !cartDataHiddenInput) {
        console.error("Missing cart elements. Check your cart.html structure.");
        return;
    }

    try {
        const response = await fetch('/cart/items');
        if (!response.ok) throw new Error(`Status: ${response.status}`);
        const data = await response.json();
        const cart = Object.values(data.items || {});
        cartItemsList.innerHTML = '';
        let total = 0;

        if (cart.length === 0) {
            emptyCartMessage.style.display = 'block';
            cartSummarySection.style.display = 'none';
            cartTotalElement.textContent = '0.00';
            totalAmountHiddenInput.value = '0.00';
            cartDataHiddenInput.value = '[]';
            return;
        } else {
            emptyCartMessage.style.display = 'none';
            cartSummarySection.style.display = 'block';
        }

        cart.forEach(item => {
            const itemPrice = parseFloat(item.price) || 0;
            const itemQuantity = parseInt(item.quantity) || 0;
            total += itemPrice * itemQuantity;
            const imagePath = `/static/images/${item.image_path}`;

            const cartItem = document.createElement('div');
            cartItem.className = 'cart-item';
            cartItem.innerHTML = `
                <img src="${imagePath}" alt="${item.name}" class="cart-item-img">
                <div class="item-details">
                    <h3>${item.name}</h3>
                    <p class="item-subtotal">ETB ${(itemPrice * itemQuantity).toFixed(2)}</p>
                    <div class="quantity-controls">
                        <button type="button" class="quantity-btn decrease-quantity" data-product-id="${item.id}">-</button>
                        <span class="item-quantity">${itemQuantity}</span>
                        <button type="button" class="quantity-btn increase-quantity" data-product-id="${item.id}">+</button>
                    </div>
                </div>
                <button type="button" class="remove-item-btn" data-product-id="${item.id}" title="Remove item">
                    <i class="fas fa-trash"></i>
                </button>
            `;
            cartItemsList.appendChild(cartItem);
        });

        cartTotalElement.textContent = total.toFixed(2);
        totalAmountHiddenInput.value = total.toFixed(2);
        cartDataHiddenInput.value = JSON.stringify(cart);

        cartItemsList.addEventListener('click', e => {
            const target = e.target;
            const productId = target.closest('[data-product-id]')?.getAttribute('data-product-id');
            if (!productId) return;

            if (target.classList.contains('decrease-quantity')) {
                updateQuantityInCart(productId, -1);
            } else if (target.classList.contains('increase-quantity')) {
                updateQuantityInCart(productId, 1);
            } else if (target.closest('.remove-item-btn')) {
                removeFromCart(productId);
            }
        });

    } catch (err) {
        console.error('Failed to fetch cart items:', err);
        displayFlashMessage('Failed to load cart items. Try again.', 'danger');
    }
}

// ======================== 📦 Cart Page Elements (Fixed) ========================
function initializeCartPageElements() {
    console.log('✅ Cart page elements initialized.');
    // You can add additional logic here later if needed (e.g., promo code input)
}

// ======================== 💳 Payment Page ========================
function initializePaymentOptions() {
    const options = document.querySelectorAll('input[name="payment-method"]');
    options.forEach(option => {
        option.addEventListener('change', () => {
            displayFlashMessage(`💳 You selected: ${option.value}`, 'info');
        });
    });
}

// ======================== 🔐 Account Page ========================
function initializeFlorinPopAccountPage(container) {
    const loginBtn = container.querySelector('.login');
    const signupBtn = container.querySelector('.signup');
    const formWrapper = container;

    loginBtn?.addEventListener('click', () => {
        formWrapper.classList.remove('active');
    });

    signupBtn?.addEventListener('click', () => {
        formWrapper.classList.add('active');
    });
}

// ======================== 🛠️ Admin Panel (Stub) ========================
function initializeAdminPanel() {
    console.log("Admin panel initialized.");
}

// ======================== 🔔 Flash Message Utility ========================
function displayFlashMessage(message, type = 'info') {
    const flashContainer = document.createElement('div');
    flashContainer.className = `flash-messages ${type}`;
    flashContainer.textContent = message;

    document.body.appendChild(flashContainer);
    setTimeout(() => {
        flashContainer.remove();
    }, 3000);
}

// ======================== 🧠 Cart Update Stub ========================
function updateQuantityInCart(productId, delta) {
    console.log(`Cart: Update product ${productId} by ${delta}`);
    displayFlashMessage(`Cart updated for product ${productId}`, 'success');
}

function removeFromCart(productId) {
    console.log(`Cart: Removed product ${productId}`);
    displayFlashMessage(`Removed product ${productId}`, 'danger');
}
