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
    let currentTheme = localStorage.getItem('theme') || bodyElement.getAttribute('data-current-theme') || 'dark';
    let currentLang = localStorage.getItem('lang') || htmlElement.getAttribute('lang') || 'en';

    // Apply saved preferences immediately
    applyTheme(currentTheme);
    applyLanguage(currentLang);

    // Event Listeners for Toggles
    if (languageToggle) {
        languageToggle.addEventListener('click', (e) => {
            e.preventDefault();
            currentLang = (currentLang === 'en') ? 'ar' : 'en';
            applyLanguage(currentLang);
            localStorage.setItem('lang', currentLang);
            // Optionally, reload translations if using a dedicated translation library
            // For now, it just toggles visibility and updates text content
            flashMessage('Language preference updated!', 'info');
        });
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', (e) => {
            e.preventDefault();
            currentTheme = (currentTheme === 'dark') ? 'light' : 'dark';
            applyTheme(currentTheme);
            localStorage.setItem('theme', currentTheme);
            flashMessage('Theme preference updated!', 'info');
        });
    }

    // Helper functions for applying theme and language
    function applyTheme(theme) {
        bodyElement.className = ''; // Clear existing theme classes
        bodyElement.classList.add(`theme-${theme}`);
        bodyElement.setAttribute('data-current-theme', theme);
        if (theme === 'dark') {
            themeToggle.innerHTML = '<i class="fas fa-sun"></i> <span class="lang-en">Day Mode</span> <span class="lang-ar" style="display:none;">الوضع النهاري</span>';
            themeToggle.setAttribute('data-theme-target', 'light');
        } else {
            themeToggle.innerHTML = '<i class="fas fa-moon"></i> <span class="lang-en">Night Mode</span> <span class="lang-ar" style="display:none;">الوضع الليلي</span>';
            themeToggle.setAttribute('data-theme-target', 'dark');
        }
    }

    function applyLanguage(lang) {
        htmlElement.setAttribute('lang', lang);
        htmlElement.setAttribute('dir', (lang === 'ar') ? 'rtl' : 'ltr');
        document.querySelectorAll('.lang-en').forEach(el => {
            el.style.display = (lang === 'en') ? 'inline' : 'none';
        });
        document.querySelectorAll('.lang-ar').forEach(el => {
            el.style.display = (lang === 'ar') ? 'inline' : 'none';
        });

        // Update aria-labels and data-titles dynamically
        updateDynamicTextContent(lang);
    }

    function updateDynamicTextContent(lang) {
        // Update platform logo text
        if (platformLogo) {
            const enText = platformLogo.querySelector('.lang-en');
            const arText = platformLogo.querySelector('.lang-ar');
            if (enText && arText) {
                enText.style.display = (lang === 'en') ? 'inline' : 'none';
                arText.style.display = (lang === 'ar') ? 'inline' : 'none';
            }
        }

        // Update settings menu button aria-label/data-title
        const settingsBtn = document.getElementById('settingsMenuButton');
        if (settingsBtn) {
            const titleEn = settingsBtn.getAttribute('data-title-en');
            const titleAr = settingsBtn.getAttribute('data-title-ar');
            settingsBtn.setAttribute('aria-label', (lang === 'en' ? titleEn : titleAr));
        }

        // Update close alert button aria-label
        document.querySelectorAll('.close-alert-btn').forEach(button => {
            const labelEn = button.getAttribute('data-aria-label-en');
            const labelAr = button.getAttribute('data-aria-label-ar');
            button.setAttribute('aria-label', (lang === 'en' ? labelEn : labelAr));
        });

        // Update input placeholders
        document.querySelectorAll('[placeholder-en]').forEach(input => {
            const placeholderEn = input.getAttribute('placeholder-en');
            const placeholderAr = input.getAttribute('placeholder-ar');
            input.setAttribute('placeholder', (lang === 'en' ? placeholderEn : placeholderAr));
        });

        // Update username display in mobile menu
        if (usernameDisplayMobile) {
            const enSpan = usernameDisplayMobile.querySelector('.lang-en');
            const arSpan = usernameDisplayMobile.querySelector('.lang-ar');
            if (enSpan) enSpan.style.display = (lang === 'en') ? 'inline' : 'none';
            if (arSpan) arSpan.style.display = (lang === 'ar') ? 'inline' : 'none';
        }
    }


    // --- 2. Flash Messages Dismissal ---
    document.querySelectorAll('.flash-messages-container .alert').forEach(alert => {
        const closeButton = alert.querySelector('.close-alert-btn');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-20px)';
                alert.addEventListener('transitionend', () => alert.remove());
            });
        }
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alert) {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-20px)';
                alert.addEventListener('transitionend', () => alert.remove());
            }
        }, 5000);
    });

    // --- 3. Settings Dropdown Menu (Hamburger Menu) ---
    const settingsMenuButton = document.getElementById('settingsMenuButton');
    const settingsDropdown = document.getElementById('settingsDropdown');
    const closeMenuButton = document.getElementById('closeMenuButton');

    if (settingsMenuButton && settingsDropdown && closeMenuButton) {
        settingsMenuButton.addEventListener('click', () => {
            const isExpanded = settingsMenuButton.getAttribute('aria-expanded') === 'true';
            settingsMenuButton.setAttribute('aria-expanded', !isExpanded);
            settingsDropdown.classList.toggle('show');
            // Toggle body overflow to prevent scrolling when menu is open
            document.body.classList.toggle('no-scroll', !isExpanded);
        });

        closeMenuButton.addEventListener('click', () => {
            settingsMenuButton.setAttribute('aria-expanded', 'false');
            settingsDropdown.classList.remove('show');
            document.body.classList.remove('no-scroll');
        });

        // Close dropdown if clicked outside
        document.addEventListener('click', (event) => {
            if (!settingsDropdown.contains(event.target) && !settingsMenuButton.contains(event.target)) {
                if (settingsDropdown.classList.contains('show')) {
                    settingsMenuButton.setAttribute('aria-expanded', 'false');
                    settingsDropdown.classList.remove('show');
                    document.body.classList.remove('no-scroll');
                }
            }
        });
    }

    // --- 4. Password Toggle Visibility (Login/Signup Forms) ---
    const passwordToggles = document.querySelectorAll('.password-toggle-icon');
    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const passwordField = this.previousElementSibling; // Assuming input is sibling
            const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordField.setAttribute('type', type);
            // Toggle icon
            this.querySelector('i').classList.toggle('fa-eye');
            this.querySelector('i').classList.toggle('fa-eye-slash');
        });
    });

    // --- 5. Country Search Filter (for signup/login forms) ---
    const countrySearchInputs = document.querySelectorAll('.country-search-input');
    countrySearchInputs.forEach(searchInput => {
        searchInput.addEventListener('keyup', function() {
            const filter = this.value.toLowerCase();
            const selectElement = this.nextElementSibling; // Assuming select is directly after input
            if (selectElement && selectElement.tagName === 'SELECT') {
                const options = selectElement.options;
                for (let i = 0; i < options.length; i++) {
                    const option = options[i];
                    const text = option.textContent.toLowerCase();
                    if (text.includes(filter)) {
                        option.style.display = '';
                        option.classList.remove('hidden-by-search');
                    } else {
                        option.style.display = 'none';
                        option.classList.add('hidden-by-search');
                    }
                }
            }
        });
    });

    // --- 6. Role Selection Box (Signup Page) ---
    const roleBoxes = document.querySelectorAll('.role-selection-box');
    roleBoxes.forEach(box => {
        box.addEventListener('click', () => {
            // Remove 'selected' from all boxes
            roleBoxes.forEach(rb => rb.classList.remove('selected'));
            // Add 'selected' to the clicked box
            box.classList.add('selected');
            // Check the hidden radio button
            const radio = box.querySelector('.role-radio');
            if (radio) {
                radio.checked = true;
            }
        });
    });

    // Handle initial selection on page load (e.g., if reloaded due to validation error)
    const initiallySelectedRadio = document.querySelector('.role-radio:checked');
    if (initiallySelectedRadio) {
        initiallySelectedRadio.closest('.role-selection-box').classList.add('selected');
    }

    // --- 7. Dynamic Visual Effects & Animations ---

    // Apply initial animations for cards/sections
    const animatedElements = document.querySelectorAll('.card, .teacher-card, .feature-item, .accordion-item');
    animatedElements.forEach((el, index) => {
        el.style.animationDelay = `${index * 0.08}s`; // Staggered animation
        el.classList.add('animated-slide-up');
    });

    // Number animation function
    function animateNumber(element, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            element.textContent = Math.floor(progress * (end - start) + start);
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }

    // Fetch and display dashboard stats dynamically for teacher dashboard
    // This is called only if the element with id 'teacherDashboardContent' exists
    const teacherDashboardContent = document.getElementById('teacherDashboardContent');
    if (teacherDashboardContent) {
        fetchDashboardStats();
        // Optional: refresh stats every 30 seconds
        // setInterval(fetchDashboardStats, 30000);
    }

    async function fetchDashboardStats() {
        try {
            const response = await fetch('/api/teacher/dashboard_stats');
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            const stats = await response.json();

            // Update elements with animated numbers
            animateNumber(document.getElementById('subscribersCount'), 0, stats.subscribers, 1000);
            animateNumber(document.getElementById('totalViewsCount'), 0, stats.total_views, 1500);
            animateNumber(document.getElementById('quizzesMadeCount'), 0, stats.quizzes_count, 800);
            animateNumber(document.getElementById('questionsMadeCount'), 0, stats.questions_count, 1200);

        } catch (error) {
            console.error('Error fetching dashboard stats:', error);
            // Optionally, display a user-friendly error message on the dashboard
            const statsContainer = document.querySelector('#teacherDashboardContent .row.mb-5');
            if (statsContainer) {
                 statsContainer.innerHTML = `<div class="col-12 text-center text-danger">
                     <p>Failed to load dashboard statistics. Please refresh the page.</p>
                 </div>`;
            }
        }
    }

    // Ripple effect for buttons (requires corresponding CSS @keyframes ripple)
    document.querySelectorAll('.btn').forEach(button => {
        button.addEventListener('click', function(e) {
            // Only apply if the button itself is not the ripple element (to prevent recursion)
            if (!this.classList.contains('btn-ripple')) {
                const existingRipple = this.querySelector('.btn-ripple');
                if (existingRipple) {
                    existingRipple.remove();
                }

                const circle = document.createElement('span');
                this.appendChild(circle);

                const diameter = Math.max(this.clientWidth, this.clientHeight);
                const radius = diameter / 2;

                circle.style.width = circle.style.height = `${diameter}px`;
                circle.style.left = `${e.clientX - (this.getBoundingClientRect().left + radius)}px`;
                circle.style.top = `${e.clientY - (this.getBoundingClientRect().top + radius)}px`;
                circle.classList.add('btn-ripple');
            }
        });
    });


    // --- End of Dynamic Effects ---

});

