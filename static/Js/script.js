// ======================== 🚀 Initialize ========================\
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
    const accountPageContainer = document.getElementById('account-page-container');
    if (body.contains(accountPageContainer)) {
        console.log("Account page now handles OTP flow via Flask form submissions.");
    }

    // Initialize admin panel functions if on admin page
    if (body.contains(document.getElementById('admin-panel-container'))) {
        initializeAdminPanel();
    }

    // Initialize mobile navigation toggle
    initializeMobileNavToggle();

    // Initialize search functionality
    initializeProductSearch();
});

// ======================== 💬 Flash Messages ========================
function displayFlaskFlashMessages() {
    const flashDataScript = document.getElementById('flash-messages-data');
    if (!flashDataScript) {
        return;
    }

    try {
        const messages = JSON.parse(flashDataScript.textContent);
        const container = document.getElementById('flash-message-container');
        if (!container) {
            console.warn("Flash message container not found.");
            return;
        }

        messages.forEach(([category, message]) => {
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert ${category}`;
            alertDiv.textContent = message;
            container.appendChild(alertDiv);

            // Automatically remove the message after 5 seconds with fade-out
            setTimeout(() => {
                alertDiv.style.opacity = '0';
                alertDiv.style.transform = 'translateY(-20px)';
                alertDiv.addEventListener('transitionend', () => alertDiv.remove());
            }, 5000); // 5 seconds
        });
    } catch (e) {
        console.error("Error parsing flash messages:", e);
    }
}

// ======================== 🛒 Cart Management ========================
function updateCartCountInHeader() {
    fetch('/get_cart_count')
        .then(response => response.json())
        .then(data => {
            const cartCountElement = document.getElementById('cart-count');
            if (cartCountElement) {
                cartCountElement.textContent = data.cart_count || '0';
                cartCountElement.style.display = data.cart_count > 0 ? 'block' : 'none';
            }
        })
        .catch(error => console.error('Error fetching cart count:', error));
}

function initializeAddToCartButtons() {
    const addToCartButtons = document.querySelectorAll('.add-to-cart-btn');
    addToCartButtons.forEach(button => {
        button.addEventListener('click', async (event) => {
            const productId = event.target.dataset.productId;
            const productName = event.target.dataset.name;
            const productPrice = event.target.dataset.price;

            try {
                const response = await fetch('/add_to_cart', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ product_id: productId })
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    displayFlashMessage('success', data.message);
                    updateCartCountInHeader();
                } else if (response.status === 401) {
                    displayFlashMessage('warning', data.message || 'Please log in to add items to your cart.');
                    // Optionally redirect to login or show login modal
                    window.location.href = Flask.url_for('account');
                } else {
                    displayFlashMessage('danger', data.message || 'Failed to add item to cart.');
                }
            } catch (error) {
                console.error('Error adding to cart:', error);
                displayFlashMessage('danger', 'An unexpected error occurred. Please try again.');
            }
        });
    });
}

function renderCartItems() {
    const cartItemsList = document.getElementById('cart-items-list');
    const cartTotalAmountSpan = document.getElementById('cart-total-amount');
    const cartSubtotalSpan = document.getElementById('cart-subtotal');
    const emptyCartMessage = document.getElementById('empty-cart-message');
    const cartSummarySection = document.getElementById('cart-summary-section');
    const totalAmountHiddenInput = document.getElementById('total-amount-hidden');
    const cartDataHiddenInput = document.getElementById('cart-data-hidden');

    if (!cartItemsList || !cartTotalAmountSpan) return;

    fetch('/get_cart_items')
        .then(response => {
            if (response.status === 401) {
                // User not logged in, show empty cart message
                emptyCartMessage.style.display = 'block';
                cartSummarySection.style.display = 'none';
                displayFlashMessage('info', 'Please log in to view your cart.');
                return { cart_items: [] }; // Return empty data so the rest of the function can proceed safely
            }
            return response.json();
        })
        .then(data => {
            let totalAmount = 0;
            cartItemsList.innerHTML = ''; // Clear existing items

            if (data.cart_items && data.cart_items.length > 0) {
                data.cart_items.forEach(item => {
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'cart-item';
                    itemDiv.innerHTML = `
                        <img src="${item.image_url}" alt="${item.name}" class="cart-item-img">
                        <div class="item-details">
                            <h3>${item.name}</h3>
                            <p class="item-price">ETB ${(item.price * item.quantity).toFixed(2)}</p>
                        </div>
                        <div class="quantity-controls">
                            <button class="decrease-quantity-btn" data-product-id="${item.id}">-</button>
                            <span>${item.quantity}</span>
                            <button class="increase-quantity-btn" data-product-id="${item.id}">+</button>
                        </div>
                        <button class="remove-item-btn" data-product-id="${item.id}">Remove</button>
                    `;
                    cartItemsList.appendChild(itemDiv);
                    totalAmount += item.price * item.quantity;
                });
                emptyCartMessage.style.display = 'none';
                cartSummarySection.style.display = 'block';
            } else {
                emptyCartMessage.style.display = 'block';
                cartSummarySection.style.display = 'none';
            }

            cartTotalAmountSpan.textContent = totalAmount.toFixed(2);
            cartSubtotalSpan.textContent = totalAmount.toFixed(2); // For now, subtotal is same as total
            
            // Update hidden inputs for form submission
            if (totalAmountHiddenInput) {
                totalAmountHiddenInput.value = totalAmount.toFixed(2);
            }
            if (cartDataHiddenInput) {
                cartDataHiddenInput.value = JSON.stringify(data.cart_items);
            }
            
            // Re-attach event listeners after rendering
            initializeCartPageElements();
        })
        .catch(error => console.error('Error fetching cart items:', error));
}

function initializeCartPageElements() {
    // Attach event listeners for quantity controls
    document.querySelectorAll('.increase-quantity-btn').forEach(button => {
        button.onclick = () => updateCartItemQuantity(button.dataset.productId, 1);
    });
    document.querySelectorAll('.decrease-quantity-btn').forEach(button => {
        button.onclick = () => updateCartItemQuantity(button.dataset.productId, -1);
    });
    document.querySelectorAll('.remove-item-btn').forEach(button => {
        button.onclick = () => removeCartItem(button.dataset.productId);
    });
}

async function updateCartItemQuantity(productId, change) {
    const currentQuantityElement = document.querySelector(`.quantity-controls [data-product-id="${productId}"]`).previousElementSibling;
    let currentQuantity = parseInt(currentQuantityElement.textContent);
    let newQuantity = currentQuantity + change;

    if (newQuantity < 0) newQuantity = 0; // Prevent negative quantity

    try {
        const response = await fetch('/update_cart_quantity', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId, quantity: newQuantity })
        });
        const data = await response.json();

        if (response.ok && data.success) {
            displayFlashMessage('success', data.message);
            renderCartItems(); // Re-render the cart to update totals and items
            updateCartCountInHeader();
        } else if (response.status === 401) {
            displayFlashMessage('warning', data.message || 'Please log in to update your cart.');
            window.location.href = Flask.url_for('account');
        } else {
            displayFlashMessage('danger', data.message || 'Failed to update quantity.');
        }
    } catch (error) {
        console.error('Error updating cart quantity:', error);
        displayFlashMessage('danger', 'An unexpected error occurred. Please try again.');
    }
}

async function removeCartItem(productId) {
    try {
        const response = await fetch('/remove_from_cart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId })
        });
        const data = await response.json();

        if (response.ok && data.success) {
            displayFlashMessage('success', data.message);
            renderCartItems(); // Re-render cart
            updateCartCountInHeader();
        } else if (response.status === 401) {
            displayFlashMessage('warning', data.message || 'Please log in to modify your cart.');
            window.location.href = Flask.url_for('account');
        } else {
            displayFlashMessage('danger', data.message || 'Failed to remove item.');
        }
    } catch (error) {
        console.error('Error removing item:', error);
        displayFlashMessage('danger', 'An unexpected error occurred. Please try again.');
    }
}

// ======================== 💰 Payment Page ========================
function initializePaymentOptions() {
    const paymentForm = document.getElementById('payment-form');
    if (!paymentForm) return;

    const paymentRadios = paymentForm.querySelectorAll('input[name="payment_method"]');
    const telebirrDetails = document.getElementById('telebirr-details');
    const cbebirrDetails = document.getElementById('cbebirr-details');

    const togglePaymentDetails = () => {
        telebirrDetails.classList.add('hidden');
        cbebirrDetails.classList.add('hidden');

        const selectedMethod = paymentForm.querySelector('input[name="payment_method"]:checked').value;
        if (selectedMethod === 'telebirr') {
            telebirrDetails.classList.remove('hidden');
        } else if (selectedMethod === 'cbebirr') {
            cbebirrDetails.classList.remove('hidden');
        }
    };

    paymentRadios.forEach(radio => {
        radio.addEventListener('change', togglePaymentDetails);
    });

    // Initial call to set correct visibility based on default checked radio
    togglePaymentDetails();
}

// ======================== 🔑 Admin Panel ========================
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

// ======================== 📱 Mobile Navigation Toggle ========================\
function initializeMobileNavToggle() {
    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    const mainContent = document.querySelector('main'); // Select main content area

    if (menuToggle && navLinks && mainContent) {
        const toggleMenu = () => {
            navLinks.classList.toggle('active');
            menuToggle.classList.toggle('active'); // Toggle class for hamburger icon animation
            // Toggle overflow hidden on body to prevent scrolling when menu is open
            document.body.style.overflow = navLinks.classList.contains('active') ? 'hidden' : '';
        };

        menuToggle.addEventListener('click', toggleMenu);

        // Close menu when a nav link is clicked (for single page navigation or direct links)
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                if (navLinks.classList.contains('active')) {
                    toggleMenu(); // Close menu after clicking a link
                }
            });
        });

        // Close menu when clicking outside of it (on main content)
        mainContent.addEventListener('click', (event) => {
            if (navLinks.classList.contains('active') && !navLinks.contains(event.target) && !menuToggle.contains(event.target)) {
                toggleMenu();
            }
        });
    }
}

// ======================== 🔍 Product Search ========================
function initializeProductSearch() {
    const searchInput = document.getElementById('product-search-input');
    const searchResultsSection = document.getElementById('search-results-section');
    const productCategoriesDisplay = document.getElementById('product-categories-display');
    const productsSectionTitle = document.getElementById('products-section-title');
    const clearSearchBtn = document.getElementById('clear-search-btn');

    if (!searchInput || !searchResultsSection || !productCategoriesDisplay || !productsSectionTitle || !clearSearchBtn) {
        console.warn("Search elements not found. Search functionality will not be initialized.");
        return;
    }

    let searchTimeout;

    const performSearch = async (query) => {
        if (query.length < 2 && query.length !== 0) { // Require at least 2 characters for search unless clearing
            searchResultsSection.innerHTML = '';
            searchResultsSection.style.display = 'none';
            productCategoriesDisplay.style.display = 'block';
            productsSectionTitle.textContent = "All Our Products";
            clearSearchBtn.classList.add('hidden');
            return;
        }

        if (query.length === 0) {
            // If query is empty, show all products and hide search results
            searchResultsSection.innerHTML = '';
            searchResultsSection.style.display = 'none';
            productCategoriesDisplay.style.display = 'block';
            productsSectionTitle.textContent = "All Our Products";
            clearSearchBtn.classList.add('hidden');
            return;
        }

        productsSectionTitle.textContent = `Search Results for "${query}"`;
        productCategoriesDisplay.style.display = 'none'; // Hide category sections
        searchResultsSection.style.display = 'grid'; // Show search results container
        clearSearchBtn.classList.remove('hidden'); // Show clear button

        searchResultsSection.innerHTML = '<p style="text-align: center; grid-column: 1 / -1; padding: 20px;">Searching...</p>';

        try {
            const response = await fetch(`/search_products?query=${encodeURIComponent(query)}`);
            const data = await response.json();

            searchResultsSection.innerHTML = ''; // Clear "Searching..." message

            if (data.products && data.products.length > 0) {
                data.products.forEach(product => {
                    const productCard = document.createElement('div');
                    productCard.className = 'product-card';
                    productCard.innerHTML = `
                        <img src="${product.image_path}" alt="${product.name}">
                        <div class="product-info">
                            <h3>${product.name}</h3>
                            <p class="product-description">${product.description}</p>
                            <p class="product-price">ETB ${product.price.toFixed(2)}</p>
                            <button type="button" class="add-to-cart-btn"
                                    data-product-id="${product.id}"
                                    data-name="${product.name}"
                                    data-price="${product.price}">
                                Add to Cart
                            </button>
                        </div>
                    `;
                    searchResultsSection.appendChild(productCard);
                });
                initializeAddToCartButtons(); // Re-initialize buttons for new products
            } else {
                searchResultsSection.innerHTML = '<p style="text-align: center; grid-column: 1 / -1; padding: 20px;">No products found matching your search.</p>';
            }
        } catch (error) {
            console.error('Error during product search:', error);
            searchResultsSection.innerHTML = '<p style="text-align: center; grid-column: 1 / -1; padding: 20px; color: red;">Error searching for products. Please try again.</p>';
        }
    };

    searchInput.addEventListener('input', (event) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            performSearch(event.target.value);
        }, 300); // Debounce for 300ms
    });

    clearSearchBtn.addEventListener('click', () => {
        searchInput.value = ''; // Clear input
        performSearch(''); // Trigger search with empty query to show all products
    });
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
