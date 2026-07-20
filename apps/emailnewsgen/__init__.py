from flask import Blueprint, render_template, request, jsonify, Response, redirect, url_for
from models import db, Setting, Newsletter
import json
import re
import time

emailnewsgen_bp = Blueprint("emailnewsgen", __name__, url_prefix="/emailnewsgen")


def get_groq_key():
    s = Setting.query.filter_by(key="GROQ_API_KEY").first()
    return s.value.strip() if s else ""


def extract_json(text: str) -> dict:
    """Robustly extract the first complete JSON object from arbitrary text."""
    text = text.strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fence
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Find outermost { … } by tracking brace depth
    start = text.find('{')
    if start != -1:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\' and in_str:
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break

    raise json.JSONDecodeError(
        f"No valid JSON found. Raw (first 300 chars): {text[:300]}",
        text, 0,
    )


def groq_newsletter(client, messages, max_tokens=4500, retries=4):
    """Call Groq with JSON mode and retry on rate-limit or parse failures."""
    from groq import RateLimitError
    delay = 1.5
    json_failures = 0
    raw = ""

    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or ""
            return extract_json(raw)
        except RateLimitError as e:
            if attempt == retries - 1:
                raise
            wait = delay
            m = re.search(r'in (\d+(?:\.\d+)?)s', str(e))
            if m:
                wait = float(m.group(1)) + 0.5
            else:
                m = re.search(r'in (\d+)ms', str(e))
                if m:
                    wait = int(m.group(1)) / 1000 + 0.5
            time.sleep(wait)
            delay *= 2
        except json.JSONDecodeError:
            json_failures += 1
            if json_failures >= 3 or attempt == retries - 1:
                raise
            messages = list(messages) + [
                {"role": "assistant", "content": raw},
                {"role": "user",      "content": "Your response was not valid JSON. Return only a valid JSON object with keys 'subject' and 'content_html', nothing else."},
            ]
            time.sleep(1.0)


@emailnewsgen_bp.route("/")
def index():
    newsletters = Newsletter.query.order_by(Newsletter.created_at.desc()).limit(20).all()
    return render_template("emailnewsgen/index.html", newsletters=newsletters)


@emailnewsgen_bp.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    topic       = data.get("topic", "").strip()
    audience    = data.get("audience", "General audience").strip() or "General audience"
    tone        = data.get("tone", "Professional")
    num_sections = max(2, min(5, int(data.get("num_sections", 3))))
    cta_text    = data.get("cta_text", "Learn More").strip() or "Learn More"

    if not topic:
        return jsonify({"error": "Topic is required."}), 400

    key = get_groq_key()
    if not key:
        return jsonify({"error": "Groq API key not configured. Set it in Admin → Settings."}), 400

    try:
        from groq import Groq
        client = Groq(api_key=key)

        prompt = (
            f"You are an expert HTML email designer.\n"
            f"Write a {tone} email newsletter about: {topic}\n"
            f"Target audience: {audience}\n"
            f"Include exactly {num_sections} content sections and a CTA button that says \"{cta_text}\".\n\n"
            "Return a JSON object with exactly two keys:\n"
            "  subject  — a compelling email subject line (max 70 characters)\n"
            "  content_html — a complete, self-contained HTML email body with ALL styles inline\n\n"
            "HTML requirements:\n"
            "- Outer wrapper: <div style=\"font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#ffffff;\">\n"
            "- Header: gradient banner with newsletter title in large bold white text\n"
            f"- Body: {num_sections} sections, each with a bold coloured heading and 2-3 sentences of body text\n"
            f"- CTA: a prominent button styled with background-color, padding, border-radius, and text \"{cta_text}\"\n"
            "- Footer: small grey text with unsubscribe note\n"
            f"- Colour palette should feel {tone.lower()} and professional\n"
            "- All CSS must be inline (no <style> tags)\n"
            "- Use single quotes for all HTML attribute values (e.g. style='color:red') so the JSON string needs no extra escaping\n"
        )

        parsed = groq_newsletter(client, [
            {"role": "system", "content": "You are an expert HTML email designer. Always respond with valid JSON only."},
            {"role": "user",   "content": prompt},
        ])

        subject      = parsed.get("subject") or topic
        content_html = parsed.get("content_html") or parsed.get("html") or ""

        if not content_html:
            return jsonify({"error": "AI returned an empty newsletter. Please try again."}), 500

        nl = Newsletter(
            subject=subject,
            topic=topic,
            audience=audience,
            tone=tone,
            content_html=content_html,
        )
        db.session.add(nl)
        db.session.commit()

        return jsonify({
            "success":      True,
            "id":           nl.id,
            "subject":      nl.subject,
            "content_html": nl.content_html,
        })

    except json.JSONDecodeError:
        return jsonify({"error": "AI returned an invalid response after several attempts. Please try again."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@emailnewsgen_bp.route("/<int:nl_id>/preview")
def preview(nl_id):
    nl = Newsletter.query.get_or_404(nl_id)
    return render_template("emailnewsgen/preview.html", nl=nl)


@emailnewsgen_bp.route("/<int:nl_id>/save", methods=["POST"])
def save(nl_id):
    nl = Newsletter.query.get_or_404(nl_id)
    data = request.get_json()
    subject = (data.get("subject") or "").strip()
    content_html = (data.get("content_html") or "").strip()
    if subject:
        nl.subject = subject
    if content_html:
        nl.content_html = content_html
    db.session.commit()
    return jsonify({"success": True, "subject": nl.subject})


@emailnewsgen_bp.route("/<int:nl_id>/download")
def download(nl_id):
    nl = Newsletter.query.get_or_404(nl_id)
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{nl.subject}</title>
</head>
<body style="margin:0;padding:20px;background:#f4f4f4;font-family:Arial,sans-serif;">
{nl.content_html}
</body>
</html>"""
    safe = "".join(c for c in nl.subject[:30] if c.isalnum() or c in " _-").strip().replace(" ", "_")
    filename = f"Newsletter_{nl.id}_{safe}.html"
    return Response(
        full_html,
        mimetype="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@emailnewsgen_bp.route("/<int:nl_id>/delete", methods=["POST"])
def delete(nl_id):
    nl = Newsletter.query.get_or_404(nl_id)
    db.session.delete(nl)
    db.session.commit()
    return jsonify({"success": True})
