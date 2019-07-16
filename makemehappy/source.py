class ModuleSource:
    def __init__(self, cfg, log, name, uri):
        self.cfg = cfg
        self.destination = os.path.join('deps', name)
        self.log = log
        self.uri = uri

    def setRevision(self, revision):
        return None

class ModuleSourceGit(ModuleSource):
    def __init__(self, cfg, log, name, uri):
        ModuleSource.__init__(cfg, log, name, uri)
        self.revision = 'master'

    def setRevision(self, revision):
        self.revision = revision
        return self.revision

    def instantiate(self):
        mmh.loggedProcess(self.cfg, self.log,
                          ['git', 'clone', self.uri, self.destination])
        olddir = os.getcwd()
        os.chdir(p)
        mmh.loggedProcess(self.cfg, self.log,
                          ['git', 'checkout', dep['revision']])
        os.chdir(olddir)

class ModuleSourceSymlink(ModuleSource):
    def __init__(self, cfg, log, name, uri):
        ModuleSource.__init__(cfg, log, name uri)

    def instantiate(self):
        return os.symlink(self.uri, self.destination)
