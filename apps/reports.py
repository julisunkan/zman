"""Public report-submission endpoint for all AI-generated content."""
from flask import Blueprint, request, jsonify
from models import db, ContentReport, Course, Newsletter, ActivityBook

reports_bp = Blueprint("reports", __name__)

VALID_TYPES = {"course", "newsletter", "book"}

REASON_LABELS = {
    "harmful":       "Harmful or offensive content",
    "inaccurate":    "Inaccurate information",
    "inappropriate": "Inappropriate for the audience",
    "copyright":     "Copyright or plagiarism concern",
    "other":         "Other",
}


def _snapshot_title(content_type, content_id):
    """Return a human-readable title for the reported item."""
    if content_type == "course":
        obj = Course.query.get(content_id)
        return (obj.title or obj.topic) if obj else ""
    if content_type == "newsletter":
        obj = Newsletter.query.get(content_id)
        return obj.subject if obj else ""
    if content_type == "book":
        obj = ActivityBook.query.get(content_id)
        return obj.theme if obj else ""
    return ""


@reports_bp.route("/report/submit", methods=["POST"])
def submit():
    data = request.get_json() or {}
    content_type = (data.get("content_type") or "").strip()
    content_id   = int(data.get("content_id") or 0)
    reason_key   = (data.get("reason") or "").strip()
    details      = (data.get("details") or "").strip()[:1000]

    if content_type not in VALID_TYPES:
        return jsonify({"error": "Invalid content type."}), 400
    if reason_key not in REASON_LABELS:
        return jsonify({"error": "Please select a reason."}), 400
    if not content_id:
        return jsonify({"error": "Missing content ID."}), 400

    report = ContentReport(
        content_type  = content_type,
        content_id    = content_id,
        content_title = _snapshot_title(content_type, content_id),
        reason        = REASON_LABELS[reason_key],
        details       = details,
    )
    db.session.add(report)
    db.session.commit()
    return jsonify({"success": True})
