class DomainError(Exception):
    """A business-rule failure. Services raise these; one handler in main.py turns them
    into HTTP responses, so services never import FastAPI and routers stay thin."""

    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = 404


class ForbiddenError(DomainError):
    status_code = 403


class ConflictError(DomainError):
    status_code = 409
