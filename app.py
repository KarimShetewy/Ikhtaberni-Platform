import os
from datetime import datetime, timedelta
import re
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import uuid

# --- 1. Load Environment Variables ---
load_dotenv()

# --- 2. Flask Application Setup ---
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', "a_very_strong_and_unique_fallback_secret_key_!@#Ektbariny")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=int(os.getenv('SESSION_LIFETIME_DAYS', '7')))
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_MB', '50')) * 1024 * 1024 # Default 50MB for uploads

# --- File Upload Settings & Directory Creation ---
UPLOAD_FOLDER_BASE = 'static/uploads'
UPLOAD_FOLDER_VIDEOS = os.path.join(UPLOAD_FOLDER_BASE, 'videos')
UPLOAD_FOLDER_QUESTION_IMAGES = os.path.join(UPLOAD_FOLDER_BASE, 'question_images')
UPLOAD_FOLDER_PROFILE_PICS = os.path.join(UPLOAD_FOLDER_BASE, 'profile_pics')

def ensure_directory_exists(directory_path, directory_name_for_log="Directory"):
    """Creates a directory if it doesn't exist, with logging."""
    if not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path, exist_ok=True) # exist_ok=True avoids error if dir created between check and makedirs
            log_msg = f"FS_SETUP: Successfully created {directory_name_for_log}: {directory_path}"
            print(f"--- [{log_msg}] ---")
            if hasattr(app, 'logger') and app.logger: app.logger.info(log_msg)
        except OSError as e:
            err_msg = f"FS_SETUP_CRITICAL_ERROR: Could not create {directory_name_for_log} at {directory_path}: {e}"
            print(f"!!! [{err_msg}] !!!")
            if hasattr(app, 'logger') and app.logger: app.logger.critical(err_msg, exc_info=True)
            # Consider exiting if critical, e.g., import sys; sys.exit(1)
    else:
        if hasattr(app, 'logger') and app.logger:
             app.logger.debug(f"FS_SETUP: {directory_name_for_log} already exists: {directory_path}")
        else:
            print(f"--- [FS_SETUP] {directory_name_for_log} already exists: {directory_path} ---")

ensure_directory_exists(UPLOAD_FOLDER_BASE, "Base Upload Folder")
ensure_directory_exists(UPLOAD_FOLDER_VIDEOS, "Videos Upload Folder")
ensure_directory_exists(UPLOAD_FOLDER_QUESTION_IMAGES, "Question Images Upload Folder")
ensure_directory_exists(UPLOAD_FOLDER_PROFILE_PICS, "Profile Pictures Upload Folder")

ALLOWED_EXTENSIONS_VIDEOS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}
ALLOWED_EXTENSIONS_IMAGES = {'png', 'jpg', 'jpeg', 'gif', 'webp'} # Common image types
app.config['UPLOAD_FOLDER_VIDEOS'] = UPLOAD_FOLDER_VIDEOS
app.config['UPLOAD_FOLDER_QUESTION_IMAGES'] = UPLOAD_FOLDER_QUESTION_IMAGES
app.config['UPLOAD_FOLDER_PROFILE_PICS'] = UPLOAD_FOLDER_PROFILE_PICS

# --- 3. Database Connection Settings ---
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'ektbariny_db')

# --- 4. Database Connection Function ---
def get_db_connection(include_db_name=True):
    """Establishes and returns a MySQL database connection. Returns None on failure."""
    try:
        conn_params = {
            'host': DB_HOST, 'user': DB_USER, 'password': DB_PASSWORD,
            'charset': 'utf8mb4', 'collation': 'utf8mb4_unicode_ci',
            'autocommit': False # Important: Manage transactions explicitly
        }
        if include_db_name and DB_NAME:
            conn_params['database'] = DB_NAME
        
        conn = mysql.connector.connect(**conn_params)
        return conn
    except Error as e:
        # Log detailed error information
        log_msg = (f"MySQL Connection Error! Host:'{DB_HOST}', "
                   f"DB:'{DB_NAME if include_db_name else 'N/A'}'. "
                   f"ErrNo:{e.errno}, SQLState:{e.sqlstate}, Msg:{e.msg}")
        if hasattr(app, 'logger') and app.logger:
            app.logger.critical(log_msg, exc_info=False) # exc_info=False as msg is detailed
        else:
            print(f"!!! [{log_msg}] !!!") # Fallback if logger not ready
        return None

