// ======================== 🚀 Initialize ========================
document.addEventListener('DOMContentLoaded', () => {
    // Display flash messages that might have been rendered by Flask on page load
    displayFlaskFlashMessages();
    
    // Update cart count in the header on initial page load
    updateCartCountInHeader(); 

    // Initialize Add to Cart buttons on all product cards
    initializeAddToCartButtons();

    const body = document.body;

    // Check if on the cart page and render items
    if (body.contains(document.getElementById('cart-page-container'))) {
        renderCartItems();
        initializeCartPageElements(); // Attach event listeners for cart quantity/remove
    }

    // Initialize payment options on payment page
    if (body.contains(document.getElementById('payment-page-container'))) {
        initializePaymentOptions();
    }

    // Initialize account page (login/signup) - handled by account.html's own script
    const accountContainer = document.getElementById('account-page-container'); 
    if (body.contains(accountContainer)) {
        console.log("Account page elements primarily handled by account.html's internal script.");
    }

    // Initialize admin panel (placeholder)
    if (body.contains(document.getElementById('admin-panel-container'))) {
        initializeAdminPanel();
    }

    // Track Button placeholder - Ensure this is correctly linked in your HTML
    const trackButton = document.querySelector('.track-button');
    if (trackButton) {
        trackButton.addEventListener('click', (e) => {
            e.preventDefault(); // Prevent default link behavior if it's just a placeholder
            showFlashMessage('📦 Tracking feature is coming soon!', 'info');
        });
    }
});

// ======================== ✨ Flash Message Utilities ========================

// This function is for client-side triggered flash messages
function showFlashMessage(message, type = 'info') {
    const flashContainer = document.getElementById('flash-message-container');
    if (!flashContainer) {
        console.error("Flash message container not found!");
        return;
    }
    const flashDiv = document.createElement('div');
    flashDiv.className = `alert alert-${type}`;
    flashDiv.textContent = message;
    flashContainer.appendChild(flashDiv);

    setTimeout(() => {
        flashDiv.remove();
    }, 3000); // Messages disappear after 3 seconds
}

// This function handles Flask's server-side flashed messages
function displayFlaskFlashMessages() {
    const flashMessagesDataElement = document.getElementById('flash-messages-data');
    if (flashMessagesDataElement) {
        try {
            // Parse the JSON string from the hidden script tag
            const flashedMessages = JSON.parse(flashMessagesDataElement.textContent || '[]');
            const flashMessageContainer = document.getElementById('flash-message-container');

            if (flashedMessages.length > 0 && flashMessageContainer) {
                flashedMessages.forEach(msg => {
                    const alertDiv = document.createElement('div');
                    alertDiv.className = `alert alert-${msg.category}`; // Use Flask's category directly
                    alertDiv.textContent = msg.message;
                    flashMessageContainer.appendChild(alertDiv);

                    // Auto-hide messages
                    setTimeout(() => {
                        alertDiv.remove();
                    }, 4000); // Flask messages disappear after 4 seconds
                });
                // Clear the content of the script tag so messages aren't re-displayed on soft navigations
                flashMessagesDataElement.textContent = '[]'; 
            }
        } catch (e) {
            console.error("Error parsing Flask flash messages:", e);
        }
    }
}


// ======================== 🛒 Cart Functions (Core Logic) ========================

async function updateCartCountInHeader() {
    console.log("Attempting to update cart count in header...");
    try {
        const response = await fetch('/cart/total_quantity');
        if (!response.ok) {
            console.error(`Failed to fetch cart total quantity: HTTP error! status: ${response.status}`);
            const cartCounter = document.querySelector('.cart-count');
            if (cartCounter) cartCounter.textContent = '0';
            return; 
        }
        const data = await response.json();
        const cartCounter = document.querySelector('.cart-count');
        if (cartCounter) {
            cartCounter.textContent = data.total_quantity > 0 ? data.total_quantity : '';
            console.log(`Cart count updated to: ${data.total_quantity}`);
        }
    } catch (error) {
        console.error("Error fetching cart total quantity:", error);
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
            addToCart(productId, 1, productName); // Pass quantity as 1 by default
        });
    });
}

