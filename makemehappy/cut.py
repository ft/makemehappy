import datetime
import math
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

def fetch(cfg, log, src, st, trace):
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
        mmh.loggedProcess(cfg, log, ['git', 'clone', source, p])

        # Check out the requested revision
        olddir = os.getcwd()
        os.chdir(p)
        mmh.loggedProcess(cfg, log, ['git', 'checkout', dep['revision']])
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
    return fetch(cfg, log, src, st, trace)

def stepFailed(data, step):
    return (step in data and data[step] == False)

def buildFailed(data):
    return (stepFailed(data, 'configure-result') or
            stepFailed(data, 'build-result') or
            stepFailed(data, 'testsuite-result'))

def endoftime(datum):
    t = datum['type']
    if t == 'build':
        return datum['time-stamp']
    elif t == 'checkpoint':
        if 'testsuite-stamp' in datum:
            return datum['time-stamp']
        elif 'build-stamp' in datum:
            return datum['build-stamp']
        elif 'configure-stamp' in datum:
            return datum['configure-stamp']
        else:
            return datum['time-stamp']
    else:
        raise Exception

def renderTimedelta(d):
    minperday = 24 * 60
    minutes = minperday * d.days + math.floor(d.seconds / 60.)
    seconds = d.seconds % 60
    milli = round(d.microseconds/1000)
    return "{mins:03d}:{secs:02d}.{msecs:03d}".format(mins = minutes,
                                                      secs = seconds,
                                                      msecs = milli)

def maybeInfo(c, l, text):
    if c.lookup('log-all'):
        l.info(text)
    else:
        print(text)

class ExecutionStatistics:
    # The statistics log is a list of dictionaries.
    def __init__(self, cfg, log):
        self.cfg = cfg
        self.log = log
        self.data = []

    def checkpoint(self, description):
        self.data.append( { 'type': 'checkpoint',
                            'description': description,
                            'time-stamp': datetime.datetime.now() } )

    def build(self, toolchain, cpu, interface, buildcfg, buildtool):
        self.data.append( { 'type':      'build',
                            'toolchain': toolchain,
                            'cpu':       cpu,
                            'interface': interface,
                            'buildcfg':  buildcfg,
                            'buildtool': buildtool,
                            'time-stamp': datetime.datetime.now() } )

    def logConfigure(self, result):
        self.data[-1]['configure-stamp'] = datetime.datetime.now()
        self.data[-1]['configure-result'] = (result == 0)

    def logBuild(self, result):
        self.data[-1]['build-stamp'] = datetime.datetime.now()
        self.data[-1]['build-result'] = (result == 0)

    def logTestsuite(self, num, result):
        self.data[-1]['testsuite-stamp'] = datetime.datetime.now()
        self.data[-1]['testsuite-tests'] = num
        self.data[-1]['testsuite-result'] = (result == 0)

    def wasSuccessful(self):
        for entry in self.data:
            if entry['type'] != 'build':
                continue
            if buildFailed(entry):
                return False
        return True

    def countFailed(self):
        n = 0
        for entry in self.data:
            if entry['type'] != 'build':
                continue
            if buildFailed(entry):
                n = n + 1
        return n

    def countBuilds(self):
        n = 0
        for entry in self.data:
            if entry['type'] == 'build':
                n = n + 1
        return n

    def renderTimeDifference(self, prev, current):
        p = endoftime(prev)
        c = endoftime(current)
        time = renderTimedelta(current['time-stamp'] - prev['time-stamp'])
        maybeInfo(self.cfg, self.log,
                  '    {title:<9}: {time:>12}'
                  .format(title = 'Time', time = time))

    def renderCheckpoint(self, datum):
        maybeInfo(self.cfg, self.log,
                  'Checkpoint: {}'.format(datum['description']))

    def renderStepResult(self, datum, title, prefix):
        result = 'Success'
        time = ''

        if (prefix + '-stamp') in datum:
            if prefix == 'configure':
                time = renderTimedelta(datum['configure-stamp'] -
                                       datum['time-stamp'])
            elif prefix == 'build':
                time = renderTimedelta(datum['build-stamp'] -
                                       datum['configure-stamp'])
            elif prefix == 'testsuite':
                time = renderTimedelta(datum['testsuite-stamp'] -
                                       datum['build-stamp'])
            else:
                raise Exception

        if not((prefix + '-result') in datum):
            result = '---'
        elif not(datum[prefix + '-result']):
            result = 'Failure'

        maybeInfo(self.cfg, self.log,
                  '    {title:>9}: {time:>12}  {result:>10}'
                  .format(title = title,
                          time = time,
                          result = result))

    def renderConfigureStepResult(self, datum):
        self.renderStepResult(datum, 'Configure', 'configure')

    def renderBuildStepResult(self, datum):
        self.renderStepResult(datum, 'Build', 'build')

    def renderTestStepResult(self, datum):
        self.renderStepResult(datum, 'Testsuite', 'testsuite')

    def renderBuildResult(self, datum):
        result = 'Success'
        if buildFailed(datum):
            result = 'Failure   ---!!!---'
        maybeInfo(self.cfg, self.log, ''.ljust(90, '-'))
        maybeInfo(self.cfg, self.log,
                  '{toolchain:>20} {cpu:>20} {interf:>16} {config:>16} {tool:>12}'
                  .format(toolchain = 'Toolchain',
                          cpu = 'Architecture',
                          interf = 'Interface',
                          config = 'Config',
                          tool = 'Buildtool'))
        maybeInfo(self.cfg, self.log,
                  '{toolchain:>20} {cpu:>20} {interf:>16} {config:>16} {tool:>12}     {result}'
                  .format('',
                          toolchain = datum['toolchain'],
                          cpu = datum['cpu'],
                          interf = datum['interface'],
                          config = datum['buildcfg'],
                          tool = datum['buildtool'],
                          result = result))
        self.renderConfigureStepResult(datum)
        self.renderBuildStepResult(datum)
        self.renderTestStepResult(datum)

    def renderStatistics(self):
        maybeInfo(self.cfg, self.log, '')
        maybeInfo(self.cfg, self.log, 'Build Summary:')
        maybeInfo(self.cfg, self.log, '')
        last = None
        for entry in self.data:
            if not('type' in entry):
                self.log.warn('Statistics log entry has no type. Ignoring!')
                continue

            if not(last == None):
                self.renderTimeDifference(last, entry)

            last = entry
            t = entry['type']
            if t == 'build':
                self.renderBuildResult(entry)
            elif t == 'checkpoint':
                self.renderCheckpoint(entry)
            else:
                self.log.warn('Statistics log entry has unknown type: {}'
                              .format(t))
        maybeInfo(self.cfg, self.log, '')
        time = renderTimedelta(self.data[-1]['time-stamp'] -
                               self.data[0]['time-stamp'])
        maybeInfo(self.cfg, self.log,
                  'Total runtime: {time}'.format(time = time))
        maybeInfo(self.cfg, self.log, '')

