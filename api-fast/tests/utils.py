class CacheMock:
    def __init__(self, data):
        self.data = data

    def get(self, *a, **kw):
        return self.data.get(*a, **kw)

    def get_many(self, *a, **kw):
        return self.data

    def keys(self, *a, **kw):
        return self.data.keys()