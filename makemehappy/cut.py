import datetime
import math
import os
import re
import yaml

import itertools as it

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

def genNames(lst):
    return list(map(lambda x: x['name'],
                    filter(lambda x: 'name' in x, lst)))

def genOrigins(lst):
    xs = list(map(lambda x: x['origin'],
                  filter(lambda x: 'origin' in x and x['origin'] != None,
                         lst)))

    if (len(xs) == 0):
        return None

    return xs

def printTag(tag):
    if (tag == None):
        return ''
    if (isinstance(tag, str)):
        return f' [{tag}]'
    if (isinstance(tag, list)):
        if (len(tag) == 0):
            return ''
        return f' [{", ".join(tag)}]'
    return ' ' + str(tag)

def inherited(lst):
    return (lst != None and 'inherit' in lst)

class DependencyEvaluation:
    def __init__(self, sources):
        self.sources = sources
        self.data = {}
        self.journal = []

    def note(self, d):
        self.journal.append(d)

    def insertSome(self, lst, origin):
        for dep in lst:
            self.insert(dep, origin)

    def insert(self, dep, origin):
        name = dep['name']
        revision = None
        tag = None
        if ('revision' in dep):
            revision = dep['revision']
        if ('origin' in dep):
            tag = dep['origin']
        if (name not in self.data):
            self.data[name] = {}
        if (revision not in self.data[name]):
            self.data[name][revision] = []
        src = self.sources.lookup(name)
        new = { 'name': origin, 'origin': tag }
        self.data[name][revision].append(new)
        midx = mmh.findByKey(self.data[name][revision], '!meta')
        if (midx != None):
            meta = self.data[name][revision][midx]
        else:
            new = { '!meta': True }
            self.data[name][revision].append(new)
            meta = self.data[name][revision][-1]
        if ('deprecate' in src):
            if (isinstance(src['deprecate'], bool)):
                meta['module-deprecated'] = src['deprecate']
                if ('alternative' in src):
                    meta['module-alternative'] = src['alternative']
            elif (isinstance(src['deprecate'], list) and
                  revision in src['deprecate']):
                meta['revision-deprecated'] = True
            elif (revision == src['deprecate']):
                meta['revision-deprecated'] = True

    def logVersion(self, key, ver, unique):
        return { 'kind': ('version:' + ('unique' if unique else 'ambiguous')),
                 'module': key,
                 'data': ver,
                 'version': ver.string,
                 'effective': ver.render(),
                 'origins': genOrigins(ver.origin) }

    def deprecatedModule(self, key, meta, data):
        alt = None
        if ('module-alternative' in meta):
            alt = meta['module-alternative']
        return { 'kind': 'deprecated:module',
                 'module': key,
                 'alternative': alt,
                 'from': genNames(data) }

    def deprecatedRevision(self, key, revision, meta, data):
        return { 'kind': 'deprecated:revision',
                 'module': key,
                 'data': revision,
                 'version': revision.string,
                 'effective': revision.render(),
                 'from': genNames(data),
                 'tags': genOrigins(revision.origin) }

    def kinds(self, lst):
        rv = {}
        for k in lst:
            if (k.kind not in rv):
                rv[k.kind] = []
            rv[k.kind].append(k)
        return rv

    def compare(self, key, a, b):
        result = v.compare(a, b)
        if (not result.compatible):
            self.note({ 'kind': 'version:incompatible',
                        'module': key,
                        'a': a, 'b': b })
        if (result.kind == 'same'):
            # This method is currently used when higher levels detected a
            # mismatch. If we're here, that means they did something wrong,
            # or the comparison algorithm in version.py is broken.
            self.note({ 'kind': 'maybe-bug',
                        'tag':  'unexpected-same-version',
                        'meta': 'Versions should not be the same here.',
                        'module': key,
                        'a': a, 'b': b })
            return

        entry = { 'kind': 'version:mismatch:' + result.kind,
                  'module': key,
                  'result': result,
                  'a': a, 'b': b,
                  'a-origins': [],
                  'b-origins': [] }

        for origin in a.origin:
            entry['a-origins'].append({ 'name': origin['name'],
                                        'tag':  origin['origin'] })

        for origin in b.origin:
            entry['b-origins'].append({ 'name': origin['name'],
                                        'tag':  origin['origin'] })

        self.note(entry)

    def maybeBetter(self, key, kind, origins):
        # Inherited revisions can do whatever they want. We will assume, that
        # the parent module will know what it is doing.
        if (kind != 'version' and not inherited(origins)):
            return { 'kind': 'revision:kind',
                     'actual': kind,
                     'module': key,
                     'inherited': inherited(origins) }
        return None

    def judge(self, key, lst, journal):
        compat = self.kinds(lst)
        self.note({ 'kind': ('revision:' + ('incompatible' if (len(compat) > 1)
                                                           else 'compatible')),
                    'kinds': list(compat.keys()),
                    'module': key,
                    'details': journal })

        for kind in compat:
            origins = genOrigins(list(it.chain.from_iterable(
                map(lambda x: x.origin, compat[kind]))))
            detail = self.maybeBetter(key, kind, origins)
            if (detail != None):
                for vers in compat[kind]:
                    entry = { 'kind': 'revision:discouraged',
                              'detail': detail,
                              'data': vers,
                              'module': key,
                              'origins': [] }
                    for origin in self.data[key][vers.string]:
                        if ('name' not in origin):
                            continue
                        entry['origins'].append({ 'name': origin['name'],
                                                  'tag':  origin['origin'] })
                    self.note(entry)

        # Get a list of pairs of all combinations of different versions
        vps = list(filter(
            lambda x: x[0] > x[1],
            it.product(filter(lambda x: x.kind == 'version', lst),
                       repeat = 2)))
        # Compare those.
        for vp in vps:
            self.compare(key, vp[0], vp[1])

    def evaluate(self):
        for key in self.data:
            versions = list(
                filter(lambda x: not x.string.startswith('!'),
                       map(lambda x: v.Version(x, self.data[key][x]),
                           self.data[key].keys())))
            j = []
            if (len(versions) == 1):
                ver = versions[0]
                j.append(self.logVersion(key, ver, True))
            else:
                for ver in sorted(versions):
                    j.append(self.logVersion(key, ver, False))
            for ver in sorted(versions):
                here = self.data[key][ver.string]
                midx = mmh.findByKey(here, '!meta')
                meta = here[midx]
                if (mmh.trueKey(meta, 'module-deprecated')):
                    j.append(self.deprecatedModule(key, meta, here))
                if (mmh.trueKey(meta, 'revision-deprecated')):
                    j.append(self.deprecatedRevision(key, ver, meta, here))
            self.judge(key, versions, j)

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

