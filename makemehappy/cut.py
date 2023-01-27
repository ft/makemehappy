import datetime
import math
import os
import yaml

import makemehappy.utilities as mmh
import makemehappy.build as build
import makemehappy.version as v
import makemehappy.yamlstack as ys
import makemehappy.zephyr as z

from makemehappy.buildroot import BuildRoot
from makemehappy.toplevel import Toplevel

def has(key, dic, t):
    if not(isinstance(dic, dict)):
        return False
    if not(key in dic):
        return False
    if not(isinstance(dic[key], t)):
        return False
    return True

class InvalidPathExtension(Exception):
    pass

def extendPath(root, lst, datum):
    new = os.path.join(root, datum)
    if (isinstance(datum, str)):
        lst.append(new)
    elif (isinstance(datum, list)):
        lst.extend(new)
    else:
        raise(InvalidPathExtension(root, lst, datum))

def addExtension(mods, idx, entry, name):
    if (idx in entry):
        if name not in mods:
            mods[name] = {}
            mods[name]['root'] = entry['root']
        mods[name][idx] = entry[idx]

class DependencyEvaluation:
    def __init__(self, cfg, log):
        self.cfg = cfg
        self.log = log
        self.data = {}

    def insertSome(self, lst, origin):
        for dep in lst:
            self.insert(dep, origin)

    def insert(self, dep, origin):
        name = dep['name']
        revision = None
        if ('revision' in dep):
            revision = dep['revision']
        if (name not in self.data):
            self.data[name] = {}
        if (revision not in self.data[name]):
            self.data[name][revision] = []
        self.data[name][revision].append(origin)

    def logVersion(self, key, ver, unique):
        if (unique):
            t = 'Unique'
        else:
            t = 'Ambiguous'
        if (ver.kind == 'version'):
            self.log.info(
                '{} dependency: {} {} effective: {}',
                t, key, ver.string, ver.render())
        else:
            self.log.info(
                '{} dependency: {} {}',
                t, key, ver.string)

    def evaluate(self):
        for key in self.data:
            versions = list(map(v.Version, self.data[key].keys()))
            if (len(versions) == 1):
                ver = versions[0]
                self.logVersion(key, ver, True)
            else:
                for ver in versions:
                    self.logVersion(key, ver, False)

class CMakeExtensions:
    def __init__(self, moduleData, trace, order):
        self.modulepath = []
        self.toolchainpath = []
        mods = {}
        midx = 'cmake-modules'
        tidx = 'cmake-toolchains'
        if (midx in moduleData):
            extendPath(moduleData['root'], self.modulepath, moduleData[midx])
        if (tidx in moduleData):
            extendPath(moduleData['root'], self.toolchainpath, moduleData[tidx])
        for entry in trace.data:
            if 'root' not in entry:
                continue
            name = entry['name']
            addExtension(mods, midx, entry, name)
            addExtension(mods, tidx, entry, name)
        for entry in order:
            if (entry in mods) and (midx in mods[entry]):
                extendPath(mods[entry]['root'],
                           self.modulepath,
                           mods[entry][midx])
            if (entry in mods) and (tidx in mods[entry]):
                extendPath(mods[entry]['root'],
                           self.toolchainpath,
                           mods[entry][tidx])

    def modulePath(self):
        return self.modulepath

    def toolchainPath(self):
        return self.toolchainpath

class ZephyrExtensions:
    def __init__(self, moduleData, trace, order):
        self.boardroot = []
        self.dtsroot = []
        self.socroot = []
        zephyr = {}
        bidx = 'zephyr-board-root'
        didx = 'zephyr-dts-root'
        sidx = 'zephyr-soc-root'
        if (bidx in moduleData):
            extendPath(moduleData['root'], self.boardroot, moduleData[bidx])
        if (didx in moduleData):
            extendPath(moduleData['root'], self.dtsroot, moduleData[didx])
        if (sidx in moduleData):
            extendPath(moduleData['root'], self.socroot, moduleData[sidx])
        for entry in trace.data:
            if 'root' not in entry:
                continue
            name = entry['name']
            addExtension(zephyr, bidx, entry, name)
            addExtension(zephyr, didx, entry, name)
            addExtension(zephyr, sidx, entry, name)
        for entry in order:
            if (entry in zephyr) and (bidx in zephyr[entry]):
                extendPath(zephyr[entry]['root'], self.boardroot, zephyr[entry][bidx])
            if (entry in zephyr) and (didx in zephyr[entry]):
                extendPath(zephyr[entry]['root'], self.dtsroot, zephyr[entry][didx])
            if (entry in zephyr) and (sidx in zephyr[entry]):
                extendPath(zephyr[entry]['root'], self.socroot, zephyr[entry][sidx])

    def boardRoot(self):
        return self.boardroot

    def dtsRoot(self):
        return self.dtsroot

    def socRoot(self):
        return self.socroot

