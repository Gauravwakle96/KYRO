class ServiceError(RuntimeError):
    """Trusted integration error classification; never inferred from tool/model text."""

    def __init__(self, message: str, *, retryable: bool = False, retry_after: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after
