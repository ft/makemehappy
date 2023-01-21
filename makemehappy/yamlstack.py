import os

from functools import reduce

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
        # This is a little noisy, fileload() will suffice, I think.
        #self.log.info("{}: {}".format(self.desc, item))
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

def merge(a, b):
    return {**a, **b}

def mergeStack(data):
    return reduce(merge, data)

def findByName(lst, name):
    for i, d in enumerate(lst):
        if ('name' in d and d['name'] == name):
            return i
    return None

def mergeByName(a, b):
    for item in b:
        idx = findByName(a, item['name'])
        if (idx == None):
            a.append(item)
        else:
            a[idx] = {**a[idx], **item}
    return a

def mergeLODbyName(data):
    return reduce(mergeByName, data)

def processRemoveList(data, layer, needle):
    if ('remove' not in layer):
        return data
    if (needle not in layer['remove']):
        return data
    return list(filter(lambda x: (x not in layer['remove'][needle]), data))

def np(item, rem):
    return (item['name'] not in rem)

def processRemoveLOD(data, layer, needle):
    if ('remove' not in layer):
        return data
    if (needle not in layer['remove']):
        return data
    return list(map(lambda sublist: \
                    list(filter(lambda item: np(item, layer['remove'][needle]),
                                sublist)),
                    data))

def processRemoveDict(data, layer, needle):
    if ('remove' not in layer):
        return data
    if (needle not in layer['remove']):
        return data
    lst = []
    for item in data:
        for pat in layer['remove'][needle]:
            del(item[pat])
        lst += [ item ]
    return lst

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

        data = []
        for slice in self.data:
            if not('modules' in slice):
                continue
            if (needle in slice['modules']):
                data += [ slice['modules'][needle] ]

        if (len(data) == 0):
            raise(UnknownModule(needle))

        data = mergeStack(data)

        if ('main' not in data):
            data['main'] = [ 'main', 'master' ]

        return data

class NoSourceData(Exception):
    pass

class UnknownConfigItem(Exception):
    pass

class UnknownToolchain(Exception):
    pass

class ConfigStack(YamlStack):
    def __init__(self, log, desc, *lst):
        YamlStack.__init__(self, log, desc, *lst)
        self.mergeDicts = [ 'revision-overrides' ]
        self.mergeLists = [ 'buildtools', 'buildconfigs' ]
        self.mergeLODbyName = [ 'toolchains' ]

    def lookup(self, needle):
        if (self.data == False):
            raise(NoConfigData())

        if (needle in self.mergeDicts):
            data = []
            for slice in self.data:
                data = processRemoveDict(data, slice, needle)
                if (needle in slice):
                    data += [ slice[needle] ]

            if (len(data) == 0):
                raise(UnknownConfigItem(needle))

            rv = mergeStack(data)
            return rv
        elif (needle in self.mergeLODbyName):
            data = []
            for slice in self.data:
                data = processRemoveLOD(data, slice, needle)
                if (needle in slice):
                    data += [ slice[needle] ]

            if (len(data) == 0):
                raise(UnknownConfigItem(needle))

            rv = mergeLODbyName(data)
            return rv
        elif (needle in self.mergeLists):
            lst = []
            for slice in self.data:
                lst = processRemoveList(lst, slice, needle)
                if (needle in slice):
                    lst += slice[needle]
            lst = list(set(lst))
            lst.sort()
            return lst
        else:
            for slice in self.data:
                if (needle in slice):
                    return slice[needle]
            raise(UnknownConfigItem(needle))

    def fetchToolchain(self, name):
        lst = self.lookup('toolchains')
        for tc in lst:
            if (tc['name'] == name):
                return tc
        raise(UnknownToolchain(name))

    def queryToolchain(self, key):
        rv = []
        for item in self.lookup('toolchains'):
            if (isinstance(item[key], list)):
                rv += item[key]
            else:
                rv += [ item[key] ]
        rv.sort()
        return rv

    def allToolchains(self):
        return self.queryToolchain('name')

    def allArchitectures(self):
        return self.queryToolchain('architecture')

    def allBuildtools(self):
        return self.lookup('buildtools')

    def allBuildConfigs(self):
        return self.lookup('buildconfigs')

    def allOverrides(self):
        return self.lookup('revision-overrides')
