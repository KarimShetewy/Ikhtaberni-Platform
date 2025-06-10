// static/js/auth_script.js

document.addEventListener('DOMContentLoaded', () => {
    // --- تعريف العناصر (Elements) ---
    const loginSection = document.getElementById('login-section');
    const requestOtpSection = document.getElementById('request-otp-section');
    const verifyOtpSection = document.getElementById('verify-otp-section');
    const resetPasswordSection = document.getElementById('reset-password-section');

    const forgotPasswordTrigger = document.getElementById('forgot-password-trigger');
    const backToLoginLinks = document.querySelectorAll('.back-to-login-link'); // For all back links

    // Inputs
    const loginIdentifierInput = document.getElementById('login_identifier'); // For pre-filling OTP phone
    const otpPhoneNumberInput = document.getElementById('otp_phone_number');

    // Forms
    const loginForm = document.getElementById('login-form'); // Not actively used for AJAX submission here
    const requestOtpForm = document.getElementById('request-otp-form');
    const verifyOtpForm = document.getElementById('verify-otp-form');
    const resetPasswordForm = document.getElementById('reset-password-form');

    const globalMessageDiv = document.getElementById('global-message'); // For displaying messages via JS

    // لتخزين رقم الهاتف المستخدم في عملية استعادة كلمة المرور
    let phoneNumberForOtpProcess = ''; // Renamed for clarity

    // --- دالة لإظهار قسم معين وإخفاء الباقي ---
    function showSection(sectionIdToShow) {
        const sections = [loginSection, requestOtpSection, verifyOtpSection, resetPasswordSection];
        sections.forEach(section => {
            if (section) { // Check if the element exists
                if (section.id === sectionIdToShow) {
                    section.style.display = 'block';
                    section.classList.remove('hidden-section');
                } else {
                    section.style.display = 'none';
                    section.classList.add('hidden-section');
                }
            }
        });
        hideGlobalMessage(); // إخفاء أي رسالة عامة عند تغيير القسم
    }

    // --- دالة لعرض رسالة عامة (خطأ أو نجاح) ---
    // This function assumes you have CSS for .alert.alert-danger and .alert.alert-success
    function displayGlobalMessage(message, isError = true) {
        if (globalMessageDiv) {
            globalMessageDiv.textContent = message;
            globalMessageDiv.className = 'alert'; // Reset classes
            if (isError) {
                globalMessageDiv.classList.add('alert-danger'); // Bootstrap-like error
            } else {
                globalMessageDiv.classList.add('alert-success'); // Bootstrap-like success
            }
            globalMessageDiv.classList.remove('hidden-section');
            globalMessageDiv.style.display = 'block'; // Ensure it's visible
        }
    }

    function hideGlobalMessage() {
        if (globalMessageDiv) {
            globalMessageDiv.style.display = 'none';
            globalMessageDiv.classList.add('hidden-section');
            globalMessageDiv.textContent = ''; // Clear previous message
            globalMessageDiv.className = 'alert hidden-section'; // Reset classes
        }
    }


    // --- معالجات الأحداث (Event Handlers) ---

    // عند الضغط على "نسيت كلمة المرور؟"
    if (forgotPasswordTrigger) {
        forgotPasswordTrigger.addEventListener('click', (event) => {
            event.preventDefault();
            // Pre-fill phone number for OTP if it was entered in login_identifier
            if (loginIdentifierInput && otpPhoneNumberInput) {
                // Basic check if it looks like a phone number
                if (/^\+?\d{7,15}$/.test(loginIdentifierInput.value)) { 
                    otpPhoneNumberInput.value = loginIdentifierInput.value;
                } else {
                    // If login_identifier is not a phone, but otpPhoneNumberInput might have a prefilled value
                    // from a previous OTP attempt (e.g., from Flask session prefill), we don't clear it here.
                    // We only prefill from login_identifier if it's a phone.
                    // If loginIdentifier is not a phone, it keeps its current value (which might be empty or from server).
                }
            }
            showSection('request-otp-section');
            if (otpPhoneNumberInput) otpPhoneNumberInput.focus(); // Focus on the phone input
        });
    }

    // عند الضغط على روابط "العودة إلى تسجيل الدخول" أو أي رابط "back" مشابه
    backToLoginLinks.forEach(link => {
        link.addEventListener('click', (event) => {
            event.preventDefault();
            const targetSectionId = event.currentTarget.dataset.target; // Use currentTarget
            if (targetSectionId) {
                showSection(targetSectionId);
                if (targetSectionId === 'login-section' && loginIdentifierInput) {
                    loginIdentifierInput.focus();
                } else if (targetSectionId === 'request-otp-section' && otpPhoneNumberInput) {
                    otpPhoneNumberInput.focus();
                }
            }
        });
    });


    // معالجة نموذج طلب رمز OTP (باستخدام AJAX)
    if (requestOtpForm) {
        requestOtpForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            hideGlobalMessage();
            const formData = new FormData(requestOtpForm);
            const phoneNumber = formData.get('otp_phone_number');
            
            if (!phoneNumber || !/^\+?\d{7,15}$/.test(phoneNumber)) { // Basic validation
                displayGlobalMessage('يرجى إدخال رقم موبايل صالح.', true);
                if (otpPhoneNumberInput) otpPhoneNumberInput.focus();
                return;
            }
            phoneNumberForOtpProcess = phoneNumber; // احفظ الرقم لاستخدامه في الخطوة التالية

            const submitButton = requestOtpForm.querySelector('button[type="submit"]');
            const originalButtonText = submitButton.textContent;
            submitButton.disabled = true;
            submitButton.textContent = 'جاري الإرسال...';

            try {
                // Assumes authApiEndpoints is defined globally (e.g., in login_form.html)
                const response = await fetch(window.authApiEndpoints.requestOtp, { 
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        // 'X-CSRFToken': window.csrfToken // If using CSRF token for AJAX
                    },
                    body: JSON.stringify({ phone_number: phoneNumber })
                });

                const data = await response.json(); // Always try to parse JSON

                if (response.ok && data.success) {
                    displayGlobalMessage(data.message || 'تم إرسال رمز التأكيد بنجاح.', false);
                    showSection('verify-otp-section');
                    const otpCodeInput = document.getElementById('otp_code');
                    if (otpCodeInput) otpCodeInput.focus();
                } else {
                    displayGlobalMessage(data.message || 'فشل إرسال رمز التأكيد. يرجى المحاولة مرة أخرى.', true);
                }
            } catch (error) {
                console.error('Error requesting OTP:', error);
                displayGlobalMessage('حدث خطأ في الشبكة أو مشكلة في الخادم. حاول مرة أخرى.', true);
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = originalButtonText;
            }
        });
    }

    // معالجة نموذج التحقق من رمز OTP (باستخدام AJAX)
    if (verifyOtpForm) {
        verifyOtpForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            hideGlobalMessage();
            const formData = new FormData(verifyOtpForm);
            const otpCode = formData.get('otp_code');

            if (!otpCode || !/^\d{8}$/.test(otpCode)) { // Basic validation for 8 digits
                displayGlobalMessage('رمز التأكيد يجب أن يتكون من 8 أرقام.', true);
                document.getElementById('otp_code')?.focus();
                return;
            }

            const submitButton = verifyOtpForm.querySelector('button[type="submit"]');
            const originalButtonText = submitButton.textContent;
            submitButton.disabled = true;
            submitButton.textContent = 'جاري التحقق...';

            try {
                const response = await fetch(window.authApiEndpoints.verifyOtp, { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone_number: phoneNumberForOtpProcess, otp_code: otpCode })
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    displayGlobalMessage(data.message || 'تم التحقق من الرمز بنجاح.', false);
                    showSection('reset-password-section');
                    const newPasswordInput = document.getElementById('new_password');
                    if (newPasswordInput) newPasswordInput.focus();
                } else {
                    displayGlobalMessage(data.message || 'رمز التأكيد غير صحيح أو انتهت صلاحيته.', true);
                }
            } catch (error) {
                console.error('Error verifying OTP:', error);
                displayGlobalMessage('حدث خطأ في الشبكة أو مشكلة في الخادم. حاول مرة أخرى.', true);
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = originalButtonText;
            }
        });
    }

    // معالجة نموذج إعادة تعيين كلمة المرور (باستخدام AJAX)
    if (resetPasswordForm) {
        resetPasswordForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            hideGlobalMessage();
            const formData = new FormData(resetPasswordForm);
            const newPassword = formData.get('new_password');
            const confirmPassword = formData.get('confirm_password');

            if (newPassword.length < 8) { // Assuming min length 8
                displayGlobalMessage('كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل.', true);
                document.getElementById('new_password')?.focus();
                return;
            }
            if (newPassword !== confirmPassword) {
                displayGlobalMessage('كلمتا المرور الجديدتان غير متطابقتين.', true);
                document.getElementById('confirm_password')?.focus();
                return;
            }
            
            const submitButton = resetPasswordForm.querySelector('button[type="submit"]');
            const originalButtonText = submitButton.textContent;
            submitButton.disabled = true;
            submitButton.textContent = 'جاري الحفظ...';

            try {
                const response = await fetch(window.authApiEndpoints.resetPassword, { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone_number: phoneNumberForOtpProcess, new_password: newPassword })
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    displayGlobalMessage(data.message || 'تم تغيير كلمة المرور بنجاح. يمكنك الآن تسجيل الدخول.', false);
                    // Reset forms for OTP flow
                    if(requestOtpForm) requestOtpForm.reset();
                    if(verifyOtpForm) verifyOtpForm.reset();
                    resetPasswordForm.reset();
                    phoneNumberForOtpProcess = ''; // Clear stored phone number

                    // Redirect or switch to login form after a delay
                    setTimeout(() => {
                        showSection('login-section');
                        if(loginIdentifierInput) {
                            loginIdentifierInput.value = data.phone_number_for_prefill || ''; // Prefill login if server sends it back
                            loginIdentifierInput.focus();
                        }
                    }, 3000); // 3 second delay
                } else {
                    displayGlobalMessage(data.message || 'فشل تغيير كلمة المرور. يرجى المحاولة مرة أخرى.', true);
                }
            } catch (error) {
                console.error('Error resetting password:', error);
                displayGlobalMessage('حدث خطأ في الشبكة أو مشكلة في الخادم. حاول مرة أخرى.', true);
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = originalButtonText;
            }
        });
    }

    // --- العرض المبدئي ---
    // Hide all OTP sections and show only login section initially
    showSection('login-section'); 
    if(loginIdentifierInput) loginIdentifierInput.focus();

}); // End of DOMContentLoaded