class ApplicationError(Exception):
    """Base for application-layer errors."""


class SessionNotFoundError(ApplicationError):
    pass


class ShotNotFoundError(ApplicationError):
    pass


class StorageError(ApplicationError):
    pass


class QueueError(ApplicationError):
    pass
