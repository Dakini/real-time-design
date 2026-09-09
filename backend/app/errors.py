"""Uniform application error -> {code, message} JSON, per the Error schema."""


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def not_found(message: str = "Not found", code: str = "not_found") -> AppError:
    return AppError(404, code, message)


def session_not_found() -> AppError:
    return AppError(404, "not_found", "Session not found")


def forbidden(message: str = "Forbidden", code: str = "forbidden") -> AppError:
    return AppError(403, code, message)


def owner_only() -> AppError:
    return AppError(403, "forbidden", "Forbidden: owner only")


def unauthorized(message: str = "Not authenticated", code: str = "unauthenticated") -> AppError:
    return AppError(401, code, message)


def bad_request(message: str, code: str = "bad_request") -> AppError:
    return AppError(400, code, message)


def conflict(message: str, code: str = "conflict") -> AppError:
    return AppError(409, code, message)
