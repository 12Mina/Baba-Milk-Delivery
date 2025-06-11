// ======================== 🚀 Initialize ========================
document.addEventListener('DOMContentLoaded', () => {
    displayFlashMessages();
    updateCartCountInHeader();
    initializeAddToCartButtons();

    const body = document.body;

    if (body.contains(document.getElementById('cart-page-container'))) {
        renderCartItems();
        initializeCartPageElements();
    }

    if (body.contains(document.getElementById('payment-page-container'))) {
        initializePaymentOptions();
    }

    const accountContainer = document.getElementById('container');
    if (body.contains(accountContainer)) {
        console.log("🔧 Initializing Florin Pop account page functionality...");
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

// (The rest remains unchanged until renderCartItems)

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
        console.error("Missing critical cart elements. Cannot render cart items. Check your cart.html template.");
        return;
    }

    try {
        const response = await fetch('/cart/items');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
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

            const fullImagePath = `/static/image/${item.image_path}`;

            const cartItem = document.createElement('div');
            cartItem.className = 'cart-item';
            cartItem.innerHTML = `
                <img src="${fullImagePath}" alt="${item.name}" class="cart-item-img">
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

        cartItemsList.addEventListener('click', (e) => {
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

    } catch (error) {
        console.error('Error fetching cart items:', error);
        displayFlashMessage('Failed to load cart items. Please try refreshing the page.', 'danger');
    }
}
