from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from app.extensions import db, bcrypt
from app.models.user import User
from app.utils.validation import validate_registration, validate_login
from app.utils.errors import ApiError

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    error = validate_registration(data)
    if error:
        raise ApiError("validation_error", error, 400)

    email = data["email"].strip().lower()
    if User.query.filter_by(email=email).first():
        raise ApiError("conflict", "an account with this email already exists", 409)

    user = User(
        name=data["name"].strip(),
        email=email,
        password_hash=bcrypt.generate_password_hash(data["password"]).decode("utf-8"),
        role="student",
    )
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return jsonify({"user": user.to_dict(), "access_token": token}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    error = validate_login(data)
    if error:
        raise ApiError("validation_error", error, 400)

    email = data["email"].strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, data["password"]):
        raise ApiError("unauthorized", "invalid email or password", 401)

    user.last_login_at = datetime.utcnow()
    db.session.commit()

    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return jsonify({"user": user.to_dict(), "access_token": token}), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        raise ApiError("unauthorized", "user not found", 401)
    return jsonify({"user": user.to_dict()}), 200
