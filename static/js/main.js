// static/js/main.js

document.addEventListener('DOMContentLoaded', () => {
    // --- 1. Language and Theme Toggles ---
    const htmlElement = document.documentElement;
    const bodyElement = document.body;
    const languageToggle = document.getElementById('languageToggle');
    const themeToggle = document.getElementById('themeToggle');
    const platformLogo = document.getElementById('platformLogo');
    const usernameDisplayMobile = document.querySelector('.username-display-mobile');

    // Retrieve saved preferences or set defaults
    // Use 'dark' as default if no preference is found or set from server
    let currentTheme = localStorage.getItem('theme') || bodyElement.getAttribute('data-current-theme') || 'dark'; 
    // Use 'en' as default language if not found
    let currentLang = localStorage.getItem('lang') || htmlElement.getAttribute('lang') || 'en';

    // Apply saved preferences immediately
    applyTheme(currentTheme);
    applyLanguage(currentLang); // Apply language after theme to ensure text in toggles is correct

    // Event Listeners for Toggles
    if (languageToggle) {
        languageToggle.addEventListener('click', (e) => {
            e.preventDefault();
            const targetLang = languageToggle.getAttribute('data-lang-target') || ((currentLang === 'en') ? 'ar' : 'en');
            currentLang = targetLang; // Update currentLang with the target
            applyLanguage(currentLang);
            localStorage.setItem('lang', currentLang);
            
            // --- MODIFICATION: Redirect to server to set language in session ---
            // This ensures the server-side (Flask) also knows the current language
            // and can render templates correctly on next page load.
            // The flash message for language update will now come from the server.
            window.location.href = `/switch_lang/${currentLang}`; // Make sure this route exists in Flask

            // flashMessage('Language preference updated!', 'info'); // Remove client-side flash
        });
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', (e) => {
            e.preventDefault();
            const targetTheme = themeToggle.getAttribute('data-theme-target') || ((currentTheme === 'dark') ? 'light' : 'dark');
            currentTheme = targetTheme; // Update currentTheme with the target
            applyTheme(currentTheme);
            localStorage.setItem('theme', currentTheme);
            flashMessage('Theme preference updated!', 'info'); // Client-side flash is okay for theme
        });
    }

    function applyTheme(theme) {
        bodyElement.classList.remove('theme-dark', 'theme-light'); // Remove both to be safe
        bodyElement.classList.add(`theme-${theme}`);
        bodyElement.setAttribute('data-current-theme', theme); // Update data attribute
        
        if (themeToggle) { // Check if themeToggle exists
            if (theme === 'dark') {
                themeToggle.innerHTML = '<i class="fas fa-sun"></i> <span class="lang-en">Day Mode</span><span class="lang-ar" style="display:none;">الوضع النهاري</span>';
                themeToggle.setAttribute('data-theme-target', 'light');
            } else {
                themeToggle.innerHTML = '<i class="fas fa-moon"></i> <span class="lang-en">Night Mode</span><span class="lang-ar" style="display:none;">الوضع الليلي</span>';
                themeToggle.setAttribute('data-theme-target', 'dark');
            }
            // After setting innerHTML, re-apply language display for the toggle's text
            const langEnInToggle = themeToggle.querySelector('.lang-en');
            const langArInToggle = themeToggle.querySelector('.lang-ar');
            if (langEnInToggle) langEnInToggle.style.display = (currentLang === 'en') ? 'inline' : 'none';
            if (langArInToggle) langArInToggle.style.display = (currentLang === 'ar') ? 'inline' : 'none';
        }
    }

    function applyLanguage(lang) {
        htmlElement.setAttribute('lang', lang);
        htmlElement.setAttribute('dir', (lang === 'ar') ? 'rtl' : 'ltr');
        
        // Toggle visibility for all elements with lang-en and lang-ar classes
        document.querySelectorAll('.lang-en').forEach(el => {
            el.style.display = (lang === 'en') ? 'inline' : (el.tagName === 'SPAN' || el.tagName === 'A' ? 'none' : ''); // Respect block elements
        });
        document.querySelectorAll('.lang-ar').forEach(el => {
            el.style.display = (lang === 'ar') ? 'inline' : (el.tagName === 'SPAN' || el.tagName === 'A' ? 'none' : '');
        });

        // Special handling for language toggle button itself if its text changes
        if (languageToggle) {
            if (lang === 'ar') {
                languageToggle.innerHTML = '<i class="fas fa-language"></i> <span class="lang-en" style="display:none;">English</span><span class="lang-ar">English</span>'; // Display "English" in Arabic
                languageToggle.setAttribute('data-lang-target', 'en');
            } else { // lang === 'en'
                languageToggle.innerHTML = '<i class="fas fa-language"></i> <span class="lang-en">العربية</span><span class="lang-ar" style="display:none;">العربية</span>'; // Display "العربية" in English
                languageToggle.setAttribute('data-lang-target', 'ar');
            }
        }
        // Re-apply theme to ensure theme toggle text is also updated according to the new language
        applyTheme(currentTheme); 
        updateDynamicTextContent(lang); // Update placeholders, aria-labels etc.
    }


    function updateDynamicTextContent(lang) {
        if (platformLogo) {
            const enText = platformLogo.querySelector('.lang-en');
            const arText = platformLogo.querySelector('.lang-ar');
            if (enText) enText.style.display = (lang === 'en') ? 'inline' : 'none';
            if (arText) arText.style.display = (lang === 'ar') ? 'inline' : 'none';
        }

        const settingsBtn = document.getElementById('settingsMenuButton');
        if (settingsBtn) {
            const titleEn = settingsBtn.getAttribute('data-title-en');
            const titleAr = settingsBtn.getAttribute('data-title-ar');
            if (titleEn && titleAr) { // Ensure attributes exist
                settingsBtn.setAttribute('title', (lang === 'en' ? titleEn : titleAr));
                settingsBtn.setAttribute('aria-label', (lang === 'en' ? titleEn : titleAr));
            }
        }

        document.querySelectorAll('.close-alert-btn').forEach(button => {
            const labelEn = button.getAttribute('data-aria-label-en');
            const labelAr = button.getAttribute('data-aria-label-ar');
            if (labelEn && labelAr) {
                button.setAttribute('aria-label', (lang === 'en' ? labelEn : labelAr));
            }
        });

        document.querySelectorAll('[placeholder-en]').forEach(input => {
            const placeholderEn = input.getAttribute('placeholder-en');
            const placeholderAr = input.getAttribute('placeholder-ar');
            if (placeholderEn && placeholderAr){
                input.setAttribute('placeholder', (lang === 'en' ? placeholderEn : placeholderAr));
            }
        });

        if (usernameDisplayMobile) {
            const enSpan = usernameDisplayMobile.querySelector('.lang-en');
            const arSpan = usernameDisplayMobile.querySelector('.lang-ar');
            if (enSpan) enSpan.style.display = (lang === 'en') ? 'inline' : 'none';
            if (arSpan) arSpan.style.display = (lang === 'ar') ? 'inline' : 'none';
        }
    }

    // --- 2. Flash Messages Dismissal ---
    // Auto-dismiss and manual dismiss for existing flash messages on page load
    const existingFlashMessages = document.querySelectorAll('.flash-messages-container .alert:not(.hidden-section)'); // Select only visible flash messages
    existingFlashMessages.forEach(alert => {
        // Add close button functionality if it doesn't have one from dynamic creation
        if (!alert.querySelector('.close-alert-btn')) {
            const closeBtnHTML = `<button type="button" class="close-alert-btn" data-aria-label-en="Close alert" data-aria-label-ar="إغلاق التنبيه" aria-label="${currentLang === 'en' ? 'Close alert' : 'إغلاق التنبيه'}">×</button>`;
            alert.insertAdjacentHTML('beforeend', closeBtnHTML);
        }

        const closeButton = alert.querySelector('.close-alert-btn');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-20px) scale(0.95)';
                setTimeout(() => alert.remove(), 300); // Remove after transition
            });
        }
        
        // Auto-dismiss after a delay
        if (!alert.classList.contains('no-auto-dismiss')) { // Add 'no-auto-dismiss' to prevent auto-close if needed
             setTimeout(() => {
                if (alert && alert.parentElement) { // Check if alert still exists
                    closeButton.click(); // Simulate click for consistent animation/removal
                }
            }, 5000 + (Array.from(existingFlashMessages).indexOf(alert) * 300) ); // Stagger auto-dismissal
        }
    });


    // --- 3. Settings Dropdown Menu (Hamburger Menu) ---
    const settingsMenuButton = document.getElementById('settingsMenuButton');
    const settingsDropdown = document.getElementById('settingsDropdown');
    const closeMenuButton = document.getElementById('closeMenuButton');

    if (settingsMenuButton && settingsDropdown) { // closeMenuButton is optional now
        settingsMenuButton.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent click from immediately closing due to document listener
            const isExpanded = settingsMenuButton.getAttribute('aria-expanded') === 'true';
            settingsMenuButton.setAttribute('aria-expanded', String(!isExpanded));
            settingsDropdown.classList.toggle('show');
            document.body.classList.toggle('no-scroll', !isExpanded);
        });

        if (closeMenuButton) {
            closeMenuButton.addEventListener('click', () => {
                settingsMenuButton.setAttribute('aria-expanded', 'false');
                settingsDropdown.classList.remove('show');
                document.body.classList.remove('no-scroll');
            });
        }

        document.addEventListener('click', (event) => {
            if (settingsDropdown.classList.contains('show') && 
                !settingsDropdown.contains(event.target) && 
                !settingsMenuButton.contains(event.target)) {
                settingsMenuButton.setAttribute('aria-expanded', 'false');
                settingsDropdown.classList.remove('show');
                document.body.classList.remove('no-scroll');
            }
        });
    }

    // --- 4. Password Toggle Visibility (Login/Signup Forms) ---
    const passwordToggles = document.querySelectorAll('.password-toggle-icon');
    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            // Assuming the input is the previous sibling or inside a common parent
            let passwordField = this.previousElementSibling;
            if (passwordField && passwordField.tagName !== 'INPUT') { // Check if it's not an input, try to find it within parent
                 passwordField = this.closest('.password-field-container').querySelector('input[type="password"], input[type="text"]');
            }

            if (passwordField) {
                const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
                passwordField.setAttribute('type', type);
                // Toggle icon (assuming Font Awesome)
                const icon = this.querySelector('i');
                if (icon) {
                    icon.classList.toggle('fa-eye');
                    icon.classList.toggle('fa-eye-slash');
                }
            }
        });
    });

    // --- 5. Country Search Filter (for signup/login forms) ---
    const countrySearchInputs = document.querySelectorAll('.country-search-input');
    countrySearchInputs.forEach(searchInput => {
        // Get the associated select element (assuming it's the next sibling with tagName 'SELECT')
        let selectElement = searchInput.nextElementSibling;
        while(selectElement && selectElement.tagName !== 'SELECT') {
            selectElement = selectElement.nextElementSibling;
        }

        if (selectElement) {
            // Store original options if not already stored
            if (!selectElement.hasOwnProperty('originalOptions')) {
                selectElement.originalOptions = Array.from(selectElement.options).map(opt => ({
                    text: opt.text,
                    value: opt.value,
                    disabled: opt.disabled,
                    selected: opt.selected
                }));
            }
        
            searchInput.addEventListener('keyup', function() {
                const filter = this.value.toLowerCase().trim();
                // Clear current options
                selectElement.innerHTML = ''; 
                
                // Filter and add back original options
                selectElement.originalOptions.forEach(optData => {
                    if (optData.text.toLowerCase().includes(filter) || optData.value.toLowerCase().includes(filter) || filter === '') {
                        const option = new Option(optData.text, optData.value);
                        option.disabled = optData.disabled;
                        option.selected = optData.selected && filter === ''; // Re-select only if filter is empty and it was originally selected
                        selectElement.add(option);
                    }
                });
                 // Ensure select reflects change for screen readers or other tools
                if(selectElement.options.length > 0 && filter === '' && selectElement.originalOptions.find(o => o.selected)){
                    // If filter is empty, try to set the originally selected option
                    const originallySelected = selectElement.originalOptions.find(o => o.selected);
                    if (originallySelected) selectElement.value = originallySelected.value;
                } else if (selectElement.options.length > 0 && selectElement.selectedIndex === -1){
                     // If nothing is selected (e.g. after filtering out the selected one), select the first available option.
                    // selectElement.selectedIndex = 0; // Or handle as per UX preference
                }
            });
        }
    });


    // --- 6. Role Selection Box (Signup Page) ---
    const roleBoxes = document.querySelectorAll('.role-selection-box');
    roleBoxes.forEach(box => {
        box.addEventListener('click', () => {
            roleBoxes.forEach(rb => rb.classList.remove('selected'));
            box.classList.add('selected');
            const radio = box.querySelector('.role-radio');
            if (radio) {
                radio.checked = true;
                // Trigger change event for any listeners on the radio button itself
                const event = new Event('change', { bubbles: true });
                radio.dispatchEvent(event);
            }
        });
    });
    const initiallySelectedRadio = document.querySelector('.role-radio:checked');
    if (initiallySelectedRadio) {
        const parentBox = initiallySelectedRadio.closest('.role-selection-box');
        if(parentBox) parentBox.classList.add('selected');
    }


    // --- 7. Dynamic Visual Effects & Animations ---
    // <<< MODIFIED TO INCLUDE .animated-auth-element >>>
    const animatedElements = document.querySelectorAll(
        '.card, .teacher-card, .feature-item, .accordion-item, .animated-auth-element, .hero-text-content, .hero-image-content'
    ); 
    const observerOptions = {
        root: null, // relative to the viewport
        rootMargin: '0px',
        threshold: 0.1 // 10% of the item is visible
    };

    const observer = new IntersectionObserver((entries, observerInstance) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                // Stagger animation based on the actual index in the NodeList for all observed elements
                // Calculate index relative to all elements being observed
                const trueIndex = Array.from(animatedElements).indexOf(entry.target);
                entry.target.style.animationDelay = `${trueIndex * 0.08}s`;
                entry.target.classList.add('animated-slide-up');
                observerInstance.unobserve(entry.target); // Stop observing once animated
            }
        });
    }, observerOptions);

    animatedElements.forEach(el => {
        observer.observe(el);
    });


    function animateNumber(element, start, end, duration) {
        if (!element) return; // Guard clause
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            element.textContent = Math.floor(progress * (end - start) + start).toLocaleString(); // Add toLocaleString for formatting
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }
    
    const teacherDashboardContent = document.getElementById('teacherDashboardContent');
    if (teacherDashboardContent) {
        fetchDashboardStats();
        // setInterval(fetchDashboardStats, 30000); // Optional refresh
    }

    async function fetchDashboardStats() {
        // This function remains the same as in your original file.
        // It fetches data from '/api/teacher/dashboard_stats'
        // and uses animateNumber to update the UI.
        try {
            const response = await fetch('/api/teacher/dashboard_stats'); // Ensure this API endpoint exists in Flask
            if (!response.ok) {
                const errorData = await response.text();
                throw new Error(`Network response was not ok: ${response.status} ${errorData}`);
            }
            const stats = await response.json();

            animateNumber(document.getElementById('subscribersCount'), 0, stats.subscribers || 0, 1000);
            animateNumber(document.getElementById('totalViewsCount'), 0, stats.total_views || 0, 1500);
            animateNumber(document.getElementById('quizzesMadeCount'), 0, stats.quizzes_count || 0, 800);
            animateNumber(document.getElementById('questionsMadeCount'), 0, stats.questions_count || 0, 1200);

        } catch (error) {
            console.error('Error fetching dashboard stats:', error);
            const statsContainer = document.querySelector('#teacherDashboardContent .row.mb-5'); // Adjust selector if needed
            if (statsContainer) {
                 statsContainer.innerHTML = `<div class="col-12 text-center text-danger"><p>Failed to load dashboard statistics. Please try again later.</p></div>`;
            }
        }
    }

    document.querySelectorAll('.btn').forEach(button => {
        button.addEventListener('click', function(e) {
            if (!this.classList.contains('btn-ripple') && !this.closest('.no-ripple')) { // Add .no-ripple to parent to disable
                const existingRipple = this.querySelector('.btn-ripple');
                if (existingRipple) existingRipple.remove();

                const circle = document.createElement('span');
                this.appendChild(circle);
                const diameter = Math.max(this.clientWidth, this.clientHeight);
                const radius = diameter / 2;
                circle.style.width = circle.style.height = `${diameter}px`;
                
                // Calculate position relative to the button, not viewport
                const rect = this.getBoundingClientRect();
                circle.style.left = `${e.clientX - rect.left - radius}px`;
                circle.style.top = `${e.clientY - rect.top - radius}px`;
                circle.classList.add('btn-ripple');
            }
        });
    });

}); // End of DOMContentLoaded

