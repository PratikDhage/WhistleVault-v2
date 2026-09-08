"""
WhistleVault -- application factory.

Run locally with:
    flask --app app run --debug

Run in production with (see Procfile):
    gunicorn app:app
"""
import logging
import os

from flask import Flask, jsonify, render_template

from config import get_config
from extensions import db, bcrypt, limiter, csrf, migrate
from utils.email import email_service
from utils.security import apply_secure_headers


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or get_config())

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be configured.")
    if not app.config.get("ADMIN_PASSWORD") and not app.config.get("ADMIN_PASSWORD_HASH"):
        raise RuntimeError("ADMIN_PASSWORD_HASH must be configured.")

    logging.basicConfig(level=logging.INFO if not app.debug else logging.DEBUG)

    # --- Extensions ---
    db.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    email_service.init_app(app)

    os.makedirs(app.config["MEDIA_FOLDER"], exist_ok=True)

    # --- Blueprints ---
    from blueprints.auth import auth_bp
    from blueprints.posts import posts_bp
    from blueprints.admin import admin_bp
    from blueprints.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)

    # --- Security headers on every response ---
    app.after_request(apply_secure_headers)

    # --- Error handlers ---
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/error.html", code=403, message="Forbidden"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/error.html", code=404, message="Not found"), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large. Max upload size is 8MB."}), 413

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({"error": "Too many requests. Please slow down."}), 429

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server error")
        return render_template("errors/error.html", code=500, message="Something went wrong"), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))