async function addToCart(productId, quantity = 1, productName = 'item') {
    console.log(`🧺 Attempting to add product ${productId} (${productName}) to cart...`);
    try {
        const response = await fetch('/add_to_cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest' // Crucial for Flask to identify AJAX
            },
            body: JSON.stringify({ product_id: productId, quantity: quantity })
        });

        // Parse JSON immediately, as Flask now guarantees JSON even for auth errors
        const data = await response.json();
        console.log("addToCart API response:", { status: response.status, data: data });


        // Check for 401 status OR specific error message from Flask
        if (response.status === 401 || data.error === 'Not logged in') {
            showFlashMessage(data.message || 'Please log in to add items to your cart.', 'warning');
            setTimeout(() => window.location.href = '/account', 1500); // Redirect to login
            return;
        }

        // Now handle successful (2xx) or other non-auth errors
        if (response.ok && data.success) { 
            showFlashMessage(data.message || `Successfully added ${productName} to cart!`, 'success');
            updateCartCountInHeader(); 
            if (document.body.contains(document.getElementById('cart-page-container'))) {
                renderCartItems(); // Re-render cart if on the cart page
            }
        } else {
            // Server returned a 2xx status but 'success: false' or other non-401 error
            showFlashMessage(data.message || data.error || 'Failed to add item to cart.', 'danger');
        }
    } catch (error) {
        console.error("Network or parsing error adding to cart:", error);
        showFlashMessage(`Error: Could not add ${productName} to cart. Check your connection.`, 'danger');
    }
}

async function updateQuantityInCart(productId, delta) {
    console.log(`Updating quantity for product ${productId} by ${delta}...`);
    try {
        const response = await fetch('/cart/update_quantity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ product_id: productId, delta: delta })
        });

        const data = await response.json();
        console.log("updateQuantityInCart API response:", { status: response.status, data: data });

        if (response.status === 401 || data.error === 'Not logged in') {
            showFlashMessage(data.message || 'Please log in to update your cart.', 'warning');
            setTimeout(() => window.location.href = '/account', 1500);
            return;
        }

        if (response.ok && data.success) {
            showFlashMessage(data.message, 'success');
            updateCartCountInHeader(); 
            renderCartItems();
        } else {
            showFlashMessage(data.message || data.error || 'Failed to update cart quantity.', 'danger');
        }
    } catch (error) {
        console.error('Network or parsing error updating cart quantity:', error);
        showFlashMessage('An error occurred while updating cart quantity.', 'danger');
    }
}

async function removeFromCart(productId) {
    if (!confirm("Are you sure you want to remove this item from your cart?")) {
        return;
    }
    console.log(`Removing product ${productId} from cart...`);

    try {
        const response = await fetch('/cart/remove_item', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ product_id: productId })
        });

        const data = await response.json();
        console.log("removeFromCart API response:", { status: response.status, data: data });

        if (response.status === 401 || data.error === 'Not logged in') {
            showFlashMessage(data.message || 'Please log in to manage your cart.', 'warning');
            setTimeout(() => window.location.href = '/account', 1500);
            return;
        }

        if (response.ok && data.success) {
            showFlashMessage(data.message, 'info');
            updateCartCountInHeader(); 
            renderCartItems();
        } else {
            showFlashMessage(data.message || data.error || 'Failed to remove item from cart.', 'warning');
        }
    } catch (error) {
        console.error('Network or parsing error removing item from cart:', error);
        showFlashMessage('An error occurred while removing item.', 'danger');
    }
}

