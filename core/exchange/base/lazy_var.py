import threading


class LazyVar:
    def __init__(self, initializer):
        self.initializer = initializer
        self._value = None
        self._initialized = False
        self._lock = threading.Lock()

    def __getattr__(self, name):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._value = self.initializer()
                    self._initialized = True

        return getattr(self._value, name)