class Trace:
    def __init__(self):
        self.data = []
        self.westData = None

    def has(self, needle):
        return (needle in (entry['name'] for entry in self.data))

    def dependencies(self):
        return list((({'name': entry['name'],
                       'revision': entry['version'] } for entry in self.data)))

    def modDependencies(self):
        return dict({ x['name']: x['dependencies'] for x in self.data})

    def push(self, entry):
        self.data = [entry] + self.data

    def west(self, kernel = None):
        if (kernel == None):
            return self.westData
        self.westData = z.loadWestYAML(kernel)

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

def getSource(dep, src):
    if ('repository' in dep):
        tmp = dep
    else:
        tmp = src.lookup(dep['name'])

    if (tmp == False):
        return False

    if (not ('type' in tmp)):
        tmp['type'] = 'git'

    return tmp

def revisionOverride(cfg, src, mod):
    rev = cfg.processOverrides(mod)
    if (rev == '!main'):
        s = src.lookup(mod)
        m = s['main']
        if (isinstance(m, str)):
            return [ m ]
        return m
    return rev

def gitRemoteHasBranch(rev):
    rc = mmh.devnullProcess(['git', 'rev-parse', '--verify', 'origin/' + rev])
    return (rc == 0)

def fetchCheckout(cfg, log, mod, rev):
    revision = None
    if (isinstance(rev, list)):
        for branch in rev:
            if (gitRemoteHasBranch(branch)):
                log.info('Using main branch: {} for module {}'
                         .format(branch, mod))
                revision = branch
                break
        if (revision == None):
            log.error("Could not determine main branch: {} for module {}!"
                      .format(rev, mod))
            return None
    else:
        revision = rev

    rc = mmh.loggedProcess(cfg, log, ['git', 'checkout', revision])
    if (rc != 0):
        log.error("Failed to switch to revision {} for module {}!"
                  .format(revision, mod))
        return None
    return revision

class InvalidRepositoryType(Exception):
    pass

class InvalidDependency(Exception):
    pass

def fetch(cfg, log, src, st, trace):
    if (st.empty() == True):
        return trace

    for dep in st.data:
        rover = revisionOverride(cfg, src, dep['name'])
        if (rover != None):
            log.info("Revision Override for {} to {}"
                     .format(dep['name'], rover))
            dep['revision'] = rover
        if ('revision' not in dep):
            log.info('Module {} does not specify a revision'
                     .format(dep['name']))
            log.info('Attempting to resolve via zephyr-west')
            dep['revision'] = z.westRevision(src, trace.west(), dep['name'])
            if (dep['revision'] == None):
                log.error('Could not determine version for module {}'
                          .format(dep['name']))
                raise(InvalidDependency(dep))

        log.info("Fetching revision {} of module {}"
                 .format(dep['revision'], dep['name']))

        source = getSource(dep, src)
        if (source == False):
            log.error("Module {} has no source!".format(dep['name']))
            return False

        url = source['repository']
        p = os.path.join('deps', dep['name'])
        newmod = os.path.join(p, 'module.yaml')
        if (os.path.exists(p)):
            log.info("Module directory exists. Skipping initialisation.")
        elif (source['type'] == 'symlink'):
            log.info("Symlinking dependency: {} to {}" .format(dep['name'], url))
            os.symlink(url, p)
        elif (source['type'] == 'git'):
            rc = mmh.loggedProcess(cfg, log, ['git', 'clone', url, p])
            if (rc != 0):
                log.error("Failed to clone code for module {}!"
                          .format(dep['name']))
                return False
            # Check out the requested revision
            olddir = os.getcwd()
            os.chdir(p)
            rev = fetchCheckout(cfg, log, dep['name'], dep['revision'])
            if (rev == None):
                return False
            dep['revision'] = rev
            os.chdir(olddir)
        else:
            raise(InvalidRepositoryType(source))

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

        if (dep['name'] == 'zephyr-kernel'):
            # After loading the zephyr kernel repository, load its west
            # specification, in order to be able inherit zephyr-* module
            # versions later on in the fetching process.
            trace.west(p)

    # And recurse with the new stack and trace; we're done when the new stack
    # is empty.
    return fetch(cfg, log, src, st, trace)

