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

    // Track Button placeholder - Ensure this is correctly linked in your HTML
    const trackButton = document.querySelector('.track-button');
    if (trackButton) {
        trackButton.addEventListener('click', (e) => {
            e.preventDefault(); // Prevent default link behavior if it's just a placeholder
            showFlashMessage('📦 Tracking feature is coming soon!', 'info');
        });
    }

    // ======================== Mobile Menu Toggle ========================
    const mobileMenu = document.getElementById('mobile-menu');
    const navLinks = document.getElementById('nav-links');

    if (mobileMenu && navLinks) {
        mobileMenu.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });

        // Close menu if a link is clicked (optional)
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                if (navLinks.classList.contains('active')) {
                    navLinks.classList.remove('active');
                }
            });
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
                const [category, text] = message;
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

let cart = JSON.parse(localStorage.getItem('cart')) || {};

function saveCart() {
    localStorage.setItem('cart', JSON.stringify(cart));
    updateCartCountInHeader();
}

function updateCartCountInHeader() {
    const cartCountElement = document.getElementById('cart-count');
    if (cartCountElement) {
        const totalItems = Object.values(cart).reduce((sum, item) => sum + item.quantity, 0);
        cartCountElement.textContent = totalItems > 0 ? totalItems : 0;
        cartCountElement.style.display = totalItems > 0 ? 'inline-block' : 'none'; // Show/hide based on count
    }
}

function initializeAddToCartButtons() {
    const addToCartButtons = document.querySelectorAll('.add-to-cart-btn');
    addToCartButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            const productId = e.target.dataset.productId;
            const productName = e.target.dataset.name;
            const productPrice = parseFloat(e.target.dataset.price);

            if (cart[productId]) {
                cart[productId].quantity += 1;
            } else {
                cart[productId] = {
                    id: productId,
                    name: productName,
                    price: productPrice,
                    quantity: 1
                };
            }
            saveCart();
            showFlashMessage(`${productName} added to cart!`, 'success');
        });
    });
}


// ======================== 🛒 Cart Page ========================

function renderCartItems() {
    const cartItemsList = document.getElementById('cart-items-list');
    const emptyCartMessage = document.getElementById('empty-cart-message');
    const cartSummarySection = document.getElementById('cart-summary-section');
    const cartTotalAmount = document.getElementById('cart-total-amount');
    const cartSubtotal = document.getElementById('cart-subtotal');
    const totalAmountHidden = document.getElementById('total-amount-hidden');
    const cartDataHidden = document.getElementById('cart-data-hidden'); // For sending cart data to Flask

    if (!cartItemsList || !emptyCartMessage || !cartSummarySection || !cartTotalAmount || !cartSubtotal) {
        return; // Exit if elements not found (not on cart page)
    }

    cartItemsList.innerHTML = '';
    let subtotal = 0;
    const itemsInCart = Object.values(cart);

    if (itemsInCart.length === 0) {
        emptyCartMessage.style.display = 'block';
        cartSummarySection.style.display = 'none';
        return;
    } else {
        emptyCartMessage.style.display = 'none';
        cartSummarySection.style.display = 'block';
    }

    itemsInCart.forEach(item => {
        const itemTotal = item.price * item.quantity;
        subtotal += itemTotal;

        const cartItemDiv = document.createElement('div');
        cartItemDiv.className = 'cart-item';
        cartItemDiv.innerHTML = `
            <img src="${Flask.url_for('static', {filename: 'images/product' + item.id + '.png'})}" alt="${item.name}" class="cart-item-img">
            <div class="item-details">
                <h3>${item.name}</h3>
                <p class="item-price">ETB ${(item.price).toFixed(2)}</p>
                <p>Total: ETB ${(itemTotal).toFixed(2)}</p>
            </div>
            <div class="quantity-controls">
                <button data-product-id="${item.id}" data-action="decrease">-</button>
                <span>${item.quantity}</span>
                <button data-product-id="${item.id}" data-action="increase">+</button>
            </div>
            <button class="remove-item-btn" data-product-id="${item.id}">Remove</button>
        `;
        cartItemsList.appendChild(cartItemDiv);
    });

    cartSubtotal.textContent = subtotal.toFixed(2);
    // For now, total is same as subtotal, add shipping/taxes logic here if needed
    cartTotalAmount.textContent = subtotal.toFixed(2);

    // Update hidden fields for Flask
    if (totalAmountHidden) {
        totalAmountHidden.value = subtotal.toFixed(2);
    }
    if (cartDataHidden) {
        // Convert cart object to a simple array of item objects suitable for Flask
        const simpleCartData = Object.values(cart).map(item => ({
            id: item.id,
            name: item.name,
            price: item.price,
            quantity: item.quantity
        }));
        cartDataHidden.value = JSON.stringify(simpleCartData);
    }
}

function initializeCartPageElements() {
    const cartItemsList = document.getElementById('cart-items-list');
    if (cartItemsList) {
        cartItemsList.addEventListener('click', (e) => {
            const target = e.target;
            const productId = target.dataset.productId;
            const action = target.dataset.action;

            if (!productId) return;

            if (action === 'increase') {
                cart[productId].quantity += 1;
                showFlashMessage(`Increased quantity of ${cart[productId].name}`, 'info');
            } else if (action === 'decrease') {
                if (cart[productId].quantity > 1) {
                    cart[productId].quantity -= 1;
                    showFlashMessage(`Reduced quantity of ${cart[productId].name}`, 'info');
                } else {
                    delete cart[productId];
                    showFlashMessage(`Removed ${cart[productId]?.name || 'item'} from cart`, 'danger');
                }
            } else if (target.classList.contains('remove-item-btn')) {
                const itemName = cart[productId]?.name || 'item';
                delete cart[productId];
                showFlashMessage(`Removed ${itemName} from cart`, 'danger');
            }
            saveCart();
            renderCartItems(); // Re-render the cart after any change
        });
    }

    // Optional: Implement coupon button logic if you have backend support
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
    console.log("Admin Panel JS initialized.");

    // Auto-submit form when status changes
    const statusForms = document.querySelectorAll('.status-update-form');
    statusForms.forEach(form => {
        const select = form.querySelector('select[name="status"]');
        if (select) {
            select.addEventListener('change', () => {
                form.submit();
            });
        }
    });
}

// Add a global Flask object if it doesn't exist, for url_for in JS
// This simulates Flask-JS functionality if not using a specific extension
if (typeof Flask === 'undefined') {
    window.Flask = {
        url_for: function(endpoint, kwargs) {
            // Basic simulation for static files. For dynamic routes, you'd need a mapping from Flask.
            if (endpoint === 'static') {
                return `/static/${kwargs.filename}`;
            }
            // Fallback for other endpoints (might not work directly for complex routes without server-side JS mapping)
            return `/${endpoint}`; 
        }
    };
}