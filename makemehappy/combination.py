import os
import makemehappy.pathlike as p

from pathlib import Path

class Combination:
    def __init__(self, name, parents, run, kwargs):
        self.name = name
        self.parents = parents
        self.runner = run
        self.kwargs = kwargs
        self.done = False
        self.status = None
        self.log = None
        self.buildroot = None
        self.out = None

    def ensureLog(self, log):
        if self.log is not None:
            return
        self.log = log

    def skipped(self):
        return (self.status is None)

    def succeeded(self):
        return (self.status is True)

    def processed(self):
        return (self.done is True)

    def possible(self, instances):
        for p in self.parents:
            if p not in instances:
                return False
        return True

    def runnable(self, instances):
        if self.done:
            return False
        return self.possible(instances)

    def outputDirectory(self):
        return self.out

    def buildRoot(self):
        return self.buildroot

    def run(self, parents):
        self.done = True
        self.buildroot = Path(parents[0].buildroot)
        self.out = self.buildroot / 'combination' / self.name
        self.log.info(f'mkdir({self.out})')
        self.out.mkdir(parents = True, exist_ok = True)
        if self.runner is None:
            self.status = True
        else:
            self.status = self.runner(self, parents)
        return self.status

    def __str__(self):
        return self.name

class ParentInstance:
    def __init__(self, log, name, buildroot, data):
        self.log = log
        self.name = name
        self.data = data
        self.buildroot = buildroot
        self.builddir = p.BuildDirectory(buildroot, self.name, self.log)
        self.sourcedir = p.SourceDirectory(self.data.instance.systemdir)

    def cmake(self, key = None, force = False):
        return self.builddir.cmake(key, force)

    def buildDirectory(self):
        return self.builddir

    def sourceDirectory(self):
        return self.sourcedir

class Registry:
    def __init__(self):
        self.combinations = {}
        self.parents = {}
        self.entry = None
        self.finish = None
        self.log = None
        self.stats = None

    def __call__(self, *args, **kwargs):
        return self.register(*args, **kwargs)

    def setCallbacks(self, entry, finish):
        self.entry = entry
        self.finish = finish

    def setLog(self, log):
        self.log = log

    def setStats(self, stats):
        self.stats = stats

    def xcount(self, pred):
        cnt = 0
        for name in self.combinations:
            c = self.combinations[name]
            if getattr(c. pred)():
                cnt = cnt + 1
        return cnt

    def countProcessed(self):
        """Return number of combinations that where processed.

        A processed combination may have been skipped (because a parent did not
        succeed), failed or succeeded."""
        return self.xcount('processed')

    def countSkipped(self):
        """Return the number of processed but skipped combinations."""
        return self.xcount('skipped')

    def countSucceeded(self):
        """Return the number of successfully processed combinations."""
        return self.xcount('succeeded')

    def countPossible(self, instances):
        """Return the number of possible combinations to be build.

        In contrast to countProcessed(), this can be run before the entire
        build-process. Given a set of build instances to be performed, the
        number of possible combinations can be computed."""
        n = 0
        for name in self.combinations:
            c = self.combinations[name]
            if c.possible(instances):
                n = n + 1
        return n

    def addParent(self, name, buildroot, data):
        self.parents[name] = ParentInstance(self.log, name, buildroot, data)

    def register(self, name, parents, run, **kwargs):
        """Register a build-combination.

        This registers a build combination named "name", which requires the
        list of "parents" to be build before it can be executed. The "run"
        function must accept at least two arguments, the first argument will be
        the name of the combination to be built, and the second being a list of
        ParentInstance instances, corresponding to its parent list from the
        "parents" argument.

        Any other keyword arguments are passed to the "run" function verbatim.
        It therefore will have to be able to accept those as well.

        The "run" function must return a boolean value, that indicates whether
        or not processing the combination succeeded or not."""
        self.log.info(f'Registering build-combination {name}' +
                      f'with {len(parents)} depencencies.')
        self.combinations[name] = Combination(name, parents, run, kwargs)

    def listParents(self, lst):
        return list(map(lambda p: self.parents[p], lst))

    def listCombinations(self):
        return list(self.combinations)

    def execute(self):
        for name in self.combinations:
            c = self.combinations[name]
            c.ensureLog(self.log)
            if (c.runnable(self.parents.keys())):
                self.stats.systemCombination(name, c.parents)
                if self.entry is not None:
                    self.entry(name)
                plst = self.listParents(c.parents)
                parentsok = True
                for p in plst:
                    success = p.data.succeeded()
                    if not success:
                        self.log.warn(f'combination({name}):' +
                                      ' {p.description} did not succeed')
                        self.log.warn(f'combination({name}): will be skipped')
                        parentsok = False
                if not parentsok:
                    c.done = True
                    self.finish(name, 'skipped')
                else:
                    rc = c.run(plst)
                    self.stats.logBuild(0 if rc else 1)
                    if self.finish is not None:
                        self.finish(name, None if rc else 'failed')

combination = Registry()