# --- 5. Database and Tables Creation Function ---
def create_tables():
    """Creates database and all necessary tables from the predefined SQL schema."""
    # Using the SQL schema you confirmed earlier.
    full_db_schema_sql = """
    CREATE DATABASE IF NOT EXISTS `ektbariny_db` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    USE `ektbariny_db`;
    CREATE TABLE IF NOT EXISTS `users` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `username` VARCHAR(100) NOT NULL, `email` VARCHAR(120) UNIQUE NOT NULL,
      `password_hash` VARCHAR(255) NOT NULL, `role` ENUM('student', 'teacher') NOT NULL, `first_name` VARCHAR(50) NULL,
      `last_name` VARCHAR(50) NULL, `phone_number` VARCHAR(20) NULL, `country` VARCHAR(100) NULL,
      `profile_picture_url` VARCHAR(255) NULL, `bio` TEXT NULL,
      `free_video_uploads_remaining` TINYINT UNSIGNED DEFAULT 3, `free_quiz_creations_remaining` TINYINT UNSIGNED DEFAULT 3,
      `is_active` BOOLEAN DEFAULT TRUE, `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `videos` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `teacher_id` INT NOT NULL, `title` VARCHAR(255) NOT NULL, `description` TEXT NULL,
      `video_path_or_url` VARCHAR(512) NOT NULL, `thumbnail_path_or_url` VARCHAR(512) NULL, `duration_seconds` INT NULL,
      `order_in_sequence` INT DEFAULT 0, `is_viewable_free_for_student` BOOLEAN DEFAULT FALSE, `views_count` INT DEFAULT 0,
      `upload_timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `status` ENUM('processing', 'published', 'unpublished', 'error') DEFAULT 'processing',
      `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      CONSTRAINT `fk_video_teacher` FOREIGN KEY (`teacher_id`) REFERENCES `users`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      INDEX `idx_video_teacher` (`teacher_id` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `quizzes` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `teacher_id` INT NOT NULL, `video_id` INT NULL, `title` VARCHAR(255) NOT NULL,
      `description` TEXT NULL, `time_limit_minutes` INT NULL DEFAULT NULL,
      `passing_score_percentage` TINYINT UNSIGNED DEFAULT 70,
      `allow_answer_review` BOOLEAN DEFAULT FALSE, `shareable_link_id` VARCHAR(36) NULL UNIQUE, `is_active` BOOLEAN DEFAULT TRUE,
      `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      CONSTRAINT `fk_quiz_teacher` FOREIGN KEY (`teacher_id`) REFERENCES `users`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `fk_quiz_video` FOREIGN KEY (`video_id`) REFERENCES `videos`(`id`) ON DELETE SET NULL ON UPDATE CASCADE,
      INDEX `idx_quiz_teacher` (`teacher_id` ASC), INDEX `idx_quiz_video` (`video_id` ASC),
      CONSTRAINT `chk_passing_score` CHECK (`passing_score_percentage` BETWEEN 0 AND 100)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `questions` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `quiz_id` INT NOT NULL, `question_text` TEXT NOT NULL,
      `question_type` ENUM('mc', 'essay') NOT NULL DEFAULT 'mc', `image_filename` VARCHAR(255) NULL,
      `display_order` INT DEFAULT 0, `points` TINYINT UNSIGNED DEFAULT 1,
      CONSTRAINT `fk_question_quiz` FOREIGN KEY (`quiz_id`) REFERENCES `quizzes`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      INDEX `idx_question_quiz` (`quiz_id` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `choices` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `question_id` INT NOT NULL, `choice_text` TEXT NOT NULL, `is_correct` BOOLEAN DEFAULT FALSE,
      CONSTRAINT `fk_choice_question` FOREIGN KEY (`question_id`) REFERENCES `questions`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      INDEX `idx_choice_question` (`question_id` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `quiz_attempts` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `student_id` INT NOT NULL, `quiz_id` INT NOT NULL,
      `start_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `end_time` TIMESTAMP NULL, `score` INT DEFAULT 0,
      `max_possible_score` INT NULL, `time_taken_seconds` INT NULL, `submitted_at` TIMESTAMP NULL,
      `is_completed` BOOLEAN DEFAULT FALSE, `passed` BOOLEAN NULL,
      CONSTRAINT `fk_attempt_student` FOREIGN KEY (`student_id`) REFERENCES `users`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `fk_attempt_quiz` FOREIGN KEY (`quiz_id`) REFERENCES `quizzes`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      INDEX `idx_attempt_student_quiz` (`student_id` ASC, `quiz_id` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `student_answers` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `attempt_id` INT NOT NULL, `question_id` INT NOT NULL, `selected_choice_id` INT NULL,
      `essay_answer_text` TEXT NULL, `is_mc_correct` BOOLEAN NULL, `points_awarded` TINYINT UNSIGNED DEFAULT 0,
      CONSTRAINT `fk_answer_attempt` FOREIGN KEY (`attempt_id`) REFERENCES `quiz_attempts`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `fk_answer_question` FOREIGN KEY (`question_id`) REFERENCES `questions`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `fk_answer_choice` FOREIGN KEY (`selected_choice_id`) REFERENCES `choices`(`id`) ON DELETE SET NULL ON UPDATE CASCADE,
      INDEX `idx_answer_attempt` (`attempt_id` ASC), INDEX `idx_answer_question` (`question_id` ASC),
      INDEX `idx_answer_choice` (`selected_choice_id` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `student_subscriptions` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `student_id` INT NOT NULL, `teacher_id` INT NOT NULL,
      `subscription_date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `expiry_date` TIMESTAMP NULL,
      `status` ENUM('active', 'expired', 'cancelled_by_student', 'cancelled_by_admin') DEFAULT 'active',
      `payment_transaction_id` VARCHAR(255) NULL, `amount_paid` DECIMAL(10,2) NULL, `currency_code` VARCHAR(3) DEFAULT 'USD',
      `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      CONSTRAINT `fk_subscription_student` FOREIGN KEY (`student_id`) REFERENCES `users`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `fk_subscription_teacher` FOREIGN KEY (`teacher_id`) REFERENCES `users`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      UNIQUE INDEX `uq_student_teacher_active_subscription` (`student_id` ASC, `teacher_id` ASC, `status` ASC),
      INDEX `idx_subscription_student` (`student_id` ASC), INDEX `idx_subscription_teacher` (`teacher_id` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `student_watched_videos` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `student_id` INT NOT NULL, `video_id` INT NOT NULL, `teacher_id` INT NOT NULL,
      `watched_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT `fk_watched_student` FOREIGN KEY (`student_id`) REFERENCES `users`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `fk_watched_video` FOREIGN KEY (`video_id`) REFERENCES `videos`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `fk_watched_teacher_convenience` FOREIGN KEY (`teacher_id`) REFERENCES `users`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      UNIQUE INDEX `uq_student_video_watch` (`student_id` ASC, `video_id` ASC),
      INDEX `idx_watched_student` (`student_id` ASC), INDEX `idx_watched_video` (`video_id` ASC),
      INDEX `idx_watched_teacher` (`teacher_id` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `platform_payments` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `teacher_id` INT NOT NULL, `payment_for_item_id` INT NULL,
      `payment_for_type` ENUM('extra_videos_package', 'extra_quizzes_package', 'featured_listing', 'other') NULL,
      `description` VARCHAR(255) NULL, `amount` DECIMAL(10,2) NOT NULL, `currency_code` VARCHAR(3) DEFAULT 'USD',
      `payment_date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `transaction_id` VARCHAR(255) NOT NULL UNIQUE,
      `payment_gateway` VARCHAR(50) NULL, `status` ENUM('pending', 'completed', 'failed', 'refunded') DEFAULT 'pending',
      CONSTRAINT `fk_platformpayment_teacher` FOREIGN KEY (`teacher_id`) REFERENCES `users`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
      INDEX `idx_platformpayment_teacher` (`teacher_id` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `teacher_earnings` (
        `id` INT AUTO_INCREMENT PRIMARY KEY, `teacher_id` INT NOT NULL, `student_subscription_id` INT NOT NULL,
        `total_subscription_amount` DECIMAL(10,2) NOT NULL, `platform_commission_percentage` DECIMAL(5,2) NOT NULL,
        `platform_commission_amount` DECIMAL(10,2) NOT NULL, `teacher_net_earning` DECIMAL(10,2) NOT NULL,
        `earning_month` INT NOT NULL, `earning_year` INT NOT NULL,
        `status` ENUM('pending_payout', 'included_in_payout', 'on_hold') DEFAULT 'pending_payout',
        `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT `fk_earning_teacher` FOREIGN KEY (`teacher_id`) REFERENCES `users`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_earning_subscription` FOREIGN KEY (`student_subscription_id`) REFERENCES `student_subscriptions`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
        INDEX `idx_earning_teacher_month_year` (`teacher_id` ASC, `earning_year` ASC, `earning_month` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `teacher_payouts` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `teacher_id` INT NOT NULL, `payout_amount` DECIMAL(10,2) NOT NULL,
      `payout_period_start_date` DATE NULL, `payout_period_end_date` DATE NULL, `payout_method_details` TEXT NULL,
      `initiated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `completed_at` TIMESTAMP NULL, `transaction_reference` VARCHAR(255) NULL,
      `status` ENUM('pending', 'processing', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
      CONSTRAINT `fk_payout_teacher` FOREIGN KEY (`teacher_id`) REFERENCES `users`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
      INDEX `idx_payout_teacher` (`teacher_id` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    conn_init = None
    cursor_init = None
    try:
        conn_init = get_db_connection(include_db_name=False)
        if conn_init is None:
            app.logger.critical("DB_INIT_CRITICAL: Cannot connect to MySQL server for initial schema setup. Aborting.")
            return False
        
        cursor_init = conn_init.cursor()
        app.logger.info("DB_INIT: Executing database schema creation script...")
        # mysql.connector can handle multiple statements separated by ';' if multi=True
        for result in cursor_init.execute(full_db_schema_sql, multi=True):
            # Log information about each executed statement for debugging
            if result.with_rows:
                 app.logger.debug(f"DB_INIT_STATEMENT_RESULT (rows expected but not fetched): {result.statement[:120]}...")
            else:
                 app.logger.debug(f"DB_INIT_STATEMENT_EXECUTED: Affected {result.rowcount} rows. Statement: {result.statement[:120]}...")
        
        conn_init.commit()
        app.logger.info(f"DB_INIT: Database '{DB_NAME}' and tables setup/verification process completed successfully.")
        return True
    except Error as db_init_error:
        err_msg = f"DB_INIT_ERROR: SQL error during database/table initialization: {db_init_error.errno} - {db_init_error.msg}"
        app.logger.error(err_msg, exc_info=False) # exc_info can be too verbose for SQL errors here
        if conn_init: conn_init.rollback()
        return False
    except Exception as e_general_init: # Catch any other unexpected error
        err_msg = f"DB_INIT_GENERAL_ERROR: Unexpected Python error during DB initialization: {e_general_init}"
        app.logger.critical(err_msg, exc_info=True)
        if conn_init: conn_init.rollback()
        return False
    finally:
        if cursor_init: cursor_init.close()
        if conn_init and conn_init.is_connected(): conn_init.close()

# --- 6. Helper Functions & Context Processors ---
@app.context_processor
def inject_global_vars_for_templates():
    """Injects global variables into all Jinja2 templates."""
    user_selected_language = session.get('current_lang', 'en') # Default to English
    return {
        'now': datetime.utcnow(),
        'is_minimal_layout': False, # Default, can be overridden by specific routes in render_template
        'current_lang': user_selected_language
    }

def is_valid_email_format(email_address):
    """Validates email address format using a more common regex pattern."""
    if not email_address: return False
    # Regex from https://emailregex.com/ (RFC 5322 Official Standard) - simplified slightly
    pattern = re.compile(r"^[a-zA-Z0-9.!#$%&'*+\/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$")
    return bool(pattern.match(email_address))

def is_valid_phone_format_simple(phone_number_str):
    """Validates a simple phone number format (digits only, specific length range)."""
    if not phone_number_str: return True # Assuming phone number is optional
    # Allows for common international formats by just checking digits and length
    cleaned_phone = re.sub(r'\D', '', phone_number_str) # Remove non-digits
    return bool(7 <= len(cleaned_phone) <= 15)

def allowed_file(filename_str, allowed_extensions_set):
    """Checks if the uploaded file has an allowed extension. Case-insensitive."""
    return '.' in filename_str and \
           filename_str.rsplit('.', 1)[1].lower() in allowed_extensions_set

# --- 7. Decorators for Route Protection ---
def login_required(route_function):
    """Decorator: Ensures user is logged in. Redirects to login page if not."""
    @wraps(route_function)
    def decorated_view_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("You must be logged in to access this page. Please log in.", "info")
            # Store the intended URL to redirect back after login
            return redirect(url_for('login_page', next=request.url))
        return route_function(*args, **kwargs)
    return decorated_view_function

def teacher_required(route_function):
    """Decorator: Ensures user is logged in AND is a teacher."""
    @wraps(route_function)
    @login_required # Chain with login_required first
    def decorated_view_function(*args, **kwargs):
        if session.get('role') != 'teacher':
            flash("Access Denied: This page is restricted to teachers only.", "danger")
            # Redirect to a more appropriate page, e.g., their own dashboard or home
            return redirect(url_for('home' if session.get('role') != 'student' else 'student_dashboard_placeholder'))
        return route_function(*args, **kwargs)
    return decorated_view_function

def student_required(route_function):
    """Decorator: Ensures user is logged in AND is a student."""
    @wraps(route_function)
    @login_required # Chain with login_required first
    def decorated_view_function(*args, **kwargs):
        if session.get('role') != 'student':
            flash("Access Denied: This page is restricted to students only.", "danger")
            return redirect(url_for('home' if session.get('role') != 'teacher' else 'teacher_dashboard_placeholder'))
        return route_function(*args, **kwargs)
    return decorated_view_function

# --- 8. Application Routes (Authentication and Main Navigation) ---
@app.route('/')
def home():
    """Renders the main home page of the application."""
    return render_template('index.html') # Assumes is_minimal_layout=False by default

@app.route('/choose_signup_role', methods=['GET', 'POST'])
def choose_signup_role():
    """Page for users to select their role (student or teacher) before signing up."""
    if request.method == 'POST':
        selected_role = request.form.get('role')
        if selected_role not in ['student', 'teacher']:
            flash("Invalid role selected. Please choose either 'Student' or 'Teacher'.", "danger")
            return render_template('auth/choose_role_signup.html', is_minimal_layout=True)
        session['signup_attempt_role'] = selected_role
        flash(f"You are signing up as a {selected_role.capitalize()}. Please complete your registration details below.", "info")
        return redirect(url_for('signup_actual_form_page'))
    return render_template('auth/choose_role_signup.html', is_minimal_layout=True)

@app.route('/signup/form', methods=['GET', 'POST'])
def signup_actual_form_page():
    """Handles the actual user registration form after role selection."""
    user_role_for_signup = session.get('signup_attempt_role')
    if not user_role_for_signup:
        flash("Role selection is missing or your session has expired. Please choose your role again to proceed.", "warning")
        return redirect(url_for('choose_signup_role'))

    # Use request.form for POST to repopulate, empty dict for GET
    form_data_repopulate = request.form.to_dict() if request.method == 'POST' else {}

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone_number_input = request.form.get('phone_number', '').strip()
        password_input = request.form.get('password', '') # Do not strip password
        confirm_password_input = request.form.get('confirm_password', '')
        country_selected = request.form.get('country', '').strip()
        agreed_to_terms = request.form.get('agree_terms')

        validation_errors = []
        if not first_name or len(first_name) < 2: validation_errors.append("First name is required (minimum 2 characters).")
        if not last_name or len(last_name) < 2: validation_errors.append("Last name is required (minimum 2 characters).")
        if not email or not is_valid_email_format(email): validation_errors.append("A valid email address is required.")
        if phone_number_input and not is_valid_phone_format_simple(phone_number_input): validation_errors.append("Phone number format is invalid. Please enter 7-15 digits.")
        if not password_input or len(password_input) < 8: validation_errors.append("Password must be at least 8 characters long.")
        # Add more password complexity rules here if desired (e.g., uppercase, number, special char)
        if password_input != confirm_password_input: validation_errors.append("The entered passwords do not match.")
        if not country_selected: validation_errors.append("Please select your country.")
        if not agreed_to_terms: validation_errors.append("You must agree to the Terms of Service and Privacy Policy to create an account.")

        if validation_errors:
            for error_message in validation_errors: flash(error_message, "danger")
            return render_template('auth/signup_actual_form.html', role=user_role_for_signup, is_minimal_layout=True, form_data=form_data_repopulate)

        # Proceed with database operations if validation passes
        db_conn_signup = None; db_cursor_signup = None
        try:
            db_conn_signup = get_db_connection()
            if db_conn_signup is None:
                raise Error("Database connection failed. Cannot register at this moment.") # Custom error for generic handling
            
            db_cursor_signup = db_conn_signup.cursor(dictionary=True)
            db_cursor_signup.execute("SELECT id FROM users WHERE email = %s", (email,))
            if db_cursor_signup.fetchone():
                flash(f"The email address '{email}' is already associated with an existing account. Please log in or use a different email.", "warning")
                return render_template('auth/signup_actual_form.html', role=user_role_for_signup, is_minimal_layout=True, form_data=form_data_repopulate)

            hashed_user_password = generate_password_hash(password_input)
            # Generate a more robust unique username
            base_username_for_generation = f"{first_name.lower().replace(' ', '_')}{last_name.lower()[0] if last_name else ''}"
            unique_generated_username = f"{base_username_for_generation[:20]}_{uuid.uuid4().hex[:8]}"[:100]

            sql_insert_user_query = """
                INSERT INTO users (username, email, password_hash, role, first_name, last_name, phone_number, country) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            user_data_tuple_for_insert = (
                unique_generated_username, email, hashed_user_password, user_role_for_signup,
                first_name, last_name, phone_number_input if phone_number_input else None, country_selected
            )
            db_cursor_signup.execute(sql_insert_user_query, user_data_tuple_for_insert)
            db_conn_signup.commit() # Commit the transaction
            
            session.pop('signup_attempt_role', None) # Clear role from session
            flash(f"Congratulations, {first_name}! Your account as a {user_role_for_signup.capitalize()} has been successfully created. You can now log in.", "success")
            return redirect(url_for('login_page'))
        
        except Error as db_signup_err:
            if db_conn_signup: db_conn_signup.rollback()
            app.logger.error(f"SIGNUP_DB_ERROR for email {email}: {db_signup_err.errno} - {db_signup_err.msg}", exc_info=False)
            flash("A database error occurred during registration. Please try again later or contact support. (Code: REG-DBE)", "danger")
        except Exception as general_signup_err: # Catch any other Python errors
            if db_conn_signup: db_conn_signup.rollback()
            app.logger.critical(f"SIGNUP_GENERAL_ERROR: An unexpected error occurred: {general_signup_err}", exc_info=True)
            flash("An unexpected error occurred during the registration process. Please try again. (Code: REG-GEN)", "danger")
        finally:
            if db_cursor_signup: db_cursor_signup.close()
            if db_conn_signup and db_conn_signup.is_connected(): db_conn_signup.close()
        
        # If execution reaches here, an error occurred, re-render form
        return render_template('auth/signup_actual_form.html', role=user_role_for_signup, is_minimal_layout=True, form_data=form_data_repopulate)

    # For GET request:
    return render_template('auth/signup_actual_form.html', role=user_role_for_signup, is_minimal_layout=True, form_data=form_data_repopulate)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Handles user login attempts."""
    # Preserve email for repopulation, get 'next' URL for redirection
    form_data_repopulate = {'email': request.form.get('email', '')} if request.method == 'POST' else {}
    next_redirect_url = request.args.get('next') or request.form.get('next') # Handles 'next' from GET or POST

    if request.method == 'POST':
        email_input = request.form.get('email', '').strip().lower()
        password_input = request.form.get('password', '') # No strip for password
        
        validation_errors = []
        if not email_input or not is_valid_email_format(email_input): validation_errors.append("A valid email address is required.")
        if not password_input: validation_errors.append("Password is required.")

        if validation_errors:
            for error_message in validation_errors: flash(error_message, "danger")
            return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_repopulate, next=next_redirect_url)

        db_conn_login = None; db_cursor_login = None
        try:
            db_conn_login = get_db_connection()
            if db_conn_login is None:
                raise Error("Database connection unavailable. Please try again shortly.")
            
            db_cursor_login = db_conn_login.cursor(dictionary=True)
            # Fetch all necessary user details for the session
            db_cursor_login.execute("""
                SELECT id, username, email, password_hash, role, first_name, last_name 
                FROM users WHERE email = %s AND is_active = TRUE
            """, (email_input,))
            user_record_from_db = db_cursor_login.fetchone()

            if user_record_from_db and check_password_hash(user_record_from_db['password_hash'], password_input):
                session.clear() # Start with a clean session
                session['user_id'] = user_record_from_db['id']
                # Prefer first name for display, fallback to username
                session['username'] = user_record_from_db.get('first_name') or user_record_from_db.get('username', 'Valued User')
                session['role'] = user_record_from_db['role']
                session['email'] = user_record_from_db['email']
                # session['current_lang'] could be loaded from user profile settings here if stored
                session.permanent = True # Make session adhere to PERMANENT_SESSION_LIFETIME
                
                flash(f"Login successful! Welcome back, {session['username']}.", "success")
                
                # Safe redirection to 'next' URL or role-based dashboard
                if next_redirect_url and (next_redirect_url.startswith('/') or next_redirect_url.startswith(request.host_url)):
                    return redirect(next_redirect_url)
                
                if user_record_from_db['role'] == 'teacher':
                    return redirect(url_for('teacher_dashboard_placeholder'))
                elif user_record_from_db['role'] == 'student':
                    return redirect(url_for('student_dashboard_placeholder'))
                else: # Fallback, though role should always be 'student' or 'teacher'
                    app.logger.warning(f"User {user_record_from_db['id']} logged in with an unexpected role: {user_record_from_db['role']}")
                    return redirect(url_for('home'))
            else:
                flash("Invalid email address or password, or your account may be inactive. Please check and try again.", "danger")
        
        except Error as db_login_err:
            # Log specific DB error, but show generic message to user
            app.logger.error(f"LOGIN_DB_ERROR for email {email_input}: {db_login_err.errno} - {db_login_err.msg}", exc_info=False)
            flash("A database error occurred during login. Please try again later. (Code: LOGIN-DBE)", "danger")
        except Exception as general_login_err:
            app.logger.critical(f"LOGIN_GENERAL_ERROR: An unexpected error occurred: {general_login_err}", exc_info=True)
            flash("An unexpected error occurred. Please try logging in again. (Code: LOGIN-GEN)", "danger")
        finally:
            if db_cursor_login: db_cursor_login.close()
            if db_conn_login and db_conn_login.is_connected(): db_conn_login.close()
        
        # If login fails for any reason, re-render the login form
        return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_repopulate, next=next_redirect_url)

    # For GET request
    return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_repopulate, next=next_redirect_url)

@app.route('/logout')
@login_required # User must be logged in to log out
def logout():
    """Logs the current user out by clearing the session."""
    user_name_at_logout = session.get('username', 'User') # Get name for personalized message
    session.clear()
    flash(f"You have been successfully logged out, {user_name_at_logout}. We hope to see you again soon!", "info")
    return redirect(url_for('home'))

@app.route('/explore/teachers')
def explore_teachers_page():
    """
    Renders the page for exploring teachers, with search functionality.
    Fetches teachers based on a search query if provided.
    """
    search_query = request.args.get('search_query', '').strip()
    teachers_list = []
    db_conn = None
    db_cursor = None
    try:
        db_conn = get_db_connection()
        if db_conn is None:
            app.logger.error("EXPLORE_TEACHERS_DB_ERROR: Failed to connect to database.")
            flash("Database connection error. Please try again later.", "danger")
            return render_template('public/explore_teachers.html', teachers=[], search_query=search_query) # cite: 1

        db_cursor = db_conn.cursor(dictionary=True)

        sql_query = """
            SELECT id, first_name, last_name, username, profile_picture_url, bio
            FROM users
            WHERE role = 'teacher' AND is_active = TRUE
        """
        query_params = []

        if search_query:
            # Add conditions for searching across multiple fields
            sql_query += """
                AND (first_name LIKE %s OR last_name LIKE %s OR username LIKE %s OR bio LIKE %s)
            """
            # Add '%' for LIKE queries to match partial strings
            search_pattern = f"%{search_query}%"
            query_params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
        
        sql_query += " ORDER BY first_name ASC, last_name ASC"

        db_cursor.execute(sql_query, tuple(query_params))
        teachers_list = db_cursor.fetchall()
        
    except Error as e_db:
        app.logger.error(f"EXPLORE_TEACHERS_DB_ERROR: {e_db.msg}", exc_info=False)
        flash("An error occurred while fetching teachers. Please try again.", "danger")
    except Exception as e_general:
        app.logger.critical(f"EXPLORE_TEACHERS_GENERAL_ERROR: {e_general}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if db_cursor:
            db_cursor.close()
        if db_conn and db_conn.is_connected():
            db_conn.close()

    # Pass current_lang from session to the template for initial rendering of placeholders/buttons
    return render_template('public/explore_teachers.html', 
                           teachers=teachers_list, 
                           search_query=search_query,
                           current_lang=session.get('current_lang', 'en')) # cite: 1


# --- 9. Teacher Video Management Routes ---
@app.route('/teacher/videos/upload', methods=['GET', 'POST'])
@teacher_required
def upload_video_page():
    teacher_id = session['user_id']
    # Initialize form_data for GET and for repopulating on POST error
    form_data_repopulate = request.form.to_dict() if request.method == 'POST' else {}
    
    # Fetch free video uploads remaining for the teacher
    conn_quota_check = None; cursor_quota_check = None
    free_uploads_left = 0
    can_upload_video = True # Assume true, then verify
    try:
        conn_quota_check = get_db_connection()
        if conn_quota_check is None:
            raise Error("Database connection failed while checking video upload quota.")
        cursor_quota_check = conn_quota_check.cursor(dictionary=True)
        cursor_quota_check.execute("SELECT free_video_uploads_remaining FROM users WHERE id = %s", (teacher_id,))
        user_quota_data = cursor_quota_check.fetchone()
        if user_quota_data:
            free_uploads_left = user_quota_data.get('free_video_uploads_remaining', 0)
        if free_uploads_left <= 0: # Or check subscription status
            can_upload_video = False
    except Error as e_quota:
        app.logger.error(f"VIDEO_UPLOAD_QUOTA_ERROR for teacher {teacher_id}: {e_quota.msg}", exc_info=False)
        flash("Could not verify your video upload permissions at this time. Please try again.", "danger")
        return redirect(url_for('teacher_dashboard_placeholder'))
    finally:
        if cursor_quota_check: cursor_quota_check.close()
        if conn_quota_check and conn_quota_check.is_connected(): conn_quota_check.close()

    if request.method == 'POST':
        if not can_upload_video and free_uploads_left <= 0: # Double-check for POST request
            flash("You have used all your free video uploads. Please consider upgrading your plan to upload more.", "warning")
            return render_template('teacher/upload_video.html', 
                                   free_uploads_left=free_uploads_left, 
                                   can_upload=can_upload_video, 
                                   form_data=form_data_repopulate)

        video_title_input = request.form.get('title', '').strip()
        video_description_input = request.form.get('description', '').strip()
        video_file_object = request.files.get('video_file') # Werkzeug FileStorage object
        is_viewable_free_input = request.form.get('is_viewable_free') == 'true'

        validation_errors = []
        if not video_title_input or len(video_title_input) < 3:
            validation_errors.append("Video title is required (minimum 3 characters).")
        if not video_file_object or video_file_object.filename == '':
            validation_errors.append("A video file must be selected for upload.")
        elif not allowed_file(video_file_object.filename, ALLOWED_EXTENSIONS_VIDEOS):
            validation_errors.append(f"Invalid video file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS_VIDEOS)}.")
        # Add file size check against app.config['MAX_CONTENT_LENGTH'] if desired (Flask handles > MAX_CONTENT_LENGTH with 413)

        if validation_errors:
            for error_message in validation_errors: flash(error_message, "danger")
            return render_template('teacher/upload_video.html', 
                                   free_uploads_left=free_uploads_left, 
                                   can_upload=can_upload_video, 
                                   form_data=form_data_repopulate)
        
        original_video_filename = secure_filename(video_file_object.filename)
        file_extension = original_video_filename.rsplit('.', 1)[1].lower() if '.' in original_video_filename else ''
        # Generate a unique filename to prevent conflicts and for security
        unique_video_filename = f"video_{teacher_id}_{uuid.uuid4().hex[:12]}.{file_extension}"
        
        video_save_path_on_server_disk = os.path.join(app.config['UPLOAD_FOLDER_VIDEOS'], unique_video_filename)
        # Path to store in DB (relative to static folder)
        video_path_for_database = os.path.join('uploads/videos', unique_video_filename).replace('\\', '/')

        db_conn_upload = None; db_cursor_upload = None
        video_successfully_saved_to_disk = False
        try:
            video_file_object.save(video_save_path_on_server_disk)
            video_successfully_saved_to_disk = True
            app.logger.info(f"VIDEO_UPLOAD: File '{original_video_filename}' saved as '{unique_video_filename}' for teacher {teacher_id}.")

            db_conn_upload = get_db_connection()
            if db_conn_upload is None:
                raise Error("Database connection failed. Video saved to disk but not registered in system.")
            
            db_cursor_upload = db_conn_upload.cursor()
            sql_insert_video_query = """
                INSERT INTO videos (teacher_id, title, description, video_path_or_url, 
                                    is_viewable_free_for_student, status, upload_timestamp) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            # Status can be 'processing' if you have background tasks, or 'published' directly
            video_data_tuple_for_insert = (
                teacher_id, video_title_input, video_description_input or None, video_path_for_database,
                is_viewable_free_input, 'published', datetime.utcnow()
            )
            db_cursor_upload.execute(sql_insert_video_query, video_data_tuple_for_insert)

            # Decrement free video upload quota if applicable
            if free_uploads_left > 0: # Re-check for safety
                db_cursor_upload.execute("""
                    UPDATE users SET free_video_uploads_remaining = free_video_uploads_remaining - 1 
                    WHERE id = %s AND free_video_uploads_remaining > 0
                """, (teacher_id,))
            
            db_conn_upload.commit()
            flash(f"Video '{video_title_input}' has been successfully uploaded and published!", "success")
            return redirect(url_for('teacher_videos_list_page'))

        except Exception as e_video_upload_process: # Catch generic Python errors and DB errors
            if db_conn_upload: db_conn_upload.rollback() # Rollback DB changes if any part failed
            
            # If file was saved but DB operation failed, attempt to delete the orphaned file
            if video_successfully_saved_to_disk and os.path.exists(video_save_path_on_server_disk):
                try:
                    os.remove(video_save_path_on_server_disk)
                    app.logger.warning(f"VIDEO_UPLOAD_ROLLBACK: Deleted orphaned file '{video_save_path_on_server_disk}' due to error: {e_video_upload_process}")
                except Exception as e_remove_orphaned_file:
                    app.logger.error(f"VIDEO_UPLOAD_ROLLBACK_FAIL: Could not delete orphaned file '{video_save_path_on_server_disk}': {e_remove_orphaned_file}")
            
            error_detail_for_log = str(e_video_upload_process)
            if isinstance(e_video_upload_process, Error): # MySQL Error
                error_detail_for_log = f"DB_ERRNO_{e_video_upload_process.errno}: {e_video_upload_process.msg}"
            
            app.logger.error(f"VIDEO_UPLOAD_FAILURE for teacher {teacher_id}, file '{original_video_filename}': {error_detail_for_log}", exc_info=True)
            flash(f"An error occurred during video upload: {str(e_video_upload_process)[:150]}. Please try again.", "danger")
        finally:
            if db_cursor_upload: db_cursor_upload.close()
            if db_conn_upload and db_conn_upload.is_connected(): db_conn_upload.close()
        
        # If reached here, POST failed, re-render form
        return render_template('teacher/upload_video.html', 
                               free_uploads_left=free_uploads_left, 
                               can_upload=can_upload_video, 
                               form_data=form_data_repopulate)

    # For GET request:
    return render_template('teacher/upload_video.html', 
                           free_uploads_left=free_uploads_left, 
                           can_upload=can_upload_video, 
                           form_data=form_data_repopulate)


