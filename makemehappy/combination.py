class Combination:
    def __init__(self, name, parents, run, kwargs):
        self.name = name
        self.parents = parents
        self.runner = run
        self.kwargs = kwargs
        self.done = False
        self.status = None
        self.log = None

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

    def run(self, parents):
        self.done = True
        if self.runner is None:
            self.status = True
        else:
            self.status = self.runner(self, parents)
        return self.status

class ParentInstance:
    def __init__(self, name, data):
        self.name = name
        self.data = data
        self.cmake = None

    def getCMakeCache(self):
        # TODO: Implement a cmake-cache parser, and run it if self.cmake is
        # still None. Assign the return value to self.cmake, so the parsing
        # will only have to be done once with the same parent being used in
        # more than one combination.
        return self.cmake

class Registry:
    def __init__(self):
        self.combinations = {}
        self.parents = {}
        self.entry = None
        self.finish = None
        self.log = None
        self.stats = None

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

    def addParent(self, name, data):
        self.parents[name] = ParentInstance(name, data)

    def register(self, name, parents, run, **kwargs):
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

combinations = Registry()

def combination(name, parents, run = None, **kwargs):
    """Register a build-combination.

    This registers a build combination named "name", which requires the list of
    "parents" to be build before it can be executed. The "run" function must
    accept at least two arguments, the first argument will be the name of the
    combination to be built, and the second being a list of ParentInstance
    instances, corresponding to its parent list from the "parents" argument.

    Any other keyword arguments are passed to the "run" function verbatim. It
    therefore will have to be able to accept those as well.

    The "run" function must return a boolean value, that indicates whether or
    not processing the combination succeeded or not."""
    combinations.register(name, parents, run, **kwargs)
