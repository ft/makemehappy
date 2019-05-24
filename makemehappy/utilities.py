from __future__ import print_function

import os
import pprint
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
    'dump-description': { 'aliases': [ "dump" ] },
    'fetch-dependencies': { 'aliases': [ 'fetch', 'deps' ] },
    'generate-toplevel': { 'aliases': [ 'top' ] },
    'run-instance': { 'aliases': [ 'run' ] }
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

def load(file):
    with open(file) as fh:
        return yaml.load(fh.read())

xppx = pprint.PrettyPrinter(indent = 4)

def pp(thing):
    xppx.pprint(thing)
