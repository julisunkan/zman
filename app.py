import os
import logging
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db

logging.basicConfig(level=logging.INFO)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'data.db')}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
    app.config["UPLOAD_FOLDER"] = os.path.join(basedir, "static", "uploads")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    from apps.coursegen import coursegen_bp
    from apps.emailnewsgen import emailnewsgen_bp
    from apps.actgen import actgen_bp
    from apps.admin import admin_bp
    from apps.pwa import pwa_bp

    app.register_blueprint(pwa_bp)
    app.register_blueprint(coursegen_bp)
    app.register_blueprint(emailnewsgen_bp)
    app.register_blueprint(actgen_bp)
    app.register_blueprint(admin_bp)

    import json as _json
    @app.template_filter("from_json")
    def from_json_filter(s):
        try:
            return _json.loads(s)
        except Exception:
            return []

    @app.route("/")
    def index():
        return render_template("index.html")

    with app.app_context():
        db.create_all()
        from models import Setting
        if not Setting.query.filter_by(key="GROQ_API_KEY").first():
            db.session.add(Setting(key="GROQ_API_KEY", value=""))
            db.session.commit()

    return app

app = create_app()
