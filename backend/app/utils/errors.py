from flask import jsonify


class ApiError(Exception):
    """A deliberate, user-facing API failure: raise it from any route and
    register_error_handlers turns it into the standard `{error: {code, message}}` JSON
    shape with the given HTTP status. Distinct from an unhandled exception, which falls
    through to handle_500 instead."""

    def __init__(self, code, message, status_code):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def error_response(code, message, status_code):
    """Build the standard `{error: {code, message}}` JSON error response."""
    return jsonify({"error": {"code": code, "message": message}}), status_code


def register_error_handlers(app):
    """Wire ApiError, 404, and 500 to the standard JSON error shape for the whole app."""

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return error_response(err.code, err.message, err.status_code)

    @app.errorhandler(404)
    def handle_404(err):
        return error_response("not_found", "resource not found", 404)

    @app.errorhandler(500)
    def handle_500(err):
        return error_response("server_error", "an unexpected error occurred", 500)
