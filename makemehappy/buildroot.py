import os
import shutil
import tempfile

class BuildRoot:
    def __init__(self, log, name = None):
        self.initdirs = [ 'build', 'deps', 'tools' ]
        self.log = log
        self.calldir = os.path.realpath(os.getcwd())
        if (name == None):
            self.root = tempfile.TemporaryDirectory(prefix = 'mmh-',
                                                    suffix = '-root')
        else:
            self.root = name
            os.mkdir(name, 0o755)
        self.log.info("Setting up build-directory: {}".format(self.name()))

    def name(self):
        if (isinstance(self.root, tempfile.TemporaryDirectory)):
            return self.root.name
        else:
            return self.root

    def cleanup(self):
        self.log.info("Cleaning up build-directory: {}".format(self.name()))
        if (isinstance(self.root, tempfile.TemporaryDirectory)):
            return self.root.cleanup()
        else:
            shutil.rmtree(self.root)

    def cd(self):
        self.log.info("Changing into build-directory: {}".format(self.name()))
        os.chdir(self.name())

    def populate(self):
        for entry in self.initdirs:
            self.log.info("    Populating build-directory: {}".format(entry))
            os.mkdir(os.path.join(self.name(), entry))

    def linkCodeUnderTest(self, directory = None):
        self.log.info("    Linking code-under-test: {}".format(self.calldir))
        os.symlink(self.calldir, os.path.join(self.name(), 'code-under-test'))
