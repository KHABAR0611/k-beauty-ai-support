"""Safe public errors: never expose vendor exceptions or user input."""


class ServiceError(Exception):
    def __init__(self, code: str, http_status: int = 503):
        super().__init__(code)
        self.code, self.http_status = code, http_status


class InsufficientContext(Exception):
    def __init__(self, fields: list[str]):
        super().__init__("insufficient_context")
        self.fields = fields
