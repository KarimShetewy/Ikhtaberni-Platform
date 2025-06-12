# app.py (النسخة النهائية المصححة والمهيكلة)

import os
from datetime import datetime, timedelta
import re
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import uuid
import random
import string

# --- 1. Load Environment Variables ---
load_dotenv()

# --- 2. Flask Application Setup ---
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', "a_very_strong_and_unique_fallback_secret_key_!@#Ektbariny")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=int(os.getenv('SESSION_LIFETIME_DAYS', '7')))
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_MB', '50')) * 1024 * 1024

# --- File Upload Settings & Directory Creation ---
UPLOAD_FOLDER_BASE = 'static/uploads'
UPLOAD_FOLDER_VIDEOS = os.path.join(UPLOAD_FOLDER_BASE, 'videos')
UPLOAD_FOLDER_QUESTION_IMAGES = os.path.join(UPLOAD_FOLDER_BASE, 'question_images')
UPLOAD_FOLDER_PROFILE_PICS = os.path.join(UPLOAD_FOLDER_BASE, 'profile_pics')

def ensure_directory_exists(directory_path, directory_name_for_log="Directory"):
    """Creates a directory if it doesn't exist, with logging."""
    if not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path, exist_ok=True)
            log_msg = f"FS_SETUP: Successfully created {directory_name_for_log}: {directory_path}"
            if hasattr(app, 'logger') and app.logger: app.logger.info(log_msg)
        except OSError as e:
            err_msg = f"FS_SETUP_CRITICAL_ERROR: Could not create {directory_name_for_log} at {directory_path}: {e}"
            if hasattr(app, 'logger') and app.logger: app.logger.critical(err_msg, exc_info=True)
    else:
        if hasattr(app, 'logger') and app.logger:
             app.logger.debug(f"FS_SETUP: {directory_name_for_log} already exists: {directory_path}")

ensure_directory_exists(UPLOAD_FOLDER_BASE, "Base Upload Folder")
ensure_directory_exists(UPLOAD_FOLDER_VIDEOS, "Videos Upload Folder")
ensure_directory_exists(UPLOAD_FOLDER_QUESTION_IMAGES, "Question Images Upload Folder")
ensure_directory_exists(UPLOAD_FOLDER_PROFILE_PICS, "Profile Pictures Upload Folder")

ALLOWED_EXTENSIONS_VIDEOS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}
ALLOWED_EXTENSIONS_IMAGES = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
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
    conn = None # Initialize conn to None to prevent NameError in finally block
    try:
        conn_params = {
            'host': DB_HOST, 'user': DB_USER, 'password': DB_PASSWORD,
            'charset': 'utf8mb4', 'collation': 'utf8mb4_unicode_ci',
            'autocommit': False
        }
        if include_db_name and DB_NAME:
            conn_params['database'] = DB_NAME

        conn = mysql.connector.connect(**conn_params)
        return conn
    except Error as e:
        log_msg = (f"MySQL Connection Error! Host:'{DB_HOST}', "
                   f"DB:'{DB_NAME if include_db_name else 'N/A'}'. "
                   f"ErrNo:{e.errno}, SQLState:{e.sqlstate}, Msg:{e.msg}")
        if hasattr(app, 'logger') and app.logger:
            app.logger.critical(log_msg, exc_info=False)
        else:
            print(f"!!! [{log_msg}] !!!")
        return None

