import os
from datetime import datetime, timedelta # timedelta لـ permanent session
import re # للتحقق من الإيميل والهاتف
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash # لتشفير كلمات المرور
import mysql.connector # لمكتبة MySQL
from mysql.connector import Error # لالتقاط أخطاء MySQL
from dotenv import load_dotenv # لتحميل المتغيرات من ملف .env

# --- 1. تحميل متغيرات البيئة من ملف .env ---
load_dotenv()

# --- 2. إعداد تطبيق Flask ---
app = Flask(__name__)
# المفتاح السري ضروري جداً لأمان الجلسات. يجب أن يكون سلسلة عشوائية قوية.
app.secret_key = os.getenv('SECRET_KEY', "a_very_default_and_insecure_secret_key_123_XYZ_CHANGE_IT") 
# ضبط مدة بقاء الجلسة إذا أردت (مثال: 7 أيام)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)


# --- 3. إعدادات الاتصال بقاعدة البيانات (من ملف .env) ---
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '') # كلمة مرور فارغة كافتراضي (غير آمن للإنتاج)
DB_NAME = os.getenv('DB_NAME', 'ektbariny_db') # اسم قاعدة البيانات الافتراضي

# --- 4. دالة الاتصال بقاعدة البيانات ---
def get_db_connection():
    """إنشاء وإرجاع اتصال بقاعدة بيانات MySQL."""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4' # لضمان دعم اللغة العربية بشكل جيد
        )
        # print(f"--- [DB_CONN_SUCCESS] Connected to: {DB_NAME}@{DB_HOST} ---") # للتصحيح
        return conn
    except Error as e:
        print(f"!!! [DB_CONN_ERROR] MySQL Connection Error to '{DB_NAME}' on '{DB_HOST}': {e} !!!")
        app.logger.error(f"Database Connection Error: {e}") # استخدام مسجل Flask للأخطاء
        return None

