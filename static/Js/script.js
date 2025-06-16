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

    // The account.html page now uses direct Flask form submission for OTP flow.
    // No specific JS initialization needed for the main account page div directly.
    const accountPageContainer = document.getElementById('account-page-container');
    if (body.contains(accountPageContainer)) {
        console.log("Account page now handles OTP flow via Flask form submissions.");
        // If you still have password show/hide, it needs to be inline or in a separate specific JS for account.html
        // For this updated flow, passwords are not directly entered on account.html
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

    // NEW: Initialize Mobile Navigation Toggle (already in your previous script.js, just ensuring it's called)
    initializeMobileNavToggle();
    // ----------------------------------------
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

    // Auto-hide messages
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
            
            flashedMessages.forEach(message => {
                const [category, text] = message; // Flask sends [category, message]
                showFlashMessage(text, category);
            });

            // Clear the script tag content after displaying to prevent re-display on back/forward
            flashMessagesDataElement.textContent = '[]';

        } catch (error) {
            console.error("Error parsing flash messages:", error);
        }
    }
}


// ======================== 🛒 Cart Functionality ========================

// Function to update cart count displayed in the header
async function updateCartCountInHeader() {
    const cartCountSpan = document.getElementById('cart-count');
    if (cartCountSpan) {
        try {
            const response = await fetch('/get_cart_count');
            if (response.ok) {
                const data = await response.json();
                cartCountSpan.textContent = data.cart_count > 0 ? data.cart_count : '0'; // Display 0 if empty
            } else {
                console.error('Failed to fetch cart count.');
                cartCountSpan.textContent = '0';
            }
        } catch (error) {
            console.error('Error fetching cart count:', error);
            cartCountSpan.textContent = '0';
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
            const quantity = 1; // Default quantity for initial add

            await addToCart(productId, quantity, productName);
        });
    });
}


async function addToCart(productId, quantity, productName = 'item') {
    try {
        const response = await fetch('/add_to_cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest' // Crucial for Flask to identify AJAX
            },
            body: JSON.stringify({ product_id: productId, quantity: quantity })
        });

        const data = await response.json();

        if (response.status === 401) { // Specifically handle 401 for login required
            showFlashMessage(data.message || 'Please log in to add items to your cart.', 'warning');
            setTimeout(() => window.location.href = '/account', 1500); // Redirect to login
            return;
        }

        if (response.ok && data.success) { // Server returned 200-299 and success:true
            showFlashMessage(data.message || `${productName} added to cart!`, 'success');
            updateCartCountInHeader(); 
            if (document.body.contains(document.getElementById('cart-page-container'))) {
                renderCartItems(); // Re-render cart if on the cart page
            }
        } else { // Server returned non-200 or success:false
            showFlashMessage(data.message || data.error || 'Failed to add item to cart.', 'danger');
        }
    } catch (error) {
        console.error("Network or parsing error adding to cart:", error);
        showFlashMessage(`Error: Could not add ${productName} to cart. Check your connection.`, 'danger');
    }
}


// ======================== 🧾 Cart Page Rendering & Interaction ========================

