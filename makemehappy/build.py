import os
import re
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

def generateInstances(log, mod):
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
        warnings = {}
        for cfg in cfgs:
            for tool in tools:
                add = (lambda a:
                    instances.append({'toolchain'   : maybeToolchain(tc),
                                      'architecture': a,
                                      'interface'   : maybeInterface(tc),
                                      'buildcfg'    : cfg,
                                      'buildtool'   : tool,
                                      'type'        : mod.moduleType }))
                arch = maybeArch(tc)
                if ('architectures' in mod.moduleData):
                    result = []
                    for a in mod.moduleData['architectures']:
                        if (not a in arch and not a in warnings):
                            log.warn(('{arch} is not in toolchain\'s list of '
                                     +'architectures {archs}. Keeping it at '
                                     +'user\'s request.')
                                     .format('', arch = a, archs = arch))
                        warnings[a] = True
                        result.append(a)
                    arch = result
                if (isinstance(arch, list)):
                    for a in arch:
                        add(a)
                else:
                    add(arch)

    return instances

def generateZephyrInstances(log, mod):
    targets = mod.targets()
    cfgs = mod.buildconfigs()
    tools = mod.buildtools()

    if (len(cfgs) == 0):
        cfgs = [ 'debug' ]
    if (len(tools) == 0):
        tools = [ 'make' ]

    instances = []
    for target in targets:
        for cfg in cfgs:
            for tool in tools:
                arch = target['board'].replace('_', '-')
                mods = ''
                kcfg = ''
                opts = ''
                if ('modules' in target):
                    mods = ';'.join(target['modules'])
                if ('kconfig' in target):
                    kcfg = ';'.join(target['kconfig'])
                if ('options' in target):
                    opts = ';'.join(target['options'])
                instances.append({'toolchain'   : target['toolchain'],
                                  'board'       : target['board'],
                                  'architecture': arch,
                                  'modules'     : mods,
                                  'kconfig'     : kcfg,
                                  'options'     : opts,
                                  'interface'   : 'none',
                                  'buildcfg'    : cfg,
                                  'buildtool'   : tool,
                                  'type'        : mod.moduleType })

    return instances

