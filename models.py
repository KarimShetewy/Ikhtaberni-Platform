# models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random
import string

# قم بإنشاء كائن db هنا. سيتم تهيئته في app.py
db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users' # اسم الجدول في قاعدة البيانات

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=True) # اسم مستخدم يمكن أن يكون اختياريًا أو محذوفًا
    email = db.Column(db.String(120), unique=True, nullable=True) # بريد إلكتروني يمكن أن يكون اختياريًا
    phone_number = db.Column(db.String(20), unique=True, nullable=False) # رقم الموبايل، أساسي وفريد
    password_hash = db.Column(db.String(256), nullable=False) # لتخزين كلمة المرور المشفرة

    # حقول خاصة بعملية استعادة كلمة المرور عبر OTP
    otp_code = db.Column(db.String(8), nullable=True) # رمز التأكيد المرسل
    otp_expiry = db.Column(db.DateTime, nullable=True) # وقت انتهاء صلاحية الرمز

    # يمكنك إضافة حقول أخرى مثل تاريخ الإنشاء، الأدوار، إلخ.
    # date_created = db.Column(db.DateTime, default=datetime.utcnow)
    # role = db.Column(db.String(50), default='student')


    def __init__(self, phone_number, password, username=None, email=None):
        self.phone_number = phone_number
        self.set_password(password)
        if username:
            self.username = username
        if email:
            self.email = email

    def set_password(self, password):
        """تشفير كلمة المرور وتعيينها."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """التحقق من كلمة المرور المدخلة مقابل الهاش المخزن."""
        return check_password_hash(self.password_hash, password)

    def generate_otp(self):
        """توليد رمز تأكيد OTP وتعيين تاريخ انتهاء صلاحيته."""
        # توليد OTP مكون من 8 أرقام عشوائية
        generated_otp = "".join(random.choices(string.digits, k=8))
        self.otp_code = generated_otp
        self.otp_expiry = datetime.utcnow() + timedelta(minutes=10) # صلاحية 10 دقائق
        return generated_otp # إرجاع الرمز المولّد ليتم إرساله (أو طباعته للاختبار)

    def is_otp_valid(self, provided_otp):
        """التحقق مما إذا كان الـ OTP المقدم صحيحًا ولم تنتهِ صلاحيته."""
        if self.otp_code == provided_otp and self.otp_expiry and self.otp_expiry > datetime.utcnow():
            return True
        return False

    def clear_otp(self):
        """مسح بيانات الـ OTP بعد استخدامه أو انتهاء صلاحيته."""
        self.otp_code = None
        self.otp_expiry = None

    def __repr__(self):
        return f'<User id={self.id}, phone_number={self.phone_number}>'

# يمكنك إضافة نماذج أخرى هنا إذا احتجت (مثل Quiz, Question, إلخ.)
# مثال:
# class Quiz(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     title = db.Column(db.String(100), nullable=False)
#     # ...