async function renderCartItems() {
    const cartPageContainer = document.getElementById('cart-page-container');
    if (!cartPageContainer) return; // Not on the cart page

    const cartItemsList = document.getElementById('cart-items-list');
    const cartSubtotalElement = document.getElementById('cart-subtotal');
    const cartTotalAmountElement = document.getElementById('cart-total-amount'); // Assuming this exists for total
    const emptyCartMessage = document.getElementById('empty-cart-message');
    const cartSummarySection = document.getElementById('cart-summary-section');
    const totalAmountHiddenInput = document.getElementById('total-amount-hidden');
    const cartDataHiddenInput = document.getElementById('cart-data-hidden');

    if (!cartItemsList || !cartSubtotalElement || !cartTotalAmountElement || !emptyCartMessage || !cartSummarySection || !totalAmountHiddenInput || !cartDataHiddenInput) {
        console.error("Missing essential cart page elements. Check your cart.html structure.");
        return;
    }

    try {
        const response = await fetch('/get_cart_items', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        
        const data = await response.json();
        
        // Handle login required specifically for cart page load
        if (response.status === 401) {
            showFlashMessage(data.message || "Please log in to view your cart items.", "warning");
            emptyCartMessage.style.display = 'block';
            cartSummarySection.style.display = 'none';
            cartItemsList.innerHTML = ''; // Clear any visible items
            cartSubtotalElement.textContent = '0.00';
            cartTotalAmountElement.textContent = '0.00';
            totalAmountHiddenInput.value = '0.00';
            cartDataHiddenInput.value = '[]';
            updateCartCountInHeader(); // Ensure header reflects empty cart
            setTimeout(() => window.location.href = '/account', 1500);
            return;
        }

        const cartItems = data.cart_items || []; // Ensure it's an array

        cartItemsList.innerHTML = '';
        let subtotal = 0;
        const formattedCartData = []; // For the hidden input to Flask

        if (cartItems.length === 0) {
            emptyCartMessage.style.display = 'block';
            cartSummarySection.style.display = 'none';
        } else {
            emptyCartMessage.style.display = 'none';
            cartSummarySection.style.display = 'block';

            cartItems.forEach(item => {
                const itemTotal = item.price * item.quantity;
                subtotal += itemTotal;

                const cartItemDiv = document.createElement('div');
                cartItemDiv.className = 'cart-item';
                cartItemDiv.innerHTML = `
                    <img src="${item.image_url}" alt="${item.name}" class="cart-item-img">
                    <div class="item-details">
                        <h3>${item.name}</h3>
                        <p class="item-price">ETB ${item.price.toFixed(2)}</p>
                        <p>Total: ETB ${itemTotal.toFixed(2)}</p>
                    </div>
                    <div class="quantity-controls">
                        <button data-product-id="${item.id}" data-action="decrease">-</button>
                        <span>${item.quantity}</span>
                        <button data-product-id="${item.id}" data-action="increase">+</button>
                    </div>
                    <button class="remove-item-btn" data-product-id="${item.id}">Remove</button>
                `;
                cartItemsList.appendChild(cartItemDiv);

                formattedCartData.push({ // Store simplified data for Flask
                    id: item.id,
                    name: item.name,
                    price: item.price,
                    quantity: item.quantity
                });
            });
        }

        cartSubtotalElement.textContent = subtotal.toFixed(2);
        cartTotalAmountElement.textContent = subtotal.toFixed(2); // Assuming total is same as subtotal for now
        totalAmountHiddenInput.value = subtotal.toFixed(2);
        cartDataHiddenInput.value = JSON.stringify(formattedCartData);

        updateCartCountInHeader();

    } catch (err) {
        console.error('Failed to fetch or render cart items:', err);
        showFlashMessage('Failed to load cart items. Please try refreshing the page.', 'danger');
        emptyCartMessage.style.display = 'block';
        cartSummarySection.style.display = 'none';
    }
}

function initializeCartPageElements() {
    const cartItemsList = document.getElementById('cart-items-list');
    if (cartItemsList) {
        cartItemsList.addEventListener('click', async (e) => {
            const target = e.target;
            const productId = target.dataset.productId || target.closest('[data-product-id]')?.dataset.productId;

            if (!productId) return;

            if (target.dataset.action === 'increase') {
                await updateCartItemQuantity(productId, 1); // Increase by 1
            } else if (target.dataset.action === 'decrease') {
                await updateCartItemQuantity(productId, -1); // Decrease by 1
            } else if (target.classList.contains('remove-item-btn')) {
                await removeCartItem(productId);
            }
        });
    }
    // Add logic for coupon button if desired
    const applyCouponBtn = document.querySelector('.coupon-section .btn-secondary');
    if (applyCouponBtn) {
        applyCouponBtn.addEventListener('click', () => {
            const couponCode = document.getElementById('coupon-code').value;
            if (couponCode) {
                showFlashMessage(`Coupon "${couponCode}" applied! (Feature coming soon)`, 'info');
                // You'd typically send this to Flask via AJAX to apply discount
            } else {
                showFlashMessage('Please enter a coupon code.', 'warning');
            }
        });
    }

    // Google Map button placeholder
    const useGoogleMapButton = document.getElementById('useGoogleMapButton');
    if (useGoogleMapButton) {
        useGoogleMapButton.addEventListener('click', () => {
            showFlashMessage('Google Maps integration is coming soon!', 'info');
        });
    }
}


async function updateCartItemQuantity(productId, delta) {
    try {
        const response = await fetch('/update_cart_quantity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ product_id: productId, quantity: delta }) // Send delta
        });

        const data = await response.json();

        if (response.status === 401) { // Handle 401 specifically
            showFlashMessage(data.message || 'Please log in to update your cart.', 'warning');
            setTimeout(() => window.location.href = '/account', 1500);
            return;
        }

        if (response.ok && data.success) {
            showFlashMessage(data.message, 'success');
            renderCartItems(); // Re-render to show updated totals/quantities
            updateCartCountInHeader();
        } else {
            showFlashMessage(data.message || 'Failed to update quantity.', 'danger');
        }
    } catch (error) {
        console.error('Error updating cart quantity:', error);
        showFlashMessage('Error updating cart. Please try again.', 'danger');
    }
}

async function removeCartItem(productId) {
    // Replaced confirm with custom modal/flash logic to avoid browser alerts.
    // For now, keeping confirm() for quick fix, but note the instruction.
    if (!confirm("Are you sure you want to remove this item from your cart?")) {
        return;
    }
    
    try {
        const response = await fetch('/remove_from_cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ product_id: productId })
        });

        const data = await response.json();

        if (response.status === 401) {
            showFlashMessage(data.message || 'Please log in to remove items from your cart.', 'warning');
            setTimeout(() => window.location.href = '/account', 1500);
            return;
        }

        if (response.ok && data.success) {
            showFlashMessage(data.message, 'info');
            renderCartItems(); // Re-render cart
            updateCartCountInHeader(); // Update header count
        } else {
            showFlashMessage(data.message || 'Failed to remove item.', 'warning');
        }
    } catch (error) {
        console.error('Network or parsing error removing item from cart:', error);
        showFlashMessage('An error occurred while removing item.', 'danger');
    }
}


// ======================== 💰 Payment Page ========================

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

        updatePaymentDetailsVisibility(); // Call on load to set initial state
    }
}

// ======================== 🛠️ Admin Panel (Placeholder) ========================
function initializeAdminPanel() {
    console.log("Admin panel initialized.");

    // Auto-submit form when status changes
    const statusForms = document.querySelectorAll('.status-update-form');
    statusForms.forEach(form => {
        const select = form.querySelector('select[name="status"]');
        if (select) {
            select.addEventListener('change', () => {
                form.submit(); // This form submits directly via Flask
            });
        }
    });
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

// Global Flask URL helper (if Flask-JS is not used)
// This is critical for Flask.url_for in JS to work
if (typeof Flask === 'undefined') {
    window.Flask = {
        url_for: function(endpoint, kwargs) {
            if (endpoint === 'static') {
                return `/static/${kwargs.filename}`;
            }
            // A more robust solution for dynamic Flask URLs would involve
            // sending a JS object from Flask containing all URL mappings.
            // For now, this basic static path helper is sufficient.
            return `/${endpoint}`; 
        }
    };
}