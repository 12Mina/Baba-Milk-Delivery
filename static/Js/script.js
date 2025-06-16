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

    // The account.html page handles its own modal and password toggle logic,
    // so no need for a separate initializeAccountPage function in script.js.
    // The relevant JavaScript is inline in account.html.
    const accountPageContainer = document.getElementById('account-page-container');
    if (body.contains(accountPageContainer)) {
        console.log("Account page specific JS handled by account.html's internal script block.");
    }

    // Initialize admin panel (placeholder)
    if (body.contains(document.getElementById('admin-panel-container'))) {
        initializeAdminPanel();
    }

    // NEW: Initialize Mobile Navigation Toggle
    initializeMobileNavToggle();
    // ----------------------------------------
});


// ======================== Flash Messages ========================
function showFlashMessage(message, category) {
    const container = document.getElementById('flash-message-container');
    if (container) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `flash-message ${category}`;
        messageDiv.innerHTML = `${message}<span class="close-btn">&times;</span>`;
        
        container.appendChild(messageDiv);

        // Add close functionality
        messageDiv.querySelector('.close-btn').addEventListener('click', () => {
            messageDiv.remove();
        });

        // Auto-remove after 5 seconds
        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
    }
}

function displayFlaskFlashMessages() {
    const flashDataScript = document.getElementById('flash-messages-data');
    if (flashDataScript) {
        try {
            const messages = JSON.parse(flashDataScript.textContent);
            messages.forEach(([category, message]) => {
                showFlashMessage(message, category);
            });
        } catch (e) {
            console.error("Error parsing flash messages:", e);
        }
    }
}

// ======================== Cart Management ========================

// Function to update cart count displayed in the header
async function updateCartCountInHeader() {
    const cartCountSpan = document.getElementById('cart-count');
    if (cartCountSpan) {
        try {
            const response = await fetch('/get_cart_count');
            if (response.ok) {
                const data = await response.json();
                cartCountSpan.textContent = data.cart_count;
            } else {
                console.error('Failed to fetch cart count.');
            }
        } catch (error) {
            console.error('Error fetching cart count:', error);
        }
    }
}

// Initialize "Add to Cart" buttons
function initializeAddToCartButtons() {
    const addToCartButtons = document.querySelectorAll('.add-to-cart-btn');
    addToCartButtons.forEach(button => {
        button.addEventListener('click', async (event) => {
            const productId = event.target.dataset.productId;
            const productName = event.target.dataset.name;
            const productPrice = event.target.dataset.price; // Get price from data-attribute
            const quantity = 1; // Default quantity for initial add

            await addToCart(productId, quantity, productName, productPrice); // Pass price
        });
    });
}


async function addToCart(productId, quantity, productName, productPrice) { // Accept productPrice
    try {
        const response = await fetch('/add_to_cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ product_id: productId, quantity: quantity })
        });

        const data = await response.json();

        if (response.status === 401 || data.error === 'Not logged in') {
            showFlashMessage(data.message || 'Please log in to add items to your cart.', 'warning');
            setTimeout(() => window.location.href = '/account', 1500); // Redirect to login
            return;
        }

        if (response.ok && data.success) {
            showFlashMessage(data.message, 'success');
            updateCartCountInHeader(); // Update the cart count in the header
            
            // If on cart page, re-render items
            if (document.body.contains(document.getElementById('cart-page-container'))) {
                renderCartItems();
            }

        } else {
            showFlashMessage(data.message || 'Failed to add item to cart.', 'error');
        }
    } catch (error) {
        console.error('Error adding item to cart:', error);
        showFlashMessage('Error: Could not add item to cart. Check your connection.', 'error');
    }
}


