import os

import makemehappy.utilities as mmh

class YamlStack:
    def __init__(self, log, desc, *lst):
        self.log = log
        self.desc = desc
        self.files = lst
        self.data = False
        for item in lst:
            self.log.info("{}: {}".format(desc, item))

    def push(self, item):
        self.log.info("{}: {}".format(self.desc, item))
        self.files = self.files + [item]

    def load(self):
        self.data = list((mmh.load(x) for x in self.files
                          if os.path.isfile(x)))

    def lookup(self, needle):
        if (self.data == False):
            return False

        for slice in self.data:
            if (needle in slice['modules']):
                return slice['modules'][needle]

        return False
