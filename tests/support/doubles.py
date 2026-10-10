"""Injectable persistence and dependency doubles shared across components."""


class Cursor:
    def __init__(self, row=None, rows=(), description=None, *, failure=None):
        self.row, self.rows = row, list(rows)
        self.description = description
        self.failure = failure
        self.calls = []
        self.rowcount = 0
        self.closed = False

    def execute(self, query, params=()):
        self.query, self.params = query, tuple(params)
        self.calls.append((query, self.params))
        if self.failure is not None:
            raise self.failure

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class Connection:
    def __init__(self, *cursors, failure=None):
        self.cursors = list(cursors)
        self.failure = failure
        self.last_cursor = None
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        self.last_cursor = self.cursors.pop(0) if self.cursors else Cursor(failure=self.failure)
        return self.last_cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class FailingDependency:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise RuntimeError("private service dependency failure")
        return fail
