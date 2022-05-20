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


def makeZephyrVariants(zephyr):
    variants = []
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
                    variants.extend(['zephyr/{}/{}/{}/{}'.format(
                        board, name, tcname, cfg)])
    return variants

def makeBoardVariants(board):
    variants = []
    for cfg in board['build-configs']:
        for tc in board['toolchains']:
            variants.extend(['boards/{}/{}/{}'.format(
                board['name'], tc, cfg)])
    return variants

def makeVariants(data):
    boards = []
    zephyr = []
    if ('zephyr' in data):
        for z in data['zephyr']:
            boards += makeZephyrVariants(z)
    if ('boards' in data):
        for b in data['boards']:
            boards += makeBoardVariants(b)
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

def flatten(lst):
    if (isinstance(lst, list)):
        if (len(lst) == 0):
            return []
        (first, rest) = lst[0], lst[1:]
        return flatten(first) + flatten(rest)
    else:
        return [lst]

def cmake(lst):
    return [ 'cmake' ] + [ x for x in flatten(lst) if x != None ]

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
        self.variants = makeVariants(self.data)

    def buildBoardVariant(self, variant):
        (prefix, board, tc, cfg) = variant.split('/')
        self.stats.systemBoard(tc, board, cfg, 'ninja')
        return (self.configureBoardVariant(variant) and
                self.justbuildBoardVariant(variant) and
                self.installBoardVariant(variant)   and
                self.testBoardVariant(variant))

    def rebuildBoardVariant(self, variant):
        return (self.justbuildBoardVariant(variant) and
                self.installBoardVariant(variant)   and
                self.testBoardVariant(variant))

    def configureBoardVariant(self, variant):
        self.log.info('Configuring system variant: {}'.format(variant))
        (prefix, board, tc, cfg) = variant.split('/')
        curdir = os.getcwd()
        spec = getSpec(self.data['boards'], 'name', board)
        install = os.path.join(curdir,
                               self.args.directory,
                               spec['install-dir'],
                               board, tc, cfg)
        tcfile = os.path.join(expandFile(spec['ufw']),
                              'cmake', 'toolchains',
                              '{}.cmake'.format(tc))
        builddir = os.path.join(self.args.directory, variant)

        cmd = cmake([
            cmakeBuildtool(self.log, spec['build-tool']),
            cmakeSourceDir('.'),
            cmakeBinaryDir(builddir),
            cmakeParam('CMAKE_BUILD_TYPE', cfg),
            cmakeParam('CMAKE_INSTALL_PREFIX', install),
            cmakeParam('CMAKE_EXPORT_COMPILE_COMMANDS', 'on'),
            cmakeParam('CMAKE_TOOLCHAIN_FILE', tcfile),
            cmakeParam('TARGET_BOARD', board),
            cmakeParam('UFW_LOAD_BUILD_SYSTEM',
                       expandFile(spec['build-system']))])

        if (self.args.cmake != None):
            cmd.extend(self.args.cmake)

        rc = mmh.loggedProcess(self.cfg, self.log, cmd)
        return (rc == 0)

    def justbuildBoardVariant(self, variant):
        self.log.info('Building system variant: {}'.format(variant))
        builddir = os.path.join(self.args.directory, variant)
        cmd = [ 'cmake', '--build', builddir ]
        rc = mmh.loggedProcess(self.cfg, self.log, cmd)
        return (rc == 0)

    def installBoardVariant(self, variant):
        self.log.info('Installing system variant: {}'.format(variant))
        builddir = os.path.join(self.args.directory, variant)
        cmd = [ 'cmake', '--install', builddir ]
        rc = mmh.loggedProcess(self.cfg, self.log, cmd)
        return (rc == 0)

    def testBoardVariant(self, variant):
        self.log.info('Testing system variant: {}'.format(variant))
        builddir = os.path.join(self.args.directory, variant)
        cmd = [ 'ctest', '--test-dir', builddir ]
        rc = mmh.loggedProcess(self.cfg, self.log, cmd)
        return (rc == 0)

    def cleanBoardVariant(self, variant):
        self.log.info('Cleaning system variant: {}'.format(variant))
        builddir = os.path.join(self.args.directory, variant)
        cmd = [ 'cmake', '--build', builddir, '--target', 'clean' ]
        rc = mmh.loggedProcess(self.cfg, self.log, cmd)
        return (rc == 0)

    def buildZephyrVariant(self, variant):
        (prefix, board, app, tc, cfg) = variant.split('/')
        self.stats.systemZephyr(app, tc, board, cfg, 'ninja')
        print("DEBUG: ", variant)
        #exit(0)
        self.configureZephyrVariant(variant)
        self.justbuildZephyrVariant(variant)
        self.installZephyrVariant(variant)
        self.testZephyrVariant(variant)

    def rebuildZephyrVariant(self, variant):
        return (self.justbuildZephyrVariant(variant) and
                self.installZephyrVariant(variant)   and
                self.testZephyrVariant(variant))

    def configureZephyrVariant(self, variant):
        self.log.info('Configuring system variant: {}'.format(variant))
        (prefix, board, app, tc, cfg) = variant.split('/')
        curdir = os.getcwd()
        spec = getSpec(self.data['zephyr'], 'application', app)
        install = os.path.join(curdir,
                               self.args.directory,
                               spec['install-dir'],
                               board, tc, app, cfg)
        builddir = os.path.join(self.args.directory, variant)
        kernel = expandFile(spec['zephyr-kernel'])
        build = findZephyrBuild(spec['build'], tc, board)
        # TODO: build should inherit from spec, and we should use build
        #       everywhere after that.
        if (not 'modules' in build):
            build['modules'] = [ ]
        tcSpec = findZephyrToolchain(build, tc)
        #mmh.pp(spec)
        #mmh.pp(build)

        cmd = cmake([
            cmakeBuildtool(self.log, spec['build-tool']),
            cmakeSourceDir('.'),
            cmakeBinaryDir(builddir),
            cmakeParam('CMAKE_BUILD_TYPE', cfg),
            cmakeParam('CMAKE_INSTALL_PREFIX', install),
            cmakeParam('CMAKE_EXPORT_COMPILE_COMMANDS', 'on'),
            cmakeParam('BOARD', board),
            zephyrToolchain(tcSpec),
            cmakeParam('ZEPHYR_MODULES',
                       genZephyrModules(spec['zephyr-module-path'],
                                        build['modules'])),
            cmakeParam('OVERLAY_CONFIG',
                       [ findZephyrTransformer(spec['ufw'], cfg) ]
                       + spec['kconfig']),
            cmakeParam('UFW_ZEPHYR_KERNEL', kernel),
            cmakeParam('UFW_ZEPHYR_APPLICATION', expandFile(spec['source'])),
            cmakeParam('UFW_LOAD_BUILD_SYSTEM',
                       expandFile(spec['build-system']))])

        if (self.args.cmake != None):
            cmd.extend(self.args.cmake)

        rc = mmh.loggedProcess(self.cfg, self.log, cmd)
        return (rc == 0)

    def justbuildZephyrVariant(self, variant):
        self.log.info('Building system variant: {}'.format(variant))
        builddir = os.path.join(self.args.directory, variant)
        cmd = [ 'cmake', '--build', builddir ]
        rc = mmh.loggedProcess(self.cfg, self.log, cmd)
        return (rc == 0)

    def installZephyrVariant(self, variant):
        self.log.info('Installing system variant: {}'.format(variant))
        builddir = os.path.join(self.args.directory, variant)
        olddir = os.getcwd()
        os.chdir(builddir)
        cmd = [ 'cmake', '--install', '.' ]
        rc = mmh.loggedProcess(self.cfg, self.log, cmd)
        os.chdir(olddir)
        return (rc == 0)

    def testZephyrVariant(self, variant):
        self.log.info('Testing system variant: {}'.format(variant))
        builddir = os.path.join(self.args.directory, variant)
        cmd = [ 'ctest', '--test-dir', builddir ]
        rc = mmh.loggedProcess(self.cfg, self.log, cmd)
        return (rc == 0)

    def cleanZephyrVariant(self, variant):
        self.log.info('Cleaning system variant: {}'.format(variant))
        builddir = os.path.join(self.args.directory, variant)
        cmd = [ 'cmake', '--build', builddir, '--target', 'clean' ]
        rc = mmh.loggedProcess(self.cfg, self.log, cmd)
        return (rc == 0)

    def buildVariants(self, variants):
        for v in variants:
            self.log.info("  - {}".format(v))
        for variant in variants:
            if (variant in self.variants):
                if (variant.startswith("zephyr/")):
                    self.buildZephyrVariant(variant)
                elif (variant.startswith("boards/")):
                    self.buildBoardVariant(variant)
                else:
                      self.log.error("Invalid variant: {}", variant)
                      return False
            else:
                self.log.error("Unknown variant: {}", variant)
                return False
        return True

    def rebuildVariants(self, variants):
        for v in variants:
            self.log.info("  - {}".format(v))
        for variant in variants:
            if (variant in self.variants):
                if (variant.startswith("zephyr/")):
                    self.rebuildZephyrVariant(variant)
                elif (variant.startswith("boards/")):
                    self.rebuildBoardVariant(variant)
                else:
                      self.log.error("Invalid variant: {}", variant)
                      return False
            else:
                self.log.error("Unknown variant: {}", variant)
                return False
        return True

    def cleanVariants(self, variants):
        for v in variants:
            self.log.info("  - {}".format(v))
        for variant in variants:
            if (variant in self.variants):
                if (variant.startswith("zephyr/")):
                    self.cleanZephyrVariant(variant)
                elif (variant.startswith("boards/")):
                    self.cleanBoardVariant(variant)
                else:
                      self.log.error("Invalid variant: {}", variant)
                      return False
            else:
                self.log.error("Unknown variant: {}", variant)
                return False
        return True

    def cleanVariants(self, variants):
        for v in variants:
            self.log.info("  - {}".format(v))
        for variant in variants:
            if (variant in self.variants):
                if (variant.startswith("zephyr/")):
                    self.cleanZephyrVariant(variant)
                elif (variant.startswith("boards/")):
                    self.cleanBoardVariant(variant)
                else:
                      self.log.error("Invalid variant: {}", variant)
                      return False
            else:
                self.log.error("Unknown variant: {}", variant)
                return False
        return True

    def build(self, variants):
        if (len(variants) == 0):
            self.log.info("Building full system:")
            self.buildVariants(self.variants)
        else:
            self.log.info("Building selected variant(s):")
            self.buildVariants(variants)
        self.stats.checkpoint('finish')
        self.stats.renderStatistics()
        if self.stats.wasSuccessful():
            self.log.info('All {} builds succeeded.'.format(len(self.variants)))
            exit(0)
        else:
            self.log.info('{} build(s) out of {} failed.'
                          .format('some', len(self.variants)))
            exit(1)

    def rebuild(self, variants):
        if (len(variants) == 0):
            self.log.info("Re-Building full system:")
            return self.rebuildVariants(self.variants)
        else:
            self.log.info("Re-Building selected variant(s):")
            return self.rebuildVariants(variants)

    def clean(self, variants):
        if (len(variants) == 0):
            self.log.info("Cleaning up full system:")
            return self.cleanVariants(self.variants)
        else:
            self.log.info("Cleaning selected variant(s):")
            return self.cleanVariants(variants)

    def listVariants(self):
        self.log.info("Generating list of all system build variants:")
        for v in self.variants:
            print(v)
