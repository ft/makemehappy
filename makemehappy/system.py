import os

import mako.template as mako
import makemehappy.utilities as mmh

defaults = { 'build-configs'   : [ 'debug', 'release' ],
             'build-tool'      : 'ninja',
             'install-dir'     : 'artifacts',
             'ufw'             : '${system}/libraries/ufw',
             'zephyr-template' : 'applications/${application}' }

def cmakeBuildtool(name):
    if (name == 'make'):
        return 'Unix Makefiles'
    if (name == 'ninja'):
        return 'Ninja'
    return 'Unknown Buildtool'

def expandFile(tmpl):
    curdir = os.getcwd()
    exp = mako.Template(tmpl).render(system = curdir)
    return exp

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
    if (not 'common' in data):
        return

    if ('zephyr' in data):
        for z in data['zephyr']:
            fill(z, data['common'])
    if ('boards' in data):
        for b in data['boards']:
            fill(b, data['common'])

def getSpec(data, name):
    for d in data:
        if (name == d['name']):
            return d
    return None

class System:
    def __init__(self, log, cfg, args):
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
        spec = getSpec(self.data['boards'], board)
        install = os.path.join(curdir,
                               self.args.directory,
                               spec['install-dir'],
                               board, tc, cfg)
        tcfile = os.path.join(expandFile(spec['ufw']),
                              'cmake', 'toolchains',
                              '{}.cmake'.format(tc))
        builddir = os.path.join(self.args.directory, variant)
        buildtool = cmakeBuildtool(spec['build-tool'])

        cmd = [ 'cmake',
                '-G{}'.format(buildtool), '-S', '.', '-B', builddir,
                '-DCMAKE_INSTALL_PREFIX={}'.format(install),
                '-DCMAKE_BUILD_TYPE={}'.format(cfg),
                '-DCMAKE_TOOLCHAIN_FILE={}'.format(tcfile),
                '-DTARGET_BOARD={}'.format(board),
                '-DCMAKE_EXPORT_COMPILE_COMMANDS=on' ]

        if ('build-system' in spec):
            cmd.extend([ '-DUFW_LOAD_BUILD_SYSTEM={}'.format(
                expandFile(spec['build-system'])) ])

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
            return self.buildVariants(self.variants)
        else:
            self.log.info("Building selected variant(s):")
            return self.buildVariants(variants)

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
