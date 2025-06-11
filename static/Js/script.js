// ======================== 🚀 Initialize ========================
document.addEventListener('DOMContentLoaded', () => {
    displayFlaskFlashMessages();
    updateCartCountInHeader();
    initializeAddToCartButtons();

    const body = document.body;

   document.addEventListener("DOMContentLoaded", () => {
    const body = document.body;
    if (body.contains(document.getElementById('cart-page-container'))) {
        renderCartItems();
        initializeCartPageElements();  // ✅ Make sure this function is already defined above
    }
});


    if (body.contains(document.getElementById('payment-page-container'))) {
        initializePaymentOptions();
    }

    const accountContainer = document.getElementById('container');
    if (body.contains(accountContainer)) {
        initializeAccountPage(accountContainer);
    }

    if (body.contains(document.getElementById('admin-panel-container'))) {
        initializeAdminPanel();
    }

    const trackButton = document.querySelector('.track-button');
    if (trackButton) {
        trackButton.addEventListener('click', () => {
            showFlashMessage('📦 Tracking feature is coming soon!', 'info');
        });
    }
});

// ======================== ✨ Flash Message Utilities ========================
function showFlashMessage(message, type = 'info') {
    const flashContainer = document.createElement('div');
    flashContainer.className = `flash-messages ${type}`;
    flashContainer.textContent = message;
    document.body.appendChild(flashContainer);
    setTimeout(() => flashContainer.remove(), 3000);
}

function displayFlaskFlashMessages() {
    const flashMessagesDataElement = document.getElementById('flash-messages-data');
    if (flashMessagesDataElement) {
        try {
            const flashMessages = JSON.parse(flashMessagesDataElement.textContent);
            const flashMessageContainer = document.getElementById('flash-message-container');
            if (flashMessages.length > 0 && flashMessageContainer) {
                flashMessages.forEach(msg => {
                    const alertDiv = document.createElement('div');
                    alertDiv.className = `alert alert-${msg.category} alert-dismissible fade show`;
                    alertDiv.role = 'alert';
                    alertDiv.innerHTML = `
                        ${msg.message}
                        <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                            <span aria-hidden="true">&times;</span>
                        </button>
                    `;
                    flashMessageContainer.appendChild(alertDiv);
                });
                flashMessagesDataElement.textContent = '[]';
            }
        } catch (e) {
            console.error("Error parsing flash messages from Flask:", e);
        }
    }
}

// ======================== 🛒 Cart Functions (Core Logic) ========================
async function updateCartCountInHeader() {
    try {
        const response = await fetch('/cart/total_quantity');
        const cartCounter = document.querySelector('.cart-count');
        if (!response.ok) {
            console.error(`Cart count fetch failed: ${response.status}`);
            if (cartCounter) cartCounter.textContent = '0';
            return;
        }
        const data = await response.json();
        if (cartCounter) {
            cartCounter.textContent = data.total_quantity > 0 ? data.total_quantity : '';
        }
    } catch (error) {
        console.error("Error fetching cart count:", error);
        const cartCounter = document.querySelector('.cart-count');
        if (cartCounter) cartCounter.textContent = '';
    }
}

function initializeAddToCartButtons() {
    const buttons = document.querySelectorAll('.add-to-cart-btn');
    buttons.forEach(button => {
        button.addEventListener('click', () => {
            const productId = button.getAttribute('data-product-id');
            const productName = button.closest('.product-card')?.querySelector('h3')?.textContent || 'Unknown Product';
            addToCart(productId, productName);
        });
    });
}

async function addToCart(productId, productName) {
    console.log(`🧺 Adding ${productName} (${productId})`);
    try {
        const response = await fetch('/add_to_cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ product_id: productId })
        });

        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            const data = await response.json();
            if (response.ok) {
                showFlashMessage(data.message || `Added ${productName} to cart!`, 'success');
                updateCartCountInHeader();
                if (document.body.contains(document.getElementById('cart-page-container'))) renderCartItems();
            } else {
                showFlashMessage(data.message || 'Could not add item.', 'danger');
                if (response.status === 401) setTimeout(() => window.location.href = '/account', 1500);
            }
        } else {
            const errorText = await response.text();
            console.error("Non-JSON response:", errorText);
            showFlashMessage(`Error: Could not add ${productName}.`, 'danger');
            if (errorText.includes('Login required')) setTimeout(() => window.location.href = '/account', 1500);
        }
    } catch (error) {
        console.error("Add to cart failed:", error);
        showFlashMessage(`Network error adding ${productName}.`, 'danger');
    }
}

async function updateQuantityInCart(productId, delta) {
    try {
        const response = await fetch('/cart/update_quantity', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId, delta: delta })
        });

        const data = await response.json();
        if (response.ok) {
            showFlashMessage(data.message, 'success');
            updateCartCountInHeader();
            renderCartItems();
        } else {
            showFlashMessage(data.message || 'Update failed.', 'danger');
            if (response.status === 401) setTimeout(() => window.location.href = '/account', 1500);
        }
    } catch (error) {
        console.error("Update quantity error:", error);
        showFlashMessage('Quantity update failed.', 'danger');
    }
}

