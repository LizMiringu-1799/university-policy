import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_registration(data):
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or len(name) > 120:
        return "name is required and must be at most 120 characters"
    if not email or len(email) > 190 or not EMAIL_RE.match(email):
        return "a valid email is required"
    if len(password) < 8:
        return "password must be at least 8 characters"
    return None


def validate_login(data):
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return "email and password are required"
    return None
