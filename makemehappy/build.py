import os
import shutil
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

def instanceName(instance):
    return "{}_{}_{}_{}_{}".format(instance['toolchain'],
                                   instance['architecture'],
                                   instance['interface'],
                                   instance['buildcfg'],
                                   instance['buildtool'])

def instanceDirectory(stats, instance):
    stats.build(instance['toolchain'],
                instance['architecture'],
                instance['interface'],
                instance['buildcfg'],
                instance['buildtool'])
    return instanceName(instance)

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

def cmakeConfigure(cfg, log, stats, ext, root, instance):
    rc = mmh.loggedProcess(
        cfg, log,
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

def cmakeBuild(cfg, log, stats, instance):
    rc = mmh.loggedProcess(cfg, log, ['cmake', '--build', '.'])
    stats.logBuild(rc)
    return (rc == 0)

def cmakeTest(cfg, log, stats, instance):
    # The last line of this command reads  like this: "Total Tests: N" …where N
    # is the number of registered tests. Fetch this integer from stdout and on-
    # ly run ctest for real, if tests were registered using add_test().
    txt = subprocess.check_output(['ctest', '--show-only'])
    last = txt.splitlines()[-1]
    num = int(last.decode().split(' ')[-1])
    if (num > 0):
        rc = mmh.loggedProcess(cfg, log, ['ctest', '--extra-verbose'])
        stats.logTestsuite(num, rc)
        return (rc == 0)
    return True

def cleanInstance(log, d):
    log.info('Cleaning up {}'.format(d))
    for f in os.listdir(d):
        path = os.path.join(d, f)
        log.debug('  Removing {}'.format(path))
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.unlink(path)
        except Exception as e:
            log.error('Could not remove {}. Reason: {}'.format(path, e))

def build(cfg, log, stats, ext, root, instance):
    dname = instanceDirectory(stats, instance)
    dnamefull = os.path.join(root, 'build', dname)
    if (os.path.exists(dnamefull)):
        log.info("Instance directory exists: {}".format(dnamefull))
        cleanInstance(log, dnamefull)
    else:
        os.mkdir(dnamefull)
    os.chdir(dnamefull)
    rc = cmakeConfigure(cfg, log, stats, ext, root, instance)
    if rc:
        rc = cmakeBuild(cfg, log, stats, instance)
        if rc:
            cmakeTest(cfg, log, stats, instance)
    os.chdir(root)

def allofthem(cfg, log, mod, ext):
    olddir = os.getcwd()
    instances = generateInstances(mod)
    log.info('Using {} build-instances:'.format(len(instances)))
    for instance in instances:
        log.info('    {}'.format(instanceName(instance)))
    for instance in instances:
        log.info('Building instance: {}'.format(instanceName(instance)))
        build(cfg, log, mod.stats, ext, olddir, instance)
