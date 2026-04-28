class FakeIdGenerator:
    def __init__(self) -> None:
        self._counters = {"ses": 0, "shot": 0, "exp": 0}

    def session_id(self) -> str:
        self._counters["ses"] += 1
        return f"ses_{self._counters['ses']:04d}"

    def shot_id(self) -> str:
        self._counters["shot"] += 1
        return f"shot_{self._counters['shot']:04d}"

    def export_id(self) -> str:
        self._counters["exp"] += 1
        return f"exp_{self._counters['exp']:04d}"
