import os
import subprocess

import mako.template as mako
import makemehappy.utilities as mmh
import makemehappy.cut as cut

defaults = { 'build-configs'      : [ 'debug', 'release' ],
             'build-system'       : None,
             'build-tool'         : 'ninja',
             'install-dir'        : 'artifacts',
             'ufw'                : '${system}/libraries/ufw',
             'kconfig'            : [ ],
             'zephyr-kernel'      : '${system}/zephyr/kernel',
             'zephyr-module-path' : [ '${system}/zephyr/modules' ],
             'zephyr-template'    : 'applications/${application}' }

def cmakeBuildtool(log, name):
    std = 'Ninja'
    tool = ''
    if (name == 'make'):
        tool = 'Unix Makefiles'
    elif (name == 'ninja'):
        tool = 'Ninja'
    else:
        log.warn('Unknown build-tool {} defaulting to {}'.format(name, std))
        tool = std
    return '-G{}'.format(tool)

def cmakeSourceDir(d):
    return [ '-S' , d ]

def cmakeBinaryDir(d):
    return [ '-B' , d ]

def expandFile(tmpl):
    if (tmpl == None):
        return None
    curdir = os.getcwd()
    exp = mako.Template(tmpl).render(system = curdir)
    return exp

def zephyrToolchain(spec):
    real = None
    if (isinstance(spec, str)):
        real = { 'name' : spec, 'path' : None }
    elif (isinstance(spec, dict)):
        real = spec
    ztv = [ cmakeParam('ZEPHYR_TOOLCHAIN_VARIANT', real['name']) ]
    if (real['name'] == 'gnuarmemb'):
        ztv.extend([ cmakeParam('GNUARMEMB_TOOLCHAIN_PATH', real['path']) ])
    return ztv


def makeZephyrInstances(zephyr):
    instances = []
    name = zephyr['application']
    for cfg in zephyr['build-configs']:
        for build in zephyr['build']:
            for tc in build['toolchains']:
                tcname = ''
                if (isinstance(tc, str)):
                    tcname = tc
                else:
                    tcname = tc['name']
                for board in build['boards']:
                    instances.extend(['zephyr/{}/{}/{}/{}'.format(
                        board, name, tcname, cfg)])
    return instances

def makeBoardInstances(board):
    instances = []
    for cfg in board['build-configs']:
        for tc in board['toolchains']:
            instances.extend(['boards/{}/{}/{}'.format(
                board['name'], tc, cfg)])
    return instances

def makeInstances(data):
    boards = []
    zephyr = []
    if ('zephyr' in data):
        for z in data['zephyr']:
            boards += makeZephyrInstances(z)
    if ('boards' in data):
        for b in data['boards']:
            boards += makeBoardInstances(b)
    rv = boards + zephyr
    rv.sort()
    return rv

def maybeCopy(thing, common, key):
    if (not key in thing):
        if (key in common):
            thing[key] = common[key]
        else:
            thing[key] = defaults[key]

def fill(thing, common):
    for key in defaults:
        maybeCopy(thing, common, key)

def fillData(data):
    data['common'] = {}

    if ('zephyr' in data):
        for z in data['zephyr']:
            fill(z, data['common'])
    if ('boards' in data):
        for b in data['boards']:
            fill(b, data['common'])

def makeCMakeList(lst):
    return ';'.join([x for x in lst if x != None])

def cmakeParam(name, value, allowEmpty = False):
    exp = ''
    if (isinstance(value, str)):
        exp = value
    elif (isinstance(value, list)):
        exp = makeCMakeList(value)
    else:
        return None

    if (allowEmpty == False and exp == ''):
        return None

    return '-D{}={}'.format(name, exp)

def cmake(lst):
    return [ 'cmake' ] + [ x for x in mmh.flatten(lst) if x != None ]

def getSpec(data, key, name):
    for d in data:
        if (name == d[key]):
            return d
    return None

def isZephyrModule(d):
    return (os.path.isdir(d) and
            os.path.isdir(os.path.join(d, 'zephyr')))

def findZephyrModule(path, name):
    for d in path:
        candidate = os.path.join(d, name)
        if (isZephyrModule(candidate)):
            return candidate
    return None

def genZephyrModules(path, names):
    realpath = [ expandFile(x) for x in path ]
    modules = [ findZephyrModule(realpath, m) for m in names ]
    return modules

