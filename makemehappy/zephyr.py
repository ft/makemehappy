import os

import makemehappy.utilities as mmh

def isModule(d):
    return (os.path.isdir(d) and
            os.path.isdir(os.path.join(d, 'zephyr')))

def findModule(path, name):
    for d in path:
        candidate = os.path.join(d, name)
        if (isModule(candidate)):
            return candidate
    return { 'UnknownModule': name }

def generateModules(path, names):
    realpath = [ mmh.expandFile(x) for x in path ]
    modules = [ findModule(realpath, m) for m in names ]
    return modules

def toolchainMatch(tc, name):
    if (isinstance(tc, str)):
        if (tc == name):
            return True
    elif (tc['name'] == name):
        return True
    return False

def findBuild(builds, tc, board):
    for build in builds:
        if board in build['boards']:
            for toolchain in build['toolchains']:
                if (toolchainMatch(toolchain, tc)):
                    return build
    return None

def findToolchain(build, tc):
    for toolchain in build['toolchains']:
        if (toolchainMatch(toolchain, tc)):
            return toolchain
    return None

def findTransformer(ufw, cfg):
    name = cfg.lower()
    transformer = os.path.join(mmh.expandFile(ufw),
                               'cmake', 'kconfig',
                               cfg + '.conf')
    if (os.path.exists(transformer)):
        return transformer
    return None