def gitDetectRevision(log, path):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path,
         'describe', '--always', '--abbrev=12', '--exact-match'])
    if (rc == 0):
        return stdout
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'rev-parse', '--abbrev-ref', 'HEAD'])
    if (rc == 0 and stdout != 'HEAD'):
        return stdout
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'rev-parse', 'HEAD'])
    if (rc == 0):
        return stdout
    log.info("Could not determine repository state: {}".format(stderr))
    return None

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

    rc = mmh.loggedProcess(cfg, log, ['git',
                                      '-c', 'advice.detachedHead=false',
                                      'checkout', '--quiet',
                                      revision])

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
            dep['origin'] = 'override'
        if ('revision' not in dep):
            log.info('Module {} does not specify a revision'
                     .format(dep['name']))
            log.info('Attempting to resolve via zephyr-west')
            dep['revision'] = z.westRevision(src, trace.west(), dep['name'])
            if (dep['revision'] == None):
                log.error('Could not determine version for module {}'
                          .format(dep['name']))
                raise(InvalidDependency(dep))
            dep['origin'] = 'inherit'

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
            dep['revision'] = gitDetectRevision(log, p)
            log.info(f'Current repository state: {dep["revision"]}')
        elif (source['type'] == 'symlink'):
            log.info("Symlinking dependency: {} to {}" .format(dep['name'], url))
            os.symlink(url, p)
            dep['revision'] = gitDetectRevision(log, p)
            log.info(f'Current repository state: {dep["revision"]}')
        elif (source['type'] == 'git'):
            rc = mmh.loggedProcess(cfg, log, ['git',
                                              '-c', 'advice.detachedHead=false',
                                              'clone', '--quiet', url, p])
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
        self.depEval = DependencyEvaluation(sources)
        self.depSuccess = True
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
        self.depKWS = [
            { 'name': 'major-mismatch',        'user': 'Major Version',
              'singular': 'Mismatch',          'plural': 'Mismatches' },
            { 'name': 'minor-mismatch',        'user': 'Minor Version',
              'singular': 'Mismatch',          'plural': 'Mismatches' },
            { 'name': 'patch-mismatch',        'user': 'Patch Version',
              'singular': 'Mismatch',          'plural': 'Mismatches' },
            { 'name': 'miniscule-mismatch',    'user': 'Miniscule Version',
              'singular': 'Mismatch',          'plural': 'Mismatches' },
            { 'name': 'deprecated-module',     'user': 'Deprecated',
              'singular': 'Module',            'plural': 'Modules' },
            { 'name': 'deprecated-revision',   'user': 'Deprecated',
              'singular': 'Revision',          'plural': 'Revisions' },
            { 'name': 'discouraged-revision',  'user': 'Discouraged',
              'singular': 'Revision',          'plural': 'Revisions' },
            { 'name': 'incompatible-revision', 'user': 'Incompatible',
              'singular': 'Revision',          'plural': 'Revisions' },
            { 'name': 'unique-dependency',     'user': 'Unique',
              'singular': 'Dependency',        'plural': 'Dependencies' },
            { 'name': 'ambiguous-dependency',  'user': 'Ambiguous',
              'singular': 'Dependency',        'plural': 'Dependencies' } ]

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
        self.fullDependencyLog()

    def dependencySummary(self):
        rv = {}
        for kw in list(map(lambda x: x['name'], self.depKWS)):
            rv[kw] = 0
        for l0 in self.depEval.journal:
            intodetails = False
            if (l0['kind'] == 'revision:incompatible'):
                rv['incompatible-revision'] += 1
                intodetails = True
            elif (l0['kind'] == 'revision:compatible'):
                intodetails = True
            elif (l0['kind'] == 'revision:discouraged'):
                rv['discouraged-revision'] += 1
            elif (m := re.match('^version:mismatch:(.*)', l0['kind'])):
                rv[m.group(1) + '-mismatch'] += 1

            if intodetails:
                for l1 in l0['details']:
                    if (m := re.match('version:(unique|ambiguous)', l1['kind'])):
                        rv[m.group(1) + '-dependency'] += 1
                    elif (l1['kind'] == 'deprecated:revision'):
                        rv['deprecated-revision'] += 1
                    elif (l1['kind'] == 'deprecated:module'):
                        rv['deprecated-module'] += 1

        return rv

    def fullDependencyLog(self):
        self.log.info('Inspecting Dependency Version Tree...')
        for entry in self.depEval.journal:
            self.ppDJE(entry)
        self.log.info('Inspecting Dependency Version Tree... done.')

    def handleMismatch(self, data, kind):
        self.log.info('{} version mismatch for dependency "{}" detected!'
                      .format(kind.title(), data['module']))
        self.log.info(f'  {data["a"].string} used by:')
        for origin in data['a-origins']:
            self.log.info(f'    {origin["name"]}{printTag(origin["tag"])}')
        self.log.info(f'  {data["b"].string} used by:')
        for origin in data['b-origins']:
            self.log.info(f'    {origin["name"]}{printTag(origin["tag"])}')

    def ppDJE(self, entry):
        # Pretty Pring Dependency Journal Entry
        if ('kind' not in entry):
            self.log.fatal(f'Broken journal: {entry}')
            exit(1)
        elif (m := re.match('version:(unique|ambiguous)', entry['kind'])):
            k = m.group(1)
            if (k == 'unique' and not self.cfg.lookup('log-unique-versions')):
                return
            if (entry['data'].kind == 'version'):
                self.log.info('{} dependency: {} {} effective: {}{}'
                              .format(k.title(),
                                      entry['module'], entry['version'],
                                      entry['effective'],
                                      printTag(entry['origins'])))
            else:
                self.log.info('{} dependency: {} {}{}'
                              .format(m.group(1).title(),
                                      entry['module'], entry['version'],
                                      printTag(entry['origins'])))
        elif (entry['kind'] == 'version:incompatible'):
            self.log.info('{}: Incompatible versioning scheme: {} vs {}'
                          .format(entry['module'], entry['a'], entry['b']))
        elif (entry['kind'] == 'maybe-bug'):
            self.log.warning(f'BUG? {entry["module"]}: {entry["tag"]}')
            self.log.warning(f'BUG? {entry["meta"]}')
        elif (m := re.match('^version:mismatch:(.*)', entry['kind'])):
            self.handleMismatch(entry, m.group(1))
        elif (entry['kind'] == 'revision:kind'):
            # This is handled in revision:incompatible.
            pass
        elif (entry['kind'] == 'revision:compatible'):
            for v in entry['details']:
                self.ppDJE(v)
        elif (entry['kind'] == 'revision:incompatible'):
            self.log.info(f"Revisions for {entry['module']} are NOT compatible:")
            self.log.info(f'    kinds: [{", ".join(entry["kinds"])}]')
            for v in entry['details']:
                self.ppDJE(v)
        elif (entry['kind'] == 'revision:discouraged'):
            if entry['detail']['inherited']:
                return
            self.log.info(
                'Dependencies for module "{}" use discouraged revision kind!'
                .format(entry['module']))
            self.log.info('  {} {} used by:'.format(entry["detail"]["actual"],
                                                    entry["data"].string))
            for origin in entry['origins']:
                self.log.info('    {}{}'.format(origin["name"],
                                                printTag(origin["tag"])))
        elif (entry['kind'] == 'deprecated:module'):
            self.log.info(
                'Detected use of deprecated module "{}"! Used by:'
                .format(entry['module']))
            for origin in entry['from']:
                self.log.info('    {}'.format(origin))
            if (entry['alternative'] != None):
                self.log.info('  Possible alternative: {}'
                            .format(entry['alternative']))
        elif (entry['kind'] == 'deprecated:revision'):
            self.log.info(
                'Detected use of deprecated revision for module "{}"!:'
                .format(entry['module']))
            self.log.info('  Revision: {}{}'
                          .format(entry['version'], printTag(entry['tags'])))
            self.log.info('  Used by:')
            for origin in entry['from']:
                self.log.info('    {}'.format(origin))
        else:
            self.log.warning(f'Unsupported Journal Entry: {entry}')

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

    def renderDependencySummary(self, withSeparator):
        behaviour = self.cfg.lookup('dependency-summary')
        data = self.dependencySummary()

        final = []
        for entry in data:
            fatal = False
            b = behaviour[entry]
            tmp = mmh.findByName(self.depKWS, entry)
            if (tmp == None):
                continue
            user = self.depKWS[tmp]['user']
            sing = self.depKWS[tmp]['singular']
            plur = self.depKWS[tmp]['plural']

            if (b == 'ignore'):
                continue

            if (data[entry] == 0):
                continue

            if (b == 'error' and self.cfg.lookup('fatal-dependencies')):
                self.depSuccess = False

            final.append({ 'name': entry, 'user': user,
                           'singular': sing, 'plural': plur,
                           'count': data[entry],
                           'level': b })

        if (len(final) > 0):
            if (withSeparator):
                maybeInfo(self.cfg, self.log, '')
            maybeInfo(self.cfg, self.log, 'Dependency Evaluation Summary:')
            maybeInfo(self.cfg, self.log, '')

        for entry in final:
            maybeInfo(self.cfg, self.log,
                      '  {:8} {:2} {} {}'
                      .format(entry['level'] + ':',
                              entry['count'],
                              entry['user'],
                              entry['singular'] if (entry['count'] == 1)
                                                else entry['plural']))

        if (len(final) > 0):
            maybeInfo(self.cfg, self.log, '')

    def dependenciesOkay(self):
        return self.depSuccess

    def wasSuccessful(self):
        return self.stats.wasSuccessful()

    def countBuilds(self):
        return self.stats.countBuilds()

    def countFailed(self):
        return self.stats.countFailed()
