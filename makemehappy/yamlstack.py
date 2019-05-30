import os

import makemehappy.utilities as mmh

class YamlStack:
    def __init__(self, log, desc, *lst):
        self.log = log
        self.desc = desc
        self.files = lst
        self.data = False

    def push(self, item):
        self.log.info("{}: {}".format(self.desc, item))
        self.files = self.files + [item]

    def fileload(self, fn):
        self.log.info("Loading {}: {}".format(self.desc, fn))
        return mmh.load(fn)

    def load(self):
        self.data = list((self.fileload(x) for x in self.files
                          if os.path.isfile(x)))

class SourceStack(YamlStack):
    def __init__(self, log, desc, *lst):
        YamlStack.__init__(self, log, desc, *lst)

    def lookup(self, needle):
        if (self.data == False):
            raise(Exception)

        for slice in self.data:
            if (needle in slice['modules']):
                return slice['modules'][needle]

        raise(Exception)
