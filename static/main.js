// ======================== 🚀 Initialize ========================
// This script runs once the entire DOM is loaded, acting as the main entry point.
document.addEventListener('DOMContentLoaded', () => {
    // 1. Display flash messages from session storage (e.g., from Flask redirects)
    //    Ensure your Flask app puts these messages into sessionStorage on redirect.
    displayFlashMessages();

    // 2. Update the cart count in the header navigation immediately on page load.
    updateCartCountInHeader();

    // 3. Set up click listeners for all 'Add to Cart' buttons across product listings.
    initializeAddToCartButtons();

    // 4. Initialize page-specific functionalities
    if (document.getElementById('cart-page-container')) {
        renderCartItems();
        initializeCartPageElements();
    }

    if (document.getElementById('payment-page-container')) {
        initializePaymentOptions();
    }

    if (document.getElementById('account-page-container')) {
        setupAccountPage();
    }

    if (document.getElementById('admin-panel-container')) {
        initializeAdminPanel();
    }

    // Initialize track button (if present)
    const trackButton = document.querySelector('.track-button');
    if (trackButton) {
        trackButton.addEventListener('click', () => {
            displayFlashMessage('📦 Tracking feature is coming soon!', 'info');
        });
    }
});

// --- Core Cart Management Functions (Client-side logic sending requests to Flask) ---

// ======================== 🧾 Cart Count Handling (for header) ========================
/**
 * Fetches the current total quantity of items in the cart from the Flask backend
 * and updates the number displayed in the cart icon in the header.
 */
async function updateCartCountInHeader() {
    const cartCountEl = document.querySelector('.cart-count');
    if (!cartCountEl) {
        return;
    }

    try {
        const response = await fetch('/cart/total_quantity');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        const totalItems = data.total_quantity || 0;
        cartCountEl.textContent = totalItems;
        cartCountEl.style.display = totalItems > 0 ? 'inline-block' : 'none';
    } catch (error) {
        console.error('Error fetching cart total quantity:', error);
        cartCountEl.textContent = '0';
        cartCountEl.style.display = 'none';
        displayFlashMessage('Failed to update cart count.', 'danger');
    }
}

// ======================== 🛒 Add to Cart Logic ========================
/**
 * Sends a request to the Flask backend to add a product to the cart.
 * @param {string} productId - The ID of the product.
 * @param {string} name - The name of the product.
 * @param {number} price - The price of the product.
 * @param {string} imagePath - The relative path to the product image (e.g., "Product1.jpg").
 */
async function addToCart(productId, name, price, imagePath) {
    try {
        const response = await fetch('/add_to_cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                product_id: productId,
                name: name,
                price: price,
                image_path: imagePath
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.success) {
            updateCartCountInHeader();
            // Flask's set_flash_message handles the success message,
            // which displayFlashMessages will pick up on next page load/redirect.
        } else {
            displayFlashMessage('Error adding to cart: ' + (data.message || 'Unknown error.'), 'danger');
        }
    } catch (error) {
        console.error('Error adding to cart:', error);
        displayFlashMessage('Network error or server issue when adding to cart.', 'danger');
    }
}

// ======================== ❌ Remove Cart Item ========================
/**
 * Sends a request to the Flask backend to remove an item from the cart.
 * @param {string} productId - The ID of the product to remove.
 */
async function removeFromCart(productId) {
    if (!confirm('Are you sure you want to remove this item from your cart?')) {
        return;
    }

    try {
        const response = await fetch('/remove_from_cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ product_id: productId }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.success) {
            renderCartItems();
            updateCartCountInHeader();
            displayFlashMessage('Item removed from cart.', 'success');
        } else {
            displayFlashMessage('Error removing item: ' + (data.message || 'Unknown error.'), 'danger');
        }
    } catch (error) {
        console.error('Error removing item from cart:', error);
        displayFlashMessage('Network error when removing item.', 'danger');
    }
}

// ======================== ➕/➖ Update Cart Item Quantity ========================
/**
 * Sends a request to the Flask backend to update the quantity of a specific item in the cart.
 * @param {string} productId - The ID of the product to update.
 * @param {number} change - The amount to change the quantity by (e.g., 1 for increment, -1 for decrement).
 */
