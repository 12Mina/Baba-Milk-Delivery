// ======================== 🚀 Initialize ========================
document.addEventListener('DOMContentLoaded', () => {
    if (typeof displayFlashMessages === 'function') displayFlashMessages(); // This runs once on load
    updateCartCountInHeader(); // Initial update for header count

    // Initialize Add to Cart buttons on all product pages
    initializeAddToCartButtons();

    const body = document.body;

    // Check if on the cart page and render items
    if (body.contains(document.getElementById('cart-page-container'))) {
        renderCartItems();
        initializeCartPageElements();
    }

    // Initialize payment options on payment page
    if (body.contains(document.getElementById('payment-page-container'))) {
        initializePaymentOptions();
    }

    // Initialize account page (login/signup)
    const accountContainer = document.getElementById('container');
    if (body.contains(accountContainer)) {
        initializeFlorinPopAccountPage(accountContainer);
    }

    // Initialize admin panel
    if (body.contains(document.getElementById('admin-panel-container'))) {
        initializeAdminPanel();
    }

    // Track Button placeholder
    const trackButton = document.querySelector('.track-button');
    if (trackButton) {
        trackButton.addEventListener('click', () => {
            displayFlashMessage('📦 Tracking feature is coming soon!', 'info');
        });
    }
});

// ======================== ✨ Flash Messages ========================
// This is for auto-hiding static flash messages rendered by Flask
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

// Fetches the latest cart count from the backend and updates the header icon
async function updateCartCountInHeader() {
    try {
        const response = await fetch('/cart/total_quantity');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        const cartCounter = document.querySelector('.cart-count');
        if (cartCounter) {
            cartCounter.textContent = data.total_quantity;
        }
    } catch (error) {
        console.error("Failed to fetch cart total quantity:", error);
        // Optionally set a default or error state for the cart count
        const cartCounter = document.querySelector('.cart-count');
        if (cartCounter) cartCounter.textContent = '0'; // Or '?'
    }
}

function initializeAddToCartButtons() {
    const buttons = document.querySelectorAll('.add-to-cart-btn');
    buttons.forEach(button => {
        button.addEventListener('click', () => {
            const productId = button.getAttribute('data-product-id');
            // Extract product name if needed, or pass only ID and get name from server
            const productName = button.closest('.product-card')?.querySelector('h3')?.textContent || 'Unknown Product';
            addToCart(productId, productName); // Pass product name for better flash message
        });
    });
}

// Sends product to backend to add to cart
async function addToCart(productId, productName) {
    console.log(`🧺 Attempting to add product ${productId} (${productName}) to cart...`);
    try {
        const response = await fetch('/add_to_cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest' // Helps Flask distinguish AJAX
            },
            body: JSON.stringify({ product_id: productId }) // Only product_id needed, server fetches details
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
        }

        const data = await response.json();
        if (data.success) {
            displayFlashMessage(data.message || `Successfully added ${productName} to cart!`, 'success');
            updateCartCountInHeader(); // Update cart count in header immediately
            // If on the cart page, re-render the cart items
            if (document.body.contains(document.getElementById('cart-page-container'))) {
                renderCartItems();
            }
        } else {
            displayFlashMessage(data.message || 'Failed to add item to cart.', 'danger');
        }
    } catch (error) {
        console.error("Error adding to cart:", error);
        displayFlashMessage(`Error: Could not add ${productName} to cart.`, 'danger');
    }
}

// ======================== 🧾 Cart Rendering ========================
async function renderCartItems() {
    const cartPageContainer = document.getElementById('cart-page-container');
    if (!cartPageContainer) return; // Only run if on the actual cart page

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
        // Ensure data.items is an array or convert the object of items to an array of its values
        const cart = Array.isArray(data.items) ? data.items : Object.values(data.items || {});

        cartItemsList.innerHTML = ''; // Clear existing items
        let total = 0;

        if (cart.length === 0) {
            emptyCartMessage.style.display = 'block';
            cartSummarySection.style.display = 'none';
            cartTotalElement.textContent = '0.00';
            totalAmountHiddenInput.value = '0.00';
            cartDataHiddenInput.value = '[]';
            // Also ensure the header count reflects the empty cart
            updateCartCountInHeader();
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

        // Re-attach event listeners for quantity and remove buttons after re-rendering
        // Event delegation on `cartItemsList` is good, but ensure it's outside the loop
        // and only attached once if this function can be called multiple times.
        // For simplicity here, we'll re-attach listeners globally in initializeCartPageElements or use delegation.
        // The current delegation inside renderCartItems works, but ensure it's not adding multiple listeners if renderCartItems is called often.
        // A better approach for delegation is to set it up once in initializeCartPageElements.
        // For now, let's keep it here but know it's a potential area for optimization.
        // Ensure this listener is only added once. If renderCartItems is called multiple times,
        // it will add duplicate listeners. Better to put this in initializeCartPageElements.
        // Let's move it to initializeCartPageElements.
        // The original design of adding it inside renderCartItems was problematic for multiple calls.
        // It's removed from here now.
    } catch (err) {
        console.error('Failed to fetch cart items:', err);
        displayFlashMessage('Failed to load cart items. Try again.', 'danger');
    }
}


// ======================== 📦 Cart Page Elements (Fixed) ========================
function initializeCartPageElements() {
    console.log('✅ Cart page elements initialized.');
    const cartItemsList = document.getElementById('cart-items-list');

    if (cartItemsList) {
        // Use event delegation for quantity and remove buttons
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

// ======================== 🛒 Cart Update Functions (Backend Integration) ========================

// Handles updating item quantity in the cart (increase/decrease)
async function updateQuantityInCart(productId, delta) {
    console.log(`Cart: Updating product ${productId} by ${delta}`);
    try {
        const response = await fetch('/cart/update_quantity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ product_id: productId, delta: delta })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
        }

        const data = await response.json();
        if (data.success) {
            displayFlashMessage(data.message, 'success');
            renderCartItems(); // Re-render the cart list to show updated quantities and total
            updateCartCountInHeader(); // Update the header cart count
        } else {
            displayFlashMessage(data.message || 'Failed to update item quantity.', 'danger');
        }
    } catch (error) {
        console.error("Error updating cart quantity:", error);
        displayFlashMessage('Error: Could not update cart quantity.', 'danger');
    }
}

// Handles removing an item from the cart
async function removeFromCart(productId) {
    console.log(`Cart: Removing product ${productId}`);
    try {
        const response = await fetch('/cart/remove_item', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ product_id: productId })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
        }

        const data = await response.json();
        if (data.success) {
            displayFlashMessage(data.message, 'success');
            renderCartItems(); // Re-render the cart list
            updateCartCountInHeader(); // Update the header cart count
        } else {
            displayFlashMessage(data.message || 'Failed to remove item.', 'danger');
        }
    } catch (error) {
        console.error("Error removing item from cart:", error);
        displayFlashMessage('Error: Could not remove item from cart.', 'danger');
    }
}