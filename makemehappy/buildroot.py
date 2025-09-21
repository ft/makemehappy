import datetime
import hashlib
import os
import shutil
import time

from pathlib import Path

def timeString():
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d_%H:%M:%S.%f")

def tempString(seed):
    string = seed + timeString()
    return hashlib.sha1(string.encode('utf-8')).hexdigest()

def tempDirName(seed, name):
    return 'mmh-' + name + '-' + tempString(seed) + '-root'

def mkTempDir(seed, name):
    root = str(os.getenv('TMPDIR', os.path.join('/', 'tmp')))
    while True:
        d = os.path.join(root, tempDirName(seed, name))
        try:
            os.mkdir(d)
            return d
        except FileExistsError:
            time.sleep(0.1)

class BuildRoot:
    def __init__(self, log, seed, modName, dirName = None):
        self.initdirs = [ 'build', 'deps' ]
        self.log = log
        self.calldir = os.path.realpath(os.getcwd())
        existing = False

        if dirName is None:
            self.root = mkTempDir(seed, modName)
        elif (os.path.exists(dirName)):
            existing = True
            self.root = dirName
        else:
            self.root = dirName
            os.makedirs(self.root, mode=0o755, exist_ok=True)

        if existing:
            self.log.info("Using build-directory: {}".format(self.root))
        else:
            self.log.info("Setting up build-directory: {}".format(self.root))

    def name(self):
        return self.root

    def cleanup(self):
        self.log.info("Cleaning up build-directory: {}".format(self.name()))
        olddir = os.getcwd()
        os.chdir(self.calldir)
        shutil.rmtree(self.root)
        if (os.path.exists(olddir)):
            os.chdir(olddir)
        else:
            self.log.info("Previous directory is gone: {}".format(olddir))

    def cd(self):
        self.log.info("Changing into build-directory: {}".format(self.name()))
        os.chdir(self.calldir)
        os.chdir(self.root)

    def toCalldir(self, quiet = False):
        if quiet == False:
            self.log.info("Changing into call-directory: {}"
                          .format(self.calldir))
        os.chdir(self.calldir)

    def populate(self):
        for entry in self.initdirs:
            self.log.info("    Populating build-directory: {}".format(entry))
            os.makedirs(os.path.join(self.name(), entry),
                        mode=0o755, exist_ok=True)

    def linkCodeUnderTest(self, directory = None):
        self.log.info("    Linking code-under-test: {}".format(self.calldir))
        lnk = Path(os.path.join(self.name(), 'code-under-test'))
        if not Path.is_symlink(lnk):
            os.symlink(self.calldir, lnk)