# --- 5. Database and Tables Creation Function ---
def create_tables():
    """Creates database and all necessary tables from the predefined SQL schema."""
    full_db_schema_sql = """
    CREATE DATABASE IF NOT EXISTS `ektbariny_db` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    USE `ektbariny_db`;
    CREATE TABLE IF NOT EXISTS `users` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `username` VARCHAR(100) NOT NULL, `email` VARCHAR(120) UNIQUE NOT NULL,
      `password_hash` VARCHAR(255) NOT NULL, `role` ENUM('student', 'teacher') NOT NULL, `first_name` VARCHAR(50) NULL,
      `last_name` VARCHAR(50) NULL, `phone_number` VARCHAR(20) UNIQUE NULL,
      `country` VARCHAR(100) NULL,
      `profile_picture_url` VARCHAR(255) NULL, `bio` TEXT NULL,
      `free_video_uploads_remaining` TINYINT UNSIGNED DEFAULT 3, `free_quiz_creations_remaining` TINYINT UNSIGNED DEFAULT 3,
      `is_active` BOOLEAN DEFAULT TRUE, `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      `wallet_balance` DECIMAL(10, 2) DEFAULT 0.00,
      `otp_code` VARCHAR(8) NULL,
      `otp_expiry` TIMESTAMP NULL
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
      INDEX `idx_subscription_student` (`student_id` ASC),
      INDEX `idx_subscription_teacher` (`teacher_id` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `student_watched_videos` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `student_id` INT NOT NULL, `video_id` INT NOT NULL, `teacher_id` INT NOT NULL,
      `watched_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT `fk_watched_student` FOREIGN KEY (`student_id`) REFERENCES `users`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `fk_watched_video` FOREIGN KEY (`video_id`) REFERENCES `videos`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `fk_watched_teacher_convenience` FOREIGN KEY (`teacher_id`) REFERENCES `users`(`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      UNIQUE INDEX `uq_student_video_watch` (`student_id` ASC, `video_id` ASC),
      INDEX `idx_watched_student` (`student_id` ASC),
      INDEX `idx_watched_video` (`video_id` ASC),
      INDEX `idx_watched_teacher` (`teacher_id` ASC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    CREATE TABLE IF NOT EXISTS `platform_payments` (
      `id` INT AUTO_INCREMENT PRIMARY KEY, `teacher_id` INT NOT NULL, `payment_for_item_id` INT NULL,
      `payment_for_type` ENUM('extra_videos_package', 'extra_quizzes_package', 'featured_listing', 'other') NULL,
      `description` VARCHAR(255) NULL, `amount` DECIMAL(10,2) NOT NULL, `currency_code` VARCHAR(3) DEFAULT 'USD',
      `payment_date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP, `transaction_id` VARCHAR(255) NOT NULL UNIQUE,
      `payment_gateway` VARCHAR(50) NULL, `status` ENUM('pending', 'processing', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
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
    conn_init = None; cursor_init = None
    try:
        conn_init = get_db_connection(include_db_name=False)
        if conn_init is None:
            if hasattr(app, 'logger') and app.logger: app.logger.critical("DB_INIT_CRITICAL: Cannot connect to MySQL server. Aborting schema setup.")
            return False
        cursor_init = conn_init.cursor()
        if hasattr(app, 'logger') and app.logger: app.logger.info("DB_INIT: Executing database schema script...")
        for result in cursor_init.execute(full_db_schema_sql, multi=True):
            if hasattr(app, 'logger') and app.logger:
                log_msg_part = f"Statement: {result.statement[:100]}..." if result.statement else "No statement info"
                if result.with_rows:
                    _ = result.fetchall() 
                    app.logger.debug(f"DB_INIT_STATEMENT: {log_msg_part} (rows fetched).")
                else:
                    app.logger.debug(f"DB_INIT_STATEMENT: {log_msg_part} (Affected: {result.rowcount})")
        conn_init.commit()
        if hasattr(app, 'logger') and app.logger: app.logger.info(f"DB_INIT: Database '{DB_NAME}' schema setup/verification completed.")
        return True
    except Error as db_init_error:
        err_log_msg = f"DB_INIT_SQL_ERROR: During schema setup: {db_init_error.errno} - {db_init_error.msg}"
        if hasattr(app, 'logger') and app.logger: app.logger.error(err_log_msg, exc_info=False)
        if conn_init: conn_init.rollback()
        return False
    except Exception as e_general_init:
        err_log_msg_gen = f"DB_INIT_UNEXPECTED_ERROR: During schema setup: {e_general_init}"
        if hasattr(app, 'logger') and app.logger: app.logger.critical(err_log_msg_gen, exc_info=True)
        if conn_init: conn_init.rollback()
        return False
    finally:
        if cursor_init: cursor_init.close()
        if 'conn_init' in locals() and conn_init and conn_init.is_connected(): 
            conn_init.close()

# --- 6. Helper Functions & Context Processors ---
@app.context_processor
def inject_global_vars_for_templates():
    user_selected_language = session.get('current_lang', 'en')
    current_user_info = None
    user_id = session.get('user_id')
    if user_id:
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, username, email, role, first_name, last_name, phone_number, profile_picture_url FROM users WHERE id = %s", (user_id,))
                user_data = cursor.fetchone() 
                if user_data:
                    current_user_info = {
                        'id': user_data['id'],
                        'username': user_data.get('first_name') or user_data.get('username', 'User'),
                        'role': user_data['role'],
                        'email': user_data.get('email'),
                        'phone_number': user_data.get('phone_number'),
                        'profile_picture_url': user_data.get('profile_picture_url') if user_data.get('profile_picture_url') else 'images/default_profile.png'
                    }
                session['profile_picture_url'] = current_user_info['profile_picture_url'] if current_user_info else 'images/default_profile.png'
        except Error as e:
            if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error fetching user data for context processor: {e}", exc_info=True)
        finally:
            if cursor: cursor.close()
            if conn and conn.is_connected(): conn.close()

    return {
        'now': datetime.utcnow(),
        'is_minimal_layout': False, 
        'current_lang': user_selected_language,
        'current_user': current_user_info, 
        'user_role': session.get('role'), 
        'logged_in_user_id': user_id 
    }

def is_valid_email_format(email_address):
    if not email_address: return False
    pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    return bool(pattern.match(email_address))

def is_valid_phone_format_simple(phone_number_str):
    if not phone_number_str: return True 
    cleaned_phone = re.sub(r'\D', '', phone_number_str) 
    return bool(7 <= len(cleaned_phone) <= 15)

def allowed_file(filename_str, allowed_extensions_set):
    return '.' in filename_str and filename_str.rsplit('.', 1)[1].lower() in allowed_extensions_set

# --- 7. Decorators for Route Protection ---
def login_required(route_function):
    @wraps(route_function)
    def decorated_view_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("You must be logged in to access this page. Please log in.", "info")
            session['next_url'] = request.url 
            return redirect(url_for('login_page')) 
        return route_function(*args, **kwargs)
    return decorated_view_function

def teacher_required(route_function):
    @wraps(route_function)
    @login_required 
    def decorated_view_function(*args, **kwargs):
        if session.get('role') != 'teacher':
            flash("Access Denied: This page is restricted to teachers only.", "danger")
            if session.get('role') == 'student':
                 return redirect(url_for('student_dashboard_placeholder')) 
            return redirect(url_for('home'))
        return route_function(*args, **kwargs)
    return decorated_view_function

def student_required(route_function):
    @wraps(route_function)
    @login_required 
    def decorated_view_function(*args, **kwargs):
        if session.get('role') != 'student':
            flash("Access Denied: This page is restricted to students only.", "danger")
            if session.get('role') == 'teacher':
                return redirect(url_for('teacher_dashboard_placeholder')) 
            return redirect(url_for('home'))
        return route_function(*args, **kwargs)
    return decorated_view_function

# --- OTP Helper Functions ---
def generate_otp_for_user(user_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        generated_otp = "".join(random.choices(string.digits, k=8))
        otp_expiry_time = datetime.utcnow() + timedelta(minutes=10)
        cursor.execute("UPDATE users SET otp_code = %s, otp_expiry = %s WHERE id = %s",
                       (generated_otp, otp_expiry_time, user_id))
        conn.commit()
        return generated_otp
    except Error as e:
        if conn: conn.rollback()
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error generating OTP for user {user_id}: {e}", exc_info=True)
        return None
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

def is_otp_valid_for_user(user_id, provided_otp):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE id = %s AND otp_code = %s AND otp_expiry > %s AND is_active = TRUE", 
                       (user_id, provided_otp, datetime.utcnow()))
        user_otp_data = cursor.fetchone() 
        if user_otp_data:
            return True
        return False
    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error verifying OTP for user {user_id}: {e}", exc_info=True)
        return False
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

def clear_otp_for_user(user_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET otp_code = NULL, otp_expiry = NULL WHERE id = %s", (user_id,))
        conn.commit()
        return True
    except Error as e:
        if conn: conn.rollback()
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error clearing OTP for user {user_id}: {e}", exc_info=True)
        return False
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- 8. Application Routes (Authentication and Main Navigation) ---
@app.route('/')
def home():
    """Renders the main home page of the application."""
    return render_template('index.html') 

@app.route('/choose_signup_role', methods=['GET', 'POST'])
def choose_signup_role():
    """Page for users to select their role (student or teacher) before signing up."""
    if request.method == 'POST':
        selected_role = request.form.get('role')
        if selected_role not in ['student', 'teacher']:
            flash("Invalid role selected. Please choose either 'Student' or 'Teacher'.", "danger")
            return render_template('auth/choose_role_signup.html') 
        session['signup_attempt_role'] = selected_role
        flash(f"You are signing up as a {selected_role.capitalize()}. Please complete your registration details below.", "info")
        return redirect(url_for('signup_actual_form_page'))
    session.pop('signup_attempt_role', None) 
    return render_template('auth/choose_role_signup.html') 

@app.route('/signup/form', methods=['GET', 'POST'])
def signup_actual_form_page():
    """Handles the actual user registration form after role selection."""
    user_role_for_signup = session.get('signup_attempt_role')
    if not user_role_for_signup:
        flash("Role selection is missing or your session has expired. Please choose your role again to proceed.", "warning")
        return redirect(url_for('choose_signup_role'))

    form_data_repopulate = request.form.to_dict() if request.method == 'POST' else {}

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone_number_input = request.form.get('phone_number', '').strip()
        password_input = request.form.get('password', '') 
        confirm_password_input = request.form.get('confirm_password', '')
        country_selected = request.form.get('country', '').strip()
        agreed_to_terms = request.form.get('agree_terms')

        validation_errors = []
        if not first_name or len(first_name) < 2: validation_errors.append("First name is required (minimum 2 characters).")
        if not last_name or len(last_name) < 2: validation_errors.append("Last name is required (minimum 2 characters).")
        if not email or not is_valid_email_format(email): validation_errors.append("A valid email address is required.") 
        
        if phone_number_input: 
            if not is_valid_phone_format_simple(phone_number_input): 
                validation_errors.append("Phone number format is invalid. Please enter 7-15 digits.")

        if not password_input or len(password_input) < 8: validation_errors.append("Password must be at least 8 characters long.")
        if password_input != confirm_password_input: validation_errors.append("The entered passwords do not match.")
        if not country_selected: validation_errors.append("Please select your country.")
        if not agreed_to_terms: validation_errors.append("You must agree to the Terms of Service and Privacy Policy to create an account.")

        if validation_errors:
            for error_message in validation_errors: flash(error_message, "danger")
            return render_template('auth/signup_actual_form.html', role=user_role_for_signup, is_minimal_layout=True, form_data=form_data_repopulate)

        db_conn_signup = None; db_cursor_signup = None
        try:
            db_conn_signup = get_db_connection()
            if db_conn_signup is None:
                raise Error("Database connection failed. Cannot register at this moment.")
            
            db_cursor_signup = db_conn_signup.cursor(dictionary=True)
            db_cursor_signup.execute("SELECT id FROM users WHERE email = %s", (email,))
            _ = db_cursor_signup.fetchone() 
            if _:
                flash(f"The email address '{email}' is already associated with an existing account. Please log in or use a different email.", "warning")
                return render_template('auth/signup_actual_form.html', role=user_role_for_signup, is_minimal_layout=True, form_data=form_data_repopulate)

            if phone_number_input: 
                db_cursor_signup.execute("SELECT id FROM users WHERE phone_number = %s", (phone_number_input,))
                _ = db_cursor_signup.fetchone() 
                if _:
                    flash(f"The phone number '{phone_number_input}' is already in use by another account.", "warning")
                    return render_template('auth/signup_actual_form.html', role=user_role_for_signup, is_minimal_layout=True, form_data=form_data_repopulate)

            hashed_user_password = generate_password_hash(password_input)
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
            db_conn_signup.commit() 
            
            session.pop('signup_attempt_role', None) 
            flash(f"Congratulations, {first_name}! Your account as a {user_role_for_signup.capitalize()} has been successfully created. You can now log in.", "success")
            return redirect(url_for('login_page'))
        
        except Error as db_signup_err:
            if db_conn_signup: db_conn_signup.rollback()
            if hasattr(app, 'logger') and app.logger: app.logger.error(f"SIGNUP_DB_ERROR for email {email}: {db_signup_err.errno} - {db_signup_err.msg}", exc_info=False)
            flash("A database error occurred during registration. Please try again later or contact support. (Code: REG-DBE)", "danger")
        except Exception as general_signup_err: 
            if db_conn_signup: db_conn_signup.rollback()
            if hasattr(app, 'logger') and app.logger: app.logger.critical(f"SIGNUP_GENERAL_ERROR: An unexpected error occurred: {general_signup_err}", exc_info=True)
            flash("An unexpected error occurred during the registration process. Please try again. (Code: REG-GEN)", "danger")
        finally:
            if db_cursor_signup: db_cursor_signup.close()
            if db_conn_signup and db_conn_signup.is_connected(): db_conn_signup.close()
        
        return render_template('auth/signup_actual_form.html', role=user_role_for_signup, is_minimal_layout=True, form_data=form_data_repopulate)

    return render_template('auth/signup_actual_form.html', role=user_role_for_signup, is_minimal_layout=True, form_data=form_data_repopulate)


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    form_data_repopulate = {}
    next_redirect_url_from_session = session.pop('next_url', None) 
    next_redirect_url_from_args = request.args.get('next')
    next_redirect_url_from_form = request.form.get('next')
    
    next_redirect_url = next_redirect_url_from_form or next_redirect_url_from_session or next_redirect_url_from_args or None

    if request.method == 'POST':
        login_identifier = request.form.get('login_identifier', '').strip() 
        password_input = request.form.get('password', '')
        form_data_repopulate = {'login_identifier': login_identifier} 
    else: 
        login_identifier_from_otp_prefill = session.get('login_identifier_for_otp_prefill', '')
        form_data_repopulate = {'login_identifier': login_identifier_from_otp_prefill}


    if request.method == 'POST':
        validation_errors = []
        is_phone_login_attempt = login_identifier.replace('+', '').isdigit() and len(login_identifier.replace('+', '')) >= 7

        if not login_identifier:
            validation_errors.append("Email or Phone Number is required.")
        elif not is_phone_login_attempt and not is_valid_email_format(login_identifier.lower()):
            validation_errors.append("A valid email address is required if not entering a phone number.")
        elif is_phone_login_attempt and not is_valid_phone_format_simple(login_identifier): 
            validation_errors.append("A valid phone number is required (7-15 digits, optionally starting with +).")
            
        if not password_input: 
            validation_errors.append("Password is required.")

        if validation_errors:
            for error_message in validation_errors: flash(error_message, "danger")
            return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_repopulate, next=next_redirect_url)

        db_conn_login = None; db_cursor_login = None
        try:
            db_conn_login = get_db_connection()
            if db_conn_login is None:
                raise Error("Database connection unavailable. Please try again shortly.")
            
            db_cursor_login = db_conn_login.cursor(dictionary=True)
            user_record_from_db = None
            if is_phone_login_attempt:
                sql_query = """
                    SELECT id, username, email, password_hash, role, first_name, last_name, phone_number, profile_picture_url
                    FROM users WHERE phone_number = %s AND is_active = TRUE
                """
                query_params = (login_identifier,)
            else: 
                sql_query = """
                    SELECT id, username, email, password_hash, role, first_name, last_name, phone_number, profile_picture_url
                    FROM users WHERE email = %s AND is_active = TRUE
                """
                query_params = (login_identifier.lower(),)

            db_cursor_login.execute(sql_query, query_params)
            user_record_from_db = db_cursor_login.fetchone() 

            if user_record_from_db and check_password_hash(user_record_from_db['password_hash'], password_input):
                session.clear() 
                session['user_id'] = user_record_from_db['id']
                session['username'] = user_record_from_db.get('first_name') or user_record_from_db.get('username', 'Valued User')
                session['role'] = user_record_from_db['role']
                session['email'] = user_record_from_db.get('email')
                session['phone_number_session'] = user_record_from_db.get('phone_number')
                session['profile_picture_url'] = user_record_from_db.get('profile_picture_url') 
                session.permanent = True 
                
                flash(f"Login successful! Welcome back, {session['username']}.", "success")
                
                session.pop('login_identifier_for_otp_prefill', None) 

                if next_redirect_url and (next_redirect_url.startswith('/') or next_redirect_url.startswith(request.host_url)):
                    return redirect(next_redirect_url)
                
                if user_record_from_db['role'] == 'teacher':
                    return redirect(url_for('teacher_dashboard_placeholder'))
                elif user_record_from_db['role'] == 'student':
                    return redirect(url_for('student_dashboard_placeholder'))
                else: 
                    if hasattr(app, 'logger') and app.logger: app.logger.warning(f"User {user_record_from_db['id']} logged in with an unexpected role: {user_record_from_db['role']}")
                    return redirect(url_for('home'))
            else:
                flash("Invalid identifier or password, or your account may be inactive. Please check and try again.", "danger")
        
        except Error as db_login_err:
            if hasattr(app, 'logger') and app.logger: app.logger.error(f"LOGIN_DB_ERROR for identifier {login_identifier}: {db_login_err.errno} - {db_login_err.msg}", exc_info=False)
            flash("A database error occurred during login. (Code: LOGIN-DBE)", "danger")
        except Exception as general_login_err:
            if hasattr(app, 'logger') and app.logger: app.logger.critical(f"LOGIN_GENERAL_ERROR for identifier {login_identifier}: {general_login_err}", exc_info=True)
            flash("An unexpected error occurred. (Code: LOGIN-GEN)", "danger")
        finally:
            if db_cursor_login: db_cursor_login.close()
            if db_conn_login and db_conn_login.is_connected(): db_conn_login.close()
        
        return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_repopulate, next=next_redirect_url)

    return render_template('auth/login_form.html', is_minimal_layout=True, form_data=form_data_repopulate, next=next_redirect_url)


@app.route('/logout')
@login_required
def logout():
    user_name_at_logout = session.get('username', 'User')
    for key in list(session.keys()): 
        if key.startswith('otp_verified_for_phone_') or key == 'login_identifier_for_otp_prefill':
            session.pop(key, None)
    session.clear()
    flash(f"You have been successfully logged out, {user_name_at_logout}. We hope to see you again soon!", "info")
    return redirect(url_for('home'))

# --- OTP Routes ---
@app.route('/auth/request-otp', methods=['POST'])
def api_request_otp():
    data = request.get_json()
    if not data or 'phone_number' not in data:
        return jsonify({'success': False, 'message': 'بيانات غير صالحة: رقم الموبايل مفقود.'}), 400
    phone_number_input = data.get('phone_number', '').strip()
    if not is_valid_phone_format_simple(phone_number_input):
        return jsonify({'success': False, 'message': 'رقم الموبايل المدخل غير صالح.'}), 400
    conn = None; cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            if hasattr(app, 'logger') and app.logger: app.logger.error("OTP_REQUEST_FAIL: DB Connection Error")
            return jsonify({'success': False, 'message': 'خطأ في الاتصال بقاعدة البيانات.'}), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE phone_number = %s AND is_active = TRUE", (phone_number_input,))
        user = cursor.fetchone() 
        if not user:
            if hasattr(app, 'logger') and app.logger: app.logger.info(f"OTP_REQUEST_INFO: Phone {phone_number_input} not found. Generic success sent.")
            return jsonify({'success': True, 'message': 'إذا كان الرقم مسجلاً، سيتم إرسال رمز التأكيد.'}), 200
        otp_code_generated = "".join(random.choices("0123456789", k=8))
        otp_expiry_time = datetime.utcnow() + timedelta(minutes=10)
        cursor.execute("UPDATE users SET otp_code = %s, otp_expiry = %s WHERE id = %s",(otp_code_generated, otp_expiry_time, user['id']))
        conn.commit()
        if hasattr(app, 'logger') and app.logger: app.logger.info(f"OTP_SENT (simulated): To {phone_number_input}, OTP: {otp_code_generated}")
        print(f"DEBUG - OTP for {phone_number_input}: {otp_code_generated}") 
        return jsonify({'success': True, 'message': 'تم إرسال رمز التأكيد إلى رقم موبايلك.'}), 200
    except Error as db_err:
        if conn: conn.rollback()
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"OTP_REQUEST_DB_ERROR for phone {phone_number_input}: {db_err.msg}", exc_info=False)
        return jsonify({'success': False, 'message': 'خطأ بقاعدة البيانات عند طلب الرمز.'}), 500
    except Exception as e:
        if conn: conn.rollback()
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"OTP_REQUEST_GENERAL_ERROR: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'خطأ غير متوقع عند طلب الرمز.'}), 500
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

@app.route('/auth/verify-otp', methods=['POST'])
def api_verify_otp():
    data = request.get_json()
    if not data or 'phone_number' not in data or 'otp_code' not in data:
        return jsonify({'success': False, 'message': 'بيانات ناقصة.'}), 400
    phone_number_input = data.get('phone_number', '').strip()
    otp_code_input = data.get('otp_code', '').strip()
    if not is_valid_phone_format_simple(phone_number_input) or not otp_code_input.isdigit() or len(otp_code_input) != 8:
        return jsonify({'success': False, 'message': 'بيانات الإدخال غير صالحة.'}), 400
    conn = None; cursor = None
    try:
        conn = get_db_connection()
        if conn is None: return jsonify({'success': False, 'message': 'خطأ اتصال قاعدة البيانات.'}), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE phone_number = %s AND otp_code = %s AND otp_expiry > %s AND is_active = TRUE",
                       (phone_number_input, otp_code_input, datetime.utcnow()))
        user = cursor.fetchone() 
        if user:
            session[f'otp_verified_for_phone_{phone_number_input}'] = True
            session['login_identifier_for_otp_prefill'] = phone_number_input 
            if hasattr(app, 'logger') and app.logger: app.logger.info(f"OTP_VERIFIED: For {phone_number_input}")
            return jsonify({'success': True, 'message': 'تم التحقق من الرمز. يمكنك الآن إعادة تعيين كلمة المرور.'}), 200
        else:
            if hasattr(app, 'logger') and app.logger: app.logger.warning(f"OTP_VERIFY_FAIL: Invalid/expired for {phone_number_input}")
            session.pop(f'otp_verified_for_phone_{phone_number_input}', None)
            session.pop(f'login_identifier_for_otp_prefill', None)
            return jsonify({'success': False, 'message': 'رمز التأكيد غير صحيح أو انتهت صلاحيته.'}), 400
    except Error as db_err:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"OTP_VERIFY_DB_ERROR: {db_err.msg}", exc_info=False)
        return jsonify({'success': False, 'message': 'خطأ قاعدة بيانات عند التحقق.'}), 500
    except Exception as e:
        if conn: conn.rollback()
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"OTP_VERIFY_GENERAL_ERROR: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'خطأ غير متوقع عند التحقق.'}), 500
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

@app.route('/auth/reset-password', methods=['POST'])
def api_reset_password():
    data = request.get_json()
    if not data or 'phone_number' not in data or 'new_password' not in data:
        return jsonify({'success': False, 'message': 'بيانات ناقصة.'}), 400
    phone_number_input = data.get('phone_number', '').strip()
    new_password_input = data.get('new_password', '')
    if not is_valid_phone_format_simple(phone_number_input) or len(new_password_input) < 8 :
        return jsonify({'success': False, 'message': 'بيانات الإدخال غير صالحة (رقم الهاتف أو كلمة المرور).'}), 400
    if not session.get(f'otp_verified_for_phone_{phone_number_input}'):
        if hasattr(app, 'logger') and app.logger: app.logger.warning(f"RESET_PASS_UNAUTHORIZED: For {phone_number_input} - No OTP session flag.")
        return jsonify({'success': False, 'message': 'غير مصرح به أو انتهت الجلسة. يرجى التحقق من الرمز أولاً.'}), 403
    conn = None; cursor = None
    try:
        conn = get_db_connection()
        if conn is None: return jsonify({'success': False, 'message': 'خطأ اتصال قاعدة البيانات.'}), 500
        cursor = conn.cursor()
        new_password_hashed = generate_password_hash(new_password_input)
        cursor.execute("UPDATE users SET password_hash = %s, otp_code = NULL, otp_expiry = NULL WHERE phone_number = %s AND is_active = TRUE",
                       (new_password_hashed, phone_number_input))
        if cursor.rowcount > 0:
            conn.commit()
            session.pop(f'otp_verified_for_phone_{phone_number_input}', None)
            session['login_identifier_for_otp_prefill'] = phone_number_input 
            if hasattr(app, 'logger') and app.logger: app.logger.info(f"RESET_PASS_SUCCESS: For {phone_number_input}")
            return jsonify({'success': True, 'message': 'تم إعادة تعيين كلمة المرور بنجاح. يمكنك الآن تسجيل الدخول.'}), 200
        else:
            conn.rollback()
            if hasattr(app, 'logger') and app.logger: app.logger.error(f"RESET_PASS_FAIL: User {phone_number_input} not found or not updated. Rowcount: {cursor.rowcount}")
            session.pop(f'otp_verified_for_phone_{phone_number_input}', None) 
            session.pop(f'login_identifier_for_otp_prefill', None)
            return jsonify({'success': False, 'message': 'فشل إعادة تعيين كلمة المرور (مستخدم غير موجود/نشط).'}), 404
    except Error as db_err:
        if conn: conn.rollback()
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"RESET_PASS_DB_ERROR: {db_err.msg}", exc_info=False)
        return jsonify({'success': False, 'message': 'خطأ قاعدة بيانات عند إعادة التعيين.'}), 500
    except Exception as e:
        if conn: conn.rollback()
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"RESET_PASS_GENERAL_ERROR: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'خطأ غير متوقع عند إعادة التعيين.'}), 500
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- Public Routes ---
@app.route('/explore/teachers')
def explore_teachers_page():
    search_query = request.args.get('search_query', '').strip()
    teachers_list = []
    db_conn = None; db_cursor = None
    try:
        db_conn = get_db_connection()
        if db_conn is None:
            if hasattr(app, 'logger') and app.logger: app.logger.error("EXPLORE_TEACHERS_DB_ERROR: Failed to connect to database.")
            flash("Database connection error. Please try again later.", "danger")
            return render_template('public/explore_teachers.html', teachers=[], search_query=search_query)
        db_cursor = db_conn.cursor(dictionary=True)
        sql_query = "SELECT id, first_name, last_name, username, profile_picture_url, bio FROM users WHERE role = 'teacher' AND is_active = TRUE"
        query_params = []
        if search_query:
            sql_query += " AND (first_name LIKE %s OR last_name LIKE %s OR username LIKE %s OR bio LIKE %s)"
            search_pattern = f"%{search_query}%"
            query_params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
        sql_query += " ORDER BY first_name ASC, last_name ASC"
        db_cursor.execute(sql_query, tuple(query_params))
        teachers_list = db_cursor.fetchall()
    except Error as e_db:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"EXPLORE_TEACHERS_DB_ERROR: {e_db.msg}", exc_info=True)
        flash("An error occurred while fetching teachers. Please try again.", "danger")
    except Exception as e_general:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"EXPLORE_TEACHERS_GENERAL_ERROR: {e_general}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if db_cursor: db_cursor.close()
        if db_conn and db_conn.is_connected(): db_conn.close()
    return render_template('public/explore_teachers.html', teachers=teachers_list, search_query=search_query, current_lang=session.get('current_lang', 'en'))

@app.route('/teacher_profile/<int:teacher_id>')
def public_teacher_profile_page(teacher_id):
    teacher_profile = None
    teacher_videos = []
    teacher_quizzes = []
    is_subscribed = False # Assume not subscribed by default

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return render_template('public/teacher_profile.html', teacher_profile=None)
        
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, first_name, last_name, bio, country, profile_picture_url
            FROM users WHERE id = %s AND role = 'teacher' AND is_active = TRUE
        """, (teacher_id,))
        teacher_profile = cursor.fetchone() 
        if not teacher_profile:
            flash("Teacher not found or is inactive.", "warning")
            return redirect(url_for('explore_teachers_page'))
        
        current_user_id = session.get('user_id')
        if current_user_id and session.get('role') == 'student':
            cursor.execute("""
                SELECT id FROM student_subscriptions
                WHERE student_id = %s AND teacher_id = %s AND status = 'active'
            """, (current_user_id, teacher_id))
            _ = cursor.fetchone() 
            if _:
                is_subscribed = True
        
        cursor.execute("""
            SELECT id, title, description, thumbnail_path_or_url, is_viewable_free_for_student
            FROM videos WHERE teacher_id = %s AND status = 'published' ORDER BY upload_timestamp DESC
        """, (teacher_id,))
        videos_raw = cursor.fetchall()

        for video in videos_raw:
            video['has_access'] = is_subscribed or video['is_viewable_free_for_student']
            teacher_videos.append(video)

        cursor.execute("""
            SELECT q.id, q.title, q.description, q.time_limit_minutes, q.passing_score_percentage, q.allow_answer_review, v.title AS video_title,
                   (SELECT COUNT(*) FROM questions WHERE quiz_id = q.id) AS question_count
            FROM quizzes q
            LEFT JOIN videos v ON q.video_id = v.id
            WHERE q.teacher_id = %s AND q.is_active = TRUE ORDER BY q.created_at DESC
        """, (teacher_id,))
        quizzes_raw = cursor.fetchall()

        for quiz in quizzes_raw:
            quiz['has_access'] = is_subscribed 
            teacher_quizzes.append(quiz)

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"Error loading teacher profile {teacher_id}: {e}", exc_info=True)
        flash("An error occurred while loading the teacher's profile. Please try again.", "danger")
        return redirect(url_for('explore_teachers_page'))
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"EXPLORE_TEACHERS_GENERAL_ERROR: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
        return redirect(url_for('explore_teachers_page'))
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('public/teacher_profile.html',
                           teacher_profile=teacher_profile,
                           teacher_videos=teacher_videos,
                           teacher_quizzes=teacher_quizzes,
                           is_subscribed=is_subscribed,
                           current_user_id=session.get('user_id'),
                           current_lang=session.get('current_lang', 'en'))

