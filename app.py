# app.py
import os
from datetime import datetime 
import re # لاستخدامه في التحقق من صحة الإيميل ورقم الهاتف
from flask import Flask, render_template, request, redirect, url_for, session, flash 
from werkzeug.security import generate_password_hash, check_password_hash # لتشفير والتحقق من كلمات المرور
import mysql.connector # مكتبة الاتصال بـ MySQL
from mysql.connector import Error # لالتقاط أخطاء MySQL
from dotenv import load_dotenv # لتحميل المتغيرات من ملف .env

# --- 1. تحميل متغيرات البيئة من ملف .env ---
load_dotenv() 

# --- 2. إعداد تطبيق Flask ---
app = Flask(__name__) 
app.secret_key = os.getenv('SECRET_KEY') 
if not app.secret_key:
    print("!!! تحذير خطير جداً: SECRET_KEY غير مُعيَّن في ملف .env! !!!")
    print("!!! لضمان أمان التطبيق، يجب تعيين مفتاح سري قوي وفريد فورًا. !!!")
    print("!!! سيتم استخدام مفتاح افتراضي ضعيف للغاية للتطوير فقط. لا تستخدم هذا في بيئة إنتاج! !!!")
    app.secret_key = "SUPER_INSECURE_DEFAULT_SECRET_KEY_CHANGE_THIS_IMMEDIATELY_12345_XYZ" 

# --- 3. إعدادات الاتصال بقاعدة البيانات ---
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '') # كلمة مرور فارغة كافتراضي (غير آمن) إذا لم توجد
DB_NAME = os.getenv('DB_NAME', 'ektbariny_db')

# --- 4. دالة الاتصال بقاعدة البيانات ---
def get_db_connection():
    # print("--- [DB_CONN] محاولة الاتصال بقاعدة البيانات... ---") # للتصحيح
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME, charset='utf8mb4' 
        )
        # print(f"--- [DB_CONN] تم الاتصال بنجاح بـ: {DB_NAME}@{DB_HOST} ---") # للتصحيح
        return conn
    except Error as e:
        print(f"!!! [DB_CONN_ERROR] فشل الاتصال بقاعدة بيانات MySQL ({DB_NAME}@{DB_HOST}): {e} !!!")
        # flash("نعتذر، لا يمكن الاتصال بقاعدة البيانات حاليًا. يرجى المحاولة لاحقًا.", "danger") # هذا سيعمل فقط داخل سياق طلب Flask
        return None

