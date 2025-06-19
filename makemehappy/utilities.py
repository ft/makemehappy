from __future__ import print_function

import contextlib
import fnmatch
import hashlib
import math
import os
import pprint
import re
import subprocess
import shlex
import shutil
import sys
import yaml

from pathlib import Path

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

def install(i, o, cb = None):
    oldmask = os.umask(0o022)
    try:
        odir = o.parent
        odir.mkdir(parents = True, exist_ok = True)
        shutil.copyfile(i, o)
        if cb is not None:
            cb(i, o)
    finally:
        os.umask(oldmask)

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

currentInstance = 0
expectedInstances__ = None
def expectedInstances(n):
    global expectedInstances__
    expectedInstances__ = n

def nextInstance():
    global currentInstance
    currentInstance += 1

def extendPhasesNote(note):
    if expectedInstances__ is None:
        return note
    width = math.floor(math.log10(expectedInstances__) + 1)
    cur = currentInstance
    exp = expectedInstances__
    return f'[{cur:{0}{width}}/{exp}] ' + note

def maybeShowPhase(log, phase, tag, args, thunk):
    string = f'{tag}: {phase}'
    log.info(f'Phase: {string}')
    string = extendPhasesNote(string)
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

class WorldWriteableFragment(Exception):
    pass

def loadPython(log, fn, localenv = None):
    info = os.stat(fn)
    if (info.st_mode & 2):
        log.error(f'Python fragment is world-writeable: {fn}')
        raise WorldWriteableFragment(fn, info)
    log.info(f'Loading python fragment: {fn}')
    with open(fn, mode = "r", encoding = "utf-8") as fragment:
        code = fragment.read()
        exec(code, None, localenv)

def checksumFile(filename, variant = hashlib.md5, buffersize = 2**13):
    state = variant()
    with open(filename, 'rb') as fh:
        data = fh.read(buffersize)
        while data:
            state.update(data)
            data = fh.read(buffersize)
    return state.hexdigest()

def checksumFiles(files, variant = hashlib.md5, buffersize = 2**13):
    for file in files:
        chksum = checksumFile(file, variant, buffersize)
        print(f'{chksum}  {file}')

def checksum(files, output, variant = hashlib.md5, buffersize = 2**13):
    with open(output, 'w') as ofh:
        with contextlib.redirect_stdout(ofh):
            checksumFiles(files, variant, buffersize)

class InvalidChecksumRecord(Exception):
    pass

class ChecksumVariantMismatch(Exception):
    pass

def checksumTokenise(line):
    m = re.match('^([0-9a-fA-F]+)  (.*)$', line)
    if (len(m.groups()) != 2):
        raise InvalidChecksumRecord(line)
    return (m.group(1), m.group(2))

def checksumGuess(string):
    tab = { 'md5':     32,
            'sha256':  64,
            'sha512': 128 }
    n = len(string)
    for (name, size) in tab.items():
        if size == n:
            return name
    return None

class ChecksumData:
    def __init__(self, file, variant):
        self.datafile = file
        self.variant = variant
        self.records = []
        self.start = None
        self.end = None
        self.current = None

    def __lshift__(self, rhs):
        self.records.append(rhs)

    def __iter__(self):
        self.start = 0
        self.end = len(self.records)
        self.current = self.start
        return self

    def __next__(self):
        if self.current < self.end:
            rv = self.records[self.current]
            self.current += 1
            return rv
        else:
            raise StopIteration()

def checksumVerify(file, root = '.', variant = None):
    realroot = Path(root)
    algos = { 'md5':    hashlib.md5,
              'sha256': hashlib.sha256,
              'sha512': hashlib.sha512 }
    data = checksumRead(file, variant)
    algo = algos[data.variant]
    errors = []
    for (expect, filename) in data:
        fn = realroot / filename
        actual = checksumFile(fn, algo)
        if expect != actual:
            errors.append((fn, expect, actual))
    return errors

def checksumRead(file, variant = None):
    with open(file, 'r') as fh:
        line1 = fh.readline().strip('\n')

    (checksum1, filename1) = checksumTokenise(line1)
    guess = checksumGuess(checksum1)
    if guess is None:
        raise InvalidChecksumRecord(line1)

    if variant is not None:
        if guess != variant:
            raise ChecksumVariantMismatch(variant, guess, line1)
    else:
        variant = guess

    # We do the variant detection based on the first record in a file. All
    # other records must use the same variant. So from now on out all checksum
    # tokens must yield this size:
    checksumSize = len(checksum1)

    retval = ChecksumData(file, variant)
    with open(file, 'r') as fh:
        for line in fh:
            (checksum, filename) = checksumTokenise(line.strip('\n'))
            guess = checksumGuess(checksum)
            if guess != variant:
                raise ChecksumVariantMismatch(variant, guess, line)
            retval << (checksum, filename)

    return retval