# --- Teacher Routes ---
@app.route('/teacher/dashboard')
@teacher_required
def teacher_dashboard_placeholder():
    user_id = session.get('user_id')
    username = session.get('username')

    subscribers = 0
    total_views = 0
    quizzes_count = 0
    questions_count = 0

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) AS count FROM student_subscriptions WHERE teacher_id = %s AND status = 'active'", (user_id,))
            subscribers = cursor.fetchone()['count']

            cursor.execute("SELECT SUM(views_count) AS total FROM videos WHERE teacher_id = %s", (user_id,))
            total_views_result = cursor.fetchone()['total']
            total_views = total_views_result if total_views_result is not None else 0

            cursor.execute("SELECT COUNT(*) AS count FROM quizzes WHERE teacher_id = %s", (user_id,))
            quizzes_count = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(q.id) AS count FROM questions q
                JOIN quizzes quiz ON q.quiz_id = quiz.id
                WHERE quiz.teacher_id = %s
            """, (user_id,))
            questions_count = cursor.fetchone()['count']

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error fetching teacher dashboard stats for user {user_id}: {e}", exc_info=True)
        flash("Could not load some dashboard statistics.", "warning")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('teacher/dashboard.html',
                           username=username,
                           subscribers=subscribers,
                           total_views=total_views,
                           quizzes_count=quizzes_count,
                           questions_count=questions_count)

@app.route('/teacher/upload_video', methods=['GET', 'POST'])
@teacher_required
def upload_video_page():
    user_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Cannot upload video at this time.", "danger")
            return render_template('teacher/upload_video.html', request_form=request.form)

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT free_video_uploads_remaining FROM users WHERE id = %s", (user_id,))
        user_limits = cursor.fetchone() 
        free_uploads_remaining = user_limits['free_video_uploads_remaining'] if user_limits else 0

        if request.method == 'POST':
            if free_uploads_remaining <= 0:
                flash("You have used all your free video uploads. Please upgrade your account to upload more.", "warning")
                return render_template('teacher/upload_video.html', request_form=request.form)

            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            is_viewable_free = request.form.get('is_viewable_free') == 'true'
            video_file = request.files.get('video_file')

            validation_errors = []
            if not title: validation_errors.append("Video title is required.")
            if not video_file or video_file.filename == '': validation_errors.append("Video file is required.")
            elif not allowed_file(video_file.filename, ALLOWED_EXTENSIONS_VIDEOS): validation_errors.append("Invalid video file format. Allowed: MP4, MOV, AVI, MKV, WebM.")

            if validation_errors:
                for error_message in validation_errors: flash(error_message, "danger")
                return render_template('teacher/upload_video.html', request_form=request.form)

            filename = secure_filename(video_file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            video_path = os.path.join(app.config['UPLOAD_FOLDER_VIDEOS'], unique_filename)
            
            try:
                video_file.save(video_path)
            except Exception as e:
                if hasattr(app, 'logger') and app.logger: app.logger.critical(f"Failed to save video file {unique_filename}: {e}", exc_info=True)
                flash("Failed to save video file on server. Please try again.", "danger")
                return render_template('teacher/upload_video.html', request_form=request.form)

            try:
                cursor.execute("""
                    INSERT INTO videos (teacher_id, title, description, video_path_or_url, is_viewable_free_for_student, status)
                    VALUES (%s, %s, %s, %s, %s, 'published')
                """, (user_id, title, description, os.path.join('uploads', 'videos', unique_filename), is_viewable_free))
                conn.commit()

                if not is_viewable_free:
                     cursor.execute("UPDATE users SET free_video_uploads_remaining = free_video_uploads_remaining - 1 WHERE id = %s", (user_id,))
                     conn.commit()

                flash("Video uploaded and published successfully!", "success")
                return redirect(url_for('teacher_videos_list_page'))
            except Error as e:
                conn.rollback()
                if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error during video upload for user {user_id}: {e}", exc_info=True)
                if os.path.exists(video_path):
                    os.remove(video_path)
                flash("A database error occurred during video upload. Please try again.", "danger")
            except Exception as e:
                conn.rollback()
                if hasattr(app, 'logger') and app.logger: app.logger.critical(f"Unexpected error during video upload for user {user_id}: {e}", exc_info=True)
                if os.path.exists(video_path):
                    os.remove(video_path)
                flash("An unexpected error occurred. Please try again.", "danger")

        return render_template('teacher/upload_video.html', request_form=request.form, free_uploads_remaining=free_uploads_remaining)
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on upload_video_page: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
        return redirect(url_for('teacher_dashboard_placeholder'))
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

@app.route('/teacher/videos')
@teacher_required
def teacher_videos_list_page():
    user_id = session.get('user_id')
    videos = []
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, title, description, video_path_or_url, thumbnail_path_or_url, upload_timestamp, status FROM videos WHERE teacher_id = %s ORDER BY upload_timestamp DESC", (user_id,))
            videos = cursor.fetchall()
    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error fetching teacher videos for user {user_id}: {e}", exc_info=True)
        flash("An error occurred while fetching your videos. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
    return render_template('teacher/videos_list.html', videos=videos)

@app.route('/teacher/quizzes')
@teacher_required
def teacher_quizzes_list_page():
    user_id = session.get('user_id')
    quizzes = []
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT q.id, q.title, q.description, q.created_at, q.is_active, v.title AS video_title
                FROM quizzes q
                LEFT JOIN videos v ON q.video_id = v.id
                WHERE q.teacher_id = %s
                ORDER BY q.created_at DESC
            """, (user_id,))
            quizzes = cursor.fetchall()
    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error fetching teacher quizzes for user {user_id}: {e}", exc_info=True)
        flash("An error occurred while fetching your quizzes. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
    return render_template('teacher/quizzes_list.html', quizzes=quizzes)

@app.route('/teacher/quiz/create', methods=['GET', 'POST'])
@teacher_required
def create_quiz_page():
    user_id = session.get('user_id')
    teacher_videos = []
    can_create_quiz = False
    free_quizzes_left = 0
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, title FROM videos WHERE teacher_id = %s AND status = 'published' ORDER BY title ASC", (user_id,))
            teacher_videos = cursor.fetchall()

            cursor.execute("SELECT free_quiz_creations_remaining FROM users WHERE id = %s", (user_id,))
            user_limits = cursor.fetchone() 
            free_quizzes_left = user_limits['free_quiz_creations_remaining'] if user_limits else 0
            if free_quizzes_left > 0:
                can_create_quiz = True

            if request.method == 'POST':
                if not can_create_quiz:
                    flash("You have used all your free quiz creations. Please upgrade your account to create more quizzes.", "warning")
                    return render_template('teacher/create_quiz.html', teacher_videos=teacher_videos, can_create_quiz=can_create_quiz, free_quizzes_left=free_quizzes_left, quiz_title=request.form.get('quiz_title'), quiz_description=request.form.get('quiz_description'), time_limit_minutes=request.form.get('time_limit_minutes'), passing_score_percentage=request.form.get('passing_score_percentage'), allow_answer_review=request.form.get('allow_answer_review'))

                title = request.form.get('quiz_title', '').strip()
                description = request.form.get('quiz_description', '').strip()
                linked_video_id = request.form.get('linked_video_id')
                time_limit_minutes = request.form.get('time_limit_minutes')
                passing_score_percentage = request.form.get('passing_score_percentage')
                allow_answer_review = request.form.get('allow_answer_review') == 'on'

                validation_errors = []
                if not title: validation_errors.append("Quiz title is required.")
                if time_limit_minutes:
                    try: time_limit_minutes = int(time_limit_minutes)
                    except ValueError: validation_errors.append("Time limit must be a valid number.")
                    if time_limit_minutes < 0: validation_errors.append("Time limit cannot be negative.")
                else: time_limit_minutes = None

                if passing_score_percentage:
                    try: passing_score_percentage = int(passing_score_percentage)
                    except ValueError: validation_errors.append("Passing score must be a valid number.")
                    if not (0 <= passing_score_percentage <= 100): validation_errors.append("Passing score must be between 0 and 100.")
                else: passing_score_percentage = 70 # Default

                if validation_errors:
                    for error_message in validation_errors: flash(error_message, "danger")
                    return render_template('teacher/create_quiz.html', teacher_videos=teacher_videos, can_create_quiz=can_create_quiz, free_quizzes_left=free_quizzes_left, quiz_title=title, quiz_description=description, time_limit_minutes=time_limit_minutes, passing_score_percentage=passing_score_percentage, allow_answer_review=allow_answer_review, linked_video_id_selected=linked_video_id)

                try:
                    cursor.execute("""
                        INSERT INTO quizzes (teacher_id, title, description, video_id, time_limit_minutes, passing_score_percentage, allow_answer_review, shareable_link_id, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                    """, (user_id, title, description, linked_video_id if linked_video_id else None, time_limit_minutes, passing_score_percentage, allow_answer_review, str(uuid.uuid4())))
                    quiz_id = cursor.lastrowid 
                    
                    cursor.execute("UPDATE users SET free_quiz_creations_remaining = free_quiz_creations_remaining - 1 WHERE id = %s", (user_id,))
                    conn.commit()

                    flash(f"Quiz '{title}' created successfully! Now add some questions.", "success")
                    return redirect(url_for('add_question_to_quiz_page', quiz_id=quiz_id))

                except Error as e:
                    conn.rollback()
                    if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error creating quiz for user {user_id}: {e}", exc_info=True)
                    flash("A database error occurred while creating the quiz. Please try again.", "danger")
                except Exception as e:
                    conn.rollback()
                    if hasattr(app, 'logger') and app.logger: app.logger.critical(f"Unexpected error creating quiz for user {user_id}: {e}", exc_info=True)
                    flash("An unexpected error occurred. Please try again.", "danger")

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error on create_quiz_page load for user {user_id}: {e}", exc_info=True)
        flash("An error occurred while loading quiz creation page data. Please try again.", "danger")
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on create_quiz_page: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('teacher/create_quiz.html', teacher_videos=teacher_videos, can_create_quiz=can_create_quiz, free_quizzes_left=free_quizzes_left, video_id_preselected=request.args.get('video_id'))

@app.route('/teacher/quiz/edit/<int:quiz_id>', methods=['GET', 'POST'])
@teacher_required
def edit_quiz_page(quiz_id):
    user_id = session.get('user_id')
    quiz = None
    teacher_videos = []
    submitted_data = None

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return redirect(url_for('teacher_quizzes_list_page'))
        
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id, title, description, video_id, time_limit_minutes, passing_score_percentage, allow_answer_review, is_active FROM quizzes WHERE id = %s AND teacher_id = %s", (quiz_id, user_id))
        quiz = cursor.fetchone() 

        if not quiz:
            flash("Quiz not found or you don't have permission to edit it.", "danger")
            return redirect(url_for('teacher_quizzes_list_page'))
        
        cursor.execute("SELECT id, title FROM videos WHERE teacher_id = %s AND status = 'published' ORDER BY title ASC", (user_id,))
        teacher_videos = cursor.fetchall()

        if request.method == 'POST':
            submitted_data = request.form.get('quiz_title', '').strip()
            title = request.form.get('quiz_title', '').strip()
            description = request.form.get('quiz_description', '').strip()
            linked_video_id = request.form.get('linked_video_id')
            time_limit_minutes = request.form.get('time_limit_minutes')
            passing_score_percentage = request.form.get('passing_score_percentage')
            allow_answer_review = request.form.get('allow_answer_review') == 'on'

            validation_errors = []
            if not title: validation_errors.append("Quiz title is required.")
            if time_limit_minutes:
                try: time_limit_minutes = int(time_limit_minutes)
                except ValueError: validation_errors.append("Time limit must be a valid number.")
                if time_limit_minutes < 0: validation_errors.append("Time limit cannot be negative.")
            else: time_limit_minutes = None

            if passing_score_percentage:
                try: passing_score_percentage = int(passing_score_percentage)
                except ValueError: validation_errors.append("Passing score must be a valid number.")
                if not (0 <= passing_score_percentage <= 100): validation_errors.append("Passing score must be between 0 and 100.")
            else: passing_score_percentage = 70 # Default

            if validation_errors:
                for error_message in validation_errors: flash(error_message, "danger")
                return render_template('teacher/edit_quiz.html', quiz=quiz, teacher_videos=teacher_videos, submitted_data=submitted_data)

            try:
                cursor.execute("""
                    UPDATE quizzes SET
                    title = %s, description = %s, video_id = %s,
                    time_limit_minutes = %s, passing_score_percentage = %s, allow_answer_review = %s,
                    updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND teacher_id = %s
                """, (title, description, linked_video_id if linked_video_id else None,
                      time_limit_minutes, passing_score_percentage, allow_answer_review,
                      quiz_id, user_id))
                conn.commit()
                flash("Quiz updated successfully!", "success")
                return redirect(url_for('teacher_quizzes_list_page'))
            except Error as e:
                conn.rollback()
                if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error updating quiz {quiz_id} for user {user_id}: {e}", exc_info=True)
                flash("A database error occurred while updating the quiz. Please try again.", "danger")
            except Exception as e:
                conn.rollback()
                if hasattr(app, 'logger') and app.logger: app.logger.critical(f"Unexpected error updating quiz {quiz_id} for user {user_id}: {e}", exc_info=True)
                flash("An unexpected error occurred. Please try again.", "danger")

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error on edit_quiz_page load for quiz {quiz_id}: {e}", exc_info=True)
        flash("An error occurred while loading quiz data. Please try again.", "danger")
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on edit_quiz_page: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('teacher/edit_quiz.html', quiz=quiz, teacher_videos=teacher_videos, submitted_data=submitted_data)

@app.route('/teacher/quiz/delete/<int:quiz_id>', methods=['POST'])
@teacher_required
def delete_quiz_page(quiz_id):
    user_id = session.get('user_id')
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Could not delete quiz.", "danger")
            return redirect(url_for('teacher_quizzes_list_page'))
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quizzes WHERE id = %s AND teacher_id = %s", (quiz_id, user_id))
        conn.commit()

        if cursor.rowcount > 0:
            flash("Quiz and all associated data deleted successfully!", "success")
        else:
            flash("Quiz not found or you don't have permission to delete it.", "danger")
    except Error as e:
        conn.rollback()
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error deleting quiz {quiz_id} for user {user_id}: {e}", exc_info=True)
        flash("A database error occurred while deleting the quiz. Please try again.", "danger")
    except Exception as e:
        conn.rollback()
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"Unexpected error deleting quiz {quiz_id} for user {user_id}: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
    return redirect(url_for('teacher_quizzes_list_page'))

@app.route('/teacher/quiz/<int:quiz_id>/add_question', methods=['GET', 'POST'])
@teacher_required
def add_question_to_quiz_page(quiz_id):
    user_id = session.get('user_id')
    quiz = None
    existing_questions = []
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return redirect(url_for('teacher_quizzes_list_page'))
        
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id, title FROM quizzes WHERE id = %s AND teacher_id = %s", (quiz_id, user_id))
        quiz = cursor.fetchone() 

        if not quiz:
            flash("Quiz not found or you don't have permission.", "danger")
            return redirect(url_for('teacher_quizzes_list_page'))
        
        cursor.execute("""
            SELECT q.id, q.question_text, q.points, q.question_type,
                   GROUP_CONCAT(c.choice_text ORDER BY c.id ASC) AS choices_text_concat,
                   GROUP_CONCAT(c.is_correct ORDER BY c.id ASC) AS is_correct_concat
            FROM questions q
            LEFT JOIN choices c ON q.id = c.question_id
            WHERE q.quiz_id = %s
            GROUP BY q.id
            ORDER BY q.display_order ASC
        """, (quiz_id,))
        
        raw_questions = cursor.fetchall()
        for q in raw_questions:
            q['choices_text'] = q['choices_text_concat'].split(',') if q['choices_text_concat'] else []
            q['is_correct_list'] = [bool(int(x)) for x in q['is_correct_concat'].split(',')] if q['is_correct_concat'] else []
            existing_questions.append(q)

        if request.method == 'POST':
            question_text = request.form.get('question_text', '').strip()
            points = request.form.get('points', 1)
            correct_choice_index = request.form.get('correct_choice_index') 
            
            choices_texts = []
            for i in range(4): 
                choice_text = request.form.get(f'choice_{i+1}_text', '').strip()
                choices_texts.append(choice_text)

            validation_errors = []
            if not question_text: validation_errors.append("Question text is required.")
            if sum(1 for ct in choices_texts if ct) < 2: validation_errors.append("At least two choices are required for an MCQ.")
            if correct_choice_index is None: validation_errors.append("A correct answer must be selected.")
            elif not choices_texts[int(correct_choice_index)]: validation_errors.append("The selected correct choice cannot be empty.")
            
            try: points = int(points)
            except ValueError: validation_errors.append("Points must be a valid number.")
            if points < 1: validation_errors.append("Points must be at least 1.")

            if validation_errors:
                for error_message in validation_errors: flash(error_message, "danger")
                return render_template('teacher/add_question_to_quiz.html',
                                       quiz=quiz,
                                       existing_questions=existing_questions,
                                       question_text=question_text,
                                       points=points,
                                       choices_text=choices_texts,
                                       correct_choice_index_submitted=int(correct_choice_index) if correct_choice_index is not None else None)

            try:
                cursor.execute("SELECT MAX(display_order) AS max_order FROM questions WHERE quiz_id = %s", (quiz_id,))
                max_order_result = cursor.fetchone() 
                next_display_order = (max_order_result['max_order'] or 0) + 1

                cursor.execute("""
                    INSERT INTO questions (quiz_id, question_text, question_type, display_order, points)
                    VALUES (%s, %s, 'mc', %s, %s)
                """, (quiz_id, question_text, next_display_order, points))
                question_id = cursor.lastrowid

                for i, choice_text in enumerate(choices_texts):
                    if choice_text: 
                        is_correct = (i == int(correct_choice_index))
                        cursor.execute("""
                            INSERT INTO choices (question_id, choice_text, is_correct)
                            VALUES (%s, %s, %s)
                        """, (question_id, choice_text, is_correct))
                conn.commit()
                flash("Question added successfully!", "success")
                return redirect(url_for('add_question_to_quiz_page', quiz_id=quiz.id))
            except Error as e:
                conn.rollback()
                if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error adding question to quiz {quiz_id} for user {user_id}: {e}", exc_info=True)
                flash("A database error occurred while adding the question. Please try again.", "danger")
            except Exception as e:
                conn.rollback()
                if hasattr(app, 'logger') and app.logger: app.logger.critical(f"Unexpected error adding question to quiz {quiz_id} for user {user_id}: {e}", exc_info=True)
                flash("An unexpected error occurred. Please try again.", "danger")

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error on add_question_to_quiz_page load for quiz {quiz_id}: {e}", exc_info=True)
        flash("An error occurred while loading the quiz questions. Please try again.", "danger")
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on add_question_to_quiz_page: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('teacher/add_question_to_quiz.html', quiz=quiz, existing_questions=existing_questions)

@app.route('/teacher/quiz/<int:quiz_id>/edit_question/<int:question_id>', methods=['GET', 'POST'])
@teacher_required
def edit_question_page(quiz_id, question_id):
    user_id = session.get('user_id')
    quiz = None
    question = None
    choices = []
    submitted_question_text = None
    submitted_points = None
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return redirect(url_for('teacher_quizzes_list_page'))
        
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id, title FROM quizzes WHERE id = %s AND teacher_id = %s", (quiz_id, user_id))
        quiz = cursor.fetchone() 
        if not quiz:
            flash("Quiz not found or you don't have permission to edit it.", "danger")
            return redirect(url_for('teacher_quizzes_list_page'))

        cursor.execute("SELECT id, question_text, points, question_type FROM questions WHERE id = %s AND quiz_id = %s", (question_id, quiz_id))
        question = cursor.fetchone() 
        if not question:
            flash("Question not found in this quiz.", "danger")
            return redirect(url_for('add_question_to_quiz_page', quiz_id=quiz.id))
        
        cursor.execute("SELECT id, choice_text, is_correct FROM choices WHERE question_id = %s ORDER BY id ASC", (question_id,))
        choices = cursor.fetchall()

        if request.method == 'POST':
            submitted_question_text = request.form.get('question_text', '').strip()
            submitted_points = request.form.get('points', 1)
            correct_choice_index = request.form.get('correct_choice_index')

            submitted_choices_texts = []
            for i in range(4): 
                choice_text = request.form.get(f'choice_{i+1}_text', '').strip()
                submitted_choices_texts.append(choice_text)

            validation_errors = []
            if not submitted_question_text: validation_errors.append("Question text is required.")
            if question.question_type == 'mc' and sum(1 for ct in submitted_choices_texts if ct) < 2: 
                validation_errors.append("At least two choices are required for an MCQ.")
            
            if question.question_type == 'mc':
                if correct_choice_index is None: 
                    validation_errors.append("A correct answer must be selected.")
                elif not (0 <= int(correct_choice_index) < len(submitted_choices_texts) and submitted_choices_texts[int(correct_choice_index)]):
                    validation_errors.append("The selected correct choice cannot be empty or invalid.")
            
            try: submitted_points = int(submitted_points)
            except ValueError: validation_errors.append("Points must be a valid number.")
            if submitted_points < 1: validation_errors.append("Points must be at least 1.")

            if validation_errors:
                for error_message in validation_errors: flash(error_message, "danger")
                return render_template('teacher/edit_question.html',
                                       quiz=quiz,
                                       question=question,
                                       choices=choices, 
                                       submitted_question_text=submitted_question_text,
                                       submitted_points=submitted_points,
                                       lang_code=session.get('current_lang', 'en'))

            try:
                cursor.execute("""
                    UPDATE questions SET
                    question_text = %s, points = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (submitted_question_text, submitted_points, question_id))

                if question.question_type == 'mc':
                    cursor.execute("DELETE FROM choices WHERE question_id = %s", (question_id,))
                    
                    for i, choice_text in enumerate(choices_texts):
                        if choice_text: 
                            is_correct = (i == int(correct_choice_index))
                            cursor.execute("""
                                INSERT INTO choices (question_id, choice_text, is_correct)
                                VALUES (%s, %s, %s)
                            """, (question_id, choice_text, is_correct))
                conn.commit()
                flash("Question updated successfully!", "success")
                return redirect(url_for('add_question_to_quiz_page', quiz_id=quiz.id))
            except Error as e:
                conn.rollback()
                if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error updating question {question_id} for quiz {quiz_id}: {e}", exc_info=True)
                flash("A database error occurred while updating the question. Please try again.", "danger")
            except Exception as e:
                conn.rollback()
                if hasattr(app, 'logger') and app.logger: app.logger.critical(f"Unexpected error updating question {question_id} for quiz {quiz_id}: {e}", exc_info=True)
                flash("An unexpected error occurred. Please try again.", "danger")

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error on edit_question_page load for question {question_id}: {e}", exc_info=True)
        flash("An error occurred while loading question data. Please try again.", "danger")
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on edit_question_page: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('teacher/edit_question.html',
                           quiz=quiz,
                           question=question,
                           choices=choices,
                           lang_code=session.get('current_lang', 'en'))

@app.route('/teacher/edit_profile', methods=['GET', 'POST'])
@teacher_required
def edit_teacher_profile():
    user_id = session.get('user_id')
    teacher_profile_data = {}
    current_profile_pic_url = None

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return redirect(url_for('teacher_dashboard_placeholder'))
        
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            phone_number = request.form.get('phone_number', '').strip()
            country = request.form.get('country', '').strip()
            bio = request.form.get('bio', '').strip()
            profile_picture_file = request.files.get('profile_picture')

            form_data = {
                'first_name': first_name,
                'last_name': last_name,
                'phone_number': phone_number,
                'country': country,
                'bio': bio,
                'email': session.get('email')
            }

            validation_errors = []
            if not first_name or len(first_name) < 2: validation_errors.append("First name is required (minimum 2 characters).")
            if not last_name or len(last_name) < 2: validation_errors.append("Last name is required (minimum 2 characters).")
            if phone_number and not is_valid_phone_format_simple(phone_number): validation_errors.append("Phone number format is invalid.")
            if len(bio) > 1000: validation_errors.append("Bio cannot exceed 1000 characters.")

            new_profile_pic_path = None
            if profile_picture_file and profile_picture_file.filename != '':
                if allowed_file(profile_picture_file.filename, ALLOWED_EXTENSIONS_IMAGES):
                    filename = secure_filename(profile_picture_file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    upload_path = os.path.join(app.config['UPLOAD_FOLDER_PROFILE_PICS'], unique_filename)
                    try:
                        profile_picture_file.save(upload_path)
                        new_profile_pic_path = os.path.join('uploads', 'profile_pics', unique_filename)
                    except Exception as e:
                        if hasattr(app, 'logger') and app.logger: app.logger.error(f"Failed to save profile picture for user {user_id}: {e}", exc_info=True)
                        validation_errors.append("Failed to save profile picture.")
                else:
                    validation_errors.append("Invalid image file format. Allowed: PNG, JPG, GIF, WEBP.")

            if phone_number and phone_number != session.get('phone_number_session'):
                cursor.execute("SELECT id FROM users WHERE phone_number = %s AND id != %s", (phone_number, user_id))
                found_phone = cursor.fetchone() 
                if found_phone:
                    validation_errors.append(f"The phone number '{phone_number}' is already in use by another account.")

            if validation_errors:
                for error_message in validation_errors: flash(error_message, "danger")
                if new_profile_pic_path and os.path.exists(os.path.join('static', new_profile_pic_path)):
                    os.remove(os.path.join('static', new_profile_pic_path))
                return render_template('teacher/edit_profile.html', form_data=form_data, teacher_id_for_preview=user_id)
            
            cursor.execute("SELECT profile_picture_url FROM users WHERE id = %s", (user_id,))
            old_profile_pic_result = cursor.fetchone() 
            old_profile_pic_url = old_profile_pic_result['profile_picture_url'] if old_profile_pic_result else None


            update_sql = """
                UPDATE users SET
                first_name = %s, last_name = %s, phone_number = %s, country = %s, bio = %s,
                updated_at = CURRENT_TIMESTAMP
            """
            update_params = [first_name, last_name, phone_number if phone_number else None, country if country else None, bio if bio else None]

            if new_profile_pic_path:
                update_sql += ", profile_picture_url = %s"
                update_params.append(new_profile_pic_path)
            
            update_sql += " WHERE id = %s"
            update_params.append(user_id)
            
            cursor.execute(update_sql, tuple(update_params))
            conn.commit()

            session['username'] = first_name
            session['phone_number_session'] = phone_number

            if new_profile_pic_path and old_profile_pic_url and os.path.basename(old_profile_pic_url) != 'default_profile.png':
                old_path_full = os.path.join(app.root_path, 'static', old_profile_pic_url)
                if os.path.exists(old_path_full):
                    try:
                        os.remove(old_path_full)
                        if hasattr(app, 'logger') and app.logger: app.logger.info(f"Deleted old profile picture: {old_path_full}")
                    except OSError as e:
                        if hasattr(app, 'logger') and app.logger: app.logger.warning(f"Could not delete old profile picture {old_path_full}: {e}")

            flash("Your profile has been updated successfully!", "success")
            return redirect(url_for('teacher_dashboard_placeholder'))

        else: # GET request
            cursor.execute("SELECT first_name, last_name, email, phone_number, country, bio, profile_picture_url FROM users WHERE id = %s", (user_id,))
            teacher_profile_data = cursor.fetchone() 
            if teacher_profile_data:
                current_profile_pic_url = teacher_profile_data['profile_picture_url']
                for key in teacher_profile_data:
                    if teacher_profile_data[key] is None:
                        teacher_profile_data[key] = ''
            else:
                flash("Could not load your profile data.", "danger")
                return redirect(url_for('teacher_dashboard_placeholder'))

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error on edit_teacher_profile for user {user_id}: {e}", exc_info=True)
        flash("A database error occurred. Please try again.", "danger")
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on edit_teacher_profile: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('teacher/edit_profile.html', form_data=teacher_profile_data, current_profile_pic_url=current_profile_pic_url, teacher_id_for_preview=user_id)


# --- Student Routes ---
@app.route('/student/dashboard')
@student_required
def student_dashboard_placeholder():
    user_id = session.get('user_id')
    username = session.get('username')
    
    recently_watched_videos = []
    latest_quiz_attempts = []
    available_videos = []
    available_quizzes = []

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT swv.video_id, v.title AS video_title, v.thumbnail_path_or_url,
                       u.first_name AS teacher_first_name, u.last_name AS teacher_last_name, swv.watched_at
                FROM student_watched_videos swv
                JOIN videos v ON swv.video_id = v.id
                JOIN users u ON v.teacher_id = u.id
                WHERE swv.student_id = %s
                ORDER BY swv.watched_at DESC
                LIMIT 3
            """, (user_id,))
            recently_watched_videos = cursor.fetchall()

            cursor.execute("""
                SELECT qa.id, qa.score, qa.max_possible_score, qa.submitted_at, qa.passed,
                       q.title AS quiz_title, q.passing_score_percentage, q.id AS quiz_id
                FROM quiz_attempts qa
                JOIN quizzes q ON qa.quiz_id = q.id
                WHERE qa.student_id = %s
                ORDER BY qa.submitted_at DESC
                LIMIT 3
            """, (user_id,))
            latest_quiz_attempts = cursor.fetchall()

            cursor.execute("""
                SELECT DISTINCT v.id, v.title, v.description, v.thumbnail_path_or_url,
                       u.first_name AS teacher_first_name, u.last_name AS teacher_last_name,
                       CASE WHEN swv.video_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_watched
                FROM videos v
                JOIN users u ON v.teacher_id = u.id
                LEFT JOIN student_watched_videos swv ON v.id = swv.video_id AND swv.student_id = %s
                LEFT JOIN student_subscriptions ss ON v.teacher_id = ss.teacher_id AND ss.student_id = %s AND ss.status = 'active'
                WHERE v.status = 'published' AND (v.is_viewable_free_for_student = TRUE OR ss.student_id IS NOT NULL)
                ORDER BY v.upload_timestamp DESC
                LIMIT 6
            """, (user_id, user_id))
            available_videos = cursor.fetchall()

            cursor.execute("""
                SELECT DISTINCT q.id, q.title, q.description, q.time_limit_minutes, q.passing_score_percentage,
                       u.first_name AS teacher_first_name, u.last_name AS teacher_last_name,
                       (SELECT COUNT(*) FROM questions WHERE quiz_id = q.id) AS question_count,
                       (SELECT qa2.score FROM quiz_attempts qa2 WHERE qa2.quiz_id = q.id AND qa2.student_id = %s ORDER BY qa2.submitted_at DESC LIMIT 1) AS last_attempt_score,
                       (SELECT qa2.max_possible_score FROM quiz_attempts qa2 WHERE qa2.quiz_id = q.id AND qa2.student_id = %s ORDER BY qa2.submitted_at DESC LIMIT 1) AS last_attempt_max_score,
                       (SELECT qa2.passed FROM quiz_attempts qa2 WHERE qa2.quiz_id = q.id AND qa2.student_id = %s ORDER BY qa2.submitted_at DESC LIMIT 1) AS last_attempt_passed,
                       (SELECT qa2.submitted_at FROM quiz_attempts qa2 WHERE qa2.quiz_id = q.id AND qa2.student_id = %s ORDER BY qa2.submitted_at DESC LIMIT 1) AS last_attempt_date,
                       (SELECT qa2.id FROM quiz_attempts qa2 WHERE qa2.quiz_id = q.id AND qa2.student_id = %s ORDER BY qa2.submitted_at DESC LIMIT 1) AS last_attempt_id
                FROM quizzes q
                JOIN users u ON q.teacher_id = u.id
                LEFT JOIN student_subscriptions ss ON q.teacher_id = ss.teacher_id AND ss.student_id = %s AND ss.status = 'active'
                WHERE q.is_active = TRUE AND ss.student_id IS NOT NULL
                ORDER BY q.created_at DESC
                LIMIT 6
            """, (user_id, user_id, user_id, user_id, user_id, user_id)) 
            available_quizzes = cursor.fetchall()

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error fetching student dashboard data for user {user_id}: {e}", exc_info=True)
        flash("Could not load some dashboard information.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('student/dashboard.html',
                           username=username,
                           recently_watched_videos=recently_watched_videos,
                           latest_quiz_attempts=latest_quiz_attempts,
                           available_videos=available_videos,
                           available_quizzes=available_quizzes)

@app.route('/student/profile')
@student_required
def student_profile_page():
    user_id = session.get('user_id')
    student_profile = None
    student_subscriptions = []
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return redirect(url_for('student_dashboard_placeholder'))
        
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT first_name, last_name, email, phone_number, country, profile_picture_url, wallet_balance FROM users WHERE id = %s AND role = 'student'", (user_id,))
        student_profile = cursor.fetchone() 

        if not student_profile:
            flash("Student profile not found.", "danger")
            return redirect(url_for('student_dashboard_placeholder'))
        
        cursor.execute("""
            SELECT ss.expiry_date, u.first_name AS teacher_first_name, u.last_name AS teacher_last_name, u.id AS teacher_id
            FROM student_subscriptions ss
            JOIN users u ON ss.teacher_id = u.id
            WHERE ss.student_id = %s AND ss.status = 'active'
            ORDER BY ss.subscription_date DESC
        """, (user_id,))
        student_subscriptions = cursor.fetchall()

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error fetching student profile {user_id}: {e}", exc_info=True)
        flash("An error occurred while loading your profile. Please try again.", "danger")
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on student_profile_page: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('student/student_profile.html',
                           student_profile=student_profile,
                           student_subscriptions=student_subscriptions)


@app.route('/student/edit_profile', methods=['GET', 'POST'])
@student_required
def edit_student_profile():
    user_id = session.get('user_id')
    student_profile_data = {}
    current_profile_pic_url = None

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return redirect(url_for('student_profile_page'))

        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            phone_number = request.form.get('phone_number', '').strip()
            country = request.form.get('country', '').strip()
            profile_picture_file = request.files.get('profile_picture')

            form_data = {
                'first_name': first_name,
                'last_name': last_name,
                'phone_number': phone_number,
                'country': country,
                'email': session.get('email')
            }

            validation_errors = []
            if not first_name or len(first_name) < 2: validation_errors.append("First name is required (minimum 2 characters).")
            if not last_name or len(last_name) < 2: validation_errors.append("Last name is required (minimum 2 characters).")
            if phone_number and not is_valid_phone_format_simple(phone_number): validation_errors.append("Phone number format is invalid.")

            new_profile_pic_path = None
            if profile_picture_file and profile_picture_file.filename != '':
                if allowed_file(profile_picture_file.filename, ALLOWED_EXTENSIONS_IMAGES):
                    filename = secure_filename(profile_picture_file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    upload_path = os.path.join(app.config['UPLOAD_FOLDER_PROFILE_PICS'], unique_filename)
                    try:
                        profile_picture_file.save(upload_path)
                        new_profile_pic_path = os.path.join('uploads', 'profile_pics', unique_filename)
                    except Exception as e:
                        if hasattr(app, 'logger') and app.logger: app.logger.error(f"Failed to save profile picture for user {user_id}: {e}", exc_info=True)
                        validation_errors.append("Failed to save profile picture.")
                else:
                    validation_errors.append("Invalid image file format. Allowed: PNG, JPG, GIF, WEBP.")

            if phone_number and phone_number != session.get('phone_number_session'):
                cursor.execute("SELECT id FROM users WHERE phone_number = %s AND id != %s", (phone_number, user_id))
                found_phone = cursor.fetchone() 
                if found_phone:
                    validation_errors.append(f"The phone number '{phone_number}' is already in use by another account.")

            if validation_errors:
                for error_message in validation_errors: flash(error_message, "danger")
                if new_profile_pic_path and os.path.exists(os.path.join('static', new_profile_pic_path)):
                    os.remove(os.path.join('static', new_profile_pic_path))
                return render_template('student/edit_profile.html', form_data=form_data)

            cursor.execute("SELECT profile_picture_url FROM users WHERE id = %s", (user_id,))
            old_profile_pic_result = cursor.fetchone() 
            old_profile_pic_url = old_profile_pic_result['profile_picture_url'] if old_profile_pic_result else None

            update_sql = """
                UPDATE users SET
                first_name = %s, last_name = %s, phone_number = %s, country = %s,
                updated_at = CURRENT_TIMESTAMP
            """
            update_params = [first_name, last_name, phone_number if phone_number else None, country if country else None]

            if new_profile_pic_path:
                update_sql += ", profile_picture_url = %s"
                update_params.append(new_profile_pic_path)

            update_sql += " WHERE id = %s"
            update_params.append(user_id)

            cursor.execute(update_sql, tuple(update_params))
            conn.commit()

            session['username'] = first_name
            session['phone_number_session'] = phone_number

            if new_profile_pic_path and old_profile_pic_url and os.path.basename(old_profile_pic_url) != 'default_profile.png':
                old_path_full = os.path.join(app.root_path, 'static', old_profile_pic_url)
                if os.path.exists(old_path_full):
                    try:
                        os.remove(old_path_full)
                        if hasattr(app, 'logger') and app.logger: app.logger.info(f"Deleted old profile picture: {old_path_full}")
                    except OSError as e:
                        if hasattr(app, 'logger') and app.logger: app.logger.warning(f"Could not delete old profile picture {old_path_full}: {e}")

            flash("Your profile has been updated successfully!", "success")
            return redirect(url_for('student_profile_page'))

        else: # GET request
            cursor.execute("SELECT first_name, last_name, email, phone_number, country, profile_picture_url FROM users WHERE id = %s", (user_id,))
            student_profile_data = cursor.fetchone() 
            if student_profile_data:
                current_profile_pic_url = student_profile_data['profile_picture_url']
                for key in student_profile_data:
                    if student_profile_data[key] is None:
                        student_profile_data[key] = ''
            else:
                flash("Could not load your profile data.", "danger")
                return redirect(url_for('student_dashboard_placeholder'))

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error on edit_student_profile for user {user_id}: {e}", exc_info=True)
        flash("A database error occurred. Please try again.", "danger")
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on edit_student_profile: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('student/edit_profile.html', form_data=student_profile_data, current_profile_pic_url=current_profile_pic_url)


@app.route('/student/add_wallet_balance', methods=['GET', 'POST'])
@student_required
def add_wallet_balance():
    user_id = session.get('user_id')
    current_balance = 0.00
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return redirect(url_for('student_profile_page'))
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT wallet_balance FROM users WHERE id = %s", (user_id,))
        user_wallet = cursor.fetchone() 
        if user_wallet:
            current_balance = float(user_wallet['wallet_balance'])
        else:
            flash("Could not retrieve wallet balance.", "danger")
            return redirect(url_for('student_dashboard_placeholder'))

        if request.method == 'POST':
            amount_str = request.form.get('amount', '').strip()
            
            try:
                amount = float(amount_str)
                if amount <= 0:
                    flash("Amount must be a positive number.", "danger")
                else:
                    new_balance = current_balance + amount
                    cursor.execute("UPDATE users SET wallet_balance = %s WHERE id = %s", (new_balance, user_id))
                    conn.commit()
                    flash(f"Successfully added {amount:.2f} to your wallet. New balance: {new_balance:.2f}", "success")
                    return redirect(url_for('student_profile_page'))
            except ValueError:
                flash("Invalid amount. Please enter a valid number.", "danger")
            except Error as e:
                conn.rollback()
                if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error adding wallet balance for user {user_id}: {e}", exc_info=True)
                flash("A database error occurred. Please try again.", "danger")
            except Exception as e:
                conn.rollback()
                if hasattr(app, 'logger') and app.logger: app.logger.critical(f"Unexpected error adding wallet balance for user {user_id}: {e}", exc_info=True)
                flash("An unexpected error occurred. Please try again.", "danger")

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error on add_wallet_balance page load for user {user_id}: {e}", exc_info=True)
        flash("An error occurred. Please try again.", "danger")
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on add_wallet_balance: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
        
    return render_template('student/add_wallet_balance.html', current_balance=current_balance)

@app.route('/student/watch_video/<int:video_id>')
@student_required
def student_view_video_page(video_id):
    user_id = session.get('user_id')
    video = None
    quizzes_for_video = []
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return redirect(url_for('student_dashboard_placeholder'))
        
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT v.id, v.title, v.description, v.video_path_or_url, v.teacher_id, v.is_viewable_free_for_student,
                   u.first_name AS teacher_first_name, u.last_name AS teacher_last_name
            FROM videos v
            JOIN users u ON v.teacher_id = u.id
            WHERE v.id = %s AND v.status = 'published'
        """, (video_id,))
        video = cursor.fetchone() 

        if not video:
            flash("Video not found or is unavailable.", "danger")
            return redirect(url_for('student_dashboard_placeholder'))
        
        is_subscribed_to_teacher = False
        cursor.execute("""
            SELECT id FROM student_subscriptions
            WHERE student_id = %s AND teacher_id = %s AND status = 'active'
        """, (user_id, video['teacher_id']))
        _ = cursor.fetchone() 
        if _:
            is_subscribed_to_teacher = True

        if not video['is_viewable_free_for_student'] and not is_subscribed_to_teacher:
            flash("Access Denied: This video is premium content. Please subscribe to the teacher.", "danger")
            return redirect(url_for('public_teacher_profile_page', teacher_id=video['teacher_id']))

        cursor.execute("SELECT id FROM student_watched_videos WHERE student_id = %s AND video_id = %s", (user_id, video_id))
        _ = cursor.fetchone() 
        if not _:
            cursor.execute("INSERT INTO student_watched_videos (student_id, video_id, teacher_id) VALUES (%s, %s, %s)", (user_id, video_id, video['teacher_id']))
            cursor.execute("UPDATE videos SET views_count = views_count + 1 WHERE id = %s", (video_id,))
            conn.commit()

        cursor.execute("""
            SELECT q.id, q.title, q.description
            FROM quizzes q
            WHERE q.video_id = %s AND q.is_active = TRUE
            ORDER BY q.created_at DESC
        """, (video_id,))
        quizzes_for_video = cursor.fetchall()

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error fetching video {video_id} for user {user_id}: {e}", exc_info=True)
        flash("An error occurred while loading the video. Please try again.", "danger")
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on student_view_video_page: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('student/student_view_video.html', video=video, quizzes=quizzes_for_video)

@app.route('/student/take_quiz/<int:quiz_id>', methods=['GET', 'POST'])
@student_required
def student_take_quiz_page(quiz_id):
    user_id = session.get('user_id')
    quiz = None
    questions = []
    attempt = None
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return redirect(url_for('student_dashboard_placeholder'))
        
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT qz.id, qz.title, qz.description, qz.time_limit_minutes, qz.passing_score_percentage, qz.allow_answer_review, qz.teacher_id,
                   u.first_name AS teacher_first_name, u.last_name AS teacher_last_name
            FROM quizzes qz
            JOIN users u ON qz.teacher_id = u.id
            WHERE qz.id = %s AND qz.is_active = TRUE
        """, (quiz_id,))
        quiz = cursor.fetchone() 

        if not quiz:
            flash("Quiz not found or is inactive.", "danger")
            return redirect(url_for('student_dashboard_placeholder'))
        
        is_subscribed_to_teacher = False
        cursor.execute("""
            SELECT id FROM student_subscriptions
            WHERE student_id = %s AND teacher_id = %s AND status = 'active'
        """, (user_id, quiz['teacher_id']))
        _ = cursor.fetchone() 
        if _:
            is_subscribed_to_teacher = True
        
        if not is_subscribed_to_teacher:
            flash("Access Denied: This quiz is premium content. Please subscribe to the teacher.", "danger")
            return redirect(url_for('public_teacher_profile_page', teacher_id=quiz['teacher_id']))

        cursor.execute("""
            SELECT id, start_time, time_taken_seconds FROM quiz_attempts
            WHERE student_id = %s AND quiz_id = %s AND is_completed = FALSE
            ORDER BY start_time DESC LIMIT 1
        """, (user_id, quiz_id))
        attempt = cursor.fetchone() 

        if request.method == 'GET':
            if not attempt:
                cursor.execute("""
                    INSERT INTO quiz_attempts (student_id, quiz_id, is_completed)
                    VALUES (%s, %s, FALSE)
                """, (user_id, quiz_id))
                conn.commit()
                attempt_id = cursor.lastrowid
                attempt = {'id': attempt_id, 'start_time': datetime.utcnow(), 'time_taken_seconds': 0}
            
            cursor.execute("""
                SELECT q.id AS question_id, q.question_text, q.question_type, q.points,
                       GROUP_CONCAT(c.id ORDER BY c.id ASC) AS choice_ids,
                       GROUP_CONCAT(c.choice_text ORDER BY c.id ASC) AS choice_texts
                FROM questions q
                LEFT JOIN choices c ON q.id = c.question_id
                WHERE q.quiz_id = %s
                GROUP BY q.id
                ORDER BY q.display_order ASC
            """, (quiz_id,))
            
            raw_questions = cursor.fetchall()
            for q_row in raw_questions:
                if q_row['question_type'] == 'mc':
                    choices_list = []
                    if q_row['choice_ids'] and q_row['choice_texts']:
                        ids = [int(x) for x in q_row['choice_ids'].split(',')]
                        texts = q_row['choice_texts'].split(',')
                        for i in range(len(ids)):
                            choices_list.append({'id': ids[i], 'choice_text': texts[i]})
                    q_row['choices'] = choices_list
                questions.append(q_row)

        elif request.method == 'POST':
            if not attempt:
                flash("No active quiz attempt found. Please start the quiz again.", "danger")
                return redirect(url_for('student_take_quiz_page', quiz_id=quiz.id))

            total_score = 0
            max_possible_score = 0
            
            cursor.execute("""
                SELECT q.id AS question_id, q.question_type, q.points, c.id AS choice_id, c.is_correct
                FROM questions q
                LEFT JOIN choices c ON q.id = c.question_id
                WHERE q.quiz_id = %s
            """, (quiz_id,))
            quiz_questions_data = cursor.fetchall()
            
            questions_map = {}
            for q_data in quiz_questions_data:
                q_id = q_data['question_id']
                if q_id not in questions_map:
                    questions_map[q_id] = {'points': q_data['points'], 'type': q_data['question_type'], 'choices': {}}
                if q_data['choice_id']:
                    questions_map[q_id]['choices'][q_data['choice_id']] = q_data['is_correct']

            cursor.execute("DELETE FROM student_answers WHERE attempt_id = %s", (attempt['id'],))
            
            for question_id_str in request.form:
                if question_id_str.startswith('question_'):
                    q_id = int(question_id_str.replace('question_', ''))
                    
                    if q_id not in questions_map:
                        if hasattr(app, 'logger') and app.logger: app.logger.warning(f"Attempting to answer non-existent question {q_id} for quiz {quiz_id}.")
                        continue

                    question_info = questions_map[q_id]
                    max_possible_score += question_info['points']

                    if question_info['type'] == 'mc':
                        selected_choice_id = request.form.get(question_id_str)
                        if selected_choice_id:
                            selected_choice_id = int(selected_choice_id)
                            is_mc_correct = question_info['choices'].get(selected_choice_id, False)
                            points_awarded = question_info['points'] if is_mc_correct else 0
                            total_score += points_awarded
                            
                            cursor.execute("""
                                INSERT INTO student_answers (attempt_id, question_id, selected_choice_id, is_mc_correct, points_awarded)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (attempt['id'], q_id, selected_choice_id, is_mc_correct, points_awarded))
                        else:
                            cursor.execute("""
                                INSERT INTO student_answers (attempt_id, question_id, selected_choice_id, is_mc_correct, points_awarded)
                                VALUES (%s, %s, NULL, FALSE, 0)
                            """, (attempt['id'], q_id))
                    elif question_info['type'] == 'essay':
                        essay_answer_text = request.form.get(question_id_str, '').strip()
                        cursor.execute("""
                            INSERT INTO student_answers (attempt_id, question_id, essay_answer_text, points_awarded)
                            VALUES (%s, %s, %s, 0)
                        """, (attempt['id'], q_id, essay_answer_text if essay_answer_text else None))

            time_taken_seconds = (datetime.utcnow() - attempt['start_time']).total_seconds() if attempt['start_time'] else None
            
            passed = (total_score >= (max_possible_score * (quiz['passing_score_percentage'] / 100))) if max_possible_score > 0 else False
            if max_possible_score == 0 and total_score == 0: passed = True

            cursor.execute("""
                UPDATE quiz_attempts SET
                end_time = %s, score = %s, max_possible_score = %s, time_taken_seconds = %s,
                submitted_at = %s, is_completed = TRUE, passed = %s
                WHERE id = %s
            """, (datetime.utcnow(), total_score, max_possible_score, time_taken_seconds,
                  datetime.utcnow(), passed, attempt['id']))
            conn.commit()

            flash("Quiz submitted successfully! See your results below.", "success")
            return redirect(url_for('student_quiz_result_page', attempt_id=attempt['id']))

    except Error as e:
        conn.rollback()
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error on student_take_quiz_page for quiz {quiz_id} and user {user_id}: {e}", exc_info=True)
        flash("A database error occurred. Please try again.", "danger")
    except Exception as e:
        conn.rollback()
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on student_take_quiz_page: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('student/student_take_quiz.html', quiz=quiz, questions=questions, attempt=attempt)


@app.route('/student/quiz_result/<int:attempt_id>')
@student_required
def student_quiz_result_page(attempt_id):
    user_id = session.get('user_id')
    attempt = None
    answers_data = []

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return redirect(url_for('student_dashboard_placeholder'))
        
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT qa.id, qa.quiz_id, qa.score, qa.max_possible_score, qa.submitted_at, qa.passed, qa.time_taken_seconds,
                   q.title AS quiz_title, q.description AS quiz_description, q.passing_score_percentage, q.allow_answer_review
            FROM quiz_attempts qa
            JOIN quizzes q ON qa.quiz_id = q.id
            WHERE qa.id = %s AND qa.student_id = %s AND qa.is_completed = TRUE
        """, (attempt_id, user_id))
        attempt = cursor.fetchone() 

        if not attempt:
            flash("Quiz attempt not found or not completed, or you don't have permission.", "danger")
            return redirect(url_for('student_dashboard_placeholder'))
        
        if attempt['allow_answer_review']:
            cursor.execute("""
                SELECT sa.id AS answer_id, sa.selected_choice_id, sa.essay_answer_text, sa.is_mc_correct, sa.points_awarded,
                       q.id AS question_id, q.question_text, q.question_type, q.points AS question_max_points,
                       GROUP_CONCAT(CASE WHEN c.is_correct THEN c.choice_text ELSE NULL END) AS correct_choice_text,
                       selected_c.choice_text AS student_choice_text
                FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                LEFT JOIN choices c ON q.id = c.question_id AND c.is_correct = TRUE
                LEFT JOIN choices selected_c ON sa.selected_choice_id = selected_c.id
                WHERE sa.attempt_id = %s
                GROUP BY sa.id, q.id
                ORDER BY q.display_order ASC
            """, (attempt_id,))
            answers_data = cursor.fetchall()
            
    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"DB Error fetching quiz result {attempt_id} for user {user_id}: {e}", exc_info=True)
        flash("An error occurred while loading quiz results. Please try again.", "danger")
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"General error on student_quiz_result_page: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "danger")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

    return render_template('student/student_quiz_result.html', attempt=attempt, answers_data=answers_data)