# --- 5. دالة إنشاء الجداول ---
def create_tables():
    conn = None
    cursor = None 
    print("--- [DB_SETUP] بدء عملية التحقق من/إنشاء جداول قاعدة البيانات... ---")
    all_tables_processed_ok = True 
    try:
        conn = get_db_connection() 
        if conn is None: 
            print("!!! [DB_SETUP] إلغاء: فشل الاتصال الأولي بقاعدة البيانات عند محاولة إنشاء الجداول. !!!")
            all_tables_processed_ok = False
            return # لا يمكن المتابعة
        
        cursor = conn.cursor()
        
        users_table_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role ENUM('student', 'teacher') NOT NULL,
            first_name VARCHAR(50) NULL, 
            last_name VARCHAR(50) NULL,
            phone_number VARCHAR(20) NULL,  -- العمود الجديد لرقم الهاتف
            country VARCHAR(100) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(users_table_sql)
        print("    - [DB_SETUP] جدول 'users' تم التحقق منه/إنشاؤه (متضمنًا phone_number).")

        quizzes_table_sql = """
        CREATE TABLE IF NOT EXISTS quizzes (
            id INT AUTO_INCREMENT PRIMARY KEY, teacher_id INT NOT NULL, title VARCHAR(255) NOT NULL, description TEXT NULL,
            time_limit_minutes INT DEFAULT 60, shareable_link_id VARCHAR(36) UNIQUE NOT NULL, 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(quizzes_table_sql)
        print("    - [DB_SETUP] جدول 'quizzes' تم التحقق منه/إنشاؤه.")

        questions_table_sql = """
        CREATE TABLE IF NOT EXISTS questions (
            id INT AUTO_INCREMENT PRIMARY KEY, quiz_id INT NOT NULL, question_text TEXT NOT NULL,
            question_type ENUM('mc', 'essay') NOT NULL, image_filename VARCHAR(255) NULL,
            display_order INT DEFAULT 0, FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(questions_table_sql)
        print("    - [DB_SETUP] جدول 'questions' تم التحقق منه/إنشاؤه.")

        choices_table_sql = """
        CREATE TABLE IF NOT EXISTS choices (
            id INT AUTO_INCREMENT PRIMARY KEY, question_id INT NOT NULL, choice_text TEXT NOT NULL,
            is_correct BOOLEAN DEFAULT FALSE, FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(choices_table_sql)
        print("    - [DB_SETUP] جدول 'choices' تم التحقق منه/إنشاؤه.")

        quiz_attempts_table_sql = """
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INT AUTO_INCREMENT PRIMARY KEY, student_id INT NOT NULL, quiz_id INT NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, end_time TIMESTAMP NULL, score INT DEFAULT 0,
            time_taken_seconds INT NULL, submitted_at TIMESTAMP NULL, is_completed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(quiz_attempts_table_sql)
        print("    - [DB_SETUP] جدول 'quiz_attempts' تم التحقق منه/إنشاؤه.")

        student_answers_table_sql = """
        CREATE TABLE IF NOT EXISTS student_answers (
            id INT AUTO_INCREMENT PRIMARY KEY, attempt_id INT NOT NULL, question_id INT NOT NULL,
            selected_choice_id INT NULL, essay_answer_text TEXT NULL, is_mc_correct BOOLEAN NULL,
            FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
            FOREIGN KEY (selected_choice_id) REFERENCES choices(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(student_answers_table_sql)
        print("    - [DB_SETUP] جدول 'student_answers' تم التحقق منه/إنشاؤه.")
        
        conn.commit() 
        print("--- [DB_SETUP] اكتملت عملية التحقق من/إنشاء جميع جداول قاعدة البيانات بنجاح. ---")

    except Error as db_setup_error: 
        print(f"!!! [DB_SETUP] خطأ فادح أثناء عملية إنشاء الجداول: {db_setup_error} !!!")
        all_tables_processed_ok = False
        if conn: conn.rollback() 
    except Exception as e_general_create:
        print(f"!!! [DB_SETUP] خطأ عام غير متوقع أثناء إنشاء الجداول: {e_general_create} !!!")
        all_tables_processed_ok = False
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
    
    if not all_tables_processed_ok:
        print("!!! [DB_SETUP] تحذير هام: لم يتم التحقق من/إنشاء جميع الجداول بنجاح بسبب خطأ. يرجى مراجعة رسائل الخطأ أعلاه. !!!")


@app.context_processor
def inject_global_vars():
    return {'now': datetime.utcnow(), 'is_minimal_layout': False}

@app.route('/')
def home():
    return render_template('index.html') 

@app.route('/choose_signup_role', methods=['GET', 'POST'])
def choose_signup_role():
    if request.method == 'POST':
        role_selected = request.form.get('role')
        if role_selected not in ['student', 'teacher']:
            flash("يرجى تحديد دورك (طالب أو معلم) بشكل صحيح للمتابعة.", "warning")
            return render_template('auth/choose_role_signup.html', is_minimal_layout=True)
        
        session['signup_attempt_role'] = role_selected 
        role_display_name = "طالب" if role_selected == 'student' else "معلم"
        flash(f"خطوة رائعة! أنت على وشك إنشاء حساب كـ '{role_display_name}'. يرجى الآن إكمال بياناتك.", "info")
        return redirect(url_for('signup_actual_form_page'))
    
    return render_template('auth/choose_role_signup.html', is_minimal_layout=True)

def is_valid_email_format(email_to_check):
    # تحقق بسيط جدًا لصيغة الإيميل
    if email_to_check and re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email_to_check):
        return True
    return False

def is_valid_phone_format_simple(phone_number_to_check):
    # تحقق بسيط: أرقام فقط، بين 7 و 15 رقمًا.
    # يمكنك تعديل هذا النمط ليكون أكثر تحديدًا لصيغ أرقام الهواتف في بلدك.
    if phone_number_to_check and phone_number_to_check.isdigit() and 7 <= len(phone_number_to_check) <= 15:
        return True
    # إذا كان فارغًا، نعتبره صالحًا لأنه حقل اختياري
    if not phone_number_to_check:
        return True
    return False

@app.route('/signup/form', methods=['GET', 'POST']) 
def signup_actual_form_page():
    role_for_form_being_created = session.get('signup_attempt_role') 
    if not role_for_form_being_created:
        flash("حدث خطأ أو انتهت جلستك. يرجى اختيار دورك مجددًا.", "warning")
        return redirect(url_for('choose_signup_role'))

    form_data_to_repopulate = {} # لإعادة ملء النموذج عند الخطأ

    if request.method == 'POST':
        # استخلاص البيانات مع .strip() لإزالة المسافات الزائدة
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone_number = request.form.get('phone_number', '').strip() # استخلاص رقم الهاتف
        password = request.form.get('password', '') # لا نستخدم strip لكلمة المرور
        confirm_password = request.form.get('confirm_password', '')
        country = request.form.get('country', '') 
        agree_terms = request.form.get('agree_terms') # سيكون 'on' أو None

        form_data_to_repopulate = request.form # لحفظ البيانات لإعادة ملء النموذج

        validation_errors_list = [] 
        if not first_name: validation_errors_list.append("الاسم الأول مطلوب.")
        if not last_name: validation_errors_list.append("اسم العائلة مطلوب.")
        if not email: 
            validation_errors_list.append("البريد الإلكتروني مطلوب.")
        elif not is_valid_email_format(email):
             validation_errors_list.append("صيغة البريد الإلكتروني المدخلة غير صحيحة.")
        
        if phone_number and not is_valid_phone_format_simple(phone_number): 
            validation_errors_list.append("صيغة رقم الهاتف غير صحيحة (يجب أن يكون أرقام فقط، من 7 إلى 15 رقمًا).")
        
        if not password: 
            validation_errors_list.append("كلمة المرور مطلوبة.")
        elif len(password) < 8: 
            validation_errors_list.append("كلمة المرور يجب أن تكون 8 أحرف على الأقل.")
        if password != confirm_password:
            validation_errors_list.append("كلمتا المرور غير متطابقتين.")
        if not agree_terms: 
            validation_errors_list.append("يجب الموافقة على شروط الخدمة وسياسة الخصوصية.")

        if validation_errors_list: 
            for err_msg in validation_errors_list:
                flash(err_msg, "danger") 
            return render_template('auth/signup_actual_form.html', role=role_for_form_being_created, is_minimal_layout=True, form_data=form_data_to_repopulate)

        db_connection_obj = None 
        db_cursor_obj = None
        try:
            db_connection_obj = get_db_connection()
            if db_connection_obj is None: 
                flash("نعتذر، مشكلة في الاتصال بخادم البيانات (CODE: SIGNUP_DB_CONN_FAIL). يرجى المحاولة مرة أخرى.", "danger")
                return render_template('auth/signup_actual_form.html', role=role_for_form_being_created, is_minimal_layout=True, form_data=form_data_to_repopulate)
            
            db_cursor_obj = db_connection_obj.cursor(dictionary=True) 
            
            db_cursor_obj.execute("SELECT id FROM users WHERE email = %s", (email,))
            if db_cursor_obj.fetchone(): 
                flash(f"البريد الإلكتروني '{email}' مُسجل لدينا بالفعل. إذا كان هذا حسابك، يمكنك محاولة تسجيل الدخول.", "warning")
                return render_template('auth/signup_actual_form.html', role=role_for_form_being_created, is_minimal_layout=True, form_data=form_data_to_repopulate)

            hashed_password_to_store = generate_password_hash(password)
            generated_username = f"{first_name} {last_name}" 

            # تأكد أن أسماء الأعمدة في INSERT تتطابق مع تعريف الجدول في create_tables
            sql_insert_query = """
                INSERT INTO users 
                    (username, email, password_hash, role, first_name, last_name, phone_number, country) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            sql_user_data = (
                generated_username, email, hashed_password_to_store, role_for_form_being_created, 
                first_name, last_name, 
                phone_number if phone_number else None,  # إرسال None إذا كان phone_number فارغًا
                country if country else None             # إرسال None إذا كانت الدولة فارغة
            )
            db_cursor_obj.execute(sql_insert_query, sql_user_data) 
            db_connection_obj.commit() 

            session.pop('signup_attempt_role', None) 
            role_success_display_name = "طالب" if role_for_form_being_created == 'student' else "معلم"
            flash(f"تهانينا يا {first_name}! تم إنشاء حسابك بنجاح كـ '{role_success_display_name}'. يمكنك الآن تسجيل الدخول.", "success")
            return redirect(url_for('login_page')) 

        except Error as db_error_during_insert: 
            print(f"!!! خطأ MySQL عند محاولة إدخال مستخدم جديد ({email}): {db_error_during_insert} !!!")
            # تفاصيل الخطأ هذه لا يجب عرضها للمستخدم مباشرة في بيئة الإنتاج
            flash(f"نعتذر، حدث خطأ غير متوقع أثناء محاولة حفظ بياناتك (رمز: DB_INSERT_ERR). تفاصيل فنية: {db_error_during_insert}", "danger")
            if db_connection_obj: db_connection_obj.rollback() 
        except Exception as general_signup_error: 
            print(f"!!! خطأ عام غير متوقع في signup_actual_form_page (POST): {general_signup_error} !!!")
            flash("نعتذر، حدث خطأ عام وغير متوقع أثناء معالجة طلبك. يرجى المحاولة مرة أخرى.", "danger")
        finally:
            if db_cursor_obj: db_cursor_obj.close()
            if db_connection_obj and db_connection_obj.is_connected(): db_connection_obj.close()
        
        # إذا وصلنا هنا، فهذا يعني حدوث خطأ ولم يتم التوجيه
        return render_template('auth/signup_actual_form.html', role=role_for_form_being_created, is_minimal_layout=True, form_data=form_data_to_repopulate)

    # GET request: عرض النموذج مع البيانات السابقة إذا كانت موجودة في request.form (عادة من محاولة POST فاشلة)
    # أو قاموس فارغ إذا كان طلب GET نقيًا.
    return render_template('auth/signup_actual_form.html', role=role_for_form_being_created, is_minimal_layout=True, form_data=request.form if request.form else {})

@app.route('/login', methods=['GET', 'POST']) 
def login_page(): 
    form_data_to_repopulate = {} # لإعادة ملء النموذج عند الخطأ
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        form_data_to_repopulate = request.form 

        validation_errors_list = []
        if not email: 
            validation_errors_list.append("البريد الإلكتروني مطلوب.")
        elif not is_valid_email_format(email): 
            validation_errors_list.append("صيغة البريد الإلكتروني المدخلة غير صحيحة.")
        if not password: 
            validation_errors_list.append("كلمة المرور مطلوبة.")
        
        if validation_errors_list:
            for err_msg in validation_errors_list: 
                flash(err_msg, "danger")
            return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_to_repopulate)

        db_connection_obj = None
        db_cursor_obj = None
        try:
            db_connection_obj = get_db_connection()
            if db_connection_obj is None:
                flash("نعتذر، مشكلة في الاتصال بالخادم حاليًا (CODE: LOGIN_DB_CONN_FAIL). يرجى المحاولة مرة أخرى.", "danger")
                return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_to_repopulate)

            db_cursor_obj = db_connection_obj.cursor(dictionary=True)
            # جلب الأعمدة المطلوبة للجلسة
            db_cursor_obj.execute("SELECT id, username, email, password_hash, role, first_name FROM users WHERE email = %s", (email,))
            user_from_db = db_cursor_obj.fetchone()

            if user_from_db and check_password_hash(user_from_db['password_hash'], password):
                # تسجيل الدخول ناجح
                session.clear() # مسح أي جلسة قديمة لضمان النظافة
                session['user_id'] = user_from_db['id']
                # استخدام الاسم الأول إذا كان متاحًا، وإلا اسم المستخدم العام
                session['username'] = user_from_db.get('first_name') or user_from_db['username'] 
                session['role'] = user_from_db['role']
                session['email'] = user_from_db['email'] 
                session.permanent = True # لتمديد عمر الجلسة (يمكن التحكم بمدتها من إعدادات Flask)
                
                display_name_for_welcome = session['username'] # الاسم الذي سيُعرض في رسالة الترحيب
                flash(f"أهلاً بعودتك يا {display_name_for_welcome}! تم تسجيل دخولك بنجاح.", "success")
                
                # توجيه المستخدم للوحة التحكم المناسبة حسب دوره
                if user_from_db['role'] == 'student':
                    return redirect(url_for('student_dashboard_placeholder'))
                elif user_from_db['role'] == 'teacher':
                    return redirect(url_for('teacher_dashboard_placeholder'))
                else:
                    # حالة غير متوقعة (دور غير معروف)، توجيه للصفحة الرئيسية كإجراء احتياطي
                    return redirect(url_for('home')) 
            else:
                # فشل تسجيل الدخول (إيميل أو كلمة مرور غير صحيحة)
                flash("البريد الإلكتروني أو كلمة المرور التي أدخلتها غير صحيحة. يرجى التحقق منها والمحاولة مرة أخرى.", "danger")
                return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_to_repopulate)

        except Error as db_login_error_detail:
            print(f"!!! خطأ في قاعدة البيانات MySQL أثناء محاولة تسجيل الدخول للمستخدم {email}: {db_login_error_detail} !!!")
            flash(f"حدث خطأ غير متوقع أثناء محاولة تسجيل دخولك (رمز: LOGIN_DB_PROCESS_ERR).", "danger")
        except Exception as generic_login_err_detail:
            print(f"!!! خطأ عام غير متوقع أثناء معالجة نموذج تسجيل الدخول: {generic_login_err_detail} !!!")
            flash("نعتذر، حدث خطأ عام غير متوقع أثناء محاولة تسجيل دخولك.", "danger")
        finally:
            if db_cursor_obj: db_cursor_obj.close()
            if db_connection_obj and db_connection_obj.is_connected(): db_connection_obj.close()
        
        # إذا حدث خطأ أثناء معالجة قاعدة البيانات ولم يتم التوجيه
        return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_to_repopulate)

    # GET request: عرض صفحة نموذج تسجيل الدخول (مع بيانات سابقة إذا فشل POST)
    return render_template('auth/login_form.html', is_minimal_layout=True, form_data=request.form if request.form else {})