@app.route('/teacher/videos')
@teacher_required
def teacher_videos_list_page():
    """Displays a list of videos uploaded by the current teacher."""
    teacher_id = session['user_id']
    videos_list_from_db = []
    db_conn_list_videos = None; db_cursor_list_videos = None
    try:
        db_conn_list_videos = get_db_connection()
        if db_conn_list_videos is None:
            raise Error("Database connection failed while trying to list videos.")
        
        db_cursor_list_videos = db_conn_list_videos.cursor(dictionary=True)
        db_cursor_list_videos.execute("""
            SELECT id, title, status, upload_timestamp, is_viewable_free_for_student 
            FROM videos 
            WHERE teacher_id = %s 
            ORDER BY upload_timestamp DESC
        """, (teacher_id,))
        videos_list_from_db = db_cursor_list_videos.fetchall()
    except Error as e_list_videos_db:
        app.logger.error(f"LIST_VIDEOS_DB_ERROR for teacher {teacher_id}: {e_list_videos_db.msg}", exc_info=False)
        flash("A database error occurred while retrieving your videos. Please try again later.", "danger")
    except Exception as e_list_videos_general:
        app.logger.error(f"LIST_VIDEOS_GENERAL_ERROR for teacher {teacher_id}: {e_list_videos_general}", exc_info=True)
        flash("An unexpected error occurred while retrieving your videos.", "warning")
    finally:
        if db_cursor_list_videos: db_cursor_list_videos.close()
        if db_conn_list_videos and db_conn_list_videos.is_connected(): db_conn_list_videos.close()
    
    return render_template('teacher/videos_list.html', videos=videos_list_from_db)

