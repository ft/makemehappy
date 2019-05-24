class YamlStack:
    def __init__(self, log, desc, *lst):
        self.log = log
        self.desc = desc
        for item in lst:
            self.log.info("{}: {}".format(desc, item))

    def push(self, item):
        self.log.info("{}: {}".format(self.desc, item))

    def lookup(self, needle):
        return False
