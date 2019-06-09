import makemehappy.utilities as mmh

def has(key, dic, t):
    if not(key in dic):
        return False
    if not(isinstance(dic[key], t)):
        return False
    return True

class CodeUnderTest:
    def __init__(self, log, src):
        self.log = log
        self.src = src

    def load(self):
        self.log.info("Loading module description: {}".format(self.src))
        self.data = mmh.load(self.src)

    def dependencies(self):
        if (has('dependencies', self.data, list)):
            return self.data['dependencies']
        return []

    def cmakeModules(self):
        if (has('cmake-modules', self.data, str)):
            return self.data['cmake-modules']
        return None

    def cmake3rdParty(self):
        if (has('cmake-third-party', self.data, dict)):
            return self.data['cmake-third-party']
        return {}

    def toolchains(self):
        if (has('toolchains', self.data, list)):
            return self.data['toolchains']
        return []

    def buildtools(self):
        if (has('buildtools', self.data, list)):
            return self.data['buildtools']
        return []

    def buildconfigs(self):
        if (has('buildconfigs', self.data, list)):
            return self.data['buildconfigs']
        return []