# --- 10. Teacher Quiz Management Routes (Full implementations) ---
@app.route('/teacher/quizzes')
@teacher_required
def teacher_quizzes_list_page():
    teacher_id = session['user_id']
    quizzes = []
    conn = None; cursor = None
    try:
        conn = get_db_connection()
        if not conn: raise Error("DB connection error listing quizzes.")
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT q.id, q.title, q.is_active, q.created_at, v.title as video_title 
            FROM quizzes q LEFT JOIN videos v ON q.video_id = v.id 
            WHERE q.teacher_id = %s ORDER BY q.created_at DESC
        """
        cursor.execute(sql, (teacher_id,)); quizzes = cursor.fetchall()
    except Error as e:
        app.logger.error(f"Error fetching quizzes for teacher {teacher_id}: {e.msg}", exc_info=False)
        flash("Could not retrieve your quizzes. Please try again.", "warning")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
    return render_template('teacher/quizzes_list.html', quizzes=quizzes)

@app.route('/teacher/quizzes/create', methods=['GET', 'POST'])
@app.route('/teacher/videos/<int:video_id>/quiz/create', methods=['GET', 'POST'])
@teacher_required
def create_quiz_page(video_id=None):
    teacher_id = session['user_id']
    form_data = request.form.to_dict() if request.method == 'POST' else {}
    teacher_videos = []; conn_fetch_vids = None; cursor_fetch_vids = None
    try:
        conn_fetch_vids = get_db_connection();
        if not conn_fetch_vids: raise Error("DB error fetching videos for quiz form.")
        cursor_fetch_vids = conn_fetch_vids.cursor(dictionary=True)
        cursor_fetch_vids.execute("SELECT id, title FROM videos WHERE teacher_id = %s ORDER BY title ASC", (teacher_id,))
        teacher_videos = cursor_fetch_vids.fetchall()
    except Error as e_fetch_v: app.logger.error(f"Err fetching videos for quiz form (TID:{teacher_id}): {e_fetch_v.msg}", exc_info=False)
    finally:
        if cursor_fetch_vids: cursor_fetch_vids.close()
        if conn_fetch_vids and conn_fetch_vids.is_connected(): conn_fetch_vids.close()

    free_quizzes_left = 0; can_create_quiz = True; conn_q_quota = None; cursor_q_quota = None
    try:
        conn_q_quota = get_db_connection();
        if not conn_q_quota: raise Error("DB error fetching quiz quota.")
        cursor_q_quota = conn_q_quota.cursor(dictionary=True)
        cursor_q_quota.execute("SELECT free_quiz_creations_remaining FROM users WHERE id = %s", (teacher_id,))
        user_meta_q = cursor_q_quota.fetchone()
        if user_meta_q: free_quizzes_left = user_meta_q.get('free_quiz_creations_remaining', 0)
        if free_quizzes_left <= 0: can_create_quiz = False
    except Error as e_q_quota:
        app.logger.error(f"Err fetching quiz quota (TID:{teacher_id}): {e_q_quota.msg}", exc_info=False)
        flash("Error checking quiz creation permissions.", "danger")
        return redirect(url_for('teacher_dashboard_placeholder'))
    finally:
        if cursor_q_quota: cursor_q_quota.close()
        if conn_q_quota and conn_q_quota.is_connected(): conn_q_quota.close()

    if request.method == 'POST':
        if not can_create_quiz and free_quizzes_left <= 0:
            flash("All free quiz creations used. Upgrade for more.", "warning")
            return render_template('teacher/create_quiz.html', teacher_videos=teacher_videos, video_id_preselected=video_id, free_quizzes_left=free_quizzes_left, can_create_quiz=can_create_quiz, form_data=form_data)

        quiz_title = request.form.get('quiz_title', '').strip()
        quiz_desc = request.form.get('quiz_description', '').strip()
        linked_video_id_str = request.form.get('linked_video_id')
        time_limit_str = request.form.get('time_limit_minutes', '0').strip()
        passing_score_str = request.form.get('passing_score_percentage', '70').strip()
        allow_review_input = request.form.get('allow_answer_review') == 'on'
        
        errors = []
        if not quiz_title or len(quiz_title) < 3: errors.append("Quiz title (min 3 characters) is required.")
        
        time_limit_val = None
        if time_limit_str.isdigit():
            if int(time_limit_str) < 0: errors.append("Time limit cannot be negative.")
            elif int(time_limit_str) > 0: time_limit_val = int(time_limit_str)
        elif time_limit_str: errors.append("Time limit must be a valid number (minutes).")

        passing_score_val = 70 # Default
        if passing_score_str.isdigit() and 0 <= int(passing_score_str) <= 100:
            passing_score_val = int(passing_score_str)
        elif passing_score_str: errors.append("Passing score must be a percentage between 0 and 100.")
        
        linked_video_id_val = int(linked_video_id_str) if linked_video_id_str and linked_video_id_str.isdigit() else None
        if linked_video_id_val is not None and not any(v['id'] == linked_video_id_val for v in teacher_videos):
            errors.append("The selected video for linking is invalid or does not belong to you.")
            linked_video_id_val = None # Reset if invalid

        if errors:
            for e_msg in errors: flash(e_msg, "danger")
            return render_template('teacher/create_quiz.html', teacher_videos=teacher_videos, video_id_preselected=video_id, free_quizzes_left=free_quizzes_left, can_create_quiz=can_create_quiz, form_data=form_data)

        conn_insert_quiz = None; cursor_insert_quiz = None
        try:
            conn_insert_quiz = get_db_connection()
            if not conn_insert_quiz: raise Error("Database connection failed while trying to create the quiz.")
            cursor_insert_quiz = conn_insert_quiz.cursor()
            sql_insert = """INSERT INTO quizzes 
                                (teacher_id, video_id, title, description, time_limit_minutes, 
                                 passing_score_percentage, allow_answer_review, is_active) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)"""
            cursor_insert_quiz.execute(sql_insert, (teacher_id, linked_video_id_val, quiz_title, quiz_desc or None, 
                                            time_limit_val, passing_score_val, allow_review_input))
            new_quiz_id = cursor_insert_quiz.lastrowid
            
            if free_quizzes_left > 0: # Decrement quota
                cursor_insert_quiz.execute("UPDATE users SET free_quiz_creations_remaining = free_quiz_creations_remaining - 1 WHERE id = %s AND free_quiz_creations_remaining > 0", (teacher_id,))
            
            conn_insert_quiz.commit()
            flash(f"Quiz '{quiz_title}' was created successfully! You can now add questions to it.", "success")
            return redirect(url_for('add_question_to_quiz_page', quiz_id=new_quiz_id))
        except Error as e_db_ins_quiz:
            if conn_insert_quiz: conn_insert_quiz.rollback()
            app.logger.error(f"CREATE_QUIZ_DB_ERROR for teacher {teacher_id}: {e_db_ins_quiz.msg}", exc_info=False)
            flash(f"A database error occurred while creating the quiz: {str(e_db_ins_quiz.msg)[:100]}. Please try again.", "danger")
        except Exception as e_gen_create_quiz:
            if conn_insert_quiz: conn_insert_quiz.rollback()
            app.logger.critical(f"CREATE_QUIZ_GENERAL_ERROR for teacher {teacher_id}: {e_gen_create_quiz}", exc_info=True)
            flash("An unexpected error occurred while creating the quiz. Please try again.", "danger")
        finally:
            if cursor_insert_quiz: cursor_insert_quiz.close()
            if conn_insert_quiz and conn_insert_quiz.is_connected(): conn_insert_quiz.close()
        
        return render_template('teacher/create_quiz.html', teacher_videos=teacher_videos, video_id_preselected=video_id, free_quizzes_left=free_quizzes_left, can_create_quiz=can_create_quiz, form_data=form_data)
    
    return render_template('teacher/create_quiz.html', teacher_videos=teacher_videos, video_id_preselected=video_id, free_quizzes_left=free_quizzes_left, can_create_quiz=can_create_quiz, form_data=form_data)

@app.route('/teacher/quizzes/<int:quiz_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_quiz_page(quiz_id):
    teacher_id = session['user_id']
    quiz_to_edit_data = None; teacher_videos_list = []; submitted_form_data = None
    conn_fetch_edit_quiz = None; cursor_fetch_edit_quiz = None
    try:
        conn_fetch_edit_quiz = get_db_connection()
        if not conn_fetch_edit_quiz: raise Error("DB connection error fetching quiz for edit.")
        cursor_fetch_edit_quiz = conn_fetch_edit_quiz.cursor(dictionary=True)
        cursor_fetch_edit_quiz.execute("SELECT * FROM quizzes WHERE id = %s AND teacher_id = %s", (quiz_id, teacher_id))
        quiz_to_edit_data = cursor_fetch_edit_quiz.fetchone()
        if not quiz_to_edit_data:
            flash("Quiz not found or you are not authorized to edit this quiz.", "warning")
            return redirect(url_for('teacher_quizzes_list_page'))
        cursor_fetch_edit_quiz.execute("SELECT id, title FROM videos WHERE teacher_id = %s ORDER BY title ASC", (teacher_id,))
        teacher_videos_list = cursor_fetch_edit_quiz.fetchall()
    except Error as e_fetch_edit_q_data:
        app.logger.error(f"EDIT_QUIZ_FETCH_ERROR (QuizID {quiz_id}, TeacherID {teacher_id}): {e_fetch_edit_q_data.msg}", exc_info=False)
        flash("An error occurred while loading the quiz data for editing. Please try again.", "danger")
        return redirect(url_for('teacher_quizzes_list_page'))
    finally:
        if cursor_fetch_edit_quiz: cursor_fetch_edit_quiz.close()
        if conn_fetch_edit_quiz and conn_fetch_edit_quiz.is_connected(): conn_fetch_edit_quiz.close()
    if not quiz_to_edit_data: return redirect(url_for('teacher_quizzes_list_page')) # Should have been caught

    submitted_form_data = request.form.to_dict() if request.method == 'POST' else None

    if request.method == 'POST':
        quiz_title_updated = request.form.get('quiz_title', '').strip()
        quiz_desc_updated = request.form.get('quiz_description', '').strip()
        linked_video_id_str_updated = request.form.get('linked_video_id')
        time_limit_str_updated = request.form.get('time_limit_minutes', '').strip()
        passing_score_str_updated = request.form.get('passing_score_percentage', '').strip()
        allow_review_input_updated = request.form.get('allow_answer_review') == 'on'
        
        validation_errors = []
        if not quiz_title_updated or len(quiz_title_updated) < 3: validation_errors.append("Quiz title must be at least 3 characters long.")

        time_limit_val_updated = None
        if not time_limit_str_updated: validation_errors.append("Time limit is required (enter 0 for no time limit).")
        elif not time_limit_str_updated.isdigit() or int(time_limit_str_updated) < 0: validation_errors.append("Time limit must be a non-negative number.")
        else:
            time_limit_val_updated = int(time_limit_str_updated) if int(time_limit_str_updated) > 0 else None

        passing_score_val_updated = None
        if not passing_score_str_updated: validation_errors.append("Passing score percentage is required.")
        elif not passing_score_str_updated.isdigit() or not (0 <= int(passing_score_str_updated) <= 100):
            validation_errors.append("Passing score must be a percentage between 0 and 100.")
        else: passing_score_val_updated = int(passing_score_str_updated)

        linked_video_id_val_updated = int(linked_video_id_str_updated) if linked_video_id_str_updated and linked_video_id_str_updated.isdigit() else None
        if linked_video_id_val_updated is not None and not any(v['id'] == linked_video_id_val_updated for v in teacher_videos_list):
            validation_errors.append("Invalid video selected for linking. Please choose from your list or 'No Video'.")
        
        if validation_errors:
            for e_msg in validation_errors: flash(e_msg, "danger")
            # Pass original quiz_to_edit_data for non-submitted fields, and submitted_form_data for repopulation
            return render_template('teacher/edit_quiz.html', quiz=quiz_to_edit_data, teacher_videos=teacher_videos_list, submitted_data=submitted_form_data)

        conn_update_quiz_details = None; cursor_update_quiz_details = None
        try:
            conn_update_quiz_details = get_db_connection()
            if not conn_update_quiz_details: raise Error("Database connection failed while attempting to update quiz details.")
            cursor_update_quiz_details = conn_update_quiz_details.cursor()
            sql_update_query = """
                UPDATE quizzes SET title=%s, description=%s, video_id=%s, time_limit_minutes=%s, 
                                  passing_score_percentage=%s, allow_answer_review=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s AND teacher_id=%s
            """
            cursor_update_quiz_details.execute(sql_update_query, (
                quiz_title_updated, quiz_desc_updated or None, linked_video_id_val_updated, 
                time_limit_val_updated, passing_score_val_updated, allow_review_input_updated, 
                quiz_id, teacher_id
            ))
            conn_update_quiz_details.commit()
            flash(f"Quiz '{quiz_title_updated}' details have been updated successfully!", "success")
            return redirect(url_for('teacher_quizzes_list_page'))
        except Error as e_db_update_quiz:
            if conn_update_quiz_details: conn_update_quiz_details.rollback()
            app.logger.error(f"EDIT_QUIZ_DB_ERROR (QuizID {quiz_id}): {e_db_update_quiz.msg}", exc_info=False)
            flash(f"A database error occurred while updating the quiz: {str(e_db_update_quiz.msg)[:100]}.", "danger")
        except Exception as e_gen_update_quiz:
            if conn_update_quiz_details: conn_update_quiz_details.rollback()
            app.logger.critical(f"EDIT_QUIZ_GENERAL_ERROR (QuizID {quiz_id}): {e_gen_update_quiz}", exc_info=True)
            flash("An unexpected error occurred while updating the quiz details. Please try again.", "danger")
        finally:
            if cursor_update_quiz_details: cursor_update_quiz_details.close()
            if conn_update_quiz_details and conn_update_quiz_details.is_connected(): conn_update_quiz_details.close()
        
        # If POST failed, re-render with submitted data
        return render_template('teacher/edit_quiz.html', quiz=quiz_to_edit_data, teacher_videos=teacher_videos_list, submitted_data=submitted_form_data)
    
    # For GET request, pass the fetched quiz data to the template
    return render_template('teacher/edit_quiz.html', quiz=quiz_to_edit_data, teacher_videos=teacher_videos_list, submitted_data=None)

@app.route('/teacher/quizzes/<int:quiz_id>/delete', methods=['POST'])
@teacher_required
def delete_quiz_page(quiz_id):
    teacher_id = session['user_id']
    quiz_title_for_flash_msg = "The selected quiz" # Fallback title
    conn_delete_quiz = None; cursor_delete_quiz = None
    try:
        conn_delete_quiz = get_db_connection()
        if not conn_delete_quiz: raise Error("Database connection failed while attempting to delete the quiz.")
        cursor_delete_quiz = conn_delete_quiz.cursor(dictionary=True) # For fetching title
        
        # Fetch quiz title for a more informative flash message and verify ownership
        cursor_delete_quiz.execute("SELECT title FROM quizzes WHERE id = %s AND teacher_id = %s", (quiz_id, teacher_id))
        quiz_to_delete_info = cursor_delete_quiz.fetchone()
        if not quiz_to_delete_info:
            flash("Quiz not found or you are not authorized to delete it. Deletion aborted.", "warning")
            return redirect(url_for('teacher_quizzes_list_page'))
        quiz_title_for_flash_msg = quiz_to_delete_info['title']
        
        # Proceed with deletion (ON DELETE CASCADE in DB schema should handle related data)
        cursor_delete_quiz.execute("DELETE FROM quizzes WHERE id = %s AND teacher_id = %s", (quiz_id, teacher_id))
        
        if cursor_delete_quiz.rowcount > 0:
            conn_delete_quiz.commit()
            flash(f"Quiz '{quiz_title_for_flash_msg}' and all its associated questions and attempts have been permanently deleted.", "success")
            app.logger.info(f"QUIZ_DELETE: Teacher {teacher_id} successfully deleted quiz {quiz_id} ('{quiz_title_for_flash_msg}').")
        else:
            # This case should ideally not be reached if the ownership check above passed
            conn_delete_quiz.rollback()
            flash(f"Could not delete quiz '{quiz_title_for_flash_msg}'. It might have already been deleted or an issue occurred.", "warning")
            app.logger.warning(f"QUIZ_DELETE_FAIL: Teacher {teacher_id} attempt to delete quiz {quiz_id} ('{quiz_title_for_flash_msg}') resulted in 0 rows affected post-ownership check.")
            
    except Error as e_db_delete_quiz:
        if conn_delete_quiz: conn_delete_quiz.rollback()
        app.logger.error(f"DELETE_QUIZ_DB_ERROR (QuizID {quiz_id}): {e_db_delete_quiz.msg}", exc_info=False)
        flash(f"A database error occurred while trying to delete quiz '{quiz_title_for_flash_msg}': {str(e_db_delete_quiz.msg)[:100]}.", "danger")
    except Exception as e_gen_delete_quiz:
        if conn_delete_quiz: conn_delete_quiz.rollback()
        app.logger.critical(f"DELETE_QUIZ_GENERAL_ERROR (QuizID {quiz_id}): {e_gen_delete_quiz}", exc_info=True)
        flash(f"An unexpected error occurred while deleting quiz '{quiz_title_for_flash_msg}'. Please try again.", "danger")
    finally:
        if cursor_delete_quiz: cursor_delete_quiz.close()
        if conn_delete_quiz and conn_delete_quiz.is_connected(): conn_delete_quiz.close()
    return redirect(url_for('teacher_quizzes_list_page'))

@app.route('/teacher/quizzes/<int:quiz_id>/questions/add', methods=['GET', 'POST'])
@teacher_required
def add_question_to_quiz_page(quiz_id):
    teacher_id = session['user_id']
    quiz_info_data = None; existing_quiz_questions = []
    # For repopulating form on validation error
    form_data_repopulate_q = request.form.to_dict() if request.method == 'POST' else {}
    # Specific handling for choices array and correct index repopulation
    choices_text_for_repop = [form_data_repopulate_q.get(f'choice_{i+1}_text', '') for i in range(4)] if request.method == 'POST' else ['','','','']
    correct_choice_idx_for_repop = int(form_data_repopulate_q.get('correct_choice_index', -1)) if request.method == 'POST' else -1
    points_for_repop = form_data_repopulate_q.get('points', '1') if request.method == 'POST' else '1'


    conn_fetch_q_page = None; cursor_fetch_q_page = None
    try:
        conn_fetch_q_page = get_db_connection()
        if not conn_fetch_q_page: raise Error("DB connection error fetching quiz info for questions page.")
        cursor_fetch_q_page = conn_fetch_q_page.cursor(dictionary=True)
        cursor_fetch_q_page.execute("SELECT id, title FROM quizzes WHERE id = %s AND teacher_id = %s", (quiz_id, teacher_id))
        quiz_info_data = cursor_fetch_q_page.fetchone()
        if not quiz_info_data:
            flash("Quiz not found or you are not authorized to manage its questions.", "warning")
            return redirect(url_for('teacher_quizzes_list_page'))
        cursor_fetch_q_page.execute("SELECT id, question_text, points FROM questions WHERE quiz_id = %s ORDER BY display_order ASC, id ASC", (quiz_id,))
        existing_quiz_questions = cursor_fetch_q_page.fetchall()
    except Error as e_fetch_q_data_err:
        app.logger.error(f"ADD_QUESTION_FETCH_ERROR (QuizID {quiz_id}): {e_fetch_q_data_err.msg}", exc_info=False)
        flash("An error occurred while loading quiz question data. Please try again.", "danger")
        return redirect(url_for('teacher_quizzes_list_page'))
    finally:
        if cursor_fetch_q_page: cursor_fetch_q_page.close()
        if conn_fetch_q_page and conn_fetch_q_page.is_connected(): conn_fetch_q_page.close()
    if not quiz_info_data: return redirect(url_for('teacher_quizzes_list_page')) # Should have been caught

    if request.method == 'POST':
        question_text_input = request.form.get('question_text', '').strip()
        # choices_text_repopulate and correct_choice_idx_repopulate already set from form_data
        points_input_str = request.form.get('points', '1').strip()
        
        validation_errors = []
        if not question_text_input or len(question_text_input) < 5: validation_errors.append("Question text is required (minimum 5 characters).")
        
        valid_choices_provided = [choice for choice in choices_text_for_repop if choice]
        if len(valid_choices_provided) < 2: validation_errors.append("At least two answer choices must be provided with text.")
        
        if not (0 <= correct_choice_idx_for_repop < 4) or not choices_text_for_repop[correct_choice_idx_for_repop]:
            validation_errors.append("A valid correct answer choice (with text) must be selected.")
        
        points_val = 1
        if points_input_str.isdigit() and int(points_input_str) >= 1:
            points_val = int(points_input_str)
        else: validation_errors.append("Points for the question must be a positive number.")

        if validation_errors:
            for e_msg in validation_errors: flash(e_msg, "danger")
            return render_template('teacher/add_question_to_quiz.html', 
                                   quiz=quiz_info_data, existing_questions=existing_quiz_questions,
                                   question_text=question_text_input, choices_text=choices_text_for_repop,
                                   correct_choice_index_submitted=correct_choice_idx_for_repop, points=points_val) # Pass validated/defaulted points
        
        conn_insert_new_q = None; cursor_insert_new_q = None
        try:
            conn_insert_new_q = get_db_connection()
            if not conn_insert_new_q: raise Error("Database connection failed while adding the new question.")
            cursor_insert_new_q = conn_insert_new_q.cursor()
            
            sql_insert_question = "INSERT INTO questions (quiz_id, question_text, question_type, points) VALUES (%s, %s, 'mc', %s)"
            cursor_insert_new_q.execute(sql_insert_question, (quiz_id, question_text_input, points_val))
            new_question_id_from_db = cursor_insert_new_q.lastrowid
            
            sql_insert_choice = "INSERT INTO choices (question_id, choice_text, is_correct) VALUES (%s, %s, %s)"
            for idx, choice_text_val in enumerate(choices_text_for_repop):
                if choice_text_val: # Only insert choices that have text
                    is_this_choice_correct = (idx == correct_choice_idx_for_repop)
                    cursor_insert_new_q.execute(sql_insert_choice, (new_question_id_from_db, choice_text_val, is_this_choice_correct))
            
            conn_insert_new_q.commit()
            flash(f"New question '{question_text_input[:30]}...' added successfully to quiz '{quiz_info_data['title']}'.", "success")
            return redirect(url_for('add_question_to_quiz_page', quiz_id=quiz_id)) # Refresh page
        except Error as e_db_add_q:
            if conn_insert_new_q: conn_insert_new_q.rollback()
            app.logger.error(f"ADD_QUESTION_DB_ERROR (QuizID {quiz_id}): {e_db_add_q.msg}", exc_info=False)
            flash(f"A database error occurred while adding the question: {str(e_db_add_q.msg)[:100]}.", "danger")
        except Exception as e_gen_add_q:
            if conn_insert_new_q: conn_insert_new_q.rollback()
            app.logger.critical(f"ADD_QUESTION_GENERAL_ERROR (QuizID {quiz_id}): {e_gen_add_q}", exc_info=True)
            flash("An unexpected error occurred while adding the question. Please try again.", "danger")
        finally:
            if cursor_insert_new_q: cursor_insert_new_q.close()
            if conn_insert_new_q and conn_insert_new_q.is_connected(): conn_insert_new_q.close()
        
        # If POST failed during DB op, re-render with submitted data
        return render_template('teacher/add_question_to_quiz.html', 
                               quiz=quiz_info_data, existing_questions=existing_quiz_questions,
                               question_text=question_text_input, choices_text=choices_text_for_repop,
                               correct_choice_index_submitted=correct_choice_idx_for_repop, points=points_val)
    
    # For GET request:
    return render_template('teacher/add_question_to_quiz.html', 
                           quiz=quiz_info_data, existing_questions=existing_quiz_questions,
                           question_text='', choices_text=['','','',''], # Empty for new question
                           correct_choice_index_submitted=-1, points=1) # Defaults for new question

@app.route('/teacher/quizzes/<int:quiz_id>/questions/<int:question_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_question_page(quiz_id, question_id):
    teacher_id = session['user_id']
    quiz_info_for_edit_q = None; question_to_edit_data = None; choices_for_edit_q_padded = []
    # For repopulating form on error (POST)
    submitted_question_text_val = request.form.get('question_text') if request.method == 'POST' else None
    submitted_points_val = request.form.get('points') if request.method == 'POST' else None


    conn_fetch_edit_q_data = None; cursor_fetch_edit_q_data = None
    try:
        conn_fetch_edit_q_data = get_db_connection()
        if not conn_fetch_edit_q_data: raise Error("DB connection error fetching question for edit.")
        cursor_fetch_edit_q_data = conn_fetch_edit_q_data.cursor(dictionary=True)
        
        # Verify quiz ownership and get quiz title
        cursor_fetch_edit_q_data.execute("SELECT id, title FROM quizzes WHERE id = %s AND teacher_id = %s", (quiz_id, teacher_id))
        quiz_info_for_edit_q = cursor_fetch_edit_q_data.fetchone()
        if not quiz_info_for_edit_q:
            flash("Quiz not found or you are not authorized to edit its questions.", "warning")
            return redirect(url_for('teacher_quizzes_list_page'))
        
        # Fetch the specific question to edit
        cursor_fetch_edit_q_data.execute("SELECT * FROM questions WHERE id = %s AND quiz_id = %s", (question_id, quiz_id))
        question_to_edit_data = cursor_fetch_edit_q_data.fetchone()
        if not question_to_edit_data:
            flash("Question not found or it does not belong to the specified quiz.", "warning")
            return redirect(url_for('add_question_to_quiz_page', quiz_id=quiz_id))

        # Fetch existing choices for this question
        cursor_fetch_edit_q_data.execute("SELECT id, choice_text, is_correct FROM choices WHERE question_id = %s ORDER BY id ASC", (question_id,))
        db_choices_for_question = cursor_fetch_edit_q_data.fetchall()
        
        # Pad choices to always have 4 for the form, pre-fill with DB data or submitted data if POST
        choices_for_edit_q_padded = []
        for i in range(4):
            if request.method == 'POST': # If POST, prioritize form data for repopulation
                choice_text_from_form = request.form.get(f'choice_{i+1}_text', '')
                is_correct_from_form = (str(i) == request.form.get('correct_choice_index'))
                # Use original ID if available from initial fetch for potential update-in-place logic (not used in delete/re-insert)
                original_choice_id = db_choices_for_question[i]['id'] if i < len(db_choices_for_question) else None
                choices_for_edit_q_padded.append({'id': original_choice_id, 'choice_text': choice_text_from_form, 'is_correct': is_correct_from_form})
            elif i < len(db_choices_for_question): # GET request, use DB data
                choices_for_edit_q_padded.append(db_choices_for_question[i].copy())
            else: # GET request, pad with empty choice
                choices_for_edit_q_padded.append({'id': None, 'choice_text': '', 'is_correct': False})

    except Error as e_fetch_edit_q_err:
        app.logger.error(f"EDIT_QUESTION_FETCH_ERROR (QID {question_id}, QuizID {quiz_id}): {e_fetch_edit_q_err.msg}", exc_info=False)
        flash("An error occurred while loading the question data for editing. Please try again.", "danger")
        return redirect(url_for('add_question_to_quiz_page', quiz_id=quiz_id))
    finally:
        if cursor_fetch_edit_q_data: cursor_fetch_edit_q_data.close()
        if conn_fetch_edit_q_data and conn_fetch_edit_q_data.is_connected(): conn_fetch_edit_q_data.close()
    
    if not quiz_info_for_edit_q or not question_to_edit_data: # Should have been caught by earlier checks
        return redirect(url_for('teacher_quizzes_list_page'))

    if request.method == 'POST':
        updated_question_text = request.form.get('question_text', '').strip()
        # choices are in choices_for_edit_q_padded if repopulating, or new_choices_texts if fresh POST
        updated_choices_texts_from_form = [request.form.get(f'choice_{i+1}_text', '').strip() for i in range(4)]
        updated_correct_choice_idx_str = request.form.get('correct_choice_index')
        updated_points_str = request.form.get('points', '1').strip()
        
        validation_errors = []
        if not updated_question_text or len(updated_question_text) < 5: validation_errors.append("Question text is required (minimum 5 characters).")
        
        valid_updated_choices = [choice for choice in updated_choices_texts_from_form if choice]
        if len(valid_updated_choices) < 2: validation_errors.append("At least two answer choices must be provided with text.")
        
        updated_correct_choice_idx = -1
        if updated_correct_choice_idx_str is None or not updated_correct_choice_idx_str.isdigit():
            validation_errors.append("A correct answer choice must be selected.")
        else:
            updated_correct_choice_idx = int(updated_correct_choice_idx_str)
            if not (0 <= updated_correct_choice_idx < 4) or not updated_choices_texts_from_form[updated_correct_choice_idx]:
                validation_errors.append("The selected correct answer choice is invalid or has no text.")
        
        updated_points_val = 1
        if updated_points_str.isdigit() and int(updated_points_str) >= 1:
            updated_points_val = int(updated_points_str)
        else: validation_errors.append("Points for the question must be a positive number.")

        if validation_errors:
            for e_msg in validation_errors: flash(e_msg, "danger")
            # choices_for_edit_q_padded should already contain the submitted values from the try-block
            return render_template('teacher/edit_question.html', 
                                   quiz=quiz_info_for_edit_q, question=question_to_edit_data, 
                                   choices=choices_for_edit_q_padded, # This was populated with form data
                                   submitted_question_text=updated_question_text, # For specific field repopulation if needed
                                   submitted_points=updated_points_val)

        conn_update_edited_q = None; cursor_update_edited_q = None
        try:
            conn_update_edited_q = get_db_connection()
            if not conn_update_edited_q: raise Error("Database connection failed while updating the question.")
            cursor_update_edited_q = conn_update_edited_q.cursor()
            
            # Update question text and points
            cursor_update_edited_q.execute("UPDATE questions SET question_text = %s, points = %s WHERE id = %s AND quiz_id = %s", 
                                 (updated_question_text, updated_points_val, question_id, quiz_id))
            
            # Delete old choices and insert new/updated ones
            cursor_update_edited_q.execute("DELETE FROM choices WHERE question_id = %s", (question_id,))
            sql_insert_updated_choice = "INSERT INTO choices (question_id, choice_text, is_correct) VALUES (%s, %s, %s)"
            for idx, choice_text_val in enumerate(updated_choices_texts_from_form):
                if choice_text_val: # Only insert choices that have text
                    is_this_choice_correct_updated = (idx == updated_correct_choice_idx)
                    cursor_update_edited_q.execute(sql_insert_updated_choice, (question_id, choice_text_val, is_this_choice_correct_updated))
            
            conn_update_edited_q.commit()
            flash(f"Question in quiz '{quiz_info_for_edit_q['title']}' has been updated successfully!", "success")
            return redirect(url_for('add_question_to_quiz_page', quiz_id=quiz_id))
        except Error as e_db_update_edited_q:
            if conn_update_edited_q: conn_update_edited_q.rollback()
            app.logger.error(f"EDIT_QUESTION_DB_ERROR (QID {question_id}): {e_db_update_edited_q.msg}", exc_info=False)
            flash(f"A database error occurred while updating the question: {str(e_db_update_edited_q.msg)[:100]}.", "danger")
        except Exception as e_gen_update_edited_q:
            if conn_update_edited_q: conn_update_edited_q.rollback()
            app.logger.critical(f"EDIT_QUESTION_GENERAL_ERROR (QID {question_id}): {e_gen_update_edited_q}", exc_info=True)
            flash("An unexpected error occurred while updating the question. Please try again.", "danger")
        finally:
            if cursor_update_edited_q: cursor_update_edited_q.close()
            if conn_update_edited_q and conn_update_edited_q.is_connected(): conn_update_edited_q.close()
        
        # If POST failed during DB op, re-render with submitted data (choices_for_edit_q_padded already has form data)
        return render_template('teacher/edit_question.html', 
                               quiz=quiz_info_for_edit_q, question=question_to_edit_data, 
                               choices=choices_for_edit_q_padded,
                               submitted_question_text=updated_question_text,
                               submitted_points=updated_points_val)
    
    # For GET request:
    # submitted_question_text_val and submitted_points_val will be None here
    return render_template('teacher/edit_question.html', 
                           quiz=quiz_info_for_edit_q, 
                           question=question_to_edit_data, 
                           choices=choices_for_edit_q_padded,
                           submitted_question_text=question_to_edit_data['question_text'], # Fill from DB for GET
                           submitted_points=question_to_edit_data['points']) # Fill from DB for GET


# --- 11. Teacher Profile Management ---
@app.route('/teacher/profile/edit', methods=['GET', 'POST'])
@teacher_required
def edit_teacher_profile():
    teacher_id = session['user_id']
    user_profile_data_from_db = None
    # For repopulating form: use POST data if available, else fetched DB data for GET
    form_data_for_template = request.form.to_dict() if request.method == 'POST' else {}
    current_profile_pic_url_for_template = None

    conn_fetch_profile = None; cursor_fetch_profile = None
    try:
        conn_fetch_profile = get_db_connection()
        if not conn_fetch_profile: raise Error("DB connection failed loading profile for edit.")
        cursor_fetch_profile = conn_fetch_profile.cursor(dictionary=True)
        cursor_fetch_profile.execute("""
            SELECT first_name, last_name, email, phone_number, country, bio, profile_picture_url 
            FROM users WHERE id = %s
        """, (teacher_id,))
        user_profile_data_from_db = cursor_fetch_profile.fetchone()

        if not user_profile_data_from_db:
            flash("Your user profile could not be found.", "danger")
            return redirect(url_for('teacher_dashboard_placeholder'))
        
        current_profile_pic_url_for_template = user_profile_data_from_db.get('profile_picture_url')
        if request.method == 'GET': # For GET, pre-fill form_data from DB
            form_data_for_template = user_profile_data_from_db.copy()

    except Error as e_fetch_profile_err:
        app.logger.error(f"EDIT_PROFILE_FETCH_ERROR (TeacherID {teacher_id}): {e_fetch_profile_err.msg}", exc_info=False)
        flash("An error occurred while loading your profile data. Please try again.", "danger")
        return redirect(url_for('teacher_dashboard_placeholder'))
    finally:
        if cursor_fetch_profile: cursor_fetch_profile.close()
        if conn_fetch_profile and conn_fetch_profile.is_connected(): conn_fetch_profile.close()
    
    if not user_profile_data_from_db: return redirect(url_for('teacher_dashboard_placeholder')) # Should be caught

    if request.method == 'POST':
        # form_data_for_template already contains POST data
        first_name_updated = request.form.get('first_name', '').strip()
        last_name_updated = request.form.get('last_name', '').strip()
        phone_number_updated = request.form.get('phone_number', '').strip()
        country_updated = request.form.get('country', '').strip()
        bio_updated = request.form.get('bio', '').strip()
        profile_picture_file_obj = request.files.get('profile_picture')

        validation_errors = []
        if not first_name_updated or len(first_name_updated) < 2: validation_errors.append("First name (min 2 characters) is required.")
        if not last_name_updated or len(last_name_updated) < 2: validation_errors.append("Last name (min 2 characters) is required.")
        if phone_number_updated and not is_valid_phone_format_simple(phone_number_updated):
            validation_errors.append("Invalid phone number format (7-15 digits).")
        if len(bio_updated) > 1000: validation_errors.append("Bio should not exceed 1000 characters.")
        # Country can be any string for now, or add dropdown validation later

        new_profile_pic_db_path_to_save = current_profile_pic_url_for_template # Default to old or existing
        path_to_old_profile_pic_on_disk = None
        path_to_newly_saved_pic_on_disk = None # For potential rollback

        if profile_picture_file_obj and profile_picture_file_obj.filename != '':
            if allowed_file(profile_picture_file_obj.filename, ALLOWED_EXTENSIONS_IMAGES):
                original_pic_filename = secure_filename(profile_picture_file_obj.filename)
                pic_extension = original_pic_filename.rsplit('.', 1)[1].lower() if '.' in original_pic_filename else ''
                # Create a more unique filename
                unique_pic_filename = f"profile_{teacher_id}_{uuid.uuid4().hex[:10]}.{pic_extension}"
                
                path_to_newly_saved_pic_on_disk = os.path.join(app.config['UPLOAD_FOLDER_PROFILE_PICS'], unique_pic_filename)
                new_profile_pic_db_path_to_save = os.path.join('uploads/profile_pics', unique_pic_filename).replace('\\', '/')
                
                if current_profile_pic_url_for_template: # Path to old pic for deletion
                    path_to_old_profile_pic_on_disk = os.path.join(app.config.get('UPLOAD_FOLDER_BASE', 'static'), current_profile_pic_url_for_template.replace('/', os.sep))
            else:
                validation_errors.append(f"Invalid profile picture file type. Allowed: {', '.join(ALLOWED_EXTENSIONS_IMAGES)}.")
        
        if validation_errors:
            for e_msg in validation_errors: flash(e_msg, "danger")
            # form_data_for_template already has submitted data
            return render_template('teacher/edit_profile.html', 
                                   form_data=form_data_for_template, 
                                   current_profile_pic_url=current_profile_pic_url_for_template)

        # Proceed with file saving and DB update
        conn_update_profile_db = None; cursor_update_profile_db = None
        new_pic_saved_this_request = False
        try:
            # Save new profile picture file if one was uploaded and is different
            if profile_picture_file_obj and profile_picture_file_obj.filename != '' and new_profile_pic_db_path_to_save != current_profile_pic_url_for_template:
                ensure_directory_exists(app.config['UPLOAD_FOLDER_PROFILE_PICS'], "Profile Pictures Upload Folder") # Ensure again
                profile_picture_file_obj.save(path_to_newly_saved_pic_on_disk)
                new_pic_saved_this_request = True
                app.logger.info(f"PROFILE_PIC_UPLOAD: New picture saved for teacher {teacher_id} at {path_to_newly_saved_pic_on_disk}")
            
            conn_update_profile_db = get_db_connection()
            if not conn_update_profile_db: raise Error("Database connection failed during profile update.")
            cursor_update_profile_db = conn_update_profile_db.cursor()
            sql_update_user_profile = """
                UPDATE users SET first_name = %s, last_name = %s, phone_number = %s, 
                                 country = %s, bio = %s, profile_picture_url = %s,
                                 updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """
            data_for_profile_update = (
                first_name_updated, last_name_updated, phone_number_updated or None, 
                country_updated or None, bio_updated or None, new_profile_pic_db_path_to_save,
                teacher_id
            )
            cursor_update_profile_db.execute(sql_update_user_profile, data_for_profile_update)
            conn_update_profile_db.commit()
            
            # If DB update successful & new pic saved, delete old pic from disk
            if new_pic_saved_this_request and path_to_old_profile_pic_on_disk and os.path.exists(path_to_old_profile_pic_on_disk):
                try:
                    os.remove(path_to_old_profile_pic_on_disk)
                    app.logger.info(f"PROFILE_PIC_DELETE_OLD: Deleted old picture {path_to_old_profile_pic_on_disk}")
                except Exception as e_remove_old:
                    app.logger.error(f"PROFILE_PIC_DELETE_OLD_ERROR: Failed to delete old picture {path_to_old_profile_pic_on_disk}: {e_remove_old}")
            
            # Update session username if first_name changed
            if first_name_updated != user_profile_data_from_db.get('first_name'):
                session['username'] = first_name_updated # Or combined name as per your preference

            flash("Your profile has been updated successfully!", "success")
            return redirect(url_for('edit_teacher_profile')) # Redirect to same page to see changes or to dashboard

        except Exception as e_update_profile_proc: # Catch DB errors or file system errors
            if conn_update_profile_db: conn_update_profile_db.rollback()
            
            # If a new picture was saved but DB update failed, attempt to delete the newly saved picture
            if new_pic_saved_this_request and path_to_newly_saved_pic_on_disk and os.path.exists(path_to_newly_saved_pic_on_disk):
                try:
                    os.remove(path_to_newly_saved_pic_on_disk)
                    app.logger.warning(f"PROFILE_PIC_ROLLBACK_NEW: Deleted newly saved picture {path_to_newly_saved_pic_on_disk} due to DB/process error.")
                except Exception as e_remove_new_rollback:
                    app.logger.error(f"PROFILE_PIC_ROLLBACK_NEW_ERROR: Could not delete newly saved picture during error rollback: {e_remove_new_rollback}")

            error_detail = str(e_update_profile_proc)
            if isinstance(e_update_profile_proc, Error): error_detail = f"DB_ERRNO_{e_update_profile_proc.errno}: {e_update_profile_proc.msg}"
            
            app.logger.error(f"EDIT_PROFILE_PROCESS_ERROR (TeacherID {teacher_id}): {error_detail}", exc_info=True)
            flash(f"An error occurred while updating your profile: {str(e_update_profile_proc)[:150]}. Please try again.", "danger")
        finally:
            if cursor_update_profile_db: cursor_update_profile_db.close()
            if conn_update_profile_db and conn_update_profile_db.is_connected(): conn_update_profile_db.close()
        
        # If POST failed, re-render with submitted data (form_data_for_template already has POST data)
        return render_template('teacher/edit_profile.html', 
                               form_data=form_data_for_template, 
                               current_profile_pic_url=current_profile_pic_url_for_template) # Show original pic if update failed

    # For GET request: form_data_for_template was filled from user_profile_data_from_db
    return render_template('teacher/edit_profile.html', 
                           form_data=form_data_for_template, 
                           current_profile_pic_url=current_profile_pic_url_for_template)


# --- 12. Placeholder Dashboard Routes & Language Switch ---
@app.route('/student/dashboard')
@student_required
def student_dashboard_placeholder():
    username = session.get('username', 'Student User')
    return render_template('student/dashboard.html', username=username, is_minimal_layout=False)

@app.route('/teacher/dashboard')
@teacher_required
def teacher_dashboard_placeholder():
    username = session.get('username', 'Teacher User')
    return render_template('teacher/dashboard.html', username=username, is_minimal_layout=False)

@app.route('/switch_lang/<lang_code>')
def switch_lang(lang_code_requested):
    supported_languages_list = ['en', 'ar']
    if lang_code_requested in supported_languages_list:
        session['current_lang'] = lang_code_requested
        flash(f"Language preference updated to {'English' if lang_code_requested == 'en' else 'العربية'}.", "info")
    else:
        flash(f"Sorry, the language '{lang_code_requested}' is not supported at this time.", "warning")
    
    # Redirect back to the page the user was on, or to home as a fallback
    previous_page_url = request.referrer
    if previous_page_url and (previous_page_url.startswith('/') or previous_page_url.startswith(request.host_url)):
        return redirect(previous_page_url)
    return redirect(url_for('home'))

# --- 13. Application Runner and Logger Setup ---
if __name__ == '__main__':
    # Configure basic logging (console output primarily for startup messages before file handler)
    log_level_config_str = os.getenv('FLASK_LOG_LEVEL', 'INFO' if not app.debug else 'DEBUG').upper()
    effective_log_level = getattr(logging, log_level_config_str, logging.INFO) # Default if invalid
    
    # Basic config for early messages
    logging.basicConfig(level=effective_log_level, format='%(asctime)s %(levelname)s: %(name)s - %(message)s [in %(pathname)s:%(lineno)d]')

    # Setup more detailed file logger for non-debug mode
    if not app.debug and not os.environ.get("WERKZEUG_RUN_MAIN"): # Avoid duplicate logs with Flask reloader
        log_directory = 'logs'
        ensure_directory_exists(log_directory, "Application Logs Directory") # Use the helper
        application_log_file_path = os.path.join(log_directory, 'ektbariny_app.log')
        
        try:
            # Rotating file handler to manage log file size
            main_file_handler = RotatingFileHandler(
                application_log_file_path, 
                maxBytes=25*1024*1024,  # 25 MB per file
                backupCount=7,          # Keep 7 backup log files
                encoding='utf-8'
            )
            # More detailed log format for file logs
            file_formatter = logging.Formatter(
                '%(asctime)s %(levelname)-8s [%(threadName)s] %(module)s.%(funcName)s:%(lineno)d - %(message)s'
            )
            main_file_handler.setFormatter(file_formatter)
            main_file_handler.setLevel(logging.INFO) # Set level for file handler (e.g., INFO and above)
            
            # Add this handler to Flask's app.logger
            # Ensure no duplicate handlers of the same type if already configured by basicConfig
            if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
                app.logger.addHandler(main_file_handler)
            
            app.logger.setLevel(logging.INFO) # Set overall app logger level for production/non-debug
            app.logger.info("--- Ektbariny Application Starting Up (File Logger Configured and Active) ---")
        except Exception as e_logger_config:
            logging.error(f"CRITICAL: Failed to initialize file logger at '{application_log_file_path}': {e_logger_config}", exc_info=True)
            print(f"!!! [LOGGER_CRITICAL_ERROR] File logger initialization failed: {e_logger_config} !!!")
            # Application will continue with console logging from basicConfig

    elif app.debug:
        app.logger.setLevel(logging.DEBUG) # Ensure Flask's logger is at DEBUG level in debug mode
        app.logger.debug("--- Ektbariny Application Starting in DEBUG Mode (Console Logger Active at DEBUG Level) ---")

    # Application startup sequence
    try:
        app.logger.info(f"--- [APP_INIT] Initializing Ektbariny Application. App Name: {app.name}, Time: {datetime.now()} ---")
        
        # Database and Table Creation/Verification
        if os.getenv('CREATE_TABLES_ON_STARTUP', 'True').lower() in ('true', '1', 'yes'):
            app.logger.info("--- [DB_SETUP_TASK] CREATE_TABLES_ON_STARTUP is True. Initiating table creation/verification... ---")
            if not create_tables(): # create_tables should return True on success
                app.logger.critical("!!! [DB_SETUP_CRITICAL_FAILURE] Database or table creation/verification FAILED. Application may not function as expected. !!!")
                # Depending on policy, you might exit: import sys; sys.exit("Critical Database Setup Failed.")
            else:
                app.logger.info("--- [DB_SETUP_TASK] Database and tables setup process completed (or structures already exist). ---")
        else:
            app.logger.info("--- [DB_SETUP_TASK] Skipping automatic table creation/verification based on 'CREATE_TABLES_ON_STARTUP' environment variable. ---")
        
        # Configure Flask server host and port from environment variables
        server_host = os.getenv('FLASK_HOST', '0.0.0.0') # Default to listen on all available interfaces
        try:
            server_port = int(os.getenv('FLASK_PORT', '5001')) # Default port
        except ValueError:
            app.logger.warning(f"Invalid FLASK_PORT value '{os.getenv('FLASK_PORT')}'. Defaulting to port 5001.")
            server_port = 5001
        
        app.logger.info(f"--- [FLASK_SERVER_START] Attempting to start Flask development server on http://{server_host}:{server_port}/ (Application Debug Mode: {app.debug}) ---")
        app.run(host=server_host, port=server_port, debug=app.debug) # app.debug is controlled by FLASK_DEBUG env var

    except SystemExit as e_system_exit:
        app.logger.warning(f"Application terminated via SystemExit with code {e_system_exit.code}.", exc_info=True)
    except OSError as e_os_error: # Typically for "address already in use"
        app.logger.critical(f"OSError during application startup (Is port {server_port} already in use?): {e_os_error}", exc_info=True)
    except Exception as e_general_startup_error: # Catch-all for other startup errors
        app.logger.critical(f"FATAL UNHANDLED EXCEPTION during application startup sequence: {e_general_startup_error}", exc_info=True)
    finally:
        # This message logs when the Flask app or script execution finishes
        shutdown_log_message = f"-------- Ektbariny Application Is Shutting Down (Timestamp: {datetime.now()}) --------"
        # Check if app.logger and its file handler are still valid before logging
        if hasattr(app, 'logger') and app.logger.handlers and any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
            app.logger.info(shutdown_log_message)
        else: # Fallback to print if specific file logger isn't confirmed
            print(shutdown_log_message)