// Helper function to show flash message dynamically
function flashMessage(message, category = 'info', duration = 5000) {
    const container = document.querySelector('.flash-messages-container');
    if (!container) {
        console.warn("Flash message container not found. Cannot display message:", message);
        return;
    }

    const alertDiv = document.createElement('div');
    // Ensure category is one of the expected alert types for styling
    const validCategories = ['success', 'danger', 'warning', 'info'];
    const alertCategory = validCategories.includes(category) ? category : 'info';

    alertDiv.className = `alert alert-${alertCategory} animated-slide-up`; // Use className for multiple classes
    alertDiv.setAttribute('role', 'alert');
    
    const currentLang = document.documentElement.getAttribute('lang') || 'en';
    const closeButtonLabel = currentLang === 'en' ? 'Close alert' : 'إغلاق التنبيه';

    alertDiv.innerHTML = `${message} <button type="button" class="close-alert-btn" aria-label="${closeButtonLabel}">×</button>`;

    const closeButton = alertDiv.querySelector('.close-alert-btn');
    if (closeButton) {
        closeButton.addEventListener('click', () => {
            alertDiv.style.opacity = '0';
            alertDiv.style.transform = 'translateY(-20px) scale(0.95)';
            setTimeout(() => alertDiv.remove(), 300); 
        });
    }
    container.appendChild(alertDiv);

    if (!alertDiv.classList.contains('no-auto-dismiss')) {
        setTimeout(() => {
            if (alertDiv && alertDiv.parentElement) { // Check if still in DOM
               if(closeButton) closeButton.click(); // Trigger click for consistent removal
               else { // Fallback if no close button (shouldn't happen with above code)
                    alertDiv.style.opacity = '0';
                    alertDiv.style.transform = 'translateY(-20px) scale(0.95)';
                    setTimeout(() => alertDiv.remove(), 300);
               }
            }
        }, duration);
    }
}