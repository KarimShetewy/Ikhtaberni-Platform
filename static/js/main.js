// static/js/main.js

document.addEventListener('DOMContentLoaded', () => {
    // --- 1. Language and Theme Toggles ---
    const htmlElement = document.documentElement;
    const bodyElement = document.body;
    const languageToggle = document.getElementById('languageToggle');
    const themeToggle = document.getElementById('themeToggle');
    const platformLogo = document.getElementById('platformLogo'); // للتأكد من وجوده فقط

    // Retrieve saved preferences or set defaults
    let currentTheme = localStorage.getItem('theme') || bodyElement.getAttribute('data-current-theme') || 'dark'; 
    let currentLang = localStorage.getItem('lang') || htmlElement.getAttribute('lang') || 'en';

    // Apply saved preferences immediately on load
    applyTheme(currentTheme);
    applyLanguage(currentLang); 

    // Event Listeners for Toggles
    if (languageToggle) {
        languageToggle.addEventListener('click', (e) => {
            e.preventDefault();
            const newLang = (currentLang === 'en') ? 'ar' : 'en';
            currentLang = newLang; 
            localStorage.setItem('lang', currentLang); 
            
            // Redirect to Flask route to change language in session
            window.location.href = `/switch_lang/${currentLang}`; 
        });
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', (e) => {
            e.preventDefault();
            const newTheme = (currentTheme === 'dark') ? 'light' : 'dark';
            currentTheme = newTheme; 
            applyTheme(currentTheme); 
            localStorage.setItem('theme', currentTheme); 
            // Optional: flashMessage('Theme preference updated!', 'info'); // You can re-enable this if needed
        });
    }

    /** Applies the selected theme class and updates the theme toggle button content. */
    function applyTheme(theme) {
        bodyElement.classList.remove('theme-dark', 'theme-light'); 
        bodyElement.classList.add(`theme-${theme}`);
        bodyElement.setAttribute('data-current-theme', theme); 
        
        if (themeToggle) {
            const icon = themeToggle.querySelector('i');
            // Ensure spans exist or create them
            let langEnSpan = themeToggle.querySelector('.lang-en-theme-text');
            let langArSpan = themeToggle.querySelector('.lang-ar-theme-text');

            if (!langEnSpan) {
                langEnSpan = document.createElement('span');
                langEnSpan.classList.add('lang-en-theme-text', 'lang-en');
                themeToggle.appendChild(langEnSpan);
            }
            if (!langArSpan) {
                langArSpan = document.createElement('span');
                langArSpan.classList.add('lang-ar-theme-text', 'lang-ar');
                langArSpan.style.display = 'none'; // Initially hidden
                themeToggle.appendChild(langArSpan);
            }

            if (theme === 'dark') {
                icon.classList.remove('fa-sun');
                icon.classList.add('fa-moon');
                langEnSpan.textContent = 'Night Mode';
                langArSpan.textContent = 'الوضع الليلي';
                themeToggle.setAttribute('data-theme-target', 'light');
            } else { // light
                icon.classList.remove('fa-moon');
                icon.classList.add('fa-sun');
                langEnSpan.textContent = 'Day Mode';
                langArSpan.textContent = 'الوضع النهاري';
                themeToggle.setAttribute('data-theme-target', 'dark');
            }
            updateLanguageSpecificElements(currentLang); 
        }
    }

    /** Applies the selected language and updates all language-specific text elements. */
    function applyLanguage(lang) {
        htmlElement.setAttribute('lang', lang);
        htmlElement.setAttribute('dir', (lang === 'ar') ? 'rtl' : 'ltr');
        bodyElement.setAttribute('data-current-lang', lang); 

        updateLanguageSpecificElements(lang);
        
        if (languageToggle) {
            const icon = languageToggle.querySelector('i');
            if (icon) { 
                // We use spans for text now, so just update their content
                languageToggle.querySelector('.lang-en').textContent = (lang === 'en' ? 'Switch to عربي' : 'Switch to English');
                languageToggle.querySelector('.lang-ar').textContent = (lang === 'ar' ? 'Switch to English' : 'Switch to عربي');
            }
        }
        applyTheme(currentTheme); 
        
        document.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang: lang } }));
    }

    /** Helper to toggle visibility of elements based on current language. */
    function updateLanguageSpecificElements(lang) {
        document.querySelectorAll('.lang-en').forEach(el => {
            el.style.display = (lang === 'en') ? '' : 'none'; 
        });
        document.querySelectorAll('.lang-ar').forEach(el => {
            el.style.display = (lang === 'ar') ? '' : 'none';
        });

        document.querySelectorAll('[data-title-en], [data-title-ar]').forEach(el => {
            const titleEn = el.getAttribute('data-title-en');
            const titleAr = el.getAttribute('data-title-ar');
            if (titleEn && titleAr) {
                el.setAttribute('title', (lang === 'en' ? titleEn : titleAr));
            }
        });
        document.querySelectorAll('[data-aria-label-en], [data-aria-label-ar]').forEach(el => {
            const labelEn = el.getAttribute('data-aria-label-en');
            const labelAr = el.getAttribute('data-aria-label-ar');
            if (labelEn && labelAr) {
                el.setAttribute('aria-label', (lang === 'en' ? labelEn : labelAr));
            }
        });
        document.querySelectorAll('[placeholder-en], [placeholder-ar]').forEach(el => {
            const placeholderEn = el.getAttribute('placeholder-en');
            const placeholderAr = el.getAttribute('placeholder-ar');
            if (placeholderEn && placeholderAr) {
                el.setAttribute('placeholder', (lang === 'en' ? placeholderEn : placeholderAr));
            }
        });
    }

    // --- 2. Flash Messages Dismissal ---
    // This function can be called by Flask routes if needed, or by other JS
    window.flashMessage = function(message, category = 'info', duration = 5000) {
        const container = document.querySelector('.flash-messages-container');
        if (!container) {
            console.warn("Flash message container not found. Cannot display message:", message);
            return;
        }

        const alertDiv = document.createElement('div');
        const validCategories = ['success', 'danger', 'warning', 'info'];
        const alertCategory = validCategories.includes(category) ? category : 'info';

        alertDiv.className = `alert alert-${alertCategory} animated-slide-up`; 
        alertDiv.setAttribute('role', 'alert');
        
        const closeButtonLabel = (currentLang === 'en' ? 'Close alert' : 'إغلاق التنبيه');
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

        // Auto-dismiss after a delay
        if (!alertDiv.classList.contains('no-auto-dismiss')) { 
            setTimeout(() => {
                if (alertDiv && alertDiv.parentElement) { 
                   closeButton.click(); 
                }
            }, duration);
        }
    };

    // Auto-dismiss and manual dismiss for existing flash messages on page load
    document.querySelectorAll('.flash-messages-container .alert').forEach(alert => {
        const closeButton = alert.querySelector('.close-alert-btn');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-20px) scale(0.95)';
                setTimeout(() => alert.remove(), 300);
            });
            const duration = 5000 + (Array.from(document.querySelectorAll('.flash-messages-container .alert')).indexOf(alert) * 300);
            setTimeout(() => {
                if (alert && alert.parentElement) {
                    closeButton.click();
                }
            }, duration);
        }
    });

    // --- 3. Settings Dropdown Menu (Hamburger Menu) ---
    const settingsMenuButton = document.getElementById('settingsMenuButton');
    const settingsDropdown = document.getElementById('settingsDropdown');
    const closeMenuButton = document.getElementById('closeMenuButton');

    if (settingsMenuButton && settingsDropdown) {
        settingsMenuButton.addEventListener('click', (e) => {
            e.stopPropagation(); 
            const isExpanded = settingsMenuButton.getAttribute('aria-expanded') === 'true';
            settingsMenuButton.setAttribute('aria-expanded', String(!isExpanded));
            settingsDropdown.classList.toggle('show');
            document.body.classList.toggle('no-scroll', !isExpanded); // Prevent body scroll when menu is open
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

    // --- 4. User Profile Dropdown Toggle Logic ---
    const userProfileButton = document.getElementById('userProfileButton');
    const userDropdown = document.getElementById('userDropdown');

    if (userProfileButton && userDropdown) {
        userProfileButton.addEventListener('click', function(e) {
            e.stopPropagation(); // Prevent clicks on button from immediately closing the dropdown from document click listener
            userDropdown.classList.toggle('show');
            this.setAttribute('aria-expanded', userDropdown.classList.contains('show'));
        });

        document.addEventListener('click', function(event) {
            if (userDropdown.classList.contains('show') && 
                !userDropdown.contains(event.target) && 
                !userProfileButton.contains(event.target)) {
                userDropdown.classList.remove('show');
                userProfileButton.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // --- 5. Password Toggle Visibility (for login/signup forms) ---
    function togglePasswordVisibility(fieldId, iconElement) {
        const passwordField = document.getElementById(fieldId);
        const icon = iconElement.querySelector('i');
        const currentLang = document.documentElement.lang || 'en'; 

        if (passwordField && icon) {
            const type = passwordField.type === "password" ? "text" : "password";
            passwordField.type = type;
            icon.classList.toggle("fa-eye");
            icon.classList.toggle("fa-eye-slash");
            iconElement.setAttribute('aria-pressed', type === "text" ? 'true' : 'false');
            
            const newLabel = (type === "text") ? (currentLang === 'ar' ? 'إخفاء كلمة المرور' : 'Hide password') : (currentLang === 'ar' ? 'إظهار كلمة المرور' : 'Show password');
            iconElement.setAttribute('aria-label', newLabel);
            iconElement.setAttribute('title', newLabel);
        }
    }
    document.querySelectorAll('.password-toggle-icon').forEach(toggle => {
        toggle.addEventListener('click', function() {
            togglePasswordVisibility(this.previousElementSibling.id, this);
        });
        const currentLang = document.documentElement.lang || 'en';
        const isPasswordVisible = toggle.previousElementSibling.type === 'text';
        const newLabel = (isPasswordVisible) ? (currentLang === 'ar' ? 'إخفاء كلمة المرور' : 'Hide password') : (currentLang === 'ar' ? 'إظهار كلمة المرور' : 'Show password');
        toggle.setAttribute('aria-label', newLabel);
        toggle.setAttribute('title', newLabel);
    });

    // --- 6. Country Search Filter (for signup/login forms) ---
    window.filterCountriesSignup = function() { 
        const input = document.getElementById('country_signup_search_input');
        const filter = input.value.toLowerCase().trim();
        const select = document.getElementById('country_signup_select');
        const options = Array.from(select.options); 
        const currentLang = document.documentElement.lang || 'en';

        select.innerHTML = ''; 
        
        const defaultOptionData = options.find(opt => opt.value === "");
        if (defaultOptionData) {
            const defaultOption = new Option(defaultOptionData.text, defaultOptionData.value);
            defaultOption.disabled = defaultOptionData.disabled;
            defaultOption.selected = true; 
            select.add(defaultOption);
        }

        options.forEach(opt => {
            if (opt.value === "") return; 

            let textContentToSearch = '';
            const dataTextEn = opt.getAttribute('data-text-en');
            const dataTextAr = opt.getAttribute('data-text-ar');

            if (currentLang === 'ar' && dataTextAr) {
                textContentToSearch = dataTextAr.toLowerCase();
            } else if (dataTextEn) {
                textContentToSearch = dataTextEn.toLowerCase();
            } else {
                textContentToSearch = opt.textContent.toLowerCase();
            }

            if (textContentToSearch.includes(filter)) {
                const option = new Option(opt.textContent, opt.value);
                option.disabled = opt.disabled;
                option.selected = opt.selected; 
                select.add(option);
            }
        });

        if (select.selectedIndex === -1 && select.options.length > 0) {
            const originalSelectedOption = options.find(o => o.selected);
            if (originalSelectedOption && options.some(o => o.value === originalSelectedOption.value && o.style.display !== 'none')) {
                select.value = originalSelectedOption.value;
            } else {
                const firstAvailable = Array.from(select.options).find(o => !o.disabled && o.style.display !== 'none');
                if (firstAvailable) {
                    select.value = firstAvailable.value;
                }
            }
        }
    }


    // --- 7. Role Selection Box (Signup Page) ---
    const roleBoxes = document.querySelectorAll('.role-selection-box');
    const studentRadio = document.getElementById('role_student');
    const teacherRadio = document.getElementById('role_teacher');
    const selectedRoleTextEnSpan = document.getElementById('selectedRoleTextEn');
    const selectedRoleTextArSpan = document.getElementById('selectedRoleTextAr');
    const roleSelectionForm = document.getElementById('roleSelectionForm');

    function updateRoleSelectionVisuals() {
        let roleNameEn = '';
        let roleNameAr = '';
        
        roleBoxes.forEach(box => {
            box.classList.remove('selected');
            box.setAttribute('aria-checked', 'false');
        });
        
        if (studentRadio && studentRadio.checked) {
            const box = studentRadio.closest('.role-selection-box');
            if (box) {
                box.classList.add('selected');
                box.setAttribute('aria-checked', 'true');
            }
            roleNameEn = ' Student';
            roleNameAr = ' طالب';
        } else if (teacherRadio && teacherRadio.checked) {
            const box = teacherRadio.closest('.role-selection-box');
            if (box) {
                box.classList.add('selected');
                box.setAttribute('aria-checked', 'true');
            }
            roleNameEn = ' Teacher';
            roleNameAr = ' معلم';
        }
        
        if(selectedRoleTextEnSpan) selectedRoleTextEnSpan.textContent = roleNameEn;
        if(selectedRoleTextArSpan) selectedRoleTextArSpan.textContent = roleNameAr;
    }

    roleBoxes.forEach(box => {
        box.addEventListener('click', (e) => {
            e.preventDefault(); 
            const radio = box.querySelector('.role-radio');
            if (radio) {
                radio.checked = true;
                updateRoleSelectionVisuals();
            }
        });
    });

    updateRoleSelectionVisuals(); 

    if (roleSelectionForm) {
        roleSelectionForm.addEventListener('submit', function(event) {
            const selectedRoleRadio = document.querySelector('input[name="role"]:checked');
            if (!selectedRoleRadio) {
                event.preventDefault(); 
                const alertMsg = (document.documentElement.lang === 'ar') ? 
                                 'يرجى اختيار دورك (طالب أو معلم) للمتابعة.' : 
                                 'Please choose your role (student or teacher) to continue.';
                window.flashMessage(alertMsg, 'danger'); 
            }
        });
    }

    // --- 8. Dynamic Content Animations (Intersection Observer) ---
    const animatedElements = document.querySelectorAll(
        '.card, .teacher-card, .feature-item, .accordion-item, .animated-auth-element, .hero-text-content, .hero-image-content'
    ); 
    const observerOptions = {
        root: null, 
        rootMargin: '0px',
        threshold: 0.1 
    };

    const observer = new IntersectionObserver((entries, observerInstance) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                const trueIndex = Array.from(animatedElements).indexOf(entry.target); 
                entry.target.style.animationDelay = `${trueIndex * 0.08}s`; 
                entry.target.classList.add('animated-slide-up');
                observerInstance.unobserve(entry.target); 
            }
        });
    }, observerOptions);

    animatedElements.forEach(el => {
        observer.observe(el);
    });

    // --- 9. Dashboard Stats Animation (for teacher/student dashboards) ---
    function animateNumber(element, start, end, duration) {
        if (!element) return; 
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            element.textContent = Math.floor(progress * (end - start) + start).toLocaleString(); 
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }
    
    const teacherDashboardContent = document.getElementById('teacherDashboardContent');
    const studentDashboardContent = document.getElementById('studentDashboardContent'); 

    if (teacherDashboardContent || studentDashboardContent) {
        fetchDashboardStats(); 
    }

    async function fetchDashboardStats() {
        const userRole = bodyElement.getAttribute('data-user-role'); 
        let apiUrl = '';
        if (userRole === 'teacher') {
            apiUrl = '/api/teacher/dashboard_stats'; 
        } else if (userRole === 'student') {
            apiUrl = '/api/student/dashboard_stats'; 
        } else {
            console.warn("User role not set or not recognized for dashboard stats API call.");
            return;
        }

        try {
            const response = await fetch(apiUrl);
            if (!response.ok) {
                const errorData = await response.text();
                throw new Error(`Network response was not ok: ${response.status} ${errorData}`);
            }
            const stats = await response.json();

            if (document.getElementById('subscribersCount')) animateNumber(document.getElementById('subscribersCount'), 0, stats.subscribers || 0, 1000);
            if (document.getElementById('totalViewsCount')) animateNumber(document.getElementById('totalViewsCount'), 0, stats.total_views || 0, 1500);
            if (document.getElementById('quizzesMadeCount')) animateNumber(document.getElementById('quizzesMadeCount'), 0, stats.quizzes_count || 0, 800);
            if (document.getElementById('questionsMadeCount')) animateNumber(document.getElementById('questionsMadeCount'), 0, stats.questions_count || 0, 1200);
            if (document.getElementById('videosWatchedCount')) animateNumber(document.getElementById('videosWatchedCount'), 0, stats.videos_watched_count || 0, 1000);
            if (document.getElementById('quizzesTakenCount')) animateNumber(document.getElementById('quizzesTakenCount'), 0, stats.quizzes_taken_count || 0, 1000);

        } catch (error) {
            console.error('Error fetching dashboard stats:', error);
            const dashboardSection = document.querySelector('.dashboard-section'); 
            if (dashboardSection) {
                 const messageDiv = document.createElement('div');
                 messageDiv.className = 'alert alert-danger text-center mt-4';
                 messageDiv.textContent = (currentLang === 'ar' ? 'فشل تحميل إحصائيات لوحة التحكم. يرجى المحاولة لاحقاً.' : 'Failed to load dashboard statistics. Please try again later.');
                 dashboardSection.appendChild(messageDiv);
            }
        }
    }

    // --- 10. Button Ripple Effect ---
    document.querySelectorAll('.btn').forEach(button => {
        button.addEventListener('click', function(e) {
            if (!this.classList.contains('no-ripple') && !this.closest('.no-ripple')) { 
                const existingRipple = this.querySelector('.btn-ripple');
                if (existingRipple) existingRipple.remove(); 

                const circle = document.createElement('span');
                this.appendChild(circle); 
                
                const diameter = Math.max(this.clientWidth, this.clientHeight);
                const radius = diameter / 2;

                circle.style.width = circle.style.height = `${diameter}px`;
                const rect = this.getBoundingClientRect();
                circle.style.left = `${e.clientX - rect.left - radius}px`;
                circle.style.top = `${e.clientY - rect.top - radius}px`;
                circle.classList.add('btn-ripple');
            }
        });
    });

}); // End of DOMContentLoaded