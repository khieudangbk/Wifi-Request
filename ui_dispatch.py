"""Post UI work without making any Tcl/Tk calls from background threads."""
from queue import Empty, SimpleQueue
from threading import get_ident


class UiDispatcher:
    def __init__(self, root):
        self.root = root
        self.owner = get_ident()
        self.queue = SimpleQueue()
        self.closed = False
        self.job = root.after(50, self.drain)

    def post(self, callback, *args, **kwargs):
        if self.closed:
            return
        if get_ident() == self.owner:
            callback(*args, **kwargs)
        else:
            self.queue.put((callback, args, kwargs))

    def drain(self):
        if self.closed:
            return
        try:
            for _ in range(100):
                try:
                    callback, args, kwargs = self.queue.get_nowait()
                except Empty:
                    break
                callback(*args, **kwargs)
        finally:
            if not self.closed:
                self.job = self.root.after(50, self.drain)

    def close(self):
        self.closed = True
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None
