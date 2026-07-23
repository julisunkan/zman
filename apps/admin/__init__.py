import functools
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from models import db, Setting, Course, Newsletter, ActivityBook, ContentReport
from werkzeug.security import check_password_hash, generate_password_hash

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# ── Auth helpers ──────────────────────────────────────────────────────────────

def _get_admin_password():
    """Return the stored admin password hash, or None if not set."""
    s = Setting.query.filter_by(key="ADMIN_PASSWORD").first()
    return s.value.strip() if s and s.value.strip() else None


def _auth_required(f):
    """Decorator: block access unless the admin session is active."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        pw_hash = _get_admin_password()
        # If no password is configured, admin panel is open (first-run UX)
        if pw_hash and not session.get("admin_authed"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return wrapper


# ── Auth routes ───────────────────────────────────────────────────────────────

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    pw_hash = _get_admin_password()
    # No password set — skip login entirely
    if not pw_hash:
        session["admin_authed"] = True
        return redirect(url_for("admin.index"))

    error = None
    if request.method == "POST":
        entered = request.form.get("password", "")
        if check_password_hash(pw_hash, entered):
            session["admin_authed"] = True
            return redirect(url_for("admin.index"))
        error = "Incorrect password."

    return render_template("admin/login.html", error=error)


@admin_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("admin_authed", None)
    return redirect(url_for("admin.login"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stats():
    return {
        "courses":     Course.query.count(),
        "newsletters": Newsletter.query.count(),
        "books":       ActivityBook.query.count(),
        "settings":    Setting.query.count(),
        "reports":     ContentReport.query.count(),
        "pending_reports": ContentReport.query.filter_by(status="pending").count(),
    }


# ── Main routes ───────────────────────────────────────────────────────────────

@admin_bp.route("/")
@_auth_required
def index():
    settings    = Setting.query.order_by(Setting.key).all()
    stats       = _stats()
    courses     = Course.query.order_by(Course.created_at.desc()).all()
    newsletters = Newsletter.query.order_by(Newsletter.created_at.desc()).all()
    books       = ActivityBook.query.order_by(ActivityBook.created_at.desc()).all()
    reports     = ContentReport.query.order_by(ContentReport.created_at.desc()).all()
    return render_template(
        "admin/index.html",
        settings=settings,
        stats=stats,
        courses=courses,
        newsletters=newsletters,
        books=books,
        reports=reports,
    )


@admin_bp.route("/settings/save", methods=["POST"])
@_auth_required
def settings_save():
    data  = request.get_json()
    key   = (data.get("key") or "").strip()
    value = (data.get("value") or "").strip()
    if not key:
        return jsonify({"error": "Key is required."}), 400

    # Hash the password before storing
    if key == "ADMIN_PASSWORD" and value:
        value = generate_password_hash(value)

    s = Setting.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        s = Setting(key=key, value=value)
        db.session.add(s)
    db.session.commit()
    return jsonify({"success": True, "id": s.id})


@admin_bp.route("/settings/add", methods=["POST"])
@_auth_required
def settings_add():
    data  = request.get_json()
    key   = (data.get("key") or "").strip()
    value = (data.get("value") or "").strip()
    if not key:
        return jsonify({"error": "Key is required."}), 400
    if Setting.query.filter_by(key=key).first():
        return jsonify({"error": f"Setting '{key}' already exists."}), 409

    if key == "ADMIN_PASSWORD" and value:
        value = generate_password_hash(value)

    s = Setting(key=key, value=value)
    db.session.add(s)
    db.session.commit()
    return jsonify({"success": True, "id": s.id, "key": s.key, "value": ""})


@admin_bp.route("/settings/delete/<int:setting_id>", methods=["POST"])
@_auth_required
def settings_delete(setting_id):
    s = Setting.query.get_or_404(setting_id)
    db.session.delete(s)
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/settings/set-password", methods=["POST"])
@_auth_required
def settings_set_password():
    """Dedicated endpoint for changing the admin password."""
    data = request.get_json()
    new_pw = (data.get("password") or "").strip()
    if not new_pw:
        return jsonify({"error": "Password cannot be empty."}), 400

    s = Setting.query.filter_by(key="ADMIN_PASSWORD").first()
    hashed = generate_password_hash(new_pw)
    if s:
        s.value = hashed
    else:
        s = Setting(key="ADMIN_PASSWORD", value=hashed)
        db.session.add(s)
    db.session.commit()
    # Keep the session valid after password change
    session["admin_authed"] = True
    return jsonify({"success": True})


@admin_bp.route("/data/delete/<string:model>/<int:record_id>", methods=["POST"])
@_auth_required
def data_delete(model, record_id):
    model_map = {
        "course":     Course,
        "newsletter": Newsletter,
        "book":       ActivityBook,
    }
    cls = model_map.get(model)
    if not cls:
        return jsonify({"error": "Unknown model."}), 400

    record = cls.query.get_or_404(record_id)
    db.session.delete(record)
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/reports/<int:report_id>/update-status", methods=["POST"])
@_auth_required
def report_update_status(report_id):
    data   = request.get_json() or {}
    status = data.get("status", "")
    if status not in ("pending", "reviewed", "dismissed"):
        return jsonify({"error": "Invalid status."}), 400
    r = ContentReport.query.get_or_404(report_id)
    r.status = status
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/reports/<int:report_id>/delete", methods=["POST"])
@_auth_required
def report_delete(report_id):
    r = ContentReport.query.get_or_404(report_id)
    db.session.delete(r)
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/reports/delete-all", methods=["POST"])
@_auth_required
def reports_delete_all():
    ContentReport.query.delete()
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/data/delete-all/<string:model>", methods=["POST"])
@_auth_required
def data_delete_all(model):
    model_map = {
        "course":     Course,
        "newsletter": Newsletter,
        "book":       ActivityBook,
    }
    cls = model_map.get(model)
    if not cls:
        return jsonify({"error": "Unknown model."}), 400

    # Fetch all instances and delete individually so SQLAlchemy
    # cascade rules (delete-orphan on child relationships) fire correctly.
    records = cls.query.all()
    for record in records:
        db.session.delete(record)
    db.session.commit()
    return jsonify({"success": True})