def instanceName(instance):
    tc = instance['toolchain']
    if (instance['type'] == 'zephyr'):
        tc = 'zephyr-' + tc
    return "{}_{}_{}_{}_{}".format(tc,
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

class UnknownToolchain(Exception):
    pass

class UnknownModuleType(Exception):
    pass

def findToolchainByExtension(ext, tc):
    return findToolchain(ext.toolchainPath(), tc)

def cmakeConfigure(cfg, log, args, stats, ext, root, instance):
    cmakeArgs = None
    if (args.cmake == None):
        cmakeArgs = []
    else:
        cmakeArgs = args.cmake

    if (instance['type'] == 'cmake'):
        cmd = ['cmake',
               '-G{}'.format(cmakeBuildtool(instance['buildtool'])),
               '-DCMAKE_TOOLCHAIN_FILE={}'.format(
                   findToolchainByExtension(ext, instance['toolchain'])),
               '-DCMAKE_BUILD_TYPE={}'.format(instance['buildcfg']),
               '-DPROJECT_TARGET_CPU={}'.format(instance['architecture']),
               '-DINTERFACE_TARGET={}'.format(instance['interface'])
               ] + cmakeArgs + [root]
    elif (instance['type'] == 'zephyr'):
        cmd = ['cmake',
               '-G{}'.format(cmakeBuildtool(instance['buildtool'])),
               '-DZEPHYR_TOOLCHAIN_VARIANT={}'.format(instance['toolchain']),
               '-DCMAKE_BUILD_TYPE={}'.format(instance['buildcfg']),
               '-DMMH_TARGET_BOARD={}'.format(instance['board']),
               '-DMMH_ZEPHYR_TOOLCHAIN={}'.format(instance['toolchain']),
               '-DMMH_ZEPHYR_MODULES={}'.format(instance['modules']),
               '-DMMH_ZEPHYR_KCONFIG={}'.format(instance['kconfig']),
               '-DMMH_ZEPHYR_OPTIONS={}'.format(instance['options']),
               '-DINTERFACE_TARGET={}'.format(instance['interface'])
               ] + cmakeArgs + [root]
    else:
        raise(UnknownModuleType(instance['type']))
    rc = mmh.loggedProcess(cfg, log, cmd)
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
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.unlink(path)
        except Exception as e:
            log.error('Could not remove {}. Reason: {}'.format(path, e))

def build(cfg, log, args, stats, ext, root, instance):
    dname = instanceDirectory(stats, instance)
    dnamefull = os.path.join(root, 'build', dname)
    if (os.path.exists(dnamefull)):
        log.info("Instance directory exists: {}".format(dnamefull))
        cleanInstance(log, dnamefull)
    else:
        os.mkdir(dnamefull)
    os.chdir(dnamefull)
    rc = cmakeConfigure(cfg, log, args, stats, ext, root, instance)
    if rc:
        rc = cmakeBuild(cfg, log, stats, instance)
        if rc:
            cmakeTest(cfg, log, stats, instance)
    os.chdir(root)

def allofthem(cfg, log, mod, ext):
    olddir = os.getcwd()
    if (mod.moduleType == 'zephyr'):
        instances = generateZephyrInstances(log, mod)
    else:
        instances = generateInstances(log, mod)
    log.info('Using {} build-instances:'.format(len(instances)))
    for instance in instances:
        log.info('    {}'.format(instanceName(instance)))
    for instance in instances:
        log.info('Building instance: {}'.format(instanceName(instance)))
        build(cfg, log, mod.args, mod.stats, ext, olddir, instance)

def findToolchain(tcp, tc):
    extension = '.cmake'
    for d in tcp:
        candidate = os.path.join(d, tc + extension)
        if (os.path.exists(candidate)):
            return candidate
    raise(UnknownToolchain(tcp, tc))

def runInstance(cfg, log, args, directory):
    dirs = os.path.split(directory)
    m = re.match('([^_]+)_([^_]+)_([^_]+)_([^_]+)_([^_]+)', dirs[-1])
    if (m is None):
        log.warning("Not a build-instance directory: {}".format(directory))
        return
    cleanInstance(log, directory)
    olddir = os.getcwd()
    root = os.path.join(olddir, args.directory)
    (toolchain, architecture, interface, buildconfig, buildtool) = m.groups()
    tc = findToolchain(args.toolchainPath, toolchain)
    cmakeArgs = []
    if (args.cmake is not None):
        cmakeArgs = args.cmake
    log.info("Moving to build-instance {}".format(directory))
    os.chdir(directory)
    cmd = ['cmake',
           '-G{}'.format(cmakeBuildtool(buildtool)),
           '-DCMAKE_TOOLCHAIN_FILE={}'.format(tc),
           '-DCMAKE_BUILD_TYPE={}'.format(buildconfig),
           '-DPROJECT_TARGET_CPU={}'.format(architecture),
           '-DINTERFACE_TARGET={}'.format(interface)
           ] + cmakeArgs + [root]
    rc = mmh.loggedProcess(cfg, log, cmd)
    if (rc != 0):
        log.warning("CMake failed for {}".format(directory))
        log.info("Moving back to {}".format(olddir))
        os.chdir(olddir)
        return
    rc = mmh.loggedProcess(cfg, log, ['cmake', '--build', '.'])
    if (rc != 0):
        log.warning("Build-process failed for {}".format(directory))
        log.info("Moving back to {}".format(olddir))
        os.chdir(olddir)
        return
    txt = subprocess.check_output(['ctest', '--show-only'])
    last = txt.splitlines()[-1]
    num = int(last.decode().split(' ')[-1])
    if (num > 0):
        rc = mmh.loggedProcess(cfg, log, ['ctest', '--extra-verbose'])
        if (rc != 0):
            log.warning("Test-suite failed for {}".format(directory))
    log.info("Moving back to {}".format(olddir))
    os.chdir(olddir)