async function removeFromCart(productId) {
    if (!confirm("Remove this item?")) return;
    try {
        const response = await fetch('/cart/remove_item', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId })
        });
        const data = await response.json();
        if (response.ok) {
            showFlashMessage(data.message, 'info');
            updateCartCountInHeader();
            renderCartItems();
        } else {
            showFlashMessage(data.message || 'Remove failed.', 'warning');
            if (response.status === 401) setTimeout(() => window.location.href = '/account', 1500);
        }
    } catch (error) {
        console.error("Remove item error:", error);
        showFlashMessage('Error removing item.', 'danger');
    }
}

// ======================== 🧾 Cart Page Rendering ========================
async function renderCartItems() {
    const cartItemsList = document.getElementById('cart-items-list');
    const cartTotalElement = document.getElementById('cart-total');
    const emptyCartMessage = document.getElementById('empty-cart-message');
    const cartSummarySection = document.getElementById('cart-summary-section');
    const totalAmountHiddenInput = document.getElementById('total-amount-hidden');
    const cartDataHiddenInput = document.getElementById('cart-data-hidden');

    try {
        const response = await fetch('/cart/items');

        if (!response.ok) {
            if (response.status === 401) {
                console.warn("401 Unauthorized: User not logged in.");
                showFlashMessage("Please log in to view your cart.", "warning");
                return;
            } else if (response.status === 404) {
                console.warn("404 Not Found: /cart/items endpoint is missing.");
                showFlashMessage("Cart service not available.", "danger");
                return;
            } else {
                throw new Error(`Unexpected response status: ${response.status}`);
            }
        }

        let data;
        try {
            data = await response.json();
        } catch (jsonErr) {
            console.error("Failed to parse JSON from /cart/items:", jsonErr);
            showFlashMessage("Invalid response from server.", "danger");
            return;
        }

        const cart = Array.isArray(data.items) ? data.items : Object.values(data.items || {});
        cartItemsList.innerHTML = '';
        let total = 0;

        if (cart.length === 0) {
            emptyCartMessage.style.display = 'block';
            cartSummarySection.style.display = 'none';
            cartTotalElement.textContent = '0.00';
            totalAmountHiddenInput.value = '0.00';
            cartDataHiddenInput.value = '[]';
            updateCartCountInHeader();
            return;
        } else {
            emptyCartMessage.style.display = 'none';
            cartSummarySection.style.display = 'block';
        }

        cart.forEach(item => {
            const price = parseFloat(item.price) || 0;
            const quantity = parseInt(item.quantity) || 0;
            const subtotal = price * quantity;
            total += subtotal;
            const imagePath = `/static/${item.image_path}`;
            const div = document.createElement('div');
            div.className = 'cart-item';
            div.innerHTML = `
                <img src="${imagePath}" alt="${item.name}" class="cart-item-img">
                <div class="item-details">
                    <h3>${item.name}</h3>
                    <p class="item-price">ETB ${price.toFixed(2)}</p>
                    <p class="item-subtotal">Subtotal: ETB ${subtotal.toFixed(2)}</p>
                    <div class="quantity-controls">
                        <button type="button" class="quantity-btn decrease-quantity" data-product-id="${item.id}">-</button>
                        <span class="item-quantity">${quantity}</span>
                        <button type="button" class="quantity-btn increase-quantity" data-product-id="${item.id}">+</button>
                    </div>
                </div>
                <button type="button" class="remove-item-btn" data-product-id="${item.id}" title="Remove item">
                    <i class="fas fa-trash"></i>
                </button>
            `;
            cartItemsList.appendChild(div);
        });

        cartTotalElement.textContent = total.toFixed(2);
        totalAmountHiddenInput.value = total.toFixed(2);
        cartDataHiddenInput.value = JSON.stringify(cart);
        updateCartCountInHeader();

    } catch (err) {
        console.error("Cart fetch error:", err);
        showFlashMessage('Something went wrong while loading your cart.', 'danger');
    }
}

// ======================== 💳 Payment Page ========================
function initializePaymentOptions() {
    const radios = document.querySelectorAll('input[name="payment_method"]');
    const telebirr = document.getElementById('telebirr-details');
    const cbebirr = document.getElementById('cbebirr-details');

    const toggleSections = () => {
        if (telebirr) telebirr.style.display = 'none';
        if (cbebirr) cbebirr.style.display = 'none';

        const selected = document.querySelector('input[name="payment_method"]:checked')?.value;
        if (selected === 'telebirr' && telebirr) telebirr.style.display = 'block';
        else if (selected === 'cbebirr' && cbebirr) cbebirr.style.display = 'block';
    };

    radios.forEach(radio => radio.addEventListener('change', toggleSections));
    toggleSections(); // Init on load
}

// ======================== 🔐 Account Page ========================
function initializeAccountPage(container) {
    const loginBtn = container.querySelector('.login');
    const signupBtn = container.querySelector('.signup');
    loginBtn?.addEventListener('click', () => container.classList.remove('active'));
    signupBtn?.addEventListener('click', () => container.classList.add('active'));
}

// ======================== 🛠️ Admin Panel ========================
function initializeAdminPanel() {
    console.log("Admin panel initialized.");
}