def zephyrToolchainMatch(tc, name):
    if (isinstance(tc, str)):
        if (tc == name):
            return True
    elif (tc['name'] == name):
        return True
    return False

def findZephyrBuild(builds, tc, board):
    for build in builds:
        if board in build['boards']:
            for toolchain in build['toolchains']:
                if (zephyrToolchainMatch(toolchain, tc)):
                    return build
    return None

def findZephyrToolchain(build, tc):
    for toolchain in build['toolchains']:
        if (zephyrToolchainMatch(toolchain, tc)):
            return toolchain
    return None

def findZephyrTransformer(ufw, cfg):
    name = cfg.lower()
    transformer = os.path.join(expandFile(ufw),
                               'cmake', 'kconfig',
                               cfg + '.conf')
    if (os.path.exists(transformer)):
        return transformer
    return None

class InvalidSystemInstance(Exception):
    pass

class SystemInstanceBoard:
    def __init__(self, sys, board, tc, cfg):
        self.sys = sys
        self.board = board
        self.tc = tc
        self.cfg = cfg
        self.spec = getSpec(self.sys.data['boards'], 'name', self.board)
        self.systemdir = os.getcwd()
        if (sys.mode == 'system-single'):
            self.builddir = self.sys.args.directory
            self.installdir = os.path.join(self.systemdir,
                                           self.sys.args.directory,
                                           self.spec['install-dir'])
        else:
            self.builddir = os.path.join(self.sys.args.directory, 'boards',
                                        self.board, self.tc, self.cfg)
            self.installdir = os.path.join(self.systemdir,
                                           self.sys.args.directory,
                                           self.spec['install-dir'],
                                           self.board, self.tc, self.cfg)
        self.tcfile = os.path.join(expandFile(self.spec['ufw']),
                                   'cmake', 'toolchains',
                                   '{}.cmake'.format(tc))
        self.sys.stats.systemBoard(tc, board, cfg, self.spec['build-tool'])

    def configure(self):
        cmd = cmake([
            cmakeBuildtool(self.sys.log, self.spec['build-tool']),
            cmakeSourceDir('.'),
            cmakeBinaryDir(self.builddir),
            cmakeParam('CMAKE_BUILD_TYPE', self.cfg),
            cmakeParam('CMAKE_INSTALL_PREFIX', self.installdir),
            cmakeParam('CMAKE_EXPORT_COMPILE_COMMANDS', 'on'),
            cmakeParam('CMAKE_TOOLCHAIN_FILE', self.tcfile),
            cmakeParam('TARGET_BOARD', self.board),
            cmakeParam('UFW_LOAD_BUILD_SYSTEM',
                       expandFile(self.spec['build-system']))])

        if (self.sys.args.cmake != None):
            cmd.extend(self.sys.args.cmake)

        rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd)
        self.sys.stats.logConfigure(rc)
        return (rc == 0)

class SystemInstanceZephyr:
    def __init__(self, sys, board, app, tc, cfg):
        self.sys = sys
        self.board = board
        self.app = app
        self.tc = tc
        self.cfg = cfg
        self.spec = getSpec(self.sys.data['zephyr'], 'application', self.app)
        self.systemdir = os.getcwd()
        if (sys.mode == 'system-single'):
            self.builddir = self.sys.args.directory
            self.installdir = os.path.join(self.systemdir,
                                           self.sys.args.directory,
                                           self.spec['install-dir'])
        else:
            self.builddir = os.path.join(self.sys.args.directory, 'zephyr',
                                        self.board, self.tc, self.app, self.cfg)
            self.installdir = os.path.join(self.systemdir,
                                        self.sys.args.directory,
                                        self.spec['install-dir'],
                                        self.board, self.tc, self.app, self.cfg)
        self.sys.stats.systemZephyr(app, tc, board, cfg, self.spec['build-tool'])

    def configure(self):
        kernel = expandFile(self.spec['zephyr-kernel'])
        build = findZephyrBuild(self.spec['build'], self.tc, self.board)
        # TODO: build should inherit from spec, and we should use build
        #       everywhere after that.
        if (not 'modules' in build):
            build['modules'] = [ ]
        tcSpec = findZephyrToolchain(build, self.tc)
        #mmh.pp(spec)
        #mmh.pp(build)

        cmd = cmake([
            cmakeBuildtool(self.sys.log, self.spec['build-tool']),
            cmakeSourceDir('.'),
            cmakeBinaryDir(self.builddir),
            cmakeParam('CMAKE_BUILD_TYPE', self.cfg),
            cmakeParam('CMAKE_INSTALL_PREFIX', self.installdir),
            cmakeParam('CMAKE_EXPORT_COMPILE_COMMANDS', 'on'),
            cmakeParam('BOARD', self.board),
            zephyrToolchain(tcSpec),
            cmakeParam('ZEPHYR_MODULES',
                       genZephyrModules(self.spec['zephyr-module-path'],
                                        build['modules'])),
            cmakeParam('OVERLAY_CONFIG',
                       [ findZephyrTransformer(self.spec['ufw'], self.cfg) ]
                       + self.spec['kconfig']),
            cmakeParam('UFW_ZEPHYR_KERNEL', kernel),
            cmakeParam('UFW_ZEPHYR_APPLICATION', expandFile(self.spec['source'])),
            cmakeParam('UFW_LOAD_BUILD_SYSTEM',
                       expandFile(self.spec['build-system']))])

        if (self.sys.args.cmake != None):
            cmd.extend(self.sys.args.cmake)

        rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd)
        self.sys.stats.logConfigure(rc)
        return (rc == 0)