def stepFailed(data, step):
    return (step in data and data[step] == False)

def buildFailed(data):
    return (stepFailed(data, 'configure-result') or
            stepFailed(data, 'build-result') or
            stepFailed(data, 'testsuite-result'))

class InvalidTimeStampKind(Exception):
    pass

def endoftime(datum):
    t = datum['type']
    if (t == 'build' or t == 'system-board' or t == 'system-zephyr'):
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
        raise(InvalidTimeStampKind(datum['type']))

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

class InvalidStepKind(Exception):
    pass

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

    def build(self, toolchain, cpu, buildcfg, buildtool):
        self.data.append( { 'type':      'build',
                            'toolchain': toolchain,
                            'cpu':       cpu,
                            'buildcfg':  buildcfg,
                            'buildtool': buildtool,
                            'time-stamp': datetime.datetime.now() } )

    def systemBoard(self, toolchain, board, buildcfg, buildtool):
        self.data.append( { 'type':      'system-board',
                            'toolchain': toolchain,
                            'board':     board,
                            'buildcfg':  buildcfg,
                            'buildtool': buildtool,
                            'time-stamp': datetime.datetime.now() } )

    def systemZephyr(self, app, toolchain, board, buildcfg, buildtool):
        self.data.append( { 'type':      'system-zephyr',
                            'application': app,
                            'toolchain': toolchain,
                            'board':     board,
                            'buildcfg':  buildcfg,
                            'buildtool': buildtool,
                            'time-stamp': datetime.datetime.now() } )

    def logConfigure(self, result):
        self.data[-1]['configure-stamp'] = datetime.datetime.now()
        self.data[-1]['configure-result'] = (result == 0)

    def logBuild(self, result):
        self.data[-1]['build-stamp'] = datetime.datetime.now()
        self.data[-1]['build-result'] = (result == 0)

    def logInstall(self, result):
        self.data[-1]['install-stamp'] = datetime.datetime.now()
        self.data[-1]['install-result'] = (result == 0)

    def logTestsuite(self, num, result):
        self.data[-1]['testsuite-stamp'] = datetime.datetime.now()
        self.data[-1]['testsuite-tests'] = num
        self.data[-1]['testsuite-result'] = (result == 0)

    def wasSuccessful(self):
        for entry in self.data:
            if entry['type'] == 'checkpoint':
                continue
            if buildFailed(entry):
                return False
        return True

    def countFailed(self):
        n = 0
        for entry in self.data:
            if entry['type'] == 'checkpoint':
                continue
            if buildFailed(entry):
                n = n + 1
        return n

    def countBuilds(self):
        n = 0
        for entry in self.data:
            if entry['type'] != 'checkpoint':
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
                if ('configure-stamp' in datum):
                    previous = datum['configure-stamp']
                else:
                    previous = datum['time-stamp']
                time = renderTimedelta(datum['build-stamp'] - previous)
            elif prefix == 'testsuite':
                time = renderTimedelta(datum['testsuite-stamp'] -
                                       datum['build-stamp'])
            elif prefix == 'install':
                if ('testsuite-stamp' in datum):
                    previous = datum['testsuite-stamp']
                else:
                    previous = datum['build-stamp']
                time = renderTimedelta(datum['install-stamp'] - previous)
            else:
                raise(InvalidStepKind(prefix))

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

    def renderInstallStepResult(self, datum):
        self.renderStepResult(datum, 'Install', 'install')

    def renderToolchain(self, tc):
        if (isinstance(tc, dict)):
            return tc['name']
        return tc

    def renderBuildResult(self, datum):
        result = 'Success'
        if buildFailed(datum):
            result = 'Failure   ---!!!---'
        maybeInfo(self.cfg, self.log, ''.ljust(100, '-'))
        maybeInfo(self.cfg, self.log,
                  '{pad:>21}{toolchain:>20} {cpu:>28} {config:>16} {tool:>12}'
                  .format(pad = '',
                          toolchain = 'Toolchain',
                          cpu = 'Architecture',
                          config = 'Config',
                          tool = 'Buildtool'))
        maybeInfo(self.cfg, self.log,
                  '{pad:>21}{toolchain:>20} {cpu:>28} {config:>16} {tool:>12}     {result}'
                  .format(pad = '',
                          toolchain = self.renderToolchain(datum['toolchain']),
                          cpu = datum['cpu'],
                          config = datum['buildcfg'],
                          tool = datum['buildtool'],
                          result = result))
        self.renderConfigureStepResult(datum)
        self.renderBuildStepResult(datum)
        self.renderTestStepResult(datum)
        self.renderInstallStepResult(datum)

    def renderSystemBoardResult(self, datum):
        result = 'Success'
        if buildFailed(datum):
            result = 'Failure   ---!!!---'
        maybeInfo(self.cfg, self.log, ''.ljust(100, '-'))
        maybeInfo(self.cfg, self.log,
                  '{pad:>21}{toolchain:>20} {board:>28} {config:>16} {tool:>12}'
                  .format(pad = '',
                          toolchain = 'Toolchain',
                          board = 'Board',
                          config = 'Config',
                          tool = 'Buildtool'))
        maybeInfo(self.cfg, self.log,
                  '{pad:>21}{toolchain:>20} {board:>28} {config:>16} {tool:>12}     {result}'
                  .format(pad = '',
                          toolchain = datum['toolchain'],
                          board = datum['board'],
                          config = datum['buildcfg'],
                          tool = datum['buildtool'],
                          result = result))
        self.renderConfigureStepResult(datum)
        self.renderBuildStepResult(datum)
        self.renderTestStepResult(datum)
        self.renderInstallStepResult(datum)

    def renderSystemZephyrResult(self, datum):
        result = 'Success'
        if buildFailed(datum):
            result = 'Failure   ---!!!---'
        maybeInfo(self.cfg, self.log, ''.ljust(100, '-'))
        maybeInfo(self.cfg, self.log,
                  '{application:>20} {toolchain:>20} {board:>28} {config:>16} {tool:>12}'
                  .format(application = 'Application',
                          toolchain = 'Toolchain',
                          board = 'Board',
                          config = 'Config',
                          tool = 'Buildtool'))
        maybeInfo(self.cfg, self.log,
                  '{application:>20} {toolchain:>20} {board:>28} {config:>16} {tool:>12}     {result}'
                  .format(application = datum['application'],
                          toolchain = self.renderToolchain(datum['toolchain']),
                          board = datum['board'],
                          config = datum['buildcfg'],
                          tool = datum['buildtool'],
                          result = result))
        self.renderConfigureStepResult(datum)
        self.renderBuildStepResult(datum)
        self.renderTestStepResult(datum)
        self.renderInstallStepResult(datum)

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
            elif t == 'system-board':
                self.renderSystemBoardResult(entry)
            elif t == 'system-zephyr':
                self.renderSystemZephyrResult(entry)
            elif t == 'checkpoint':
                self.renderCheckpoint(entry)
            else:
                self.log.warn('Statistics log entry has unknown type: {}'
                              .format(t))
        #print("DEBUG: {}", self.data)
        maybeInfo(self.cfg, self.log, '')
        time = renderTimedelta(self.data[-1]['time-stamp'] -
                               self.data[0]['time-stamp'])
        maybeInfo(self.cfg, self.log,
                  'Total runtime: {time}'.format(time = time))
        maybeInfo(self.cfg, self.log, '')

