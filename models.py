from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ── Shared ────────────────────────────────────────────────────────────────────
class Setting(db.Model):
    __tablename__ = "settings"
    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default="")

# ── Course Generator ──────────────────────────────────────────────────────────
class Course(db.Model):
    __tablename__ = "courses"
    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(400))
    topic         = db.Column(db.Text)
    difficulty    = db.Column(db.String(50))
    language      = db.Column(db.String(100))
    total_modules = db.Column(db.Integer, default=0)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    modules       = db.relationship("CourseModule", backref="course",
                                    cascade="all, delete-orphan", order_by="CourseModule.number")

class CourseModule(db.Model):
    __tablename__ = "course_modules"
    id         = db.Column(db.Integer, primary_key=True)
    course_id  = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    number     = db.Column(db.Integer)
    title      = db.Column(db.String(400))
    content    = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    quizzes    = db.relationship("CourseQuiz",       backref="module",
                                 cascade="all, delete-orphan")
    assignments = db.relationship("CourseAssignment", backref="module",
                                  cascade="all, delete-orphan")

class CourseQuiz(db.Model):
    __tablename__  = "course_quizzes"
    id             = db.Column(db.Integer, primary_key=True)
    module_id      = db.Column(db.Integer, db.ForeignKey("course_modules.id"), nullable=False)
    question       = db.Column(db.Text)
    options        = db.Column(db.Text)   # JSON list of 4 strings
    correct_answer = db.Column(db.Integer)  # 0-based index
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

class CourseAssignment(db.Model):
    __tablename__ = "course_assignments"
    id          = db.Column(db.Integer, primary_key=True)
    module_id   = db.Column(db.Integer, db.ForeignKey("course_modules.id"), nullable=False)
    title       = db.Column(db.String(400))
    description = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

# ── Email Newsletter ──────────────────────────────────────────────────────────
class Newsletter(db.Model):
    __tablename__ = "newsletters"
    id           = db.Column(db.Integer, primary_key=True)
    subject      = db.Column(db.String(500))
    topic        = db.Column(db.Text)
    audience     = db.Column(db.String(200))
    tone         = db.Column(db.String(100))
    content_html = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

# ── Activity Book ─────────────────────────────────────────────────────────────
class ActivityBook(db.Model):
    __tablename__ = "activity_books"
    id         = db.Column(db.Integer, primary_key=True)
    theme      = db.Column(db.String(200))
    difficulty = db.Column(db.String(50))
    age_group  = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    activities = db.relationship("Activity", backref="book",
                                 cascade="all, delete-orphan", order_by="Activity.id")

class Activity(db.Model):
    __tablename__  = "activities"
    id             = db.Column(db.Integer, primary_key=True)
    book_id        = db.Column(db.Integer, db.ForeignKey("activity_books.id"), nullable=False)
    activity_type  = db.Column(db.String(50))   # wordsearch | sudoku | maze | crossword | trivia
    title          = db.Column(db.String(200))
    data           = db.Column(db.Text)          # JSON payload
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
