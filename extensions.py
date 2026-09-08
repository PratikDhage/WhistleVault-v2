"""
Extension instances, created here (uninitialized) and bound to the app
in app.py via .init_app(). Keeping them here avoids circular imports
between blueprints and the app factory.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from flask_migrate import Migrate

db = SQLAlchemy()
bcrypt = Bcrypt()
limiter = Limiter(key_func=get_remote_address)
csrf = CSRFProtect()
migrate = Migrate()