# --- 5. دالة إنشاء الجداول ---
# (أكمل تعريفات الجداول الأخرى حسب ما لديك)
def create_tables():
    """إنشاء جداول قاعدة البيانات إذا لم تكن موجودة."""
    conn = None
    cursor = None
    print("--- [DB_SETUP] Checking and/or Creating database tables... ---")
    all_tables_ok = True
    try:
        conn = get_db_connection()
        if conn is None:
            print("!!! [DB_SETUP] ABORTED: Database connection failed, cannot create tables. !!!")
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
            phone_number VARCHAR(20) NULL,
            country VARCHAR(100) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(users_table_sql)
        print("    - [DB_SETUP] 'users' table checked/created.")

        quizzes_table_sql = """
        CREATE TABLE IF NOT EXISTS quizzes (
            id INT AUTO_INCREMENT PRIMARY KEY, teacher_id INT NOT NULL, title VARCHAR(255) NOT NULL, 
            description TEXT NULL, time_limit_minutes INT DEFAULT 60, 
            shareable_link_id VARCHAR(36) UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(quizzes_table_sql); print("    - [DB_SETUP] 'quizzes' table checked/created.")

        questions_table_sql = """
        CREATE TABLE IF NOT EXISTS questions (
            id INT AUTO_INCREMENT PRIMARY KEY, quiz_id INT NOT NULL, question_text TEXT NOT NULL,
            question_type ENUM('mc', 'essay') NOT NULL, image_filename VARCHAR(255) NULL,
            display_order INT DEFAULT 0, 
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(questions_table_sql); print("    - [DB_SETUP] 'questions' table checked/created.")
        
        choices_table_sql = """
        CREATE TABLE IF NOT EXISTS choices (
            id INT AUTO_INCREMENT PRIMARY KEY, question_id INT NOT NULL, choice_text TEXT NOT NULL,
            is_correct BOOLEAN DEFAULT FALSE, 
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(choices_table_sql); print("    - [DB_SETUP] 'choices' table checked/created.")

        quiz_attempts_table_sql = """
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INT AUTO_INCREMENT PRIMARY KEY, student_id INT NOT NULL, quiz_id INT NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, end_time TIMESTAMP NULL, score INT DEFAULT 0,
            time_taken_seconds INT NULL, submitted_at TIMESTAMP NULL, is_completed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(quiz_attempts_table_sql); print("    - [DB_SETUP] 'quiz_attempts' table checked/created.")

        student_answers_table_sql = """
        CREATE TABLE IF NOT EXISTS student_answers (
            id INT AUTO_INCREMENT PRIMARY KEY, attempt_id INT NOT NULL, question_id INT NOT NULL,
            selected_choice_id INT NULL, essay_answer_text TEXT NULL, is_mc_correct BOOLEAN NULL,
            FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
            FOREIGN KEY (selected_choice_id) REFERENCES choices(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        cursor.execute(student_answers_table_sql); print("    - [DB_SETUP] 'student_answers' table checked/created.")
        
        conn.commit() 
        print("--- [DB_SETUP] Database tables check/creation process completed. ---")

    except Error as db_setup_error: 
        print(f"!!! [DB_SETUP] FATAL ERROR during table creation: {db_setup_error} !!!")
        all_tables_ok = False
        if conn: conn.rollback() 
        app.logger.error(f"Database Setup Error: {db_setup_error}")
    except Exception as e_general_create:
        print(f"!!! [DB_SETUP] UNEXPECTED GENERAL ERROR during table creation: {e_general_create} !!!")
        all_tables_ok = False
        app.logger.error(f"General Table Creation Error: {e_general_create}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
    
    if not all_tables_ok:
        print("!!! [DB_SETUP] WARNING: Not all tables were successfully checked/created. Please review logs. !!!")


# --- دوال مساعدة ووظائف عامة ---
@app.context_processor
def inject_global_vars():
    # متغير `now` يُستخدم في الفوتر لعرض السنة الحالية.
    # `is_minimal_layout` للتحكم في عرض شريط التنقل في layout.html.
    return {'now': datetime.utcnow(), 'is_minimal_layout': False}

def is_valid_email_format(email_to_check):
    """تحقق بسيط من صحة صيغة البريد الإلكتروني."""
    if email_to_check and re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email_to_check):
        return True
    return False

def is_valid_phone_format_simple(phone_number_to_check):
    """تحقق بسيط من صيغة رقم الهاتف (اختياري)."""
    if not phone_number_to_check: # إذا كان فارغًا، فهو صالح (لأنه اختياري)
        return True
    # أرقام فقط، بين 7 و 15 رقمًا
    if phone_number_to_check and phone_number_to_check.isdigit() and 7 <= len(phone_number_to_check) <= 15:
        return True
    return False

# --- مسارات التطبيق (Routes) ---
@app.route('/')
def home():
    # سيعرض الصفحة باللغة الافتراضية المحددة في layout.html و JS
    return render_template('index.html') 

@app.route('/choose_signup_role', methods=['GET', 'POST'])
def choose_signup_role():
    if request.method == 'POST':
        role_selected = request.form.get('role')
        if role_selected not in ['student', 'teacher']:
            flash("Please select your role (Student or Teacher).", "warning") # رسالة بالإنجليزية
            return render_template('auth/choose_role_signup.html', is_minimal_layout=True)
        
        session['signup_attempt_role'] = role_selected 
        # Flash message يمكن أن يبقى بالإنجليزية أو أن تعتمد على JS لترجمة الفئة
        flash(f"Great! You're about to create an account as a '{role_selected.capitalize()}'. Please complete your details.", "info")
        return redirect(url_for('signup_actual_form_page'))
    
    return render_template('auth/choose_role_signup.html', is_minimal_layout=True)


@app.route('/signup/form', methods=['GET', 'POST']) 
def signup_actual_form_page():
    role_for_form = session.get('signup_attempt_role') 
    if not role_for_form:
        flash("Session error or role not selected. Please choose your role again.", "warning") # EN
        return redirect(url_for('choose_signup_role'))

    form_data_to_repopulate = {} # لإعادة ملء النموذج عند الخطأ

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone_number = request.form.get('phone_number', '').strip()
        password = request.form.get('password', '') # لا نستخدم strip لكلمة المرور
        confirm_password = request.form.get('confirm_password', '')
        country = request.form.get('country', '').strip() # التأكد من أن الدولة إلزامية
        agree_terms = request.form.get('agree_terms')
        form_data_to_repopulate = request.form

        validation_errors_list = [] 
        if not first_name: validation_errors_list.append("First name is required.")
        if not last_name: validation_errors_list.append("Last name is required.")
        if not email: validation_errors_list.append("Email is required.")
        elif not is_valid_email_format(email): validation_errors_list.append("Invalid email format.")
        if phone_number and not is_valid_phone_format_simple(phone_number): validation_errors_list.append("Invalid phone number format (7-15 digits).")
        if not password: validation_errors_list.append("Password is required.")
        elif len(password) < 8: validation_errors_list.append("Password must be at least 8 characters.")
        if password != confirm_password: validation_errors_list.append("Passwords do not match.")
        if not country: validation_errors_list.append("Country selection is required.") # تحقق من الدولة
        if not agree_terms: validation_errors_list.append("You must agree to the Terms of Service and Privacy Policy.")

        if validation_errors_list: 
            for err_msg in validation_errors_list: flash(err_msg, "danger") 
            return render_template('auth/signup_actual_form.html', role=role_for_form, is_minimal_layout=True, form_data=form_data_to_repopulate)

        db_connection_obj = None; db_cursor_obj = None
        try:
            db_connection_obj = get_db_connection()
            if db_connection_obj is None: 
                flash("Database connection error. Please try again. (CODE: SIGNUP_DB_CONN_FAIL)", "danger")
                return render_template('auth/signup_actual_form.html', role=role_for_form, is_minimal_layout=True, form_data=form_data_to_repopulate)
            
            db_cursor_obj = db_connection_obj.cursor(dictionary=True) 
            db_cursor_obj.execute("SELECT id FROM users WHERE email = %s", (email,))
            if db_cursor_obj.fetchone(): 
                flash(f"The email address '{email}' is already registered. If this is your account, please try logging in.", "warning")
                return render_template('auth/signup_actual_form.html', role=role_for_form, is_minimal_layout=True, form_data=form_data_to_repopulate)

            hashed_password_to_store = generate_password_hash(password)
            generated_username = f"{first_name} {last_name}" # اسم مستخدم بسيط

            sql_insert_query = "INSERT INTO users (username, email, password_hash, role, first_name, last_name, phone_number, country) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            sql_user_data = (generated_username, email, hashed_password_to_store, role_for_form, first_name, last_name, phone_number if phone_number else None, country) # الدولة الآن إلزامية
            
            db_cursor_obj.execute(sql_insert_query, sql_user_data) 
            db_connection_obj.commit() 

            session.pop('signup_attempt_role', None) 
            flash(f"Congratulations {first_name}! Your account as a '{role_for_form.capitalize()}' has been successfully created. You can now log in.", "success")
            return redirect(url_for('login_page')) 

        except Error as db_error_during_insert: 
            print(f"!!! MySQL Error during new user insertion ({email}): {db_error_during_insert} !!!")
            app.logger.error(f"DB Insert Error for {email}: {db_error_during_insert}")
            flash("A database error occurred while saving your data. (CODE: DB_INSERT_ERR)", "danger")
            if db_connection_obj: db_connection_obj.rollback() 
        except Exception as general_signup_error: 
            print(f"!!! Unexpected General Error in signup_actual_form_page (POST): {general_signup_error} !!!")
            app.logger.error(f"General Signup Error: {general_signup_error}", exc_info=True) # Log full traceback
            flash("An unexpected general error occurred while processing your request. Please try again.", "danger")
            if db_connection_obj: db_connection_obj.rollback() # Attempt rollback if connection exists
        finally:
            if db_cursor_obj: db_cursor_obj.close()
            if db_connection_obj and db_connection_obj.is_connected(): db_connection_obj.close()
        
        return render_template('auth/signup_actual_form.html', role=role_for_form, is_minimal_layout=True, form_data=form_data_to_repopulate)

    # GET request:
    return render_template('auth/signup_actual_form.html', role=role_for_form, is_minimal_layout=True, form_data={})


@app.route('/login', methods=['GET', 'POST']) 
def login_page(): 
    form_data_to_repopulate = {}
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        form_data_to_repopulate = request.form 

        validation_errors_list = []
        if not email or not is_valid_email_format(email): validation_errors_list.append("Valid email is required.")
        if not password: validation_errors_list.append("Password is required.")
        
        if validation_errors_list:
            for err_msg in validation_errors_list: flash(err_msg, "danger")
            return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_to_repopulate)

        db_connection_obj = None; db_cursor_obj = None
        try:
            db_connection_obj = get_db_connection()
            if db_connection_obj is None:
                flash("Database connection error. Please try again later. (CODE: LOGIN_DB_CONN_FAIL)", "danger")
                return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_to_repopulate)

            db_cursor_obj = db_connection_obj.cursor(dictionary=True)
            db_cursor_obj.execute("SELECT id, username, email, password_hash, role, first_name FROM users WHERE email = %s", (email,))
            user_from_db = db_cursor_obj.fetchone()

            if user_from_db and check_password_hash(user_from_db['password_hash'], password):
                session.clear() 
                session['user_id'] = user_from_db['id']
                session['username'] = user_from_db.get('first_name') or user_from_db['username'] 
                session['role'] = user_from_db['role']
                session['email'] = user_from_db['email'] 
                session.permanent = True 
                
                flash(f"Welcome back, {session['username']}! You are now logged in.", "success")
                if user_from_db['role'] == 'student':
                    return redirect(url_for('student_dashboard_placeholder'))
                elif user_from_db['role'] == 'teacher':
                    return redirect(url_for('teacher_dashboard_placeholder'))
                else:
                    return redirect(url_for('home')) 
            else:
                flash("Invalid email or password. Please check and try again.", "danger")
                return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_to_repopulate)

        except Error as db_login_error_detail:
            print(f"!!! DB Error during login for user {email}: {db_login_error_detail} !!!")
            app.logger.error(f"DB Login Error for {email}: {db_login_error_detail}")
            flash("A database error occurred during login. (CODE: LOGIN_DB_PROCESS_ERR)", "danger")
        except Exception as generic_login_err_detail:
            print(f"!!! Unexpected General Error during login processing: {generic_login_err_detail} !!!")
            app.logger.error(f"General Login Error: {generic_login_err_detail}", exc_info=True)
            flash("An unexpected general error occurred during login. Please try again.", "danger")
        finally:
            if db_cursor_obj: db_cursor_obj.close()
            if db_connection_obj and db_connection_obj.is_connected(): db_connection_obj.close()
        
        return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_to_repopulate)

    # GET request:
    return render_template('auth/login_form.html', is_minimal_layout=True, form_data={})


@app.route('/logout')
def logout():
    session.clear() 
    flash("You have been successfully logged out.", "info") # EN
    return redirect(url_for('home'))


# --- مسارات لوحات التحكم المؤقتة (ستُستبدل لاحقًا) ---
@app.route('/student_dashboard') 
def student_dashboard_placeholder():
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Please log in as a student to view the dashboard.", "warning") # EN
        return redirect(url_for('login_page')) 
    username = session.get('username', 'Student')
    return f"<h1><span class='lang-en'>Welcome to Student Dashboard, {username}! (Under Construction)</span><span class='lang-ar' style='display:none;'>مرحباً بك في لوحة تحكم الطالب، {username}! (قيد الإنشاء)</span></h1><p><a href=\"{url_for('home')}\">Home</a> | <a href=\"{url_for('logout')}\">Logout</a></p>"

@app.route('/teacher_dashboard') 
def teacher_dashboard_placeholder():
    if 'user_id' not in session or session.get('role') != 'teacher':
        flash("Please log in as a teacher to view the dashboard.", "warning") # EN
        return redirect(url_for('login_page'))
    username = session.get('username', 'Teacher')
    return f"<h1><span class='lang-en'>Welcome to Teacher Dashboard, {username}! (Under Construction)</span><span class='lang-ar' style='display:none;'>مرحباً بك في لوحة تحكم المعلم، {username}! (قيد الإنشاء)</span></h1><p><a href=\"{url_for('home')}\">Home</a> | <a href=\"{url_for('logout')}\">Logout</a></p>"


# --- تشغيل التطبيق ---
if __name__ == '__main__':
    # إعداد تسجيل الأخطاء بشكل أفضل (اختياري ولكن موصى به)
    if not app.debug: # لا يُفعل في وضع التصحيح لأنه يعرض الأخطاء في المتصفح
        import logging
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler('error.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.ERROR) # تسجيل الأخطاء فقط وما هو أخطر
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.ERROR)
        app.logger.info('Ektbariny App Startup in Production Mode')

    try:
        print("--- [STARTUP] Initializing Ektbariny App ---")
        if os.getenv('CREATE_TABLES_ON_STARTUP', 'True').lower() == 'true':
             create_tables()
        else:
            print("--- [DB_SETUP] Skipping table creation based on CREATE_TABLES_ON_STARTUP in .env ---")
        
        flask_debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() == 'true' # الافتراضي True للتطوير
        flask_port = int(os.getenv('FLASK_PORT', 5001))
        
        print(f"--- [STARTUP] Starting Flask Development Server (Debug: {flask_debug_mode}, Port: {flask_port}) ---")
        app.run(
            debug=flask_debug_mode,
            host='0.0.0.0', # يجعله متاحًا على الشبكة المحلية
            port=flask_port
        )
    except SystemExit as se:
        print(f"!!! Application terminated with SystemExit code: {se.code} !!!")
        # ... (بقية معالجة الأخطاء كما كانت لديك) ...
    except OSError as oe:
        print(f"!!! OSError during startup (port {os.getenv('FLASK_PORT', 5001)} likely in use): {oe} !!!")
    except Exception as e_startup:
        print(f"!!! FATAL UNHANDLED EXCEPTION during application startup: {e_startup} !!!")
        if app.logger: # إذا تم تهيئة المسجل
            app.logger.critical(f"CRITICAL STARTUP ERROR: {e_startup}", exc_info=True)