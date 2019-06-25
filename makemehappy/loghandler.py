import sys

from logbook.base import NOTSET
from logbook.handlers import Handler, StreamHandler, FileHandler

class MMHLogHandler(Handler):
    def __init__(self):
        # While filename is None, log everything to memory. When filename gets
        # set to a string, open that file and start logging to it (beginning
        # with emptying the backlog). If it's set to False, do the same, but
        # log to stdout.
        self.filename = None
        self._handler = None
        self.backlog = []
        Handler.__init__(self, NOTSET, None, False)

    def setFile(self, fn):
        self.filename = fn
        if isinstance(self.filename, str):
            self._handler = FileHandler(self.filename)
        elif isinstance(self.filename, bool):
            self._handler = StreamHandler(sys.stdout)
        for entry in self.backlog:
            self.emit(entry)
        backlog = []

    def close(self):
        if self._handler is not None:
            self._handler.close()

    def enqueue(self, record):
        self.backlog.append(record)

    def emit(self, record):
        if self._handler is not None:
            self._handler.emit(record)
        else:
            self.enqueue(record)