class SystemInstance:
    def __init__(self, sys, description):
        self.sys = sys
        self.desc = description
        if (description.startswith("zephyr/")):
            try:
                (self.kind,
                 self.board,
                 self.app,
                 self.tc,
                 self.cfg) = description.split('/')
            except Exception:
                raise(InvalidSystemInstance(description))

            self.instance = SystemInstanceZephyr(
                self.sys, self.board, self.app, self.tc, self.cfg)
        elif (description.startswith("boards/")):
            self.app = None
            try:
                (self.kind,
                 self.board,
                 self.tc,
                 self.cfg) = description.split('/')
            except Exception:
                raise(InvalidSystemInstance(description))

            self.instance = SystemInstanceBoard(
                self.sys, self.board, self.tc, self.cfg)
        else:
            raise(InvalidSystemInstance(description))

    def kind(self):
        return self.kind

    def configure(self):
        self.sys.log.info('Configuring system instance: {}'.format(self.desc))
        return self.instance.configure()

    def compile(self):
        self.sys.log.info('Compiling system instance: {}'.format(self.desc))
        cmd = cmake(['--build', self.instance.builddir ])
        rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd)
        self.sys.stats.logBuild(rc)
        return (rc == 0)

    def test(self):
        txt = subprocess.check_output([
            'ctest', '--show-only', '--test-dir', self.instance.builddir])
        last = txt.splitlines()[-1]
        num = int(last.decode().split(' ')[-1])
        if (num > 0):
            self.sys.log.info('Testing system instance: {}'.format(self.desc))
            cmd = [ 'ctest', '--test-dir', self.instance.builddir ]
            rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd)
            self.sys.stats.logTestsuite(num, rc)
            return (rc == 0)
        return True

    def install(self):
        self.sys.log.info('Installing system instance: {}'.format(self.desc))
        cmd = cmake([ '--install', '.' ])
        olddir = os.getcwd()
        os.chdir(self.instance.builddir)
        rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd)
        os.chdir(olddir)
        self.sys.stats.logInstall(rc)
        return (rc == 0)

    def clean(self):
        self.sys.log.info('Cleaning system instance: {}'.format(self.desc))
        cmd = cmake([ '--build', self.instance.builddir, '--target', 'clean' ])
        rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd)
        return (rc == 0)

    def build(self):
        return (self.configure() and
                self.compile()   and
                self.test()      and
                self.install())

    def rebuild(self):
        return (self.compile()   and
                self.test()      and
                self.install())

