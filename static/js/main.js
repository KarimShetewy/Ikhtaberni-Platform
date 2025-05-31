document.addEventListener('DOMContentLoaded', function() {
    // console.log("main.js: Initializing Ektbariny Platform Scripts - Full Version");

    // --- DOM Element References ---
    const settingsMenuButton = document.getElementById('settingsMenuButton');
    const settingsDropdown = document.getElementById('settingsDropdown');
    const languageToggle = document.getElementById('languageToggle');
    const themeToggle = document.getElementById('themeToggle');
    const htmlElement = document.documentElement;
    const bodyElement = document.body;

    // --- 1. UTILITY: Update Texts Based on Data Attributes ---
    function updateAttributeBasedTexts(lang) {
        if (lang !== 'en' && lang !== 'ar') {
            // console.warn('updateAttributeBasedTexts: Invalid language, defaulting to en. Received:', lang);
            lang = 'en'; // Default to English if language is invalid
        }

        const elementsToUpdate = document.querySelectorAll(
            '[data-placeholder-en], [data-title-en], [data-aria-label-en]'
        );
        
        elementsToUpdate.forEach(el => {
            const langSuffix = lang.charAt(0).toUpperCase() + lang.slice(1); // 'En' or 'Ar'
            const fallbackSuffix = 'En'; // English as a reliable fallback

            // Update placeholder
            if (el.dataset[`placeholder${langSuffix}`] !== undefined || el.dataset[`placeholder${fallbackSuffix}`] !== undefined) {
                el.placeholder = el.dataset[`placeholder${langSuffix}`] || el.dataset[`placeholder${fallbackSuffix}`] || '';
            }
            // Update title
            if (el.dataset[`title${langSuffix}`] !== undefined || el.dataset[`title${fallbackSuffix}`] !== undefined) {
                el.title = el.dataset[`title${langSuffix}`] || el.dataset[`title${fallbackSuffix}`] || '';
            }
            // Update aria-label
            if (el.dataset[`ariaLabel${langSuffix}`] !== undefined || el.dataset[`ariaLabel${fallbackSuffix}`] !== undefined) {
                el.setAttribute('aria-label', el.dataset[`ariaLabel${langSuffix}`] || el.dataset[`ariaLabel${fallbackSuffix}`] || '');
            }
        });

        // Special handling for <select> options if they use lang spans
        const countrySelects = document.querySelectorAll('select[name="country"]'); // Target all country selects
        countrySelects.forEach(select => {
            Array.from(select.options).forEach(option => {
                const enSpan = option.querySelector('.lang-en');
                const arSpan = option.querySelector('.lang-ar');
                if (enSpan && arSpan) {
                    enSpan.style.display = (lang === 'ar') ? 'none' : '';
                    arSpan.style.display = (lang === 'en') ? 'none' : '';
                }
            });
        });
    }

    // --- 2. LANGUAGE SWITCHING FUNCTIONALITY ---
    function setLanguage(lang) {
        if (lang !== 'en' && lang !== 'ar') {
            // console.warn('setLanguage: Invalid language, defaulting to en. Received:', lang);
            lang = 'en';
        }

        htmlElement.lang = lang;
        htmlElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
        bodyElement.dataset.currentLang = lang;

        // Toggle visibility of language-specific spans
        document.querySelectorAll('.lang-en, .lang-ar').forEach(el => {
            // Ensure el.style exists to prevent errors on non-HTMLElements
            if (el && typeof el.style !== 'undefined') { 
                el.style.display = el.classList.contains(`lang-${lang}`) ? '' : 'none';
            }
        });

        // Update the text and data-attribute of the language toggle button itself
        if (languageToggle) {
            const enTextSpanInToggle = languageToggle.querySelector('.lang-en');
            const arTextSpanInToggle = languageToggle.querySelector('.lang-ar');
            const nextLangTarget = (lang === 'en' ? 'ar' : 'en');

            if (enTextSpanInToggle && arTextSpanInToggle) {
                enTextSpanInToggle.textContent = (lang === 'en') ? 'Switch to عربي' : 'Switch to English';
                arTextSpanInToggle.textContent = (lang === 'ar') ? 'التحويل إلى الإنجليزية' : 'التحويل إلى العربية';
                
                // Show the text prompting to switch to the *other* language
                enTextSpanInToggle.style.display = (lang === 'en') ? '' : 'none';
                arTextSpanInToggle.style.display = (lang === 'ar') ? '' : 'none';
            }
            languageToggle.dataset.langTarget = nextLangTarget;
        }
        
        updateAttributeBasedTexts(lang); // Update placeholders, titles, aria-labels
        localStorage.setItem('userLanguage', lang);
        // console.log(`UI Language has been set to: ${lang}`);
        
        // Dispatch a custom event that other scripts can listen to
        document.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang: lang } }));
    }

    // --- 3. THEME SWITCHING FUNCTIONALITY (Dark/Light Mode) ---
    function setTheme(theme) {
        if (theme !== 'light' && theme !== 'dark') {
            // console.warn('setTheme: Invalid theme, defaulting to dark. Received:', theme);
            theme = 'dark'; // Default to dark theme if an invalid value is passed
        }
        bodyElement.classList.remove('theme-dark', 'theme-light');
        bodyElement.classList.add(`theme-${theme}`);
        bodyElement.dataset.currentTheme = theme;

        // Update the theme toggle button text and icon
        if (themeToggle) {
            const icon = themeToggle.querySelector('i');
            const enTextSpan = themeToggle.querySelector('.lang-en');
            const arTextSpan = themeToggle.querySelector('.lang-ar');
            const nextThemeTarget = (theme === 'dark' ? 'light' : 'dark');

            if (icon) {
                icon.className = (theme === 'light') ? 'fas fa-moon' : 'fas fa-sun'; // Moon icon for Light theme (to switch to Dark)
            }
            if (enTextSpan) {
                enTextSpan.textContent = (theme === 'light') ? 'Dark Mode' : 'Day Mode';
            }
            if (arTextSpan) {
                arTextSpan.textContent = (theme === 'light') ? 'الوضع الليلي' : 'الوضع النهاري';
            }
            themeToggle.dataset.themeTarget = nextThemeTarget;
        }
        localStorage.setItem('userTheme', theme);
        // console.log(`UI Theme has been set to: ${theme}`);
    }

    // --- 4. SETTINGS DROPDOWN MENU CONTROL ---
    if (settingsMenuButton && settingsDropdown) {
        settingsMenuButton.addEventListener('click', function(event) {
            event.stopPropagation(); // Prevent the click from immediately closing the dropdown via the document listener
            const isExpanded = settingsMenuButton.getAttribute('aria-expanded') === 'true';
            settingsDropdown.style.display = isExpanded ? 'none' : 'block';
            settingsMenuButton.setAttribute('aria-expanded', String(!isExpanded));
        });
    }

    // Close dropdown if clicked outside
    document.addEventListener('click', function(event) {
        if (settingsDropdown && settingsDropdown.style.display === 'block' &&
            settingsMenuButton && 
            !settingsMenuButton.contains(event.target) &&
            !settingsDropdown.contains(event.target)) {
            
            settingsDropdown.style.display = 'none';
            settingsMenuButton.setAttribute('aria-expanded', 'false');
        }
    });

    // --- 5. EVENT LISTENERS FOR TOGGLE BUTTONS ---
    if (languageToggle) {
        languageToggle.addEventListener('click', function(event) {
            event.preventDefault();
            const currentLangOnBody = bodyElement.dataset.currentLang || 'en';
            // Use the data-lang-target, or calculate the next one if somehow missing
            const targetLang = this.dataset.langTarget || (currentLangOnBody === 'en' ? 'ar' : 'en');
            setLanguage(targetLang);
            
            // Close dropdown after selection
            if (settingsDropdown) settingsDropdown.style.display = 'none';
            if (settingsMenuButton) settingsMenuButton.setAttribute('aria-expanded', 'false');
        });
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', function(event) {
            event.preventDefault();
            const currentThemeOnBody = bodyElement.dataset.currentTheme || 'dark';
            const targetTheme = this.dataset.themeTarget || (currentThemeOnBody === 'dark' ? 'light' : 'dark');
            setTheme(targetTheme);

            // Close dropdown after selection
            if (settingsDropdown) settingsDropdown.style.display = 'none';
            if (settingsMenuButton) settingsMenuButton.setAttribute('aria-expanded', 'false');
        });
    }

    // --- 6. APPLY SAVED OR DEFAULT SETTINGS ON PAGE LOAD ---
    // Apply language first, as theme-related texts might depend on it
    const savedLang = localStorage.getItem('userLanguage');
    const defaultLang = bodyElement.dataset.currentLang || 'en'; // Fallback to body attr, then 'en'
    setLanguage(savedLang || defaultLang); 

    const savedTheme = localStorage.getItem('userTheme');
    const defaultTheme = bodyElement.dataset.currentTheme || 'dark'; // Fallback to body attr, then 'dark'
    setTheme(savedTheme || defaultTheme);
    

    // --- 7. FLASH MESSAGE CLOSE FUNCTIONALITY ---
    document.querySelectorAll('.close-alert-btn').forEach(button => {
        button.addEventListener('click', function() {
            const alertBox = this.closest('.alert'); // Find the parent .alert element
            if (alertBox) {
                alertBox.style.opacity = '0';
                // Remove the element after the transition (0.3s defined in CSS)
                alertBox.addEventListener('transitionend', () => {
                    if (alertBox.parentNode) { // Check if it's still in the DOM
                        alertBox.remove();
                    }
                }, { once: true }); // Listener will run once and then remove itself
            }
        });
    });
    
    // console.log("main.js: All initializations and event listeners have been applied.");
});