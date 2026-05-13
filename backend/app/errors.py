from __future__ import annotations


class AppError(Exception):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class UpstreamServiceError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class PersistenceError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class LLMError(AppError):
    """Raised when the LLM call fails, times out, returns unparseable output,
    or exhausts its retry budget."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)
