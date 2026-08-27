import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_registration(data):
    """Check a registration payload's name/email/password. Returns an error string, or
    None when the payload is valid. Field limits mirror the users table's column sizes."""
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
    """Check a login payload has both fields present. Returns an error string, or None
    when valid. Deliberately doesn't validate email format or password strength here —
    a malformed login is just a wrong-credentials 401, not a 400."""
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return "email and password are required"
    return None
