import contextlib
import os
import subprocess

import makemehappy.utilities as mmh

class InvalidCargoFeatures(Exception):
    pass

class UnsupportedCargoParameterType(Exception):
    pass

def makeParam(name, value):
    rv = []
    exp = ''
    if (isinstance(value, str)):
        exp = '"' + value + '"'
    elif isinstance(value, bool):
        exp = str(value).lower()
    elif isinstance(value, int):
        exp = str(value)
    else:
        raise UnsupportedCargoParameterType(name, value)

    return [ '--config', f'{name}={exp}' ]

def makeParamsFromDict(d):
    rv = []
    for key in d:
        rv.append(makeParam(key, d[key]))
    return rv

def rustcPrint(query):
    return [ 'rustc', '--print', query ]

def rustHostTuple():
    cmd = rustcPrint('host-tuple')
    txt = subprocess.check_output(cmd)
    return (txt.splitlines()[-1]).decode('utf-8')

def cargo(lst):
    return mmh.commandWithArguments('cargo', lst)

def compile(target = 'native', profile = 'release',
            directory = None, features = [], variables = {}):
    if profile == 'debug':
        profile = 'dev'
    cmd = cargo(makeParamsFromDict(variables) +
                [ 'build', '--verbose',
                  '--profile', profile,
                  '--target-dir' ])
    mmh.maybeExtend(cmd, directory, default = 'target')
    if target != 'native':
        cmd.extend([ '--target', target ])

    if isinstance(features, str) and features == 'all':
        cmd.append('--all-features')
    elif isinstance(features, list) and len(features) > 0:
        cmd.extend(['--features', ','.join(features)])
    else:
        raise InvalidCargoFeatures(features)

    return cmd

def test(directory = None):
    cmd = cargo([ 'test', '--target-dir' ])
    mmh.maybeExtend(cmd, directory, default = 'target')
    return cmd

def clean(directory = None):
    cmd = cargo([ 'clean', '--target-dir' ])
    mmh.maybeExtend(cmd, directory, default = 'target')
    return cmd

def stepBuild(cfg, log, env, stats, srcdir, builddir,
              target, profile, features, variables):
    cmd = compile(target    = target,
                  profile   = profile,
                  directory = builddir,
                  features  = features,
                  variables = variables)
    with contextlib.chdir(srcdir):
        rc = mmh.loggedProcess(cfg, log, cmd, env)
    stats.logBuild(rc)
    return (rc == 0)

def stepTest(cfg, log, env, stats, srcdir, builddir):
    cmd = test(builddir)
    with contextlib.chdir(srcdir):
        rc = mmh.loggedProcess(cfg, log, cmd, env)
    stats.logTestsuite(rc, 0)
    return (rc == 0)

def stepClean(cfg, log, env, stats, srcdir, builddir):
    cmd = clean(builddir)
    with contextlib.chdir(srcdir):
        rc = mmh.loggedProcess(cfg, log, cmd, env)
    return (rc == 0)