def isSatisfied(deps, done, name):
    lst = list(x['name'] for x in deps[name])
    for dep in lst:
        if not(dep in done):
            return False
    return True

def outputMMHYAML(version, fn, data, args):
    if (data == None):
        data = {}
    data.pop('definition', None)
    data.pop('root', None)
    data['version'] = version
    data['mode'] = 'module'
    data['parameters'] = {}
    if (len(args.instances) > 0):
        data['parameters']['instances'] = args.instances
    if (args.architectures != None):
        data['parameters']['architectures'] = args.architectures
    if (args.buildconfigs != None):
        data['parameters']['buildconfigs'] = args.buildconfigs
    if (args.buildtools != None):
        data['parameters']['buildtools'] = args.buildtools
    if (args.toolchains != None):
        data['parameters']['toolchains'] = args.toolchains
    if (args.cmake != None):
        data['parameters']['cmake'] = args.cmake
    if not data['parameters']:
        data.pop('parameters', None)
    if (args.all_instances and 'instances' in data):
        del(data['instances'])
    mmh.dump(fn, data)

def updateMMHYAML(log, root, version, args):
    fn = os.path.join(root, 'MakeMeHappy.yaml')
    data = None

    if (os.path.exists(fn)):
        data = mmh.load(fn)

    if (not mmh.matchingVersion(version, data)):
        log.info('Creating instance config: {}'.format(fn))
        outputMMHYAML(version, fn, data, args)
        return

    if (not mmh.noParameters(args) or args.all_instances):
        log.info('Updating instance config: {}'.format(fn))
        outputMMHYAML(version, fn, data, args)
        return

