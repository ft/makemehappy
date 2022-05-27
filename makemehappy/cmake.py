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

def cmake(lst):
    return [ 'cmake' ] + [ x for x in mmh.flatten(lst) if x != None ]

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
