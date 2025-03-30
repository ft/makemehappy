from __future__ import print_function

import fnmatch
import os
import pprint
import re
import subprocess
import shlex
import sys
import yaml

import mako.template as mako

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
    verbosity = value

def matchingVersion(version, data):
    if data is None:
        return False
    if ('version' not in data):
        return False
    return (data['version'] == version)

def noParameters(args):
    return (args.architectures  is None and
            args.buildconfigs   is None and
            args.buildtools     is None and
            args.toolchains     is None and
            args.cmake          is None and
            len(args.instances) == 0)

def load(file):
    (root, fn) = os.path.split(os.path.realpath(file))
    with open(file) as fh:
        data = yaml.safe_load(fh.read())
        if data is None:
            data = {}
        data['root'] = root
        data['definition'] = fn
        return data

def dump(file, data):
    (root, fn) = os.path.split(os.path.realpath(file))
    data['definition'] = fn
    data['root'] = root
    with open(file, 'w') as fh:
        yaml.dump(data, fh)

def yp(data):
    print(yaml.dump(data), end = '')

xppx = pprint.PrettyPrinter(indent = 4)

def pp(thing):
    xppx.pprint(thing)

def selectPager(cfg):
    if (cfg.lookup('pager-from-env') and 'PAGER' in os.environ):
        pager = os.environ['PAGER']
    else:
        pager = cfg.lookup('pager')

    return shlex.split(pager)

def pager(cfg, thunk):
    proc = subprocess.Popen(selectPager(cfg),
                            stdin = subprocess.PIPE,
                            encoding = 'utf-8')
    with proc.stdin as sys.stdout:
        thunk()
    proc.wait()

def logOutput(log, pipe):
    for line in iter(pipe.readline, b''):
        log.info(line.decode(errors = 'backslashreplace').rstrip())

def loggedProcess(cfg, log, cmd, env = None):
    log.info("Running command: {}".format(cmd))
    if cfg.lookup('log-all'):
        proc = subprocess.Popen(
            cmd, stdout = subprocess.PIPE, stderr = subprocess.STDOUT,
            env = env)
        with proc.stdout:
            logOutput(log, proc.stdout)
        return proc.wait()
    rc = subprocess.run(cmd)
    return rc.returncode

def devnullProcess(cmd):
    rc = subprocess.run(cmd,
                        stdout = open(os.devnull, "w"),
                        stderr = subprocess.STDOUT)
    return rc.returncode

def toString(data):
    return data.decode('utf-8').strip()

def stdoutProcess(cmd):
    proc = subprocess.Popen(cmd,
                            stdout = subprocess.PIPE,
                            stderr = subprocess.PIPE)
    return (toString(proc.stdout.read()),
            toString(proc.stderr.read()),
            proc.wait())

def starPattern(s):
    return '*' in s

def questionPattern(s):
    return '?' in s

bracketExpression = re.compile(r'\[.*\]')

def bracketPattern(s):
    return re.search(bracketExpression, s) is not None

def isPattern(s):
    return starPattern(s) or questionPattern(s) or bracketPattern(s)

def flatten(lst):
    if (isinstance(lst, list)):
        if (len(lst) == 0):
            return []
        (first, rest) = lst[0], lst[1:]
        return flatten(first) + flatten(rest)
    else:
        return [lst]

def expandFile(tmpl):
    if tmpl is None:
        return None
    curdir = os.getcwd()
    exp = mako.Template(tmpl).render(system = curdir)
    return exp

def maybeMatch(lst, pat):
    m = fnmatch.filter(lst, pat)
    if (len(m) == 0):
        return [ pat ]
    else:
        return m

def patternsToList(lst, pats):
    return flatten([ maybeMatch(lst, x) for x in pats ])

def trueKey(d, k):
    return (k in d and d[k])

def findByKey(lst, key):
    for i, d in enumerate(lst):
        if (trueKey(d, key)):
            return i
    return None

def findByName(lst, name):
    for i, d in enumerate(lst):
        # print('DEBUG:', name, i, d)
        if ('name' in d and d['name'] == name):
            return i
    return None

def maybeShowPhase(log, phase, tag, args, thunk):
    string = f'{tag}: {phase}'
    log.info(f'Phase: {string}')
    if (args.log_to_file and args.show_phases):
        print(string, flush = True)
    res = thunk()
    if not res and args.log_to_file and args.show_phases:
        print(string, "...failed", flush = True)
    return res

def get_install_components(log, spec):
    if (isinstance(spec, bool)):
        if (spec == True):
            # None will trigger the default install target
            return [ None ]
        else:
            log.info('System installation disabled')
            return []

    if (isinstance(spec, str)):
        return [ spec ]

    if (isinstance(spec, list)):
        return spec

    log.warn('Invalid installation spec: {}', spec)
    return []

def makeEnvironment(log, with_overrides, spec):
    env = dict(os.environ)
    for var in spec:
        value = spec[var]
        if with_overrides == False and var in env:
            p = env[var]
            log.info(f'Existing environment for {var} ({p}) supersedes'
                     f' value from module ({value})')
            continue

        if var in env:
            p = env[var]
            log.info(f'Existing environment for {var} ({p}) overridden by'
                     f' value from module ({value})')
        else:
            log.info(f'Setting environment for {var} ({value})')

        env[var] = value

    return env

def setEnvironment(log, with_overrides, spec):
    env = makeEnvironment(log, with_overrides, spec)
    # Apparently, the assignment here is needed to invoke the underlying
    # setenv(3) call. Who cares… this is quick.
    for key in env:
        os.environ[key] = env[key]
