"""Flask extension instances, created unbound and wired to the app in create_app().

Kept separate from app/__init__.py so any module can import db/jwt/bcrypt without
triggering a circular import with the app factory itself.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt

db = SQLAlchemy()  # ORM: models, session, query interface, and Alembic's schema source of truth
migrate = Migrate()  # Alembic migration commands (flask db migrate / upgrade)
jwt = JWTManager()  # issues and verifies the access tokens auth.py hands out
bcrypt = Bcrypt()  # password hashing for User.password_hash