class System:
    def __init__(self, log, version, cfg, args):
        self.stats = cut.ExecutionStatistics(cfg, log)
        self.stats.checkpoint('system-initialisation')
        self.version = version
        self.log = log
        self.cfg = cfg
        self.args = args
        self.spec = 'system.yaml'
        self.singleInstance = None
        if (args.single_instance == None):
            self.mode = None
        elif (args.single_instance):
            n = len(args.instances)
            if (n == 1):
                self.singleInstance = args.instances[0]
            elif ((n > 1) or (n == 0 and not os.path.exists(args.directory))):
                log.error(
                    'system: --single-instance requires exactly one instance. {} specified.'
                    .format(n))
                exit(1)
            self.mode = 'system-single'
        else:
            self.mode = 'system-multi'

    def setupDirectory(self):
        d = self.args.directory
        if (os.path.exists(d)):
            self.log.info('Build directory {} exists: Examining...'.format(d))
            state = os.path.join(d, 'MakeMeHappy.yaml')
            if (os.path.exists(state)):
                data = mmh.load(state)
                if (self.mode == None):
                    self.mode = data['mode']
                    self.log.info('Using mode from state: {}'.format(self.mode))
                elif (data['mode'] != self.mode):
                    self.log.error(
                        'Build directory {} uses {} mode; Current mode: {}'
                        .format(d, data['mode'], self.mode))
                    exit(1)
                else:
                    self.log.info('Build tree matching current mode: {}. Good!'
                                  .format(self.mode))
                if (self.mode == 'system-single'):
                    if (self.singleInstance == None):
                        self.singleInstance = data['single-instance']
                    elif (data['single-instance'] != self.singleInstance):
                        self.log.error(
                            'Single-instance build tree {} set up for {}. Specified {}.'
                            .format(self.args.directory,
                                    data['single-instance'],
                                    self.singleInstance))
                        exit(1)
            else:
                self.log.error('Failed to load build state from {}'.format(state))
                exit(1)
        else:
            os.mkdir(d)
            data = { 'mode'    : self.mode,
                     'version' : self.version }
            if (self.singleInstance != None):
                data['single-instance'] = self.singleInstance
            state = os.path.join(d, 'MakeMeHappy.yaml')
            mmh.dump(state, data)

    def load(self):
        self.log.info("Loading system specification: {}".format(self.spec))
        self.data = mmh.load(self.spec)
        fillData(self.data)
        self.instances = makeInstances(self.data)

    def newInstance(self, desc):
        return SystemInstance(self, desc)

    def showStats(self):
        self.stats.checkpoint('finish')
        self.stats.renderStatistics()
        if self.stats.wasSuccessful():
            self.log.info('All {} builds succeeded.'.format(
                self.stats.countBuilds()))
            exit(0)
        else:
            self.log.info('{} build(s) out of {} failed.'
                          .format(self.stats.countFailed(),
                                  self.stats.countBuilds()))
            exit(1)

    def buildInstances(self, instances):
        for i in instances:
            self.log.info("  - {}".format(i))
        for instance in instances:
            if (instance in self.instances):
                sys = self.newInstance(instance)
                sys.build()
            else:
                self.log.error("Unknown instance: {}", instance)
                return False
        return True

    def rebuildInstances(self, instances):
        for i in instances:
            self.log.info("  - {}".format(i))
        for instance in instances:
            if (instance in self.instances):
                sys = self.newInstance(instance)
                sys.rebuild()
            else:
                self.log.error("Unknown instance: {}", instance)
                return False
        return True

    def cleanInstances(self, instances):
        for v in instances:
            self.log.info("  - {}".format(v))
        for instance in instances:
            if (instance in self.instances):
                sys = self.newInstance(instance)
                sys.clean()
            else:
                self.log.error("Unknown instance: {}", instance)
                return False
        return True

    def build(self):
        self.setupDirectory()
        if (self.singleInstance != None):
            self.log.info("Building single system instance:")
            self.buildInstances([ self.singleInstance ])
        elif (len(self.args.instances) == 0):
            self.log.info("Building full system:")
            self.buildInstances(self.instances)
        else:
            self.log.info("Building selected instance(s):")
            self.buildInstances(self.args.instances)
        self.showStats()

    def rebuild(self):
        self.setupDirectory()
        if (self.singleInstance != None):
            self.log.info("Re-Building single system instance:")
            self.rebuildInstances([ self.singleInstance ])
        elif (len(self.args.instances) == 0):
            self.log.info("Re-Building full system:")
            self.rebuildInstances(self.instances)
        else:
            self.log.info("Re-Building selected instance(s):")
            self.rebuildInstances(self.args.instances)
        # The stats code doesn't work if the parts to a build don't match what
        # it expects. So we'll need to fix that.
        #self.showStats()

    def clean(self):
        self.setupDirectory()
        if (self.singleInstance != None):
            self.log.info("Cleaning single system instance:")
            self.cleanInstances([ self.singleInstance ])
        elif (len(self.args.instances) == 0):
            self.log.info("Cleaning up full system:")
            self.cleanInstances(self.instances)
        else:
            self.log.info("Cleaning selected instance(s):")
            self.cleanInstances(self.args.instances)

    def listInstances(self):
        self.log.info("Generating list of all system build instances:")
        for v in self.instances:
            print(v)