# --- مسارات مؤقتة للوحات التحكم ---
@app.route('/student_dashboard') 
def student_dashboard_placeholder():
    if 'user_id' not in session or session.get('role') != 'student':
        flash("يرجى تسجيل الدخول كطالب أولاً لعرض لوحة التحكم.", "warning")
        return redirect(url_for('login_page')) 
    username = session.get('username', 'أيها الطالب')
    return f"<h1>مرحباً بك في لوحة تحكم الطالب، {username}! (قيد الإنشاء)</h1><p><a href=\"{url_for('home')}\">الرئيسية</a> | <a href=\"{url_for('logout')}\">تسجيل الخروج</a></p>"

@app.route('/teacher_dashboard') 
def teacher_dashboard_placeholder():
    if 'user_id' not in session or session.get('role') != 'teacher':
        flash("يرجى تسجيل الدخول كمعلم أولاً لعرض لوحة التحكم.", "warning")
        return redirect(url_for('login_page'))
    username = session.get('username', 'أيها المعلم')
    return f"<h1>مرحباً بك في لوحة تحكم المعلم، {username}! (قيد الإنشاء)</h1><p><a href=\"{url_for('home')}\">الرئيسية</a> | <a href=\"{url_for('logout')}\">تسجيل الخروج</a></p>"

