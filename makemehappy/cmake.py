import os
import subprocess

import makemehappy.utilities as mmh
import makemehappy.zephyr as z

def usetool(log, name):
    std = 'Ninja'
    tool = ''
    if (name == 'make'):
        tool = 'Unix Makefiles'
    elif (name == 'ninja'):
        tool = 'Ninja'
    else:
        log.warn('Unknown build-tool {} defaulting to {}'.format(name, std))
        tool = std
    return '-G{}'.format(tool)

def sourceDir(d):
    return [ '-S' , d ]

def binaryDir(d):
    return [ '-B' , d ]

def compileCommands():
    return makeParam('CMAKE_EXPORT_COMPILE_COMMANDS', 'on')

def makeList(lst):
    return ';'.join([x for x in lst if x != None])

def makeParam(name, value, allowEmpty = False):
    exp = ''
    if (isinstance(value, str)):
        exp = value
    elif (isinstance(value, list)):
        exp = makeList(value)
    else:
        return None

    if (allowEmpty == False and exp == ''):
        return None

    return '-D{}={}'.format(name, exp)

def zephyrToolchain(spec):
    real = None
    if (isinstance(spec, str)):
        real = { 'name' : spec, 'path' : None }
    elif (isinstance(spec, dict)):
        real = spec
    ztv = [ makeParam('ZEPHYR_TOOLCHAIN_VARIANT', real['name']) ]
    if (real['name'] == 'gnuarmemb'):
        ztv.extend([ makeParam('GNUARMEMB_TOOLCHAIN_PATH', real['path']) ])
    return ztv

def commandWithArguments(cmd, lst):
    return [ cmd ] + [ x for x in mmh.flatten(lst) if x != None ]

def cmake(lst):
    return commandWithArguments('cmake', lst)

def maybeExtend(lst, scalar, default = '.'):
    if (scalar != None):
        lst.extend([scalar])
    else:
        lst.extend([default])
    return lst

def runTarget(target, directory = None):
    cmd = c.cmake([ '--build' ])
    maybeExtend(cmd, directory)
    cmd.extend(['--target', target ])
    return cmd

def ctest(lst):
    return commandWithArguments('ctest', lst)

def configureZephyr(log, args, ufw,
                    board, buildtool, buildconfig, buildsystem,
                    toolchain, sourcedir, builddir, installdir,
                    appsource, kernel, kconfig, modulepath, modules):
    modules = z.generateModules(modulepath, modules)
    overlay = [ z.findTransformer(ufw, buildconfig) ]

    if (kconfig != None):
        overlay.extend(kconfig)

    cmd = cmake(
        [ usetool(log, buildtool),
          sourceDir(sourcedir),
          binaryDir(builddir),
          compileCommands(),
          zephyrToolchain(toolchain),
          makeParam('CMAKE_BUILD_TYPE',       buildconfig),
          makeParam('CMAKE_INSTALL_PREFIX',   installdir),
          makeParam('BOARD',                  board),
          makeParam('ZEPHYR_MODULES',         modules),
          makeParam('OVERLAY_CONFIG',         overlay),
          makeParam('UFW_ZEPHYR_KERNEL',      mmh.expandFile(kernel)),
          makeParam('UFW_ZEPHYR_APPLICATION', mmh.expandFile(appsource)),
          makeParam('UFW_LOAD_BUILD_SYSTEM',  mmh.expandFile(buildsystem)) ])

    if (args != None):
        cmd.extend(args)

    return cmd

def configureBoard(log, args, ufw,
                   board, buildtool, buildconfig, buildsystem,
                   toolchain, sourcedir, builddir, installdir):

    # TODO: We probably want a UFW class so we can access modules and
    #       extensions to cmake in a uniform manner in order to unify
    #       this way of determining the toolchain file and the more
    #       general way that is used in the build module to call the
    #       configureLibrary() function.
    tcfile = os.path.join(mmh.expandFile(ufw), 'cmake', 'toolchains',
                          '{}.cmake'.format(toolchain))

    cmd = cmake(
        [ usetool(log, buildtool),
          sourceDir(sourcedir),
          binaryDir(builddir),
          compileCommands(),
          makeParam('CMAKE_BUILD_TYPE',      buildconfig),
          makeParam('CMAKE_INSTALL_PREFIX',  installdir),
          makeParam('TARGET_BOARD',          board),
          makeParam('CMAKE_TOOLCHAIN_FILE',  tcfile),
          makeParam('UFW_LOAD_BUILD_SYSTEM', mmh.expandFile(buildsystem)) ])

    if (args != None):
        cmd.extend(args)

    return cmd

def configureLibrary(log, args,
                     buildtool, buildconfig, architecture,
                     toolchain, sourcedir, builddir):
    cmd = cmake(
        [ usetool(log, buildtool),
          sourceDir(sourcedir),
          binaryDir(builddir),
          compileCommands(),
          makeParam('CMAKE_BUILD_TYPE',      buildconfig),
          makeParam('PROJECT_TARGET_CPU',    architecture),
          makeParam('CMAKE_TOOLCHAIN_FILE',  toolchain) ])

    if (args != None):
        cmd.extend(args)

    return cmd

def compile(directory = None):
    cmd = cmake([ '--build' ])
    maybeExtend(cmd, directory)
    return cmd

def countTests(directory = None):
    cmd = ctest([ '--show-only', '--test-dir' ])
    maybeExtend(cmd, directory)
    txt = subprocess.check_output(cmd)
    last = txt.splitlines()[-1]
    return int(last.decode().split(' ')[-1])

def test(directory = None):
    cmd = ctest([ '--extra-verbose', '--test-dir' ])
    maybeExtend(cmd, directory)
    return cmd

def install(directory = None):
    cmd = cmake([ '--install' ])
    maybeExtend(cmd, directory)
    return cmd

def clean(directory = None):
    return runTarget('clean', directory)
