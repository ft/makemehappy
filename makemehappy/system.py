import copy
import os

import makemehappy.utilities as mmh
import makemehappy.cut as cut
import makemehappy.cmake as c
import makemehappy.combination as comb
import makemehappy.hooks as h
import makemehappy.manifest as m
import makemehappy.zephyr as z

from pathlib import Path

defaults = { 'build-configs'      : [ 'debug', 'release' ],
             'build-system'       : None,
             'build-tool'         : 'ninja',
             'environment'        : {},
             'install'            : True,
             'install-dir'        : 'artifacts',
             'ufw'                : '${system}/libraries/ufw',
             'dtc-overlays'       : [ ],
             'kconfig'            : [ ],
             'variables'          : {},
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
    # If something is a dict in "defaults", we merge upwards through defaults,
    # common and the final thing. This allows specifying general things for
    # everything with extending and overriding the way down. You cannot remove
    # things down the stack, of course.
    if (key in defaults and isinstance(defaults[key], dict)):
        if (not key in thing):
            thing[key] = {}

        if (key in common):
            thing[key] = { **common[key], **thing[key] }

        thing[key] = { **defaults[key], **thing[key] }
        return

    # Other values pick from common or defaults, in that order whichever one
    # has a value first.
    if (not key in thing):
        if (key in common):
            thing[key] = common[key]
        else:
            thing[key] = defaults[key]

def fill(thing, common):
    for key in defaults:
        maybeCopy(thing, common, key)

def fillData(data):
    if ('common' not in data):
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

class InvalidArguments(Exception):
    pass

class InvalidBuildTree(Exception):
    pass

class InvalidPathExtension(Exception):
    pass

class InvalidSystemInstance(Exception):
    pass

class InvalidBuildSpec(Exception):
    pass

class SystemFailedSomeBuilds(Exception):
    pass

def gotConfigureStamp(d):
    f = Path(d) / '.mmh-configure-stamp'
    return f.exists()

def removeConfigureStamp(d):
    root = Path(d)
    if root.is_dir() == False:
        return
    f = root / '.mmh-configure-stamp'
    if f.exists():
        f.unlink()

def touchConfigureStamp(d):
    f = Path(d) / '.mmh-configure-stamp'
    f.touch(mode = 0o666, exist_ok = True)

class SystemInstanceBoard:
    def __init__(self, sys, board, tc, cfg):
        self.sys = sys
        self.board = board
        self.tc = tc
        self.cfg = cfg
        self.spec = getSpec(self.sys.data['boards'], 'name', self.board)
        self.systemdir = os.getcwd()
        self.env = None
        if ('environment' in self.spec):
            self.env = mmh.makeEnvironment(self.sys.log,
                                           self.sys.args.environment_overrides,
                                           self.spec['environment'])
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
        cargs = c.makeParamsFromDict(self.spec['variables'])
        if (self.sys.args.cmake != None):
            cargs += self.sys.args.cmake

        cmd = c.configureBoard(
            log         = self.sys.log,
            args        = cargs,
            ufw         = self.spec['ufw'],
            board       = self.board,
            buildconfig = self.cfg,
            toolchain   = self.tc,
            sourcedir   = '.',
            builddir    = self.builddir,
            installdir  = self.installdir,
            buildtool   = self.spec['build-tool'],
            buildsystem = self.spec['build-system'])

        removeConfigureStamp(self.builddir)
        rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd, self.env)
        if (rc == 0):
            touchConfigureStamp(self.builddir)
        self.sys.stats.logConfigure(rc)
        return (rc == 0)