# --- Language Switcher ---
@app.route('/switch_lang/<string:lang_code>')
def switch_lang(lang_code):
    if lang_code in ['en', 'ar']:
        session['current_lang'] = lang_code
    return redirect(request.referrer or url_for('home'))

# --- API Endpoints (for JS dashboard stats animation) ---
@app.route('/api/teacher/dashboard_stats')
@teacher_required
def api_teacher_dashboard_stats():
    user_id = session.get('user_id')
    stats = {
        'subscribers': 0,
        'total_views': 0,
        'quizzes_count': 0,
        'questions_count': 0
    }
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) AS count FROM student_subscriptions WHERE teacher_id = %s AND status = 'active'", (user_id,))
            stats['subscribers'] = cursor.fetchone()['count']

            cursor.execute("SELECT SUM(views_count) AS total FROM videos WHERE teacher_id = %s", (user_id,))
            total_views_result = cursor.fetchone()['total']
            stats['total_views'] = total_views_result if total_views_result is not None else 0

            cursor.execute("SELECT COUNT(*) AS count FROM quizzes WHERE teacher_id = %s", (user_id,))
            stats['quizzes_count'] = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(q.id) AS count FROM questions q
                JOIN quizzes quiz ON q.quiz_id = quiz.id
                WHERE quiz.teacher_id = %s
            """, (user_id,))
            stats['questions_count'] = cursor.fetchone()['count']

    except Error as e:
        if hasattr(app, 'logger') and app.logger: app.logger.error(f"API_ERROR: DB Error fetching teacher dashboard stats for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': 'Database error fetching stats'}), 500
    except Exception as e:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"API_ERROR: Unexpected error fetching teacher dashboard stats for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': 'Unexpected server error'}), 500
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
    return jsonify(stats)


# --- 13. Application Runner and Logger Setup ---
if __name__ == '__main__':
    log_level_config_str = os.getenv('FLASK_LOG_LEVEL', 'INFO' if not app.debug else 'DEBUG').upper()
    effective_log_level = getattr(logging, log_level_config_str, logging.INFO) 
    logging.basicConfig(level=effective_log_level, format='%(asctime)s %(levelname)s: %(name)s - %(message)s [in %(pathname)s:%(lineno)d]')
    if not app.debug and not os.environ.get("WERKZEUG_RUN_MAIN"): 
        log_directory = 'logs'
        ensure_directory_exists(log_directory, "Application Logs Directory") 
        application_log_file_path = os.path.join(log_directory, 'ektbariny_app.log')
        try:
            main_file_handler = RotatingFileHandler(
                application_log_file_path, maxBytes=25*1024*1024, backupCount=7, encoding='utf-8'
            )
            file_formatter = logging.Formatter(
                '%(asctime)s %(levelname)-8s [%(threadName)s] %(module)s.%(funcName)s:%(lineno)d - %(message)s'
            )
            main_file_handler.setFormatter(file_formatter)
            main_file_handler.setLevel(logging.INFO)
            if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
                app.logger.addHandler(main_file_handler)
            app.logger.setLevel(logging.INFO) 
            if hasattr(app, 'logger') and app.logger: app.logger.info("--- Ektbariny Application Starting Up (File Logger Configured and Active) ---")
        except Exception as e_logger_config:
            logging.error(f"CRITICAL: Failed to initialize file logger at '{application_log_file_path}': {e_logger_config}", exc_info=True)
            print(f"!!! [LOGGER_CRITICAL_ERROR] File logger initialization failed: {e_logger_config} !!!")
    elif app.debug:
        app.logger.setLevel(logging.DEBUG) 
        if hasattr(app, 'logger') and app.logger: app.logger.debug("--- Ektbariny Application Starting in DEBUG Mode (Console Logger Active at DEBUG Level) ---")
    try:
        if hasattr(app, 'logger') and app.logger: app.logger.info(f"--- [APP_INIT] Initializing Ektbariny Application. App Name: {app.name}, Time: {datetime.now()} ---")
        if os.getenv('CREATE_TABLES_ON_STARTUP', 'True').lower() in ('true', '1', 'yes'):
            if hasattr(app, 'logger') and app.logger: app.logger.info("--- [DB_SETUP_TASK] CREATE_TABLES_ON_STARTUP is True. Initiating table creation/verification... ---")
            if not create_tables():
                if hasattr(app, 'logger') and app.logger: app.logger.critical("!!! [DB_SETUP_CRITICAL_FAILURE] Database or table creation/verification FAILED. Application may not function as expected. !!!")
            else:
                if hasattr(app, 'logger') and app.logger: app.logger.info("--- [DB_SETUP_TASK] Database and tables setup process completed (or structures already exist). ---")
        else:
            if hasattr(app, 'logger') and app.logger: app.logger.info("--- [DB_SETUP_TASK] Skipping automatic table creation/verification based on 'CREATE_TABLES_ON_STARTUP' environment variable. ---")
        server_host = os.getenv('FLASK_HOST', '0.0.0.0')
        try:
            server_port = int(os.getenv('FLASK_PORT', '5001'))
        except ValueError:
            if hasattr(app, 'logger') and app.logger: app.logger.warning(f"Invalid FLASK_PORT value '{os.getenv('FLASK_PORT')}'. Defaulting to port 5001.")
            server_port = 5001
        if hasattr(app, 'logger') and app.logger: app.logger.info(f"--- [FLASK_SERVER_START] Attempting to start Flask development server on http://{server_host}:{server_port}/ (Application Debug Mode: {app.debug}) ---")
        app.run(host=server_host, port=server_port, debug=app.debug)
    except SystemExit as e_system_exit:
        if hasattr(app, 'logger') and app.logger: app.logger.warning(f"Application terminated via SystemExit with code {e_system_exit.code}.", exc_info=True)
    except OSError as e_os_error:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"OSError during application startup (Is port {server_port} already in use?): {e_os_error}", exc_info=True)
    except Exception as e_general_startup_error:
        if hasattr(app, 'logger') and app.logger: app.logger.critical(f"FATAL UNHANDLED EXCEPTION during application startup sequence: {e_general_startup_error}", exc_info=True)
    finally:
        shutdown_log_message = f"-------- Ektbariny Application Is Shutting Down (Timestamp: {datetime.now()}) --------"
        if hasattr(app, 'logger') and app.logger.handlers and any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
            if hasattr(app, 'logger') and app.logger: app.logger.info(shutdown_log_message)
        else: 
            print(shutdown_log_message)