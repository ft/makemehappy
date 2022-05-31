import os
import re
import shutil
import subprocess

import makemehappy.cmake as c
import makemehappy.utilities as mmh

def maybeToolchain(tc):
    if ('name' in tc):
        return tc['name']
    return 'gnu'

def maybeArch(tc):
    if ('architecture' in tc):
        return tc['architecture']
    return 'native'

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
    # buildcfg, buildtool; all of these must be set, if they are missing,
    # fill in defaults.
    if (len(cfgs) == 0):
        cfgs = [ 'debug' ]
    if (len(tools) == 0):
        tools = [ 'make' ]

    install = False
    if ('install' in mod.moduleData):
        install = mod.moduleData['install']

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
                                      'buildcfg'    : cfg,
                                      'buildtool'   : tool,
                                      'install'     : install,
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

    install = False
    if ('install' in mod.moduleData):
        install = mod.moduleData['install']

    instances = []
    for target in targets:
        for cfg in cfgs:
            for tool in tools:
                for board in target['boards']:
                    for tc in target['toolchains']:
                        if ('kconfig' not in target):
                            target['kconfig'] = []
                        if ('options' not in target):
                            target['options'] = []
                        if ('modules' not in target):
                            target['modules'] = []
                        instances.append(
                            { 'toolchain'   : tc,
                              'board'       : board,
                              'architecture': board,
                              'modules'     : target['modules'],
                              'kconfig'     : target['kconfig'],
                              'options'     : target['options'],
                              'buildcfg'    : cfg,
                              'buildtool'   : tool,
                              'install'     : install,
                              'type'        : mod.moduleType })

    return instances

def instanceName(instance):
    tc = instance['toolchain']
    if (isinstance(tc, dict)):
        tc = tc['name']
    if (instance['type'] == 'zephyr'):
        tc = 'zephyr-' + tc
    return "{}/{}/{}/{}".format(tc,
                                instance['architecture'],
                                instance['buildcfg'],
                                instance['buildtool'])

def instanceDirectory(stats, instance):
    stats.build(instance['toolchain'],
                instance['architecture'],
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
        cmd = c.configureLibrary(
            log          = log,
            args         = cmakeArgs,
            architecture = instance['architecture'],
            buildtool    = instance['buildtool'],
            buildconfig  = instance['buildcfg'],
            toolchain    = findToolchainByExtension(ext, instance['toolchain']),
            sourcedir    = root,
            builddir     = '.')
    elif (instance['type'] == 'zephyr'):
        cmd = c.configureZephyr(
            log         = log,
            args        = cmakeArgs,
            ufw         = os.path.join(root, 'deps', 'ufw'),
            board       = instance['board'],
            buildconfig = instance['buildcfg'],
            toolchain   = instance['toolchain'],
            sourcedir   = root,
            builddir    = '.',
            installdir  = './artifacts',
            buildtool   = instance['buildtool'],
            buildsystem = '',
            appsource   = os.path.join(root, 'code-under-test'),
            kernel      = os.path.join(root, 'deps', 'zephyr-kernel'),
            kconfig     = instance['kconfig'],
            modulepath  = [ os.path.join(root, 'deps') ],
            modules     = instance['modules'])
    else:
        raise(UnknownModuleType(instance['type']))
    rc = mmh.loggedProcess(cfg, log, cmd)
    stats.logConfigure(rc)
    return (rc == 0)

def cmakeBuild(cfg, log, stats, instance):
    rc = mmh.loggedProcess(cfg, log, c.compile())
    stats.logBuild(rc)
    return (rc == 0)

def cmakeTest(cfg, log, stats, instance):
    # The last line of this command reads  like this: "Total Tests: N" …where N
    # is the number of registered tests. Fetch this integer from stdout and on-
    # ly run ctest for real, if tests were registered using add_test().
    num = c.countTests()
    if (num > 0):
        rc = mmh.loggedProcess(cfg, log, c.test())
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

def maybeInstall(cfg, log, stats, instance):
    if (instance['install'] == False):
        return True

    cmd = c.install()
    rc = mmh.loggedProcess(cfg, log, cmd)
    stats.logInstall(rc)
    return (rc == 0)

def build(cfg, log, args, stats, ext, root, instance):
    dname = instanceDirectory(stats, instance)
    dnamefull = os.path.join(root, 'build', dname)
    if (os.path.exists(dnamefull)):
        log.info("Instance directory exists: {}".format(dnamefull))
        cleanInstance(log, dnamefull)
    else:
        os.makedirs(dnamefull)
    os.chdir(dnamefull)
    (cmakeConfigure(cfg, log, args, stats, ext, root, instance) and
     cmakeBuild(cfg, log, stats, instance)                      and
     cmakeTest(cfg, log, stats, instance)                       and
     maybeInstall(cfg, log, stats, instance))
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
    m = re.match('([^/]+)/([^/]+)/([^/]+)/([^/]+)', directory)
    if (m is None):
        log.warning("Not a build-instance directory: {}".format(directory))
        return
    olddir = os.getcwd()
    root = os.path.join(olddir, args.directory)
    directory = os.path.join(root, 'build', directory)
    cleanInstance(log, directory)
    (toolchain, architecture, buildconfig, buildtool) = m.groups()
    tc = findToolchain(args.toolchainPath, toolchain)
    cmakeArgs = []
    if (args.cmake is not None):
        cmakeArgs = args.cmake
    log.info("Moving to build-instance {}".format(directory))
    os.chdir(directory)
    # TODO: Leaving this for now. This whole procedure is a little weird, since
    #       is reimplements a lot of the normal operation of mmh's module build
    #       facility. Except that zephyr based builds won't work. Soooo, this
    #       should probably use the normal code paths too.
    cmd = ['cmake',
           '-G{}'.format(cmakeBuildtool(buildtool)),
           '-DCMAKE_TOOLCHAIN_FILE={}'.format(tc),
           '-DCMAKE_BUILD_TYPE={}'.format(buildconfig),
           '-DPROJECT_TARGET_CPU={}'.format(architecture)
           ] + cmakeArgs + [root]
    rc = mmh.loggedProcess(cfg, log, cmd)
    if (rc != 0):
        log.warning("CMake failed for {}".format(directory))
        log.info("Moving back to {}".format(olddir))
        os.chdir(olddir)
        return
    rc = mmh.loggedProcess(cfg, log, c.compile())
    if (rc != 0):
        log.warning("Build-process failed for {}".format(directory))
        log.info("Moving back to {}".format(olddir))
        os.chdir(olddir)
        return
    num = c.countTests()
    if (num > 0):
        rc = mmh.loggedProcess(cfg, log, c.test())
        if (rc != 0):
            log.warning("Test-suite failed for {}".format(directory))
    log.info("Moving back to {}".format(olddir))
    os.chdir(olddir)
