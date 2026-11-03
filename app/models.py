from datetime import datetime, timezone
from flask import current_app
from flask_login import UserMixin
from app.extensions import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer as Serializer

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    headline = db.Column(db.String(150))
    bio = db.Column(db.Text)
    profile_pic = db.Column(db.String(200), default='default.jpg')
    is_instructor = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active_account = db.Column(db.Boolean, default=True)   # False = suspended
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    otp_hash = db.Column(db.String(256))
    otp_expires_at = db.Column(db.DateTime)
    otp_sent_at = db.Column(db.DateTime)
    otp_resend_count = db.Column(db.Integer, default=0, nullable=False)
    otp_resend_window_start = db.Column(db.DateTime)
    otp_attempts = db.Column(db.Integer, default=0, nullable=False)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    login_locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    courses = db.relationship('Course', backref='instructor', lazy=True)
    enrollments = db.relationship('Enrollment', backref='student', lazy=True,
                                  cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):            # Flask-Login: suspended users can't log in
        return bool(self.is_active_account)

    def __repr__(self):
        return f'<User {self.email}>'


    # def get_reset_token(self):     # Generates a token for password reset that expires after 30 minutes (1800 seconds)
    #     s = Serializer(current_app.config['SECRET_KEY'])
    #     return s.dumps({'user_id': self.id})

    # @staticmethod
    # def verify_reset_token(token, max_age=1800):
    #     s = Serializer(current_app.config['SECRET_KEY'])
    #     try:
    #         user_id = s.loads(token, max_age=max_age)['user_id']
    #     except:
    #         return None
    #     return db.session.get(User, user_id)
class LoginAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    attempted_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False, index=True)


# Courses   
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    courses = db.relationship('Course', backref='category', lazy=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    thumbnail = db.Column(db.String(200))
    level = db.Column(db.String(20))                      # beginner | intermediate | advanced
    is_published = db.Column(db.Boolean, default=False, index=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    sections = db.relationship('Section', backref='course', lazy=True,
                               order_by='Section.position', cascade='all, delete-orphan')
    enrollments = db.relationship('Enrollment', backref='course', lazy=True,
                                  cascade='all, delete-orphan')

    @property
    def lesson_count(self):
        return sum(len(s.lessons) for s in self.sections)

    @property
    def enrollment_count(self):
        return len(self.enrollments)


class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    position = db.Column(db.Integer, default=0)

    lessons = db.relationship('Lesson', backref='section', lazy=True,
                              order_by='Lesson.position', cascade='all, delete-orphan')


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text)                             # text content (sanitize before saving)
    video_url = db.Column(db.String(300))                 # embed URL only
    position = db.Column(db.Integer, default=0)
    is_preview = db.Column(db.Boolean, default=False)     # free preview, optional for later


# ───────────────────────── Learning progress ─────────────────────────
class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    enrolled_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('student_id', 'course_id'),)

    progress = db.relationship('LessonProgress', backref='enrollment', lazy=True,
                               cascade='all, delete-orphan')

    @property
    def progress_percent(self):
        total = self.course.lesson_count
        return round(len(self.progress) / total * 100) if total else 0

    @property
    def completed_lesson_ids(self):
        return {p.lesson_id for p in self.progress}


class LessonProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollment.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('enrollment_id', 'lesson_id'),)

    # deleting a lesson also deletes its progress rows
    lesson = db.relationship('Lesson',
                             backref=db.backref('progress', cascade='all, delete-orphan'))



# ───────────────────────── Moderation ─────────────────────────
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')      # open | resolved
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    course = db.relationship('Course',
                             backref=db.backref('reports', cascade='all, delete-orphan'))
    reporter = db.relationship('User')

class ProfileUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    summary = db.Column(db.String(120), nullable=False)       # e.g. "Bio updated"
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('profile_updates', cascade='all, delete-orphan'))