import os

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
        self.builddir = os.path.join(self.sys.args.directory, 'boards',
                                     self.board, self.tc, self.cfg)
        self.installdir = os.path.join(self.systemdir,
                                       self.sys.args.directory,
                                       self.spec['install-dir'],
                                       self.board, self.tc, self.cfg)
        self.tcfile = os.path.join(expandFile(self.spec['ufw']),
                                   'cmake', 'toolchains',
                                   '{}.cmake'.format(tc))

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
        self.installdir = os.path.join(self.systemdir,
                                       self.sys.args.directory,
                                       self.spec['install-dir'],
                                       self.board, self.tc, self.app, self.cfg)
        self.builddir = os.path.join(self.sys.args.directory, 'zephyr',
                                     self.board, self.tc, self.app, self.cfg)

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
        return (rc == 0)

    def test(self):
        self.sys.log.info('Testing system instance: {}'.format(self.desc))
        cmd = [ 'ctest', '--test-dir', self.instance.builddir ]
        rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd)
        return (rc == 0)

    def install(self):
        self.sys.log.info('Installing system instance: {}'.format(self.desc))
        cmd = cmake([ '--install', '.' ])
        olddir = os.getcwd()
        os.chdir(self.instance.builddir)
        rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd)
        os.chdir(olddir)
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
    def __init__(self, log, cfg, args):
        self.stats = cut.ExecutionStatistics(cfg, log)
        self.stats.checkpoint('system-initialisation')
        self.log = log
        self.cfg = cfg
        self.args = args
        self.spec = 'system.yaml'

    def load(self):
        self.log.info("Loading system specification: {}".format(self.spec))
        self.data = mmh.load(self.spec)
        fillData(self.data)
        self.instances = makeInstances(self.data)

    def newInstance(self, desc):
        return SystemInstance(self, desc)

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

    def build(self, instances):
        if (len(instances) == 0):
            self.log.info("Building full system:")
            self.buildInstances(self.instances)
        else:
            self.log.info("Building selected instance(s):")
            self.buildInstances(instances)
        self.stats.checkpoint('finish')
        self.stats.renderStatistics()
        if self.stats.wasSuccessful():
            self.log.info('All {} builds succeeded.'.format(len(self.instances)))
            exit(0)
        else:
            self.log.info('{} build(s) out of {} failed.'
                          .format('some', len(self.instances)))
            exit(1)

    def rebuild(self, instances):
        if (len(instances) == 0):
            self.log.info("Re-Building full system:")
            return self.rebuildInstances(self.instances)
        else:
            self.log.info("Re-Building selected instance(s):")
            return self.rebuildInstances(instances)

    def clean(self, instances):
        if (len(instances) == 0):
            self.log.info("Cleaning up full system:")
            return self.cleanInstances(self.instances)
        else:
            self.log.info("Cleaning selected instance(s):")
            return self.cleanInstances(instances)

    def listInstances(self):
        self.log.info("Generating list of all system build instances:")
        for v in self.instances:
            print(v)