# --- مسار تسجيل الخروج ---
@app.route('/logout')
def logout():
    session.clear() # مسح جميع بيانات الجلسة للمستخدم الحالي
    flash("لقد قمت بتسجيل الخروج بنجاح من حسابك.", "info")
    return redirect(url_for('home')) # توجيه المستخدم للصفحة الرئيسية


# --- تشغيل التطبيق ---
if __name__ == '__main__':
    try:
        print("--- [STARTUP] بدء تهيئة تطبيق اختبرني ---")
        create_tables() 
        print("--- [STARTUP] تم التحقق من الجداول. بدء تشغيل خادم تطوير Flask ---")
        # تم تغيير المنفذ إلى 5001 كإجراء وقائي إذا كان 5000 مستخدمًا
        app.run(debug=True, host='0.0.0.0', port=5001) 
    except SystemExit as se:
        print(f"!!! تم إنهاء البرنامج بشكل غير متوقع مع SystemExit code: {se.code} !!!")
        if hasattr(se, 'code') and str(se.code) == '3' and os.name == 'nt': 
             print("--- هذا الخطأ (SystemExit: 3) في نظام Windows قد يعني أن المنفذ المحدد (مثل 5001) مستخدم بالفعل. ---")
             print("--- حاول تغيير رقم المنفذ في السطر app.run(...) أو أغلق البرنامج الآخر الذي يستخدم هذا المنفذ. ---")
             print("--- يمكنك التحقق من المنافذ المستخدمة عبر 'netstat -ano | findstr :رقم_المنفذ' في موجه الأوامر. ---")
        elif hasattr(se, 'code'):
            print(f"--- كود الخروج SystemExit: {se.code} ---")
        else:
            print(f"--- SystemExit بدون كود خروج واضح. ---")
    except OSError as oe: 
        print(f"!!! حدث خطأ OSError أثناء بدء تشغيل تطبيق Flask (غالبًا ما يعني أن المنفذ مستخدم بالفعل): {oe} !!!")
        print("--- يرجى محاولة تغيير رقم المنفذ في السطر app.run(...) أو إيقاف العملية الأخرى التي تستخدم المنفذ الحالي. ---")
    except Exception as e_startup:
        print(f"!!! حدث خطأ فادح وعام أثناء محاولة بدء تشغيل تطبيق Flask: {e_startup} !!!")