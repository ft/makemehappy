import os
import subprocess

import makemehappy.utilities as mmh

def maybeToolchain(tc):
    if ('name' in tc):
        return tc['name']
    return 'gnu'

def maybeArch(tc):
    if ('architecture' in tc):
        return tc['architecture']
    return 'native'

def maybeInterface(tc):
    if ('interface' in tc):
        return tc['interface']
    return 'none'

def toolchainViable(md, tc):
    if not('requires' in md):
        return True
    if not('features' in tc):
        return False
    for entry in md['requires']:
        if not(entry in tc['features']):
            return False
    return True

def generateInstances(mod):
    chains = mod.toolchains()
    cfgs = mod.buildconfigs()
    tools = mod.buildtools()
    # Return a list of dicts, with dict keys: toolchain, architecture,
    # interface, buildcfg, buildtool; all of these must be set, if they are
    # missing, fill in defaults.
    if (len(cfgs) == 0):
        cfgs = [ 'debug' ]
    if (len(tools) == 0):
        tools = [ 'make' ]
    instances = []
    for tc in chains:
        if not(toolchainViable(mod.moduleData, tc)):
            continue
        for cfg in cfgs:
            for tool in tools:
                instances.append({ 'toolchain': maybeToolchain(tc),
                                   'architecture': maybeArch(tc),
                                   'interface': maybeInterface(tc),
                                   'buildcfg': cfg,
                                   'buildtool': tool })
    return instances

def instanceDirectory(stats, instance):
    stats.build(instance['toolchain'],
                instance['architecture'],
                instance['interface'],
                instance['buildcfg'],
                instance['buildtool'])
    return "{}_{}_{}_{}_{}".format(instance['toolchain'],
                                   instance['architecture'],
                                   instance['interface'],
                                   instance['buildcfg'],
                                   instance['buildtool'])

def cmakeBuildtool(name):
    if (name == 'make'):
        return 'Unix Makefiles'
    if (name == 'ninja'):
        return 'Ninja'
    return 'Unknown Buildtool'

def findToolchain(ext, tc):
    tcp = ext.toolchainPath()
    ext = '.cmake'
    for d in tcp:
        candidate = os.path.join(d, tc + ext)
        if (os.path.exists(candidate)):
            return candidate
    raise(Exception())

def cmakeConfigure(log, stats, ext, root, instance):
    rc = mmh.loggedProcess(
        log,
        ['cmake',
         '-G{}'.format(cmakeBuildtool(instance['buildtool'])),
         '-DCMAKE_TOOLCHAIN_FILE={}'.format(
             findToolchain(ext, instance['toolchain'])),
         '-DCMAKE_BUILD_TYPE={}'.format(instance['buildcfg']),
         '-DPROJECT_TARGET_CPU={}'.format(instance['architecture']),
         '-DINTERFACE_TARGET={}'.format(instance['interface']),
         root])
    stats.logConfigure(rc)
    return (rc == 0)

def cmakeBuild(log, stats, instance):
    rc = mmh.loggedProcess(log, ['cmake', '--build', '.'])
    stats.logBuild(rc)
    return (rc == 0)

def cmakeTest(log, stats, instance):
    # The last line of this command reads  like this: "Total Tests: N" …where N
    # is the number of registered tests. Fetch this integer from stdout and on-
    # ly run ctest for real, if tests were registered using add_test().
    txt = subprocess.check_output(['ctest', '--show-only'])
    last = txt.splitlines()[-1]
    num = int(last.decode().split(' ')[-1])
    if (num > 0):
        rc = mmh.loggedProcess(log, ['ctest', '--extra-verbose'])
        stats.logTestsuite(num, rc)
        return (rc == 0)
    return True

def build(log, stats, ext, root, instance):
    dname = instanceDirectory(stats, instance)
    dnamefull = os.path.join(root, 'build', dname)
    os.mkdir(dnamefull)
    os.chdir(dnamefull)
    rc = cmakeConfigure(log, stats, ext, root, instance)
    if rc:
        rc = cmakeBuild(log, stats, instance)
        if rc:
            cmakeTest(log, stats, instance)
    os.chdir(root)

def allofthem(log, mod, ext):
    olddir = os.getcwd()
    instances = generateInstances(mod)
    log.info('Using {} build-instances.'.format(len(instances)))
    for instance in instances:
        build(log, mod.stats, ext, olddir, instance)
