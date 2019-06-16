import os
import yaml

import makemehappy.utilities as mmh
import makemehappy.build as build

from makemehappy.buildroot import BuildRoot
from makemehappy.toplevel import Toplevel

def has(key, dic, t):
    if not(key in dic):
        return False
    if not(isinstance(dic[key], t)):
        return False
    return True

def extendPath(root, lst, datum):
    new = os.path.join(root, datum)
    if (isinstance(datum, str)):
        lst.append(new)
    elif (isinstance(datum, list)):
        lst.extend(new)
    else:
        raise(Exception())

class CMakeExtensions:
    def __init__(self, moduleData, trace):
        self.modulepath = []
        self.toolchainpath = []
        midx = 'cmake-modules'
        tidx = 'cmake-toolchains'
        if (midx in moduleData):
            extendPath(moduleData['root'], self.modulepath, moduleData[midx])
        if (tidx in moduleData):
            extendPath(moduleData['root'], self.toolchainpath, moduleData[tidx])
        for entry in trace.data:
            if (midx in entry):
                extendPath(entry['root'], self.modulepath, entry[midx])
            if (tidx in entry):
                extendPath(entry['root'], self.toolchainpath, entry[tidx])

    def modulePath(self):
        return self.modulepath

    def toolchainPath(self):
        return self.toolchainpath

class Trace:
    def __init__(self):
        self.data = []

    def has(self, needle):
        return (needle in (entry['name'] for entry in self.data))

    def dependencies(self):
        return list((({'name': entry['name'],
                       'revision': entry['version'] } for entry in self.data)))

    def modDependencies(self):
        return dict({ x['name']: x['dependencies'] for x in self.data})

    def push(self, entry):
        self.data = [entry] + self.data

class Stack:
    def __init__(self, init):
        self.data = init

    def empty(self):
        return (len(self.data) == 0)

    def delete(self, needle):
        self.data = list((x for x in self.data
                          if (lambda y: y['name'] != needle)(x)))

    def push(self, entry):
        self.data = [entry] + self.data

def fetch(log, src, st, trace):
    if (st.empty() == True):
        return trace

    for dep in st.data:
        log.info("Fetching revision {} of module {}"
                 .format(dep['revision'], dep['name']))
        if ('source' in dep.keys()):
            source = dep['source']
        else:
            source = src.lookup(dep['name'])['repository']

        if (source == False):
            log.error("Module {} has no source!".format(dep['name']))
            return False

        p = os.path.join('deps', dep['name'])
        newmod = os.path.join(p, 'module.yaml')
        mmh.loggedProcess(log, ['git', 'clone', source, p])

        # Check out the requested revision
        olddir = os.getcwd()
        os.chdir(p)
        mmh.loggedProcess(log, ['git', 'checkout', dep['revision']])
        os.chdir(olddir)

        newmodata = None
        if (os.path.isfile(newmod)):
            newmodata = mmh.load(newmod)
            newmodata['version'] = dep['revision']
        else:
            newmodata = {}
            newmodata['name'] = dep['name']
            newmodata['version'] = dep['revision']

        if not('dependencies' in newmodata):
            newmodata['dependencies'] = []

        trace.push(newmodata)
        for newdep in newmodata['dependencies']:
            if (trace.has(newdep['name']) == False):
                st.push(newdep)

        st.delete(dep['name'])

    # And recurse with the new stack and trace; we're done when the new stack
    # is empty.
    return fetch(log, src, st, trace)

class CodeUnderTest:
    def __init__(self, log, cfg, sources, module):
        self.log = log
        self.cfg = cfg
        self.module = module
        self.sources = sources
        self.root = None
        self.moduleData = None
        self.depstack = None
        self.depstack = None
        self.extensions = None
        self.toplevel = None

    def name(self):
        if (isinstance(self.moduleData, dict) and 'name' in self.module):
            return self.module['name']
        return 'MakeMeHappyModule'

    def loadModule(self):
        self.log.info("Loading module description: {}".format(self.module))
        self.moduleData = mmh.load(self.module)

    def loadSources(self):
        self.log.info("Loading source definitions...")
        self.sources.load()

    def initRoot(self, d):
        self.root = BuildRoot(log = self.log,
                              seed = yaml.dump(self.moduleData),
                              modName = self.name(),
                              dirName = d)

    def populateRoot(self):
        self.root.populate()

    def linkIntoRoot(self):
        self.root.linkCodeUnderTest()

    def changeToRoot(self):
        self.root.cd()

    def dependencies(self):
        if (has('dependencies', self.moduleData, list)):
            return self.moduleData['dependencies']
        return []

    def loadDependencies(self):
        self.depstack = Stack(self.dependencies())
        self.deptrace = Trace()
        fetch(self.log, self.sources, self.depstack, self.deptrace)
        self.extensions = CMakeExtensions(self.moduleData, self.deptrace)

    def cmakeModules(self):
        if (has('cmake-modules', self.moduleData, str)):
            return self.moduleData['cmake-modules']
        return None

    def generateToplevel(self):
        self.toplevel = Toplevel(self.log,
                                 self.cmake3rdParty(),
                                 self.extensions.modulePath(),
                                 self.deptrace)
        self.toplevel.generateToplevel()

    def build(self):
        build.allofthem(self.log, self, self.extensions)

    def cmake3rdParty(self):
        if (has('cmake-third-party', self.moduleData, dict)):
            return self.moduleData['cmake-third-party']
        return {}

    def toolchains(self):
        if (has('toolchains', self.moduleData, list)):
            return self.moduleData['toolchains']
        return []

    def buildtools(self):
        if (has('buildtools', self.moduleData, list)):
            return self.moduleData['buildtools']
        return []

    def buildconfigs(self):
        if (has('buildconfigs', self.moduleData, list)):
            return self.moduleData['buildconfigs']
        return []
