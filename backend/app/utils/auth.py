from functools import wraps

from flask_jwt_extended import verify_jwt_in_request, get_jwt

from app.utils.errors import ApiError


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            if get_jwt().get("role") not in roles:
                raise ApiError("forbidden", "you do not have permission to perform this action", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
