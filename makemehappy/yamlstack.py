import os

import makemehappy.utilities as mmh

class YamlStack:
    def __init__(self, log, desc, *lst):
        self.log = log
        self.desc = desc
        self.files = list(lst)
        self.data = False

    def pushLayer(self, layer):
        self.data.insert(0, layer)

    def push(self, item):
        self.log.info("{}: {}".format(self.desc, item))
        self.files = self.files + [item]

    def fileload(self, fn):
        self.log.info("Loading {}: {}".format(self.desc, fn))
        return mmh.load(fn)

    def load(self):
        self.data = list((self.fileload(x) for x in self.files
                          if os.path.isfile(x)))

class NoSourceData(Exception):
    pass

class UnknownModule(Exception):
    pass

class SourceStack(YamlStack):
    def __init__(self, log, desc, *lst):
        YamlStack.__init__(self, log, desc, *lst)

    def load(self):
        super(SourceStack, self).load()
        for slice in self.data:
            if not('modules' in slice):
                continue
            for module in slice['modules']:
                if (not ('type' in slice['modules'][module])):
                    slice['modules'][module]['type'] = 'git'

    def allSources(self):
        rv = []
        if (self.data == False):
            raise(NoSourceData())

        for slice in self.data:
            if not('modules' in slice):
                continue
            for module in slice['modules']:
                if (module in rv):
                    continue
                rv.append(module)

        return rv

    def lookup(self, needle):
        if (self.data == False):
            raise(NoSourceData())

        for slice in self.data:
            if not('modules' in slice):
                continue
            if (needle in slice['modules']):
                return slice['modules'][needle]

        raise(UnknownModule(needle))

def queryItem(data, item):
        rv = []
        for layer in data:
            if item in layer:
                rv.extend(layer[item])
        rv = list(set(rv))
        rv.sort()
        return rv

def queryToolchain(data, item):
    rv = []
    for layer in data:
        if 'toolchains' in layer:
            rv.extend(list(x[item] for x in layer['toolchains'] if item in x))
    rv = list(set(mmh.flatten(rv)))
    rv.sort()
    return rv

class NoSourceData(Exception):
    pass

class UnknownConfigItem(Exception):
    pass

class ConfigStack(YamlStack):
    def __init__(self, log, desc, *lst):
        YamlStack.__init__(self, log, desc, *lst)

    def lookup(self, needle):
        if (self.data == False):
            raise(NoConfigData())

        for slice in self.data:
            if needle in slice:
                return slice[needle]

        raise(UnknownConfigItem(needle))

    def fetchToolchain(self, name):
        for layer in self.data:
            if 'toolchains' in layer:
                for tc in layer['toolchains']:
                    if (tc['name'] == name):
                        return tc
        raise(UnknownConfigItem(name))

    def allToolchains(self):
        return queryToolchain(self.data, 'name')

    def allInterfaces(self):
        return queryToolchain(self.data, 'interface')

    def allArchitectures(self):
        return queryToolchain(self.data, 'architecture')

    def allBuildtools(self):
        return queryItem(self.data, 'buildtools')

    def allBuildConfigs(self):
        return queryItem(self.data, 'buildconfigs')