class CodeUnderTest:
    def __init__(self, log, cfg, sources, module):
        self.stats = ExecutionStatistics(cfg, log)
        self.stats.checkpoint('module-initialisation')
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
        if (isinstance(self.moduleData, dict) and 'name' in self.moduleData):
            return self.moduleData['name']
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
        self.stats.checkpoint('load-dependencies')
        self.depstack = Stack(self.dependencies())
        self.deptrace = Trace()
        fetch(self.cfg, self.log, self.sources, self.depstack, self.deptrace)
        self.extensions = CMakeExtensions(self.moduleData, self.deptrace)

    def cmakeModules(self):
        if (has('cmake-modules', self.moduleData, str)):
            return self.moduleData['cmake-modules']
        return None

    def generateToplevel(self):
        self.stats.checkpoint('generate-toplevel')
        self.toplevel = Toplevel(self.log,
                                 self.cmake3rdParty(),
                                 self.extensions.modulePath(),
                                 self.deptrace)
        self.toplevel.generateToplevel()

    def build(self):
        build.allofthem(self.cfg, self.log, self, self.extensions)

    def cmake3rdParty(self):
        if (has('cmake-third-party', self.moduleData, dict)):
            return self.moduleData['cmake-third-party']
        return {}

    def toolchains(self):
        if (has('toolchains', self.moduleData, list)):
            return self.moduleData['toolchains']
        try:
            return self.cfg.lookup('toolchains')
        except Exception:
            return []

    def buildtools(self):
        if (has('buildtools', self.moduleData, list)):
            return self.moduleData['buildtools']
        try:
            return self.cfg.lookup('buildtools')
        except Exception:
            return []

    def buildconfigs(self):
        if (has('buildconfigs', self.moduleData, list)):
            return self.moduleData['buildconfigs']
        try:
            return self.cfg.lookup('buildconfigs')
        except Exception:
            return []

    def cleanupRoot(self):
        self.stats.checkpoint('cleanup')
        self.root.cleanup()

    def renderStatistics(self):
        self.stats.checkpoint('finish')
        self.stats.renderStatistics()

    def wasSuccessful(self):
        return self.stats.wasSuccessful()

    def countBuilds(self):
        return self.stats.countBuilds()

    def countFailed(self):
        return self.stats.countFailed()
