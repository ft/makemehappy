import os

from pathlib import Path

import makemehappy.combination as comb
import makemehappy.git         as git
import makemehappy.hooks       as h
import makemehappy.result      as result
import makemehappy.system      as ms
import makemehappy.utilities   as mmh

from makemehappy.cut    import (CodeUnderTest, fetchCheckout, gitCheckout)
from makemehappy.verify import mmh_verify

def findRootDirectory(lst):
    p = Path(os.getcwd())
    p.resolve()
    while True:
        for file in lst:
            if os.path.exists(file):
                print(p)
                return 0
        if p.parent == p:
            break
        os.chdir("..")
        p = Path(os.getcwd())
        p.resolve()
    return 1

class MMHException(Exception):
    pass

class MissingModuleDefinition(MMHException):
    pass

class UnknownSubCommand(MMHException):
    pass

class ProgramExit(MMHException):
    pass

class Program:
    def __init__(self, log, cfg, src, args, version):
        self.log = log
        self.cfg = cfg
        self.src = src
        self.args = args
        self.version = version
        self.cut = None
        self.returnValue = 0
        self.initialised = False
        self.resolvedDependencies = False
        self.environmentDone = False

    def _exit(self, code = None):
        rv = self.returnValue if code is None else code
        h.finish_hook(cmdargs = self.args, exitcode = rv)
        if self.args.succeed:
            raise ProgramExit(0)
        raise ProgramExit(rv)

    def _requireModule(self):
        if os.path.isfile(self.args.module) == False:
            raise MissingModuleDefinition(self.args.module)

    def _adjustConfig(self):
        layer = {}
        adjustments = 0
        self.cfg.merge()
        if self.args.log_all == True:
            layer['log-all'] = not self.cfg.lookup('log-all')
            adjustments = adjustments + 1
        if self.args.log_to_file == True:
            layer['log-to-file'] = not self.cfg.lookup('log-to-file')
            adjustments = adjustments + 1
        if self.args.ignore_dep_errors == True:
            layer['fatal-dependencies'] = not self.cfg.lookup('fatal-dependencies')
            adjustments = adjustments + 1
        if self.args.use_pager == True:
            layer['page-output'] = not self.cfg.lookup('page-output')
            adjustments = adjustments + 1
        if (len(self.args.revision) > 0):
            layer['revision-overrides'] = []
            if ('remove' not in layer):
                layer['remove'] = {}
            for rev in reversed(self.args.revision):
                try:
                    (pat, value) = rev.split('=', 1)
                    if (value == '!main'):
                        new = { 'name': pat, 'use-main-branch': True }
                    elif (value == '!latest'):
                        new = { 'name': pat, 'use-latest-revision': True }
                    elif (m := re.match('^!latest:(.*)', value)):
                        new = { 'name': pat, 'use-latest-revision': True,
                                'use-latest-revision-pattern': m.group(1) }
                    elif (value == '!preserve'):
                        new = { 'name': pat, 'preserve': True }
                    else:
                        new = { 'name': pat, 'revision': value }

                    idx = mmh.findByName(layer['revision-overrides'], pat)
                    if (idx is not None):
                        del layer['revision-overrides'][idx]

                    layer['revision-overrides'].append(new)

                    if ('revision-overrides' not in layer['remove']):
                        layer['remove']['revision-overrides'] = []
                    layer['remove']['revision-overrides'].append(pat)
                except ValueError:
                    log.error("cmdline: Invalid revision-spec: {}"
                              .format(rev))
                    raise e
                adjustments = adjustments + 1
        if adjustments > 0:
            layer['from-cmdline'] = True
            self.cfg.pushLayer(layer)
        self.cfg.merge()

    def _cfg_load(self):
        self.cfg.load()
        self._adjustConfig()

    def _src_load(self):
        self.src.load()
        self.src.merge()

    def _makeCodeUnderTest(self):
        self.cut = CodeUnderTest(self.log,
                                 self.cfg, self.args, self.src,
                                 self.args.module)

    def _setEnvironment(self):
        if self.environmentDone:
            return None
        self.cut.setEnvironment()
        self.environmentDone = True

    def _init(self):
        if self.initialised:
            return None
        self._requireModule()
        self._cfg_load()
        self._makeCodeUnderTest()
        self.cut.initRoot(self.version, self.args)
        self.cut.loadModule()
        if (self.cut.moduleType == 'nobuild'):
            self.log.info("Module type is 'nobuild'. Doing nothing.")
            self._exit(0)
        self.cut.cliAdjust(toolchains    = self.args.toolchains,
                           architectures = self.args.architectures,
                           buildconfigs  = self.args.buildconfigs,
                           buildtools    = self.args.buildtools)
        self.initialised = True

    def _runResult(self):
        self.args.file = [ self.args.log_file ]
        self.args.full_result = False
        self.args.quiet_result = False
        self.args.short_result = True
        self.args.report_incidents = False
        self.args.json_incidents = False
        self.args.grep_result = False
        return result.show(self.cfg, self.args)

    def build_tree_init(self):
        self._init()
        self.cut.populateRoot()
        self.cut.linkIntoRoot()

    def fetch_dependencies(self):
        if self.resolvedDependencies:
            return None
        self._init()
        self.cut.loadSources()
        self.cut.changeToRoot()
        self.cut.loadDependencies()
        self.resolvedDependencies = True

    def generate_toplevel(self):
        self.fetch_dependencies()
        self.cut.generateToplevel()

    def prepare(self):
        self.build_tree_init()
        self.fetch_dependencies()
        self.generate_toplevel()
        self.cut.renderDependencySummary(True)
        if self.cut.dependenciesOkay() == False:
            log.info('Dependency Evaluation contained errors!')
            self._exit(1)

    def run_instance(self):
        self.fetch_dependencies()
        self._setEnvironment()
        self.cut.build()
        self.cut.renderStatistics()
        self.cut.renderDependencySummary(False)

        buildSuccess = self.cut.wasSuccessful()
        depSuccess = self.cut.dependenciesOkay()

        if buildSuccess:
            self.log.info('All {} builds succeeded.'
                          .format(self.cut.countBuilds()))
        else:
            selflog.info('{} build(s) out of {} failed.'
                         .format(self.cut.countFailed(),
                                 self.cut.countBuilds()))

        if depSuccess == False:
            self.log.info('Dependency Evaluation contained errors!')

        resultSuccess = True
        if self.args.log_to_file:
            self.cut.changeToCalldir(quiet = True)
            resultSuccess = self._runResult()

        if not (buildSuccess and depSuccess and resultSuccess):
            self._exit(1)

    def build(self):
        self.prepare()
        self.cut.changeToRoot()
        self.run_instance()

    def show_result(self):
        self._cfg_load()
        if result.show(self.cfg, self.args) == False:
            self._exit(1)

    def list_instances(self):
        if self.args.directory is None:
            print("list-instances only works with -d!")
            self._exit(1)

        if not os.path.exists(self.args.directory):
            print("list-instances called with non-existent build directory")
            print("If the directory is the correct name, you may want to",
                  "prepare it first")
            self._exit(1)

        self._init()

        for inst in self.cut.listInstances():
            print(inst)

    def dump_description(self):
        mmh.pp(mmh.load(self.args.module))

    def focus_instance(self):
        instance = self.args.instance[0]
        linkname = self.args.link_name
        ccj = 'compile_commands.json'
        d = self.args.directory

        if self.args.directory is not None:
            instance = os.path.join(d, 'build', instance)

        ccjTarget = os.path.join(instance, ccj)

        print("\nCreating Focus for Build Instance:")
        if self.args.no_compile_commands == False:
            print(f'  {ccj} -> {ccjTarget}')
            if os.path.islink(ccj):
                os.remove(ccj)
            os.symlink(ccjTarget, ccj)

        print(f'  {linkname} -> {instance}')
        if (os.path.islink(linkname)):
            os.remove(linkname)
        os.symlink(instance, linkname)
        print("")

    def revision_overrides(self):
        self._cfg_load()
        if len(self.args.modules) > 0:
            print("\nEffective revision(s):")
            for mod in self.args.modules:
                rev = self.cfg.processOverrides(mod)
                print(f'  {mod}: {rev}')
            print("")
        else:
            lst = self.cfg.lookup('revision-overrides')
            data = { 'revision-overrides': lst }
            print("")
            mmh.yp(data)
            print("")

    def show_source(self):
        self._src_load()
        names = self.args.modules
        if len(names) == 0:
            names = self.src.allSources()

        for name in names:
            data = self.src.lookup(name)
            print("{}: ".format(name), end = '')
            print(data)

    def download_source(self):
        self._cfg_load()
        self._src_load()

        for module in self.args.modules:
            meta = self.src.lookup(module)
            source = meta['repository']
            cmd = ['git', '-c', 'advice.detachedHead=false', 'clone', '--quiet' ]
            if (self.args.clone_bare):
                cmd.append('--bare')
            cmd += [ source, module ]
            rc = mmh.loggedProcess(self.cfg, self.log, cmd)
            if rc != 0:
                self.log.error('Git clone failed to execute')
                self._exit(1)
            olddir = os.getcwd()
            os.chdir(module)
            fetchCheckout(self.cfg, self.log, module, meta['main'])
            if (self.args.use_release):
                pat = '*'
                if ('release-pattern' in meta):
                    pat = meta['release-pattern']
                tag = git.latestTag('.', pat)
                if tag is None:
                    self.log.error('Unable to find latest release' +
                                   f' tag for module {module}')
                    self._exit(1)

                latest = gitCheckout(self.cfg, self.log, module, tag)
                if latest is None:
                    log.error(f'Error checking out tag {tag}' +
                              ' for module {module}')
                    self._exit(1)
            os.chdir(olddir)

    def download_sources(self):
        destination = self.args.destination
        self._cfg_load()
        self._src_load()
        loaded = {}
        failed = {}
        for source in self.src.data:
            if 'modules' not in source:
                continue
            mmh.expectedInstances(len(source['modules']))
            for module in source['modules']:
                if (module in loaded):
                    self.log.info("Module {} already defined by {}",
                                  module, loaded[module]['source'])
                    continue
                sf = os.path.join(source['root'], source['definition'])
                dd = os.path.join(destination, module)
                repo = source['modules'][module]['repository']
                self.log.info("Downloading module {} from {}...", module, repo)

                def rest():
                    cmd = ['git', '-c', 'advice.detachedHead=false',
                           'clone', '--quiet' ]
                    if (self.args.clone_bare):
                        cmd.append('--bare')
                    cmd += [ repo, dd ]

                    rc = mmh.loggedProcess(self.cfg, self.log, cmd)
                    if (rc == 0):
                        self.log.info("Downloading module {} was successful.",
                                      module)
                    else:
                        self.log.error("Downloading module {} failed!", module)
                        failed[module] = {'source': sf, 'repository': repo }

                    olddir = os.getcwd()
                    os.chdir(module)
                    meta = self.src.lookup(module)
                    revision = fetchCheckout(self.cfg, self.log,
                                             module, meta['main'])
                    os.chdir(olddir)

                    loaded[module] = { 'source':     sf,
                                       'repository': repo,
                                       'revision':   revision}

                    return (rc == 0)

                mmh.nextInstance()
                h.checkpoint_hook('pre/download-source', log = self.log,
                                  args = self.args, module = module)
                rc = mmh.maybeShowPhase(self.log, f'{module}',
                                        'download-sources', self.args, rest)
                h.checkpoint_hook('post/download-source', log = self.log,
                                  args = self.args, module = module,
                                  success = rc)

        for mod in sorted(loaded):
            self.log.info("  Success: {} ({}) from {} [{}]",
                          mod,
                          loaded[mod]['revision'],
                          loaded[mod]['repository'],
                          loaded[mod]['source'])
        if (len(failed) == 0):
            self.log.info("Downloading ALL sources succeeded!")
        else:
            self.log.error("Downloading {} of {} sources failed!",
                           len(failed), len(loaded))
            commandReturnValue = 1
            for fail in sorted(failed):
                self.log.error("  Failure: {} from {} [{}]",
                               fail,
                               failed[fail]['repository'],
                               failed[fail]['source'])

    def system(self):
        if ('system' not in self.args) or (self.args.system is None):
            self.args.system = 'build'

        if self.args.directory is None:
            self.args.directory = 'build'

        if 'no_combinations' not in self.args:
            self.args.no_combinations = False

        if 'instances' not in self.args:
            self.args.instances = [ ]

        if 'force_build' not in self.args:
            self.args.force_build = False

        self._cfg_load()

        if self.args.system == 'com':
            self.args.system = 'combinations'

        ninst = len(self.args.instances)
        if self.args.system == 'combinations' and ninst > 0:
            self.args.combinationspec = self.args.instances
            self.args.instances = []
        else:
            self.args.combinationspec = None

        system = ms.System(self.log, self.version,
                           self.cfg, self.args,
                           comb.combination)
        system.load()

        resultSuccess = True
        if self.args.system == 'build':
            system.build()
            if (self.args.log_to_file):
                resultSuccess = self._runResult()
        elif self.args.system == 'rebuild':
            system.rebuild()
            if self.args.log_to_file:
                resultSuccess = self._runResult()
        elif self.args.system == 'clean':
            system.clean()
        elif self.args.system == 'combinations':
            resultSuccess = system.cmdCombinations()
        elif self.args.system == 'deploy':
            resultSuccess = system.deploy()
        elif self.args.system == 'list':
            system.listInstances()
        elif self.args.system == 'db':
            system.makeDBLink()

        if resultSuccess == False:
            self._exit(1)

    def verify(self):
        if mmh_verify(self.log, self.args) == False:
            self._exit(1)

    def dispatch(self):
        table = {
            "build":              self.build,
            "build-tree-init":    self.build_tree_init,
            "download-source":    self.download_source,
            "download-sources":   self.download_sources,
            "dump-description":   self.dump_description,
            "fetch-dependencies": self.fetch_dependencies,
            "focus-instance":     self.focus_instance,
            "generate-toplevel":  self.generate_toplevel,
            "list-instances":     self.list_instances,
            "prepare":            self.prepare,
            "revision-overrides": self.revision_overrides,
            "run-instance":       self.run_instance,
            "show-result":        self.show_result,
            "show-source":        self.show_source,
            "system":             self.system,
            "verify":             self.verify
        }

        if self.args.sub_command not in table:
            raise UnknownSubCommand(self.args.sub_command)

        try:
            table[self.args.sub_command]()
        except Exception as e:
            if isinstance(e, MMHException):
                raise e
            if len(e.args) > 0:
                self.log.error(f'{type(e).__name__}: {e}')
            else:
                self.log.error(f'{type(e).__name__}')
            if self.args.raise_exceptions:
                raise e
            self._exit(1)

    def query(self):
        self._cfg_load()
        cut = CodeUnderTest(self.log,
                            self.cfg, self.args, self.src,
                            self.args.module)
        if (os.path.isfile(self.args.module) == True):
            cut.loadModule()
        q = self.args.query
        res = []
        if q == 'toolchains':
            res = cut.allToolchains()
        elif q == 'architectures':
            res = cut.allArchitectures()
        elif q == 'buildtools':
            res = cut.allBuildtools()
        elif q == 'buildconfigs':
            res = cut.allBuildConfigs()
        elif q == 'root':
            self._exit(findRootDirectory([self.args.module,
                                          self.args.system_spec]))
        elif q == 'root-module':
            self._exit(findRootDirectory([self.args.module]))
        elif q == 'root-system':
            self._exit(findRootDirectory([self.args.system_spec]))
        elif q == 'type':
            if (os.path.exists(self.args.module)):
                print('module')
            elif (os.path.exists(self.args.system_spec)):
                print('system')
            else:
                print('none')
            self._exit(0)
        else:
            mmh.warn('Unknown query: {}'.format(q))
            self._exit(1)
        print(" ".join(res))
        self._exit(0)