async function updateQuantityInCart(productId, change) {
    try {
        const response = await fetch('/update_cart_quantity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ product_id: productId, change: change }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.success) {
            renderCartItems();
            updateCartCountInHeader();
        } else {
            displayFlashMessage('Error updating quantity: ' + (data.message || 'Unknown error.'), 'danger');
        }
    } catch (error) {
        console.error('Error updating cart quantity:', error);
        displayFlashMessage('Network error when updating quantity.', 'danger');
    }
}

// --- UI Initialization & Rendering Functions ---

// ======================== 🛒 Initialize Add to Cart Buttons ========================
/**
 * Sets up click listeners for all 'Add to Cart' buttons on product pages.
 */
function initializeAddToCartButtons() {
    document.querySelectorAll('.add-to-cart-btn').forEach(button => {
        button.addEventListener('click', () => {
            const productId = button.getAttribute('data-product-id');
            const name = button.getAttribute('data-name');
            const price = parseFloat(button.getAttribute('data-price'));
            const imgElement = button.closest('.product-card')?.querySelector('img');
            let imagePath = '';

            if (imgElement) {
                const fullSrc = imgElement.getAttribute('src');
                const lastSlashIndex = fullSrc.lastIndexOf('/');
                imagePath = lastSlashIndex !== -1 ? fullSrc.substring(lastSlashIndex + 1) : fullSrc;
            } else {
                console.warn(`Could not find image for product ${productId}.`);
            }

            if (productId && name && !isNaN(price)) {
                addToCart(productId, name, price, imagePath);
            } else {
                displayFlashMessage('Invalid product data to add to cart.', 'danger');
                console.error('Missing data for product:', { productId, name, price, imagePath });
            }
        });
    });
}

// ======================== 🛍️ Render Cart Items (for cart page) ========================
/**
 * Dynamically fetches and displays items in the shopping cart on the cart page.
 */
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
            const cartItem = document.createElement('div');
            cartItem.className = 'cart-item';

            const itemPrice = parseFloat(item.price) || 0;
            const itemQuantity = parseInt(item.quantity) || 0;
            total += itemPrice * itemQuantity;

            const fullImagePath = `/static/Image/${item.image_path}`;

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

        // Attach event listeners using event delegation for efficiency
        cartItemsList.addEventListener('click', (e) => {
            const target = e.target;
            const productId = target.closest('[data-product-id]')?.getAttribute('data-product-id');

            if (!productId) return;

            if (target.classList.contains('decrease-quantity')) {
                updateQuantityInCart(productId, -1);
            } else if (target.classList.contains('increase-quantity')) {
                updateQuantityInCart(productId, 1);
            } else if (target.closest('.remove-item-btn')) { // Use closest for the button itself or its icon
                removeFromCart(productId);
            }
        });

    } catch (error) {
        console.error('Error fetching cart items:', error);
        displayFlashMessage('Failed to load cart items. Please try refreshing the page.', 'danger');
    }
}

// ======================== 🛒 Cart Page Specific Functionality (Delivery/Payment) ========================
/**
 * Initializes interactive elements on the cart page, like showing delivery information and proceeding to payment.
 */
