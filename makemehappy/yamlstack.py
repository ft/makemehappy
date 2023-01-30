import copy
import fnmatch
import os

from functools import reduce

import makemehappy.utilities as mmh

class YamlStack:
    def __init__(self, log, desc, *lst):
        self.log = log
        self.desc = desc
        self.files = list(lst)
        self.data = None

    def pushLayer(self, layer):
        self.data.insert(0, layer)

    def push(self, item):
        self.files = [ item ] + self.files

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
        self.merged = None

    def merge(self):
        if (self.data == None):
            raise(NoSourceData())

        # The top level data structure is a dict. With sources, we only care
        # about the ‘modules’ and ‘remove’ keys. The merged dict will contain
        # ‘modules’ only, processing the ‘remove’ key as we move up the layers.
        self.merged = { 'modules': {} }
        slices = copy.deepcopy(reversed(self.data))
        for slice in slices:
            if ('remove' in slice and 'modules' in slice['remove']):
                for rem in slice['remove']['modules']:
                    del(self.merged['modules'][rem])
            if ('modules' in slice):
                for mod in slice['modules']:
                    if (mod in self.merged['modules']):
                        self.merged['modules'][mod] = {
                            **self.merged['modules'][mod],
                            **slice['modules'][mod] }
                    else:
                        self.merged['modules'][mod] = slice['modules'][mod]

        for module in self.merged['modules']:
            if ('type' not in self.merged['modules'][module]):
                self.merged['modules'][module]['type'] = 'git'
            if ('main' not in self.merged['modules'][module]):
                self.merged['modules'][module]['main'] = [ 'main', 'master' ]

    def allSources(self):
        if (self.merged == None):
            raise(NoSourceData())
        return self.merged['modules'].keys()

    def lookup(self, needle):
        if (self.data == None):
            raise(NoSourceData())
        if (needle in self.merged['modules']):
            return self.merged['modules'][needle]
        raise(UnknownModule(needle))

class NoSourceData(Exception):
    pass

class UnknownConfigItem(Exception):
    pass

class UnknownToolchain(Exception):
    pass

class ConfigStack(YamlStack):
    def __init__(self, log, desc, *lst):
        YamlStack.__init__(self, log, desc, *lst)
        self.merged = None
        self.remove = [ 'definition', 'root', 'remove' ]
        self.mergeLists = [ 'buildtools', 'buildconfigs' ]
        self.mergeDicts = [ 'dependency-summary' ]
        self.mergeLODbyName = [ 'revision-overrides', 'toolchains' ]

    def merge(self):
        if (self.data == None):
            raise(NoConfigData())

        # The top level data structure is a dict. These are predefined types as
        # lists, so we're populating them here. Toolchains and overrides are
        # merged by the ‘name’ properties of their dictionary items. The tools
        # and configs are merged on string values. These lists also support
        # removal by the top-level ‘remove’ key, using the same matching. With
        # other top-level keys, the one from the highest priority layer wins.
        self.merged = { 'buildtools':         [],
                        'buildconfigs':       [],
                        'toolchains':         [],
                        'revision-overrides': [] }
        slices = list(copy.deepcopy(reversed(self.data)))
        for slice in slices:
            if ('remove' in slice):
                for cat in slice['remove']:
                    if (cat in self.mergeLists):
                        self.merged[cat] = list(
                            filter(lambda x: (x not in slice['remove'][cat]),
                                   self.merged[cat]))
                    elif (cat in self.mergeLODbyName):
                        self.merged[cat] = list(
                            filter(lambda x: (x['name'] not in slice['remove'][cat]),
                                   self.merged[cat]))

            for key in slice:
                if (key in self.mergeLists):
                    self.merged[key] = list(set(slice[key] + self.merged[key]))
                elif (key in self.mergeLODbyName):
                    # We're reversing here for correct order in revision-
                    # overrides, since those names can be patterns. With the
                    # other keys of this type, order does not matter.
                    for entry in reversed(slice[key]):
                        idx = mmh.findByName(self.merged[key], entry['name'])
                        if (idx != None):
                            new = { **self.merged[key][idx], **entry }
                            del(self.merged[key][idx])
                        else:
                            new = entry
                        self.merged[key].insert(0, new)
                elif (key in self.mergeDicts):
                    if (key not in self.merged):
                        self.merged[key] = {}
                    self.merged[key] = { **self.merged[key], **slice[key] }
                else:
                    self.merged[key] = slice[key]

        for rem in self.remove:
            if (rem in self.merged):
                del(self.merged[rem])

    def lookup(self, needle):
        if (self.data == None):
            raise(NoConfigData())
        if (needle in self.merged):
            return self.merged[needle]
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

    def processOverrides(self, mod):
        lst = self.allOverrides()
        for rover in lst:
            if ('name' not in rover):
                continue
            pattern = rover['name']
            if (fnmatch.fnmatch(mod, pattern)):
                if ('preserve' in rover):
                    if (rover['preserve']):
                        return None
                    continue
                elif ('revision' in rover):
                    return rover['revision']
                elif ('use-main-branch' in rover):
                    if (not rover['use-main-branch']):
                        return None
                    return '!main'
        return None