class SystemInstanceZephyr:
    def __init__(self, sys, board, app, tc, cfg):
        self.sys = sys
        self.board = board
        self.zephyr_board = self.sys.matchZephyrAlias(board)
        self.app = app
        self.tc = tc
        self.cfg = cfg
        self.spec = getSpec(self.sys.data['zephyr'], 'application', self.app)
        self.systemdir = os.getcwd()
        self.env = None
        if ('environment' in self.spec):
            self.env = mmh.makeEnvironment(self.sys.log,
                                           self.sys.args.environment_overrides,
                                           self.spec['environment'])
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
        self.sys.stats.systemZephyr(app, tc, self.zephyr_board, cfg, self.spec['build-tool'])

    def configure(self):
        build = z.findBuild(self.spec['build'], self.tc,
                            self.board)

        tmp = copy.deepcopy(self.spec)
        tmp.pop('build', None)
        build = { **build, **tmp }
        if ('base-modules' in build):
            build['modules'].extend(build['base-modules'])
        if (not 'modules' in build):
            build['modules'] = [ ]

        cargs = c.makeParamsFromDict(self.spec['variables'])
        if (self.sys.args.cmake != None):
            cargs += self.sys.args.cmake

        cmd = c.configureZephyr(
            log         = self.sys.log,
            args        = cargs,
            ufw         = build['ufw'],
            zephyr_board= self.zephyr_board,
            buildconfig = self.cfg,
            toolchain   = z.findToolchain(build, self.tc),
            sourcedir   = '.',
            builddir    = self.builddir,
            installdir  = self.installdir,
            buildtool   = build['build-tool'],
            buildsystem = build['build-system'],
            appsource   = build['source'],
            kernel      = build['zephyr-kernel'],
            dtc         = build['dtc-overlays'],
            kconfig     = build['kconfig'],
            modulepath  = build['zephyr-module-path'],
            modules     = build['modules'])

        removeConfigureStamp(self.builddir)
        rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd, self.env)
        if (rc == 0):
            touchConfigureStamp(self.builddir)
        self.sys.stats.logConfigure(rc)
        return (rc == 0)

class SystemInstance:
    def __init__(self, sys, description):
        self.sys = sys
        self.desc = description
        self.success = False
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
        h.phase_hook('pre/configure', log = self.sys.log, args = self.sys.args,
                     cfg = self.sys.cfg, data = self.sys.data)
        success = mmh.maybeShowPhase(self.sys.log, 'configure', self.desc,
                                     self.sys.args, self.instance.configure)
        h.phase_hook('post/configure', log = self.sys.log,
                     args = self.sys.args, cfg = self.sys.cfg,
                     data = self.sys.data, success = success)
        return success

    def compile(self):
        self.sys.log.info('Compiling system instance: {}'.format(self.desc))
        def rest():
            cmd = c.cmake(['--build', self.instance.builddir ])
            rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd,
                                   self.instance.env)
            self.sys.stats.logBuild(rc)
            return (rc == 0)
        h.phase_hook('pre/compile', log = self.sys.log, args = self.sys.args,
                     cfg = self.sys.cfg, data = self.sys.data)
        success = mmh.maybeShowPhase(self.sys.log, 'compile', self.desc,
                                     self.sys.args, rest)
        h.phase_hook('post/compile', log = self.sys.log, args = self.sys.args,
                     cfg = self.sys.cfg, data = self.sys.data,
                     success = success)
        return success

    def test(self):
        num = c.countTests(self.instance.builddir)
        if (num > 0):
            self.sys.log.info('Testing system instance: {}'.format(self.desc))
            def rest():
                cmd = c.test(self.instance.builddir)
                rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd,
                                       self.instance.env)
                self.sys.stats.logTestsuite(num, rc)
                return (rc == 0)
            h.phase_hook('pre/test', log = self.sys.log,
                         args = self.sys.args, cfg = self.sys.cfg,
                         data = self.sys.data)
            success = mmh.maybeShowPhase(self.sys.log, 'test', self.desc,
                                         self.sys.args, rest)
            h.phase_hook('post/test', log = self.sys.log,
                         args = self.sys.args, cfg = self.sys.cfg,
                         data = self.sys.data, success = success)
            return success
        return True

    def install(self):
        self.sys.log.info('Installing system instance: {}'.format(self.desc))
        def rest():
            olddir = os.getcwd()
            self.sys.log.info(
                'Changing to directory {}.'.format(self.instance.builddir))
            os.chdir(self.instance.builddir)
            rc = 0
            for component in mmh.get_install_components(
                    self.sys.log, self.instance.spec['install']):
                cmd = c.install(component = component)
                rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd,
                                       self.instance.env)
                if (rc != 0):
                    break
            self.sys.log.info('Changing back to directory {}.'.format(olddir))
            os.chdir(olddir)
            self.sys.stats.logInstall(rc)
            return (rc == 0)
        if self.instance.spec['install'] == False:
            self.sys.log.info('System installation disabled')
            return True
        h.phase_hook('pre/install', log = self.sys.log, args = self.sys.args,
                     cfg = self.sys.cfg, data = self.sys.data)
        success = mmh.maybeShowPhase(self.sys.log, 'install', self.desc,
                                     self.sys.args, rest)
        h.phase_hook('post/install', log = self.sys.log, args = self.sys.args,
                     cfg = self.sys.cfg, data = self.sys.data)
        return success

    def clean(self):
        self.sys.log.info('Cleaning system instance: {}'.format(self.desc))
        def rest():
            cmd = c.clean(self.instance.builddir)
            rc = mmh.loggedProcess(self.sys.cfg, self.sys.log, cmd,
                                   self.instance.env)
            return (rc == 0)
        h.phase_hook('pre/clean', log = self.sys.log, args = self.sys.args,
                     cfg = self.sys.cfg, data = self.sys.data)
        success = mmh.maybeShowPhase(self.sys.log, 'clean', self.desc,
                                     self.sys.args, rest)
        h.phase_hook('post/clean', log = self.sys.log, args = self.sys.args,
                     cfg = self.sys.cfg, data = self.sys.data)
        return success

    def build(self):
        if (not self.sys.args.force_build and
           gotConfigureStamp(self.instance.builddir)):
            return self.rebuild()
        self.success = (self.configure() and
                        self.compile()   and
                        self.test()      and
                        self.install())
        return self.success

    def rebuild(self):
        self.success = (self.compile()   and
                        self.test()      and
                        self.install())
        return self.success

    def succeeded(self):
        return self.success

