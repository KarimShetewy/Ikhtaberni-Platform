// static/js/main.js
document.addEventListener('DOMContentLoaded', function() {
    console.log("ملف main.js تم تحميله بنجاح! مرحباً بك في منصة اختبرني.");

    const closeAlertButtons = document.querySelectorAll('.close-alert-btn');
    closeAlertButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const alertBox = this.parentElement; 
            if (alertBox) { 
                alertBox.style.opacity = '0';
                setTimeout(function() {
                    if (alertBox) { 
                        alertBox.style.display = 'none';
                        // alertBox.remove(); 
                    }
                }, 300); 
            }
        });
    });
    
    console.log("main.js: تم الانتهاء من إعداد مستمعي الأحداث الأوليين.");
});