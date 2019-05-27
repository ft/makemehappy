import os
import subprocess

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
        for cfg in cfgs:
            for tool in tools:
                instances.append({ 'toolchain': maybeToolchain(tc),
                                   'architecture': maybeArch(tc),
                                   'interface': maybeInterface(tc),
                                   'buildcfg': cfg,
                                   'buildtool': tool })
    return instances

def instanceDirectory(instance):
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

def cmakeConfigure(ext, root, instance):
    subprocess.run(['cmake',
                    '-G{}'.format(cmakeBuildtool(instance['buildtool'])),
                    '-DCMAKE_TOOLCHAIN_FILE={}'.format(
                        findToolchain(ext, instance['toolchain'])),
                    '-DCMAKE_BUILD_TYPE={}'.format(instance['buildcfg']),
                    '-DPROJECT_TARGET_CPU={}'.format(instance['architecture']),
                    '-DINTERFACE_TARGET={}'.format(instance['interface']),
                    root])

def cmakeBuild(instance):
    subprocess.run(['cmake', '--build', '.'])

def cmakeTest(instance):
    subprocess.run(['ctest', '-VV'])

def build(ext, root, instance):
    dname = instanceDirectory(instance)
    dnamefull = os.path.join(root, 'build', dname)
    os.mkdir(dnamefull)
    os.chdir(dnamefull)
    cmakeConfigure(ext, root, instance)
    cmakeBuild(instance)
    cmakeTest(instance)
    os.chdir(root)

def allofthem(mod, ext):
    olddir = os.getcwd()
    instances = generateInstances(mod)
    for instance in instances:
        build(ext, olddir, instance)