class CircularDependency(Exception):
    pass

class CodeUnderTest:
    def __init__(self, log, cfg, args, sources, module):
        self.stats = ExecutionStatistics(cfg, log)
        self.stats.checkpoint('module-initialisation')
        self.depEval = DependencyEvaluation(cfg, log)
        self.log = log
        self.cfg = cfg
        self.args = args
        self.module = module
        self.sources = sources
        self.moduleType = 'cmake'
        self.deporder = None
        self.root = None
        self.moduleData = None
        self.depstack = None
        self.depstack = None
        self.extensions = None
        self.zephyr = None
        self.toplevel = None

    def name(self):
        if (isinstance(self.moduleData, dict) and 'name' in self.moduleData):
            return self.moduleData['name']
        return 'MakeMeHappyModule'

    def loadModule(self):
        self.log.info("Loading module description: {}".format(self.module))
        self.moduleData = mmh.load(self.module)
        if ('type' in self.moduleData):
            self.moduleType = self.moduleData['type']

    def cliAdjust(self, toolchains, architectures, buildconfigs, buildtools):
        if toolchains is not None:
            self.moduleData['toolchains'] = []
            for tc in toolchains:
                self.moduleData['toolchains'].append(self.cfg.fetchToolchain(tc))
        if architectures is not None:
            self.moduleData['architectures'] = architectures
        if buildconfigs is not None:
            self.moduleData['buildconfigs'] = buildconfigs
        if buildtools is not None:
            self.moduleData['buildtools'] = buildtools

    def loadSources(self):
        self.log.info("Loading source definitions...")
        self.sources.load()
        self.sources.merge()

    def initRoot(self, version, args):
        self.root = BuildRoot(log = self.log,
                              seed = yaml.dump(self.moduleData),
                              modName = self.name(),
                              dirName = args.directory)
        if (args.fromyaml == False or args.all_instances == True):
            updateMMHYAML(self.log, self.root.root, version, args)

    def cmakeIntoYAML(self):
        self.log.info("Updating MakeMeHappy.yaml with CMake information")
        fn = os.path.join('MakeMeHappy.yaml')
        data = mmh.load(fn)
        data['cmake'] = {}
        data['cmake']['module-path'] = self.extensions.modulePath()
        data['cmake']['toolchain-path'] = self.extensions.toolchainPath()
        data['zephyr'] = {}
        data['zephyr']['board-root'] = self.zephyr.boardRoot()
        data['zephyr']['dts-root'] = self.zephyr.dtsRoot()
        data['zephyr']['soc-root'] = self.zephyr.socRoot()
        mmh.dump(fn, data)

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

    def calculateDependencyOrder(self):
        rv = []
        deps = self.deptrace.modDependencies()
        lst = list(deps.keys())
        none = list(name for name in lst if (len(deps[name]) == 0))

        for entry in none:
            rv.append(entry)

        done = none
        rest = list(name for name in lst if (len(deps[name]) > 0))

        while (len(rest) > 0):
            lastdone = len(done)
            for item in rest:
                if (isSatisfied(deps, done, item)):
                    rv.append(item)
                    done = [item] + done
                    rest = list(x for x in rest if (x != item))
            newdone = len(done)
            if (newdone == lastdone):
                # Couldn't take a single item off of the rest in the last
                # iteration. That means that dependencies can't be satisfied.
                raise(CircularDependency(done, deps))
        return rv

    def loadDependencies(self):
        self.stats.checkpoint('load-dependencies')
        self.depstack = Stack(self.dependencies())
        self.deptrace = Trace()
        rc = fetch(self.cfg, self.log, self.sources, self.depstack, self.deptrace)

        if (rc == False):
            self.log.error("Fatal error loading dependencies. Giving up!")
            exit(1)

        self.deporder = self.calculateDependencyOrder()
        self.extensions = CMakeExtensions(self.moduleData,
                                          self.deptrace,
                                          self.deporder)
        self.zephyr = ZephyrExtensions(self.moduleData,
                                       self.deptrace,
                                       self.deporder)
        if ('dependencies' in self.moduleData):
            self.depEval.insertSome(self.moduleData['dependencies'],
                                    self.moduleData['name'])
        for dept in self.deptrace.data:
            self.depEval.insertSome(dept['dependencies'], dept['name'])
        self.depEval.evaluate()

    def cmakeModules(self):
        if (has('cmake-modules', self.moduleData, str)):
            return self.moduleData['cmake-modules']
        return None

    def generateToplevel(self):
        self.stats.checkpoint('generate-toplevel')
        self.toplevel = Toplevel(self.log,
                                 self.moduleType,
                                 self.variables(),
                                 self.targets(),
                                 self.defaults(),
                                 self.cmake3rdParty(),
                                 self.cmakeVariants(),
                                 self.zephyr.boardRoot(),
                                 self.zephyr.dtsRoot(),
                                 self.zephyr.socRoot(),
                                 self.extensions.modulePath(),
                                 self.deptrace,
                                 self.deporder)
        self.toplevel.generateToplevel()

    def listInstances(self):
        return list(map(build.instanceName,
                        build.listInstances(self.log, self, self.args)))

    def build(self):
        build.allofthem(self.cfg, self.log, self, self.extensions, self.args)

    def cmake3rdParty(self):
        if (has('cmake-extensions', self.moduleData, dict)):
            return self.moduleData['cmake-extensions']
        return {}

    def cmakeVariants(self):
        if (has('cmake-extension-variants', self.moduleData, dict)):
            return self.moduleData['cmake-extension-variants']
        return {}

    def defaults(self):
        if (has('defaults', self.moduleData, dict)):
            return self.moduleData['defaults']
        return {}

    def variables(self):
        if (has('variables', self.moduleData, dict)):
            return self.moduleData['variables']
        return {}

    def targets(self):
        if (has('targets', self.moduleData, list)):
            return self.moduleData['targets']
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

    def queryToolchain(self, start, item):
        result = start
        if (has('toolchains', self.moduleData, list)):
            result.extend(ys.queryToolchain([self.moduleData], item))
        result = list(set(result))
        result.sort()
        return result

    def queryItem(self, start, item):
        result = start
        if has(item, self.moduleData, list):
            result.extend(self.moduleData[item])
        result = list(set(result))
        result.sort()
        return result

    def allToolchains(self):
        return self.queryToolchain(self.cfg.allToolchains(), 'name')

    def allArchitectures(self):
        return self.queryToolchain(self.cfg.allArchitectures(), 'architecture')

    def allBuildtools(self):
        return self.queryItem(self.cfg.allBuildtools(), 'buildtools')

    def allBuildConfigs(self):
        return self.queryItem(self.cfg.allBuildConfigs(), 'buildconfigs')

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
