from functools import wraps

from flask_jwt_extended import verify_jwt_in_request, get_jwt

from app.utils.errors import ApiError


def role_required(*roles):
    """Route decorator factory: 403s unless the caller's JWT role is one of `roles`.

    Usage: @role_required("admin") above a Flask view function. Verifies the JWT itself
    (so routes using this don't also need @jwt_required()), then checks the "role" claim
    that auth.py embeds at login/register time.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            if get_jwt().get("role") not in roles:
                raise ApiError("forbidden", "you do not have permission to perform this action", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
