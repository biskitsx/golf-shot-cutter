from datetime import datetime


class FakeClock:
    def __init__(self, fixed: datetime) -> None:
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed

    def advance(self, *, seconds: float) -> None:
        from datetime import timedelta

        self._fixed = self._fixed + timedelta(seconds=seconds)