class System:
    def __init__(self, log, version, cfg, args, combinations):
        self.stats = cut.ExecutionStatistics(cfg, log)
        self.stats.checkpoint('system-initialisation')
        self.active_combinations = []
        self.version = version
        self.log = log
        self.cfg = cfg
        self.args = args
        self.spec = args.system_spec
        self.combinations = combinations
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
                raise(InvalidBuildTree())
            self.mode = 'system-single'
        else:
            self.mode = 'system-multi'

        def combinationEntry(c):
            log.info(f'Combination: {c}')
            mmh.nextInstance()
            if (args.log_to_file and args.show_phases):
                string = mmh.extendPhasesNote(f'combination/{c}')
                print(string, flush = True)

        def combinationFinish(c, result):
            if result is not None:
                log.info(f'Combination: {c} {result}')
            if (args.log_to_file and args.show_phases and result is not None):
                string = mmh.extendPhasesNote(f'combination/{c} ...{result}')
                print(string, flush = True)

        self.combinations.setCallbacks(combinationEntry, combinationFinish)
        self.combinations.setStats(self.stats)

    def buildRoot(self):
        return self.args.directory

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
                    raise(InvalidBuildTree())
                if (self.mode == None):
                    self.mode = data['mode']
                    self.log.info('Using mode from state: {}'.format(self.mode))
                elif (data['mode'] != self.mode):
                    self.log.error(
                        'Build directory {} uses {} mode; Current mode: {}'
                        .format(d, data['mode'], self.mode))
                    raise(InvalidBuildTree())
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
                        raise(InvalidBuildTree())
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
                raise(InvalidBuildTree())
        else:
            os.makedirs(d, mode=0o755, exist_ok=True)
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
        self.zephyr_aliases = z.generateZephyrAliases(self.data)
        if ('evaluate' in self.data):
            mmh.loadPython(self.log, self.data['evaluate'],
                           { 'system_instances': self.instances,
                             'build_prefix':     self.buildRoot(),
                             'logging':          self.log})

        ics = mmh.patternsToList(self.instances +
                                 self.combinations.listNames(),
                                 self.args.instances)
        error = False
        lst = []
        prefix = 'combination/'
        offset = len(prefix)
        self.active_combinations = list(
            filter(lambda x: x.startswith('combination/'), ics))
        self.args.instances = list(
            filter(lambda x: x.startswith('combination/') == False, ics))

        for combination in self.active_combinations:
            name = combination[offset:]
            if name not in self.combinations.combinations:
                self.log.error("Unknown combination: {}", instance)
                error = True
            else:
                for p in self.combinations.combinations[name].parents:
                    if p not in lst:
                        lst.append(p)

        lst.extend(self.args.instances)
        for instance in lst:
            if (instance not in self.instances):
                self.log.error("Unknown instance: {}", instance)
                error = True

        if (error):
            raise InvalidSystemSpec()

        self.args.instances = list(set(lst))
        self.args.instances.sort()

        if ('evaluate' in self.data):
            h.startup_hook(cfg = self.cfg, data = self.data)

    def newInstance(self, desc):
        return SystemInstance(self, desc)

    def showStats(self):
        self.stats.checkpoint('finish')
        self.stats.renderStatistics()
        if self.stats.wasSuccessful():
            self.log.info('All {} builds succeeded.'.format(
                self.stats.countBuilds()))
        else:
            self.log.info('{} build(s) out of {} failed.'
                          .format(self.stats.countFailed(),
                                  self.stats.countBuilds()))
            raise(SystemFailedSomeBuilds())

    def matchZephyrAlias(self, name):
        return self.zephyr_aliases.get(name, name)

    def _builder(self, fnc, instances):
        for i in instances:
            self.log.info("    {}".format(i))
        cn = 0
        if not self.args.no_combinations:
            cn = self.combinations.countPossible(instances)
        mmh.expectedInstances(len(instances) + cn)
        for instance in instances:
            mmh.nextInstance()
            sys = self.newInstance(instance)
            f = getattr(sys, fnc)
            f()
            if not self.args.no_combinations:
                self.combinations.addParent(instance, self.buildRoot(), sys)
                self.combinations.execute()
        return True

    def rebuildInstances(self, instances):
        self._builder('rebuild', instances)

    def buildInstances(self, instances):
        self._builder('build', instances)

    def cleanInstances(self, instances):
        for v in instances:
            self.log.info("    {}".format(v))
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

    def cmdCombinations(self):
        return comb.combinationTool(self.buildRoot(), self.log, self.args)

    def deploy(self):
        m.manifest.prefix(self.args.destination)

        if ('manifest' in self.data):
            mmh.loadPython(self.log, self.data['manifest'],
                           { 'system_instances': self.instances,
                             'build_prefix'    : self.buildRoot(),
                             'logging'         : self.log })
        else:
            print('deploy: No manifest specified!')
            self.log.error('deploy: No manifest specified!')
            return False

        m.manifest.withSpecification(self.data['manifest'])
        m.manifest.validate()
        final = m.manifest.final()

        if (self.args.show):
            spec = m.manifest.listSpec()
            if spec is None:
                print('Manifest yielded empty spec.')
                return True
            for line in spec:
                print(line)
            print(f'Deployment into: {final}')
            return True

        self.setupDirectory()
        m.manifest.collect(self.log)

        if (self.args.listCollection):
            col = m.manifest.listCollection()
            if col is None:
                print('Manifest yielded empty file collection.')
                return True
            for line in col:
                print(line)
            print(f'Deployment into: {final}')
            return True

        uniquenessviolations = m.manifest.uniquenessViolations()
        if len(uniquenessviolations) > 0:
            self.log.error(f'{len(uniquenessviolations)} uniqueness ' +
                           'violation(s) in manifest!')
            for uv in uniquenessviolations:
                self.log.error(str(uv) + ':')
                for s in uv.strlist():
                    self.log.error(' - ' + s)
            return False

        issues = m.manifest.issues()
        if len(issues) > 0:
            printi = self.log.error if self.args.strict else self.log.warn
            printi(f'Found {len(issues)} issue(s) in manifest.')
            for issue in issues:
                printi('  - ' + str(issue))
            if self.args.strict:
                printi('All issues considered errors with --strict.')
                return False

        title = f'Deploying into {final}'

        try:
            finalExists = m.manifest.destinationExists()
        except FileExistsError:
            print('Destination exists, but is not a directory!')
            print(f'Pathname: {final}')
            return False

        self.log.info(title)
        print(title)

        if finalExists and not self.args.keep:
            print(f'Removing existing destination directory!')
            m.manifest.removeDestination()

        errors = m.manifest.deploy(self.args.verbose,
                                   self.args.raise_exceptions)
        errorsn = len(errors)
        if errorsn == 0:
            return True

        print(f'{errorsn} errors while deploying. Please check:')
        for error in errors:
            if isinstance(error, str):
                print('  ' + error)
                continue
            msg = error.msg()
            if isinstance(msg, list):
                for line in msg:
                    print(' ', line)
            else:
                print(' ', msg)

        return False

    def listInstances(self):
        self.log.info("Generating list of all system build instances:")
        for v in self.instances:
            print(v)
        for c in self.combinations.listCombinations():
            print(f'combination/{c}')

    def makeDBLink(self):
        d = self.args.directory
        if (os.path.exists(d)):
            self.setupDirectory()

        n = len(self.args.instances)
        if (n != 1 and not (n == 0 and self.singleInstance != None)):
            self.log.error('The db sub-command requires exactly one argument')
            raise(InvalidArguments())

        name = 'compile_commands.json'

        if (self.singleInstance != None):
            instance = self.singleInstance
            target = os.path.join(d, name)
        else:
            instance = self.args.instances[0]
            target = os.path.join(d, instance, name)

        loc = self.args.location
        self.log.info('Creating symbolic link to {} for {} (location: {})',
                        name, instance, loc)
        link = os.path.join(self.args.location, name)
        target = os.path.relpath(target, loc)

        if (os.path.exists(link) or os.path.islink(link)):
            os.remove(link)

        os.symlink(target, link)