function initializeCartPageElements() {
    const proceedToDeliveryBtn = document.getElementById('proceedToDeliveryBtn');
    const deliveryInfoSection = document.getElementById('deliveryInfoSection');
    const deliveryForm = document.getElementById('delivery-form');
    const useGoogleMapButton = document.getElementById('useGoogleMapButton');

    if (deliveryInfoSection) {
        deliveryInfoSection.style.display = 'none';
    }

    if (proceedToDeliveryBtn && deliveryInfoSection) {
        proceedToDeliveryBtn.addEventListener('click', function() {
            const isHidden = (deliveryInfoSection.style.display === 'none' || deliveryInfoSection.style.display === '');
            deliveryInfoSection.style.display = isHidden ? 'block' : 'none';
            if (isHidden) {
                deliveryInfoSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    }

    if (useGoogleMapButton) {
        useGoogleMapButton.addEventListener('click', function() {
            displayFlashMessage('Integrating Google Maps for address selection. (You would implement Google Maps API here)', 'info');
        });
    }

    if (deliveryForm) {
        deliveryForm.addEventListener('submit', function(event) {
            const cartDataInput = document.getElementById('cart-data-hidden');
            let currentCartItems = [];
            try {
                currentCartItems = JSON.parse(cartDataInput.value || '[]');
            } catch (e) {
                console.error("Error parsing cart data before delivery submission:", e);
                displayFlashMessage('An error occurred with cart data. Please refresh and try again.', 'danger');
                event.preventDefault();
                return;
            }

            if (currentCartItems.length === 0) {
                event.preventDefault();
                displayFlashMessage('Your cart is empty. Please add items before proceeding to delivery.', 'warning');
            }
        });
    }
}

// ======================== 💰 Initialize Payment Options (for payment page) ========================
/**
 * Manages the display of payment method details based on user selection.
 */
function initializePaymentOptions() {
    const paymentForm = document.getElementById('payment-form');
    const paymentMethodRadios = document.querySelectorAll('input[name="payment_method"]');
    const telebirrDetails = document.getElementById('telebirr-details');
    const cbebirrDetails = document.getElementById('cbebirr-details');

    function hideAllPaymentDetails() {
        [telebirrDetails, cbebirrDetails].forEach(detailDiv => {
            if (detailDiv) {
                detailDiv.classList.add('hidden');
                detailDiv.querySelectorAll('input, select, textarea').forEach(el => {
                    el.removeAttribute('required');
                });
            }
        });
    }

    paymentMethodRadios.forEach(radio => {
        radio.addEventListener('change', (event) => {
            hideAllPaymentDetails();
            const selectedMethod = event.target.value;
            if (selectedMethod === 'telebirr') {
                if (telebirrDetails) {
                    telebirrDetails.classList.remove('hidden');
                    telebirrDetails.querySelector('input[type="tel"]')?.setAttribute('required', 'required');
                }
            } else if (selectedMethod === 'cbebirr') {
                if (cbebirrDetails) {
                    cbebirrDetails.classList.remove('hidden');
                    cbebirrDetails.querySelector('input[type="tel"]')?.setAttribute('required', 'required');
                }
            }
        });
    });

    let checkedRadio = document.querySelector('input[name="payment_method"]:checked');
    if (!checkedRadio && paymentMethodRadios.length > 0) {
        paymentMethodRadios[0].checked = true;
        checkedRadio = paymentMethodRadios[0];
    }
    if (checkedRadio) {
        const event = new Event('change');
        checkedRadio.dispatchEvent(event);
    }

    if (paymentForm) {
        paymentForm.addEventListener('submit', function(event) {
            const totalAmountHiddenInput = document.getElementById('total-amount-hidden-payment');
            const cartDataHiddenInput = document.getElementById('cart-data-hidden-payment');

            let totalAmount = parseFloat(totalAmountHiddenInput?.value || '0');
            let cartData = [];
            try {
                cartData = JSON.parse(cartDataHiddenInput?.value || '[]');
            } catch (e) {
                console.error("Error parsing cart data on payment submission:", e);
                displayFlashMessage('An error occurred with cart data. Please refresh and try again.', 'danger');
                event.preventDefault();
                return;
            }

            if (cartData.length === 0 || totalAmount <= 0) {
                event.preventDefault();
                displayFlashMessage('Your cart is empty. Please add items before finalizing order.', 'warning');
                return;
            }
        });
    }
}

// ======================== 👤 Account Page Functionality ========================
/**
 * Sets up listeners for login/signup form toggling and modal display.
 */
function setupAccountPage() {
    const loginFormContainer = document.getElementById('login-form-container');
    const signupModal = document.getElementById('signupModal');
    const toggleSignupLink = document.getElementById('toggle-signup');
    const closeSignupModal = document.querySelector('#signupModal .close-button');
    const toggleLoginLink = document.getElementById('toggle-login');

    if (!loginFormContainer || !signupModal || !toggleSignupLink || !closeSignupModal || !toggleLoginLink) {
        console.warn("Missing elements for account page setup. Some functionality may not work.");
        return;
    }

    signupModal.style.display = 'none';

    toggleSignupLink.addEventListener('click', (e) => {
        e.preventDefault();
        showModal(signupModal);
        loginFormContainer.classList.add('hidden');
    });

    toggleLoginLink.addEventListener('click', (e) => {
        e.preventDefault();
        hideModal(signupModal);
        loginFormContainer.classList.remove('hidden');
    });

    closeSignupModal.addEventListener('click', () => {
        hideModal(signupModal);
        loginFormContainer.classList.remove('hidden');
    });

    window.addEventListener('click', (event) => {
        if (event.target == signupModal) {
            hideModal(signupModal);
            loginFormContainer.classList.remove('hidden');
        }
    });
}

// ======================== ✨ Modal Utility Functions ========================
/**
 * Displays a given modal element.
 * @param {HTMLElement} modalElement - The modal DOM element to show.
 */
function showModal(modalElement) {
    if (modalElement) {
        modalElement.style.display = 'block';
    }
}

/**
 * Hides a given modal element.
 * @param {HTMLElement} modalElement - The modal DOM element to hide.
 */
function hideModal(modalElement) {
    if (modalElement) {
        modalElement.style.display = 'none';
    }
}

// ======================== 📊 Admin Panel Functionality ========================
/**
 * Initializes functionality specific to the admin panel, like updating order statuses.
 */
function initializeAdminPanel() {
    document.querySelectorAll('.update-status-form').forEach(form => {
        form.addEventListener('submit', function(event) {
            // This form submits directly to Flask, so no AJAX event.preventDefault() needed here
            // unless you explicitly want to handle the submission via AJAX.
        });
    });
}

// ======================== 💬 Flash Message Display ========================
/**
 * Displays flash messages retrieved from sessionStorage.
 * This function is designed to work with Flask's set_flash_message
 * which needs to pass the messages to the client-side's sessionStorage.
 *
 * How to pass flash messages from Flask to sessionStorage:
 * In your base.html (or layout template), within a <script> tag:
 *
 * <script>
 * document.addEventListener('DOMContentLoaded', function() {
 * const flaskMessages = {{ get_flashed_messages(with_categories=true) | tojson | safe }};
 * if (flaskMessages.length > 0) {
 * let existingMessages = JSON.parse(sessionStorage.getItem('flash_messages') || '[]');
 * flaskMessages.forEach(msg => {
 * existingMessages.push({ message: msg[1], category: msg[0] }); // msg[0] is category, msg[1] is message
 * });
 * sessionStorage.setItem('flash_messages', JSON.stringify(existingMessages));
 * }
 * // Now call displayFlashMessages(); from your main JS file
 * });
 * </script>
 */
function displayFlashMessages() {
    const messages = JSON.parse(sessionStorage.getItem('flash_messages') || '[]');
    const container = document.querySelector('.flash-messages');

    if (!container) {
        return;
    }

    container.innerHTML = '';

    messages.forEach(msg => {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${msg.category}`;
        alertDiv.innerHTML = `
            ${msg.message}
            <button class="close-alert-btn" onclick="this.parentElement.remove()">×</button>
        `;

        container.appendChild(alertDiv);

        if (msg.message.includes('Order placed successfully') && msg.category === 'success') {
            updateCartCountInHeader();
        }

        setTimeout(() => {
            alertDiv.style.opacity = '0';
            alertDiv.addEventListener('transitionend', () => alertDiv.remove());
        }, 6000);
    });

    sessionStorage.removeItem('flash_messages');
}

/**
 * Manually adds a flash message to sessionStorage and triggers its display.
 * Useful for client-side validations or immediate feedback.
 * @param {string} message - The message content.
 * @param {string} category - The category (e.g., 'success', 'danger', 'warning', 'info').
 */
function displayFlashMessage(message, category) {
    let messages = JSON.parse(sessionStorage.getItem('flash_messages') || '[]');
    messages.push({ message: message, category: category });
    sessionStorage.setItem('flash_messages', JSON.stringify(messages));
    displayFlashMessages();
}

// ======================== 🌐 Language Switch (Stub) ========================
/**
 * Placeholder function for switching the website language.
 * @param {string} lang - The language code (e.g., 'en', 'am').
 */
function setLang(lang) {
    displayFlashMessage("Language switching is not yet implemented. (Selected: " + lang + ")", 'info');
}