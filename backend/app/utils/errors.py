from flask import jsonify


class ApiError(Exception):
    def __init__(self, code, message, status_code):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def error_response(code, message, status_code):
    return jsonify({"error": {"code": code, "message": message}}), status_code


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return error_response(err.code, err.message, err.status_code)

    @app.errorhandler(404)
    def handle_404(err):
        return error_response("not_found", "resource not found", 404)

    @app.errorhandler(500)
    def handle_500(err):
        return error_response("server_error", "an unexpected error occurred", 500)
