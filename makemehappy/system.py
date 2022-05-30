import copy
import os

import makemehappy.utilities as mmh
import makemehappy.cut as cut
import makemehappy.cmake as c
import makemehappy.zephyr as z

defaults = { 'build-configs'      : [ 'debug', 'release' ],
             'build-system'       : None,
             'build-tool'         : 'ninja',
             'install-dir'        : 'artifacts',
             'ufw'                : '${system}/libraries/ufw',
             'kconfig'            : [ ],
             'zephyr-kernel'      : '${system}/zephyr/kernel',
             'zephyr-module-path' : [ '${system}/zephyr/modules' ],
             'zephyr-template'    : 'applications/${application}' }

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

def getSpec(data, key, name):
    for d in data:
        if (name == d[key]):
            return d
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
        self.sys.stats.systemBoard(tc, board, cfg, self.spec['build-tool'])

    def configure(self):
        cmd = c.configureBoard(
            log         = self.sys.log,
            args        = self.sys.args.cmake,
            ufw         = self.spec['ufw'],
            board       = self.board,
            buildconfig = self.cfg,
            toolchain   = self.tc,
            sourcedir   = '.',
            builddir    = self.builddir,
            installdir  = self.installdir,
            buildtool   = self.spec['build-tool'],
            buildsystem = self.spec['build-system'])

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
                                        self.board, self.app, self.tc, self.cfg)
            self.installdir = os.path.join(self.systemdir,
                                        self.sys.args.directory,
                                        self.spec['install-dir'],
                                        self.board, self.tc, self.app, self.cfg)
        self.sys.stats.systemZephyr(app, tc, board, cfg, self.spec['build-tool'])

    def configure(self):
        build = z.findBuild(self.spec['build'], self.tc, self.board)

        tmp = copy.deepcopy(self.spec)
        tmp.pop('build', None)
        build = { **build, **tmp }
        if ('base-modules' in build):
            build['modules'].extend(build['base-modules'])
        if (not 'modules' in build):
            build['modules'] = [ ]

        cmd = c.configureZephyr(
            log         = self.sys.log,
            args        = self.sys.args.cmake,
            ufw         = build['ufw'],
            board       = self.board,
            buildconfig = self.cfg,
            toolchain   = z.findToolchain(build, self.tc),
            sourcedir   = '.',
            builddir    = self.builddir,
            installdir  = self.installdir,
            buildtool   = build['build-tool'],
            buildsystem = build['build-system'],
            appsource   = build['source'],
            kernel      = build['zephyr-kernel'],
            kconfig     = build['kconfig'],
            modulepath  = build['zephyr-module-path'],
            modules     = build['modules'])

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
        cmd = c.cmake(['--build', self.instance.builddir ])
        rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd)
        self.sys.stats.logBuild(rc)
        return (rc == 0)

    def test(self):
        num = c.countTests(self.instance.builddir)
        if (num > 0):
            self.sys.log.info('Testing system instance: {}'.format(self.desc))
            cmd = c.test(self.instance.builddir)
            rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd)
            self.sys.stats.logTestsuite(num, rc)
            return (rc == 0)
        return True

    def install(self):
        self.sys.log.info('Installing system instance: {}'.format(self.desc))
        cmd = c.install()
        olddir = os.getcwd()
        self.sys.log.info(
            'Changing to directory {}.'.format(self.instance.builddir))
        os.chdir(self.instance.builddir)
        rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd)
        self.sys.log.info('Changing back to directory {}.'.format(olddir))
        os.chdir(olddir)
        self.sys.stats.logInstall(rc)
        return (rc == 0)

    def clean(self):
        self.sys.log.info('Cleaning system instance: {}'.format(self.desc))
        cmd = c.clean(self.instance.builddir)
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
                if (self.args.force == True):
                    data['version'] = self.version
                    mmh.dump(state, data)
                if (mmh.matchingVersion(self.version, data) == False):
                    fv = None
                    if (not data is None and 'version' in data):
                        fv = data['version']
                    self.log.error("{}: Version mismatch: {} != {}".format(state, self.version, fv))
                    self.log.error("If suitable ‘--force’ to force using the file!")
                    exit(1)
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
                elif (self.mode == 'system-multi'):
                    if ('instances' in data):
                        if (self.args.all_instances):
                            self.log.info('Force selection of all instances.')
                            data.pop('instances', None)
                            self.args.instances = []
                            mmh.dump(state, data)
                        elif (len(self.args.instances) == 0):
                            self.log.info('Using system instances from state file.')
                            self.args.instances = data['instances']
                        elif (self.args.instances != data['instances']):
                            self.log.info('Updating system instances from command line.')
                            data['instances'] = self.args.instances
                            mmh.dump(state, data)
                        else:
                            self.log.info('Command line instances match state file.')
                    elif (len(self.args.instances) > 0):
                        self.log.info('Adding system instances from command line.')
                        data['instances'] = self.args.instances
                        mmh.dump(state, data)
            else:
                self.log.error('Failed to load build state from {}'.format(state))
                exit(1)
        else:
            os.mkdir(d)
            if (self.mode == None):
                self.mode = 'system-multi'
            data = { 'mode'    : self.mode,
                     'version' : self.version }
            if (self.mode == 'system-multi' and len(self.args.instances) > 0):
                data['instances'] = self.args.instances
            if (self.singleInstance != None):
                data['single-instance'] = self.singleInstance
            state = os.path.join(d, 'MakeMeHappy.yaml')
            self.log.info('Creating build directory state file')
            mmh.dump(state, data)

    def load(self):
        self.log.info("Loading system specification: {}".format(self.spec))
        self.data = mmh.load(self.spec)
        fillData(self.data)
        self.instances = makeInstances(self.data)
        self.args.instances = mmh.patternsToList(self.instances,
                                                 self.args.instances)
        if (len(self.args.instances) > 0):
            error = False
            for instance in self.args.instances:
                if (not instance in self.instances):
                    self.log.error("Unknown instance: {}", instance)
                    error = True
            if (error):
                exit(1)

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
            sys = self.newInstance(instance)
            sys.build()
        return True

    def rebuildInstances(self, instances):
        for i in instances:
            self.log.info("  - {}".format(i))
        for instance in instances:
            sys = self.newInstance(instance)
            sys.rebuild()
        return True

    def cleanInstances(self, instances):
        for v in instances:
            self.log.info("  - {}".format(v))
        for instance in instances:
            sys = self.newInstance(instance)
            sys.clean()
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
        self.showStats()

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

    def makeDBLink(self):
        d = self.args.directory
        if (os.path.exists(d)):
            self.setupDirectory()

        n = len(self.args.instances)
        if (n != 1 and not (n == 0 and self.singleInstance != None)):
            self.log.error('The db sub-command requires exactly one argument')
            exit(1)

        name = 'compile_commands.json'

        if (self.singleInstance != None):
            instance = self.singleInstance
            target = os.path.join(d, name)
        else:
            instance = self.args.instances[0]
            target = os.path.join(d, instance, name)

        self.log.info('Creating symbolic link to {} for {}', name, instance)

        if (os.path.exists(name)):
            os.remove(name)

        os.symlink(target, name)
