class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def not_found(message: str = "Control was not found.") -> AppError:
    return AppError(404, "CONTROL_NOT_FOUND", message)


def bad_request(message: str) -> AppError:
    return AppError(400, "BAD_REQUEST", message)


def upstream(message: str, *, timeout: bool = False) -> AppError:
    if timeout:
        return AppError(504, "UPSTREAM_TIMEOUT", message)
    return AppError(502, "UPSTREAM_ERROR", message)