// ======================== 🧾 Cart Page Rendering ========================

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
        console.error("Missing essential cart page elements. Check your cart.html structure.");
        return;
    }
    console.log("Attempting to render cart items...");

    try {
        const response = await fetch('/cart/items', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' } // Explicitly send XHR header
        });
        
        // Parse JSON immediately, as Flask now guarantees JSON even for auth errors
        const data = await response.json();
        console.log("renderCartItems API response:", { status: response.status, data: data });
        
        // Check for 401 status or specific error message from Flask
        if (response.status === 401 || data.error === 'Not logged in') {
            showFlashMessage(data.message || "Please log in to view your cart items.", "warning");
            setTimeout(() => window.location.href = '/account', 1500);
            // After showing message and redirecting, clear and hide cart elements immediately
            cartItemsList.innerHTML = '';
            emptyCartMessage.style.display = 'block';
            cartSummarySection.style.display = 'none';
            cartTotalElement.textContent = '0.00';
            totalAmountHiddenInput.value = '0.00';
            cartDataHiddenInput.value = '[]';
            updateCartCountInHeader(); // Update header to reflect empty cart
            return; 
        }

        // Cart items are now guaranteed to be available (even if empty)
        const cart = Array.isArray(data.items) ? data.items : Object.values(data.items || {});

        cartItemsList.innerHTML = '';
        let total = 0;

        if (cart.length === 0) {
            console.log("Cart is empty.");
            emptyCartMessage.style.display = 'block';
            cartSummarySection.style.display = 'none';
            cartTotalElement.textContent = '0.00';
            totalAmountHiddenInput.value = '0.00';
            cartDataHiddenInput.value = '[]';
            updateCartCountInHeader();
            return;
        } else {
            console.log(`Cart has ${cart.length} items.`);
            emptyCartMessage.style.display = 'none';
            cartSummarySection.style.display = 'block';
        }

        cart.forEach(item => {
            const itemPrice = parseFloat(item.price) || 0;
            const itemQuantity = parseInt(item.quantity) || 0;
            const subtotal = itemPrice * itemQuantity;
            total += subtotal;
            // Use item.image_path as it's now stored in the session cart
            const imagePath = `/static/${item.image_path}`; 

            const cartItemDiv = document.createElement('div');
            cartItemDiv.className = 'cart-item';
            cartItemDiv.innerHTML = `
                <img src="${imagePath}" alt="${item.name}" class="cart-item-img">
                <div class="item-details">
                    <h3>${item.name}</h3>
                    <p class="item-price">ETB ${itemPrice.toFixed(2)}</p>
                    <p class="item-subtotal">Subtotal: ETB ${subtotal.toFixed(2)}</p>
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
            cartItemsList.appendChild(cartItemDiv);
        });

        cartTotalElement.textContent = total.toFixed(2);
        totalAmountHiddenInput.value = total.toFixed(2);
        cartDataHiddenInput.value = JSON.stringify(cart);
        updateCartCountInHeader();
    } catch (err) {
        console.error('Failed to fetch or render cart items:', err);
        showFlashMessage('Failed to load cart items. Please try refreshing the page.', 'danger');
    }
}

function initializeCartPageElements() {
    console.log('✅ Cart page elements initialized.');
    const cartItemsList = document.getElementById('cart-items-list');

    if (cartItemsList) {
        cartItemsList.addEventListener('click', async (e) => {
            const target = e.target;
            const productId = target.closest('[data-product-id]')?.getAttribute('data-product-id');

            if (!productId) return;

            if (target.classList.contains('decrease-quantity') || (target.tagName === 'I' && target.closest('.decrease-quantity'))) {
                await updateQuantityInCart(productId, -1);
            } else if (target.classList.contains('increase-quantity') || (target.tagName === 'I' && target.closest('.increase-quantity'))) {
                await updateQuantityInCart(productId, 1);
            } else if (target.closest('.remove-item-btn')) {
                await removeFromCart(productId);
            }
        });
    }
}

// ======================== 💳 Payment Page ========================

function initializePaymentOptions() {
    const paymentMethodRadios = document.querySelectorAll('input[name="payment_method"]');
    const telebirrDetails = document.getElementById('telebirr-details');
    const cbebirrDetails = document.getElementById('cbebirr-details');

    if (paymentMethodRadios.length > 0) {
        const updatePaymentDetailsVisibility = () => {
            if (telebirrDetails) telebirrDetails.style.display = 'none';
            if (cbebirrDetails) cbebirrDetails.style.display = 'none';

            const selectedMethod = document.querySelector('input[name="payment_method"]:checked')?.value;
            if (selectedMethod === 'telebirr' && telebirrDetails) {
                telebirrDetails.style.display = 'block';
            } else if (selectedMethod === 'cbebirr' && cbebirrDetails) {
                cbebirrDetails.style.display = 'block';
            }
        };

        paymentMethodRadios.forEach(radio => {
            radio.addEventListener('change', updatePaymentDetailsVisibility);
        });

        updatePaymentDetailsVisibility();
    }
}

// ======================== 🔐 Account Page ========================

function initializeAccountPage(container) {
    // This function is commented out as account.html itself handles its toggling
    // const loginBtn = container.querySelector('.login');
    // const signupBtn = container.querySelector('.signup');
    // const formWrapper = container;

    // loginBtn?.addEventListener('click', () => {
    //     formWrapper.classList.remove('active');
    // });

    // signupBtn?.addEventListener('click', () => {
    //     formWrapper.classList.add('active');
    // });
}

// ======================== 🛠️ Admin Panel (Placeholder) ========================
function initializeAdminPanel() {
    console.log("Admin panel initialized.");
}