// Function to render cart items on the cart page
async function renderCartItems() {
    const cartItemsList = document.getElementById('cart-items-list');
    const emptyCartMessage = document.getElementById('empty-cart-message');
    const cartSummarySection = document.getElementById('cart-summary-section');
    const subtotalSpan = document.getElementById('cart-subtotal');
    const totalAmountSpan = document.getElementById('cart-total');
    const totalAmountHidden = document.getElementById('total-amount-hidden');
    const cartDataHidden = document.getElementById('cart-data-hidden');


    if (!cartItemsList || !emptyCartMessage || !cartSummarySection || !subtotalSpan || !totalAmountSpan || !totalAmountHidden || !cartDataHidden) {
        // Not on the cart page, or elements are missing.
        return;
    }

    try {
        const response = await fetch('/get_cart_items');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        if (data.cart_items && data.cart_items.length > 0) {
            cartItemsList.innerHTML = ''; // Clear existing items
            let subtotal = 0;
            const cartItemsData = []; // To store data for hidden input

            data.cart_items.forEach(item => {
                const itemTotal = item.price * item.quantity;
                subtotal += itemTotal;

                const cartItemDiv = document.createElement('div');
                cartItemDiv.className = 'cart-item';
                cartItemDiv.innerHTML = `
                    <img src="${item.image_url}" alt="${item.name}">
                    <div class="item-details">
                        <h3>${item.name}</h3>
                        <p class="item-price">ETB ${item.price.toFixed(2)}</p>
                    </div>
                    <div class="item-quantity-controls">
                        <button class="quantity-minus" data-product-id="${item.id}">-</button>
                        <input type="number" class="item-quantity-input" value="${item.quantity}" min="1" data-product-id="${item.id}">
                        <button class="quantity-plus" data-product-id="${item.id}">+</button>
                    </div>
                    <p class="item-total">ETB ${itemTotal.toFixed(2)}</p>
                    <button class="remove-item-btn" data-product-id="${item.id}"><i class="fas fa-trash-alt"></i></button>
                `;
                cartItemsList.appendChild(cartItemDiv);

                cartItemsData.push({
                    id: item.id,
                    name: item.name,
                    price: item.price,
                    quantity: item.quantity
                });
            });

            subtotalSpan.textContent = subtotal.toFixed(2);
            totalAmountSpan.textContent = subtotal.toFixed(2); // Assuming no delivery fee/taxes here
            totalAmountHidden.value = subtotal.toFixed(2); // Set hidden total amount
            cartDataHidden.value = JSON.stringify(cartItemsData); // Set hidden cart data

            emptyCartMessage.style.display = 'none';
            cartSummarySection.style.display = 'block';
        } else {
            emptyCartMessage.style.display = 'block';
            cartSummarySection.style.display = 'none';
        }
    } catch (error) {
        console.error('Error rendering cart items:', error);
        showFlashMessage('Error loading cart. Please try again.', 'error');
        emptyCartMessage.style.display = 'block';
        cartSummarySection.style.display = 'none';
    }
}

// Attach event listeners for quantity changes and item removal on cart page
function initializeCartPageElements() {
    const cartItemsList = document.getElementById('cart-items-list');

    // Event delegation for quantity buttons
    cartItemsList.addEventListener('click', async (event) => {
        if (event.target.classList.contains('quantity-minus')) {
            const productId = event.target.dataset.productId;
            const input = event.target.nextElementSibling;
            let quantity = parseInt(input.value) - 1;
            if (quantity < 1) quantity = 1; // Prevent quantity from going below 1
            input.value = quantity;
            await updateCartItemQuantity(productId, quantity);
        } else if (event.target.classList.contains('quantity-plus')) {
            const productId = event.target.dataset.productId;
            const input = event.target.previousElementSibling;
            let quantity = parseInt(input.value) + 1;
            input.value = quantity;
            await updateCartItemQuantity(productId, quantity);
        } else if (event.target.classList.contains('remove-item-btn') || event.target.closest('.remove-item-btn')) {
            const button = event.target.classList.contains('remove-item-btn') ? event.target : event.target.closest('.remove-item-btn');
            const productId = button.dataset.productId;
            await removeCartItem(productId);
        }
    });

    // Event listener for quantity input changes
    cartItemsList.addEventListener('change', async (event) => {
        if (event.target.classList.contains('item-quantity-input')) {
            const productId = event.target.dataset.productId;
            let quantity = parseInt(event.target.value);
            if (isNaN(quantity) || quantity < 1) {
                quantity = 1; // Default to 1 if invalid input
                event.target.value = 1;
            }
            await updateCartItemQuantity(productId, quantity);
        }
    });
}

