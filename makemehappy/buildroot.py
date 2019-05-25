import datetime
import hashlib
import os
import shutil
import time
import yaml

def timeString():
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d_%H:%M:%S.%f")

def tempString(string):
    s = string + timeString()
    return hashlib.sha1(s.encode('utf-8')).hexdigest()

def tempDirName(mod):
    prefix = 'mmh-'
    if ('name' in mod):
        prefix = prefix + mod['name'] + '-'
    suffix = '-root'
    return prefix + tempString(yaml.dump(mod)) + suffix

def mkTempDir(mod):
    root = str(os.getenv('TMPDIR', os.path.join('/', 'tmp')))
    while True:
        d = os.path.join(root, tempDirName(mod))
        try:
            os.mkdir(d)
            return d
        except FileExistsError:
            time.sleep(0.1)

class BuildRoot:
    def __init__(self, log, mod, name = None):
        self.initdirs = [ 'build', 'deps', 'tools' ]
        self.log = log
        self.calldir = os.path.realpath(os.getcwd())
        if (name == None):
            self.root = mkTempDir(mod.data)
        else:
            self.root = name
            os.mkdir(self.root, 0o755)

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
        os.chdir(self.name())

    def populate(self):
        for entry in self.initdirs:
            self.log.info("    Populating build-directory: {}".format(entry))
            os.mkdir(os.path.join(self.name(), entry))

    def linkCodeUnderTest(self, directory = None):
        self.log.info("    Linking code-under-test: {}".format(self.calldir))
        os.symlink(self.calldir, os.path.join(self.name(), 'code-under-test'))
