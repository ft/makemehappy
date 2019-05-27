import makemehappy.utilities as mmh

class CodeUnderTest:
    def __init__(self, log, src):
        self.log = log
        self.src = src

    def load(self):
        self.log.info("Loading module description: {}".format(self.src))
        self.data = mmh.load(self.src)

    def dependencies(self):
        return self.data['dependencies']

    def cmakeModules(self):
        return self.data['cmake-modules']

    def cmake3rdParty(self):
        return self.data['cmake-third-party']

    def toolchains(self):
        return self.data['toolchains']

    def buildtools(self):
        return self.data['buildtools']

    def buildconfigs(self):
        return self.data['buildconfigs']