// Function to update item quantity in cart via API
async function updateCartItemQuantity(productId, quantity) {
    try {
        const response = await fetch('/update_cart_quantity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ product_id: productId, quantity: quantity })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showFlashMessage(data.message, 'success');
            renderCartItems(); // Re-render cart to update totals and item totals
            updateCartCountInHeader(); // Update header count
        } else {
            showFlashMessage(data.message || 'Failed to update quantity.', 'error');
        }
    } catch (error) {
        console.error('Error updating cart quantity:', error);
        showFlashMessage('Error updating cart. Please try again.', 'error');
    }
}

// Function to remove item from cart via API
async function removeCartItem(productId) {
    if (!confirm('Are you sure you want to remove this item from your cart?')) {
        return;
    }
    try {
        const response = await fetch('/remove_from_cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ product_id: productId })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showFlashMessage(data.message, 'success');
            renderCartItems(); // Re-render cart
            updateCartCountInHeader(); // Update header count
        } else {
            showFlashMessage(data.message || 'Failed to remove item.', 'error');
        }
    } catch (error) {
        console.error('Error removing item from cart:', error);
        showFlashMessage('Error removing item. Please try again.', 'error');
    }
}


// ======================== Payment Page ========================

function initializePaymentOptions() {
    const paymentMethodRadios = document.querySelectorAll('input[name=\"payment_method\"]');
    const telebirrDetails = document.getElementById('telebirr-details');
    const cbebirrDetails = document.getElementById('cbebirr-details');

    if (paymentMethodRadios.length > 0) {
        const updatePaymentDetailsVisibility = () => {
            if (telebirrDetails) telebirrDetails.style.display = 'none';
            if (cbebirrDetails) cbebirrDetails.style.display = 'none';

            const selectedMethod = document.querySelector('input[name=\"payment_method\"]:checked')?.value;
            if (selectedMethod === 'telebirr' && telebirrDetails) {
                telebirrDetails.style.display = 'block';
            } else if (selectedMethod === 'cbebirr' && cbebirrDetails) {
                cbebirrDetails.style.display = 'block';
            }
        };

        paymentMethodRadios.forEach(radio => {
            radio.addEventListener('change', updatePaymentDetailsVisibility);
        });

        updatePaymentDetailsVisibility(); // Call on load to set initial state
    }
}

// ======================== 🔐 Account Page ========================
// Function removed as account.html handles its own JS logic directly.

// ======================== 🛠️ Admin Panel (Placeholder) ========================
function initializeAdminPanel() {
    console.log("Admin Panel JS Initialized (placeholder)");
    // Add any admin-specific JS here, e.g., for order status updates
    const adminOrdersTable = document.querySelector('.admin-orders-table');
    if (adminOrdersTable) {
        adminOrdersTable.addEventListener('change', async (event) => {
            if (event.target.classList.contains('order-status-select')) {
                const selectElement = event.target;
                const orderId = selectElement.dataset.orderId;
                const newStatus = selectElement.value;

                try {
                    const response = await fetch('/update_order_status', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ order_id: orderId, status: newStatus })
                    });
                    const data = await response.json();
                    if (response.ok && data.success) {
                        showFlashMessage(data.message, 'success');
                        // Optional: update the specific status span on the page without full reload
                        const statusSpan = selectElement.closest('td').previousElementSibling.querySelector('.order-status');
                        if (statusSpan) {
                            statusSpan.textContent = newStatus.replace('_', ' ').capitalize();
                            statusSpan.className = `order-status status-${newStatus.toLowerCase().replace(' ', '_')}`;
                        }
                    } else {
                        showFlashMessage(data.message || 'Failed to update order status.', 'error');
                    }
                } catch (error) {
                    console.error('Error updating order status:', error);
                    showFlashMessage('Error updating order status. Check connection.', 'error');
                }
            }
        });
    }

    // Simple capitalize function for display
    String.prototype.capitalize = function() {
        return this.charAt(0).toUpperCase() + this.slice(1);
    }
}


// ======================== 📱 Mobile Navigation Toggle ========================
function initializeMobileNavToggle() {
    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');

    if (menuToggle && navLinks) {
        menuToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });
    }
}