# auth_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, g
from models import db, User # استيراد النماذج من models.py

# قم بإنشاء كائن Blueprint
# 'auth' هو اسم الـ Blueprint
# __name__ هو اسم الحزمة/الوحدة الحالية
# url_prefix سيتم إضافته قبل جميع المسارات المعرفة في هذا الـ Blueprint
# template_folder يحدد مكان قوالب HTML الخاصة بهذا الـ Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth', template_folder='templates/auth')
# إذا كانت قوالبك في `project_root/templates/auth/` والـ Blueprint في الجذر، لا تحتاج `template_folder`
# إذا كان Blueprint في مجلد فرعي مثل `project_root/blueprints/auth_routes.py` و
# القوالب في `project_root/templates/auth/`، قد تحتاج إلى `template_folder='../templates/auth'`

# --- مسار صفحة تسجيل الدخول (GET) ومعالجتها (POST) ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # إذا كان المستخدم مسجلاً دخوله بالفعل، وجهه إلى لوحة التحكم
    if g.user: # g.user يتم تعيينه بواسطة @app.before_request في app.py
        flash('أنت مسجل الدخول بالفعل!', 'info')
        return redirect(url_for('dashboard.dashboard_index')) # افترض أن لديك dashboard blueprint

    if request.method == 'POST':
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')

        if not phone_number or not password:
            flash('يرجى إدخال رقم الموبايل وكلمة المرور.', 'danger')
            # من الأفضل إعادة عرض نفس النموذج مع البيانات التي أدخلها المستخدم (باستثناء كلمة المرور)
            return render_template('auth/login_form.html') 

        user = User.query.filter_by(phone_number=phone_number).first()

        if user and user.check_password(password):
            session.clear() # امسح أي جلسة قديمة
            session['user_id'] = user.id
            session['phone_number'] = user.phone_number # يمكنك تخزين أي معلومات مفيدة في الجلسة
            flash(f'مرحبًا بعودتك، {user.username or user.phone_number}!', 'success')
            # عدّل هذا إلى المسار الذي تريد توجيه المستخدم إليه بعد تسجيل الدخول
            return redirect(url_for('dashboard.dashboard_index')) # مثال
        else:
            flash('رقم الموبايل أو كلمة المرور غير صحيحة. يرجى المحاولة مرة أخرى.', 'danger')
            return render_template('auth/login_form.html')

    # لعرض صفحة تسجيل الدخول (GET request)
    return render_template('auth/login_form.html')

# --- مسار تسجيل مستخدم جديد (مثال، إذا لم يكن لديك) ---
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if g.user:
        return redirect(url_for('dashboard.dashboard_index'))

    if request.method == 'POST':
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        # username = request.form.get('username') # إذا كان لديك حقل اسم مستخدم
        
        error = None
        if not phone_number:
            error = 'رقم الموبايل مطلوب.'
        elif not password:
            error = 'كلمة المرور مطلوبة.'
        elif password != confirm_password:
            error = 'كلمتا المرور غير متطابقتين.'
        elif User.query.filter_by(phone_number=phone_number).first() is not None:
            error = f'رقم الموبايل {phone_number} مسجل بالفعل.'
        # يمكنك إضافة المزيد من التحققات هنا (طول كلمة المرور، صحة رقم الهاتف، إلخ)

        if error is None:
            try:
                new_user = User(phone_number=phone_number, password=password) # يمكنك إضافة username إذا لزم الأمر
                db.session.add(new_user)
                db.session.commit()
                flash('تم إنشاء حسابك بنجاح! يمكنك الآن تسجيل الدخول.', 'success')
                return redirect(url_for('auth.login'))
            except Exception as e:
                db.session.rollback() # تراجع عن التغييرات إذا حدث خطأ
                error = f"حدث خطأ أثناء إنشاء الحساب: {e}" # سجل هذا الخطأ بشكل أفضل
        
        if error:
            flash(error, 'danger')

    return render_template('auth/register_form.html') # افترض أن لديك register_form.html


# --- نقطة نهاية API لطلب رمز OTP (باستخدام JSON) ---
@auth_bp.route('/request-otp', methods=['POST'])
def request_otp_api():
    data = request.get_json()
    if not data or 'phone_number' not in data:
        return jsonify({'success': False, 'message': 'بيانات غير صالحة: رقم الموبايل مفقود.'}), 400
    
    phone_number = data.get('phone_number')

    user = User.query.filter_by(phone_number=phone_number).first()
    if not user:
        # للمزيد من الأمان، لا تخبر المهاجم ما إذا كان الرقم موجودًا أم لا.
        # يمكنك إرجاع نجاح وهمي أو رسالة عامة جدًا.
        # حاليًا، سأوضح السيناريو المباشر.
        return jsonify({'success': False, 'message': 'لم يتم العثور على مستخدم بهذا الرقم.'}), 404 

    generated_otp = user.generate_otp() # يولد ويخزن الـ OTP وتاريخ انتهاء صلاحيته
    db.session.commit()

    try:
        # TODO: قم بدمج خدمة SMS هنا لإرسال الـ OTP إلى user.phone_number
        # مثال: send_actual_sms(user.phone_number, f"رمز تأكيد اختبرني هو: {generated_otp}")
        print(f"DEBUG: OTP for {user.phone_number} is {generated_otp}") # للاختبار فقط، احذفها في الإنتاج!
        
        return jsonify({'success': True, 'message': 'تم إرسال رمز التأكيد إلى رقم موبايلك. تحقق من رسائلك خلال 10 دقائق.'}), 200
    except Exception as e:
        print(f"ERROR - Failed to send SMS (simulation): {e}") # سجل الخطأ بشكل جيد
        # لا تمسح الـ OTP إذا فشل الإرسال، دع المستخدم يحاول مرة أخرى أو إذا وصل بطريقة أخرى
        return jsonify({'success': False, 'message': 'حدث خطأ أثناء محاولة إرسال الرمز. يرجى المحاولة مرة أخرى لاحقًا.'}), 500


# --- نقطة نهاية API للتحقق من رمز OTP (باستخدام JSON) ---
@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp_api():
    data = request.get_json()
    if not data or 'phone_number' not in data or 'otp_code' not in data:
        return jsonify({'success': False, 'message': 'بيانات غير صالحة: رقم الموبايل أو رمز التأكيد مفقود.'}), 400

    phone_number = data.get('phone_number')
    provided_otp = data.get('otp_code')

    user = User.query.filter_by(phone_number=phone_number).first()
    if not user:
        return jsonify({'success': False, 'message': 'بيانات المستخدم غير صالحة.'}), 404

    if user.is_otp_valid(provided_otp):
        # تم التحقق بنجاح. لا تمسح الـ OTP الآن. سنحتاجه كإثبات
        # في الخطوة التالية (إعادة تعيين كلمة المرور).
        # يمكننا تعيين علامة في الجلسة لتتبع هذا.
        session[f'otp_verified_for_{phone_number}'] = True # علامة أن هذا الرقم تم التحقق من OTP له
        session[f'otp_used_for_reset_{phone_number}'] = provided_otp # تخزين الـ OTP المستخدم (اختياري)
        
        return jsonify({'success': True, 'message': 'تم التحقق من الرمز بنجاح. يمكنك الآن إعادة تعيين كلمة المرور.'}), 200
    else:
        # مسح أي علامة تحقق سابقة إذا فشل التحقق الحالي
        session.pop(f'otp_verified_for_{phone_number}', None)
        session.pop(f'otp_used_for_reset_{phone_number}', None)
        return jsonify({'success': False, 'message': 'رمز التأكيد غير صحيح أو انتهت صلاحيته. حاول مرة أخرى أو اطلب رمزًا جديدًا.'}), 400


# --- نقطة نهاية API لإعادة تعيين كلمة المرور (باستخدام JSON) ---
@auth_bp.route('/reset-password', methods=['POST'])
def reset_password_api():
    data = request.get_json()
    if not data or 'phone_number' not in data or 'new_password' not in data:
        return jsonify({'success': False, 'message': 'بيانات غير صالحة: معلومات إعادة التعيين مفقودة.'}), 400

    phone_number = data.get('phone_number')
    new_password = data.get('new_password')

    if len(new_password) < 6: # أو أي شروط أخرى لكلمة المرور
        return jsonify({'success': False, 'message': 'كلمة المرور يجب أن تكون 6 أحرف على الأقل.'}), 400

    # تحقق من أن المستخدم مر بمرحلة التحقق من الـ OTP بنجاح لهذه الجلسة
    if not session.get(f'otp_verified_for_{phone_number}'):
        return jsonify({'success': False, 'message': 'الوصول غير مصرح به. يرجى التحقق من رمز OTP أولاً.'}), 403

    user = User.query.filter_by(phone_number=phone_number).first()
    if not user:
        # هذه الحالة لا يفترض أن تحدث إذا تم التحقق من otp_verified_for_phone بشكل صحيح
        session.pop(f'otp_verified_for_{phone_number}', None) # تنظيف الجلسة
        session.pop(f'otp_used_for_reset_{phone_number}', None)
        return jsonify({'success': False, 'message': 'خطأ في النظام: لم يتم العثور على المستخدم بعد التحقق.'}), 500
    
    # (اختياري) يمكنك التحقق مرة أخرى من الـ OTP المخزن في الجلسة إذا أردت
    # stored_otp_for_reset = session.get(f'otp_used_for_reset_{phone_number}')
    # if not user.is_otp_valid(stored_otp_for_reset): # افترض أن الـ OTP في قاعدة البيانات لم يتم مسحه بعد
    #     session.pop(f'otp_verified_for_{phone_number}', None)
    #     session.pop(f'otp_used_for_reset_{phone_number}', None)
    #     return jsonify({'success': False, 'message': 'جلسة التحقق من الرمز انتهت. يرجى المحاولة مرة أخرى.'}), 403


    user.set_password(new_password) # يتم التشفير داخل هذه الدالة
    user.clear_otp() # الآن قم بمسح الـ OTP من قاعدة البيانات بعد تغيير كلمة المرور
    db.session.commit()

    # قم بإزالة علامات الجلسة بعد نجاح العملية
    session.pop(f'otp_verified_for_{phone_number}', None)
    session.pop(f'otp_used_for_reset_{phone_number}', None)

    flash('تم إعادة تعيين كلمة المرور بنجاح. يمكنك الآن تسجيل الدخول.', 'success') # لإظهار رسالة إذا عاد لصفحة login HTML
    return jsonify({'success': True, 'message': 'تم إعادة تعيين كلمة المرور بنجاح. يمكنك الآن تسجيل الدخول بكلمة المرور الجديدة.'}), 200


# --- مسار تسجيل الخروج ---
@auth_bp.route('/logout')
def logout():
    # امسح أي علامات تحقق من OTP خاصة بالجلسة إذا كانت موجودة (للتنظيف)
    for key in list(session.keys()):
        if key.startswith('otp_verified_for_') or key.startswith('otp_used_for_reset_'):
            session.pop(key, None)
            
    session.pop('user_id', None)
    session.pop('phone_number', None)
    # أو ببساطة:
    # session.clear() # سيمسح كل شيء في الجلسة
    
    g.user = None # تأكد من أن المستخدم الحالي لم يعد معرفًا في سياق g
    flash('تم تسجيل خروجك بنجاح.', 'info')
    return redirect(url_for('auth.login'))