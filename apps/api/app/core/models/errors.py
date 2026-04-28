class DomainError(Exception):
    """Base for all domain rule violations."""


class InvalidValueError(DomainError):
    """Raised when a value object receives an invalid input."""


class InvalidStateTransitionError(DomainError):
    """Raised when an entity transition violates a rule."""
