class AgentGuardError(Exception):
    status_code = 400
    code = "agentguard_error"

    def __init__(self, message: str, *, metadata: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.metadata = metadata


class NotFoundError(AgentGuardError):
    status_code = 404
    code = "not_found"


class AuthenticationError(AgentGuardError):
    status_code = 401
    code = "authentication_required"


class AuthorizationError(AgentGuardError):
    status_code = 403
    code = "forbidden"


class ConflictError(AgentGuardError):
    status_code = 409
    code = "conflict"


class ValidationError(AgentGuardError):
    status_code = 422
    code = "validation_error"