// Helper function to show flash message (can be improved with CSS for animation)
function flashMessage(message, category) {
    const container = document.querySelector('.flash-messages-container');
    if (!container) return;

    const alertDiv = document.createElement('div');
    alertDiv.classList.add('alert', `alert-${category}`, 'animated-slide-up');
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML = `${message} <button type="button" class="close-alert-btn" data-aria-label-en="Close alert" data-aria-label-ar="إغلاق التنبيه">×</button>`;

    // Update aria-label for the new alert's close button based on current language
    const currentLang = document.documentElement.getAttribute('lang') || 'en';
    const closeButton = alertDiv.querySelector('.close-alert-btn');
    if (closeButton) {
        const labelEn = closeButton.getAttribute('data-aria-label-en');
        const labelAr = closeButton.getAttribute('data-aria-label-ar');
        closeButton.setAttribute('aria-label', (currentLang === 'en' ? labelEn : labelAr));
        
        closeButton.addEventListener('click', () => {
            alertDiv.style.opacity = '0';
            alertDiv.style.transform = 'translateY(-20px)';
            alertDiv.addEventListener('transitionend', () => alertDiv.remove());
        });
    }

    container.appendChild(alertDiv);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv) {
            alertDiv.style.opacity = '0';
            alertDiv.style.transform = 'translateY(-20px)';
            alertDiv.addEventListener('transitionend', () => alertDiv.remove());
        }
    }, 5000);
}