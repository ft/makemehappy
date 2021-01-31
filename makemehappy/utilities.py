from __future__ import print_function

import os
import pprint
import re
import subprocess
import sys
import yaml

def dotFile(fn):
    return os.path.join(os.environ['HOME'], '.makemehappy', fn)

def xdgFile(fn):
    key = 'XDG_CONFIG_HOME'
    if key in os.environ:
        base = os.environ[key]
    else:
        base = os.path.join(os.environ['HOME'], '.config')
    return os.path.join(base, 'makemehappy', fn)

def warn(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

verbosity = 0
def verbose(*args, **kwargs):
    if (verbosity > 0):
        print(*args, **kwargs)

def setVerbosity(value):
    global verbosity
    verbosity = value;

mmhCommands = {
    'build': { 'aliases': [ ] },
    'build-tree-init': { 'aliases': [ 'init' ] },
    'download-source': { 'aliases': [ 'download', 'get' ] },
    'download-sources': { 'aliases': [ ] },
    'dump-description': { 'aliases': [ "dump" ] },
    'fetch-dependencies': { 'aliases': [ 'fetch', 'deps' ] },
    'generate-toplevel': { 'aliases': [ 'top' ] },
    'reset-setup': { 'aliases': [ 'reset' ] },
    'run-instance': { 'aliases': [ 'run' ] },
    'show-source': { 'aliases': [ 'source' ] }
}

def lookupCommand(cmds):
    if (len(cmds) < 1):
        return False

    cmd = cmds[0]
    if cmd in mmhCommands:
        return cmd

    for item in mmhCommands:
        if cmd in mmhCommands[item]['aliases']:
            return item

    return False

def matchingVersion(version, data):
    if (data == None):
        return False
    if (not 'version' in data):
        return False
    return (data['version'] == version)

def noParameters(args):
    return (args.architectures == None and
            args.buildconfigs  == None and
            args.buildtools    == None and
            args.interfaces    == None and
            args.toolchains    == None and
            args.cmake         == None)

def load(file):
    (root,fn) = os.path.split(os.path.realpath(file))
    with open(file) as fh:
        data = yaml.safe_load(fh.read())
        if data == None:
            data = {}
        data['root'] = root
        data['definition'] = fn
        return data

def dump(fn, data):
    with open(fn, 'w') as fh:
        yaml.dump(data, fh)

xppx = pprint.PrettyPrinter(indent = 4)

def pp(thing):
    xppx.pprint(thing)

def logOutput(log, pipe):
    for line in iter(pipe.readline, b''):
        log.info(line.decode().strip())

def loggedProcess(cfg, log, cmd):
    log.info("Running command: {}".format(cmd))
    if cfg.lookup('log-all'):
        proc = subprocess.Popen(
            cmd, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        with proc.stdout:
            logOutput(log, proc.stdout)
        return proc.wait()
    rc = subprocess.run(cmd)
    return rc.returncode

def starPattern(s):
    return '*' in s

def questionPattern(s):
    return '?' in s

bracketExpression = re.compile(r'\[.*\]')

def bracketPattern(s):
    return re.search(bracketExpression, s) != None

def isPattern(s):
    return starPattern(s) or questionPattern(s) or bracketPattern(s)
