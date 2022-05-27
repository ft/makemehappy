import makemehappy.utilities as mmh

def buildtool(log, name):
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
    return makeParam('CMAKE_EXPORT_COMPILE_COMMANDS', 'on'),

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

def configureZephyr(log, args,
                    board, buildtool, buildconfig, buildsys,
                    tc, sourcedir, builddir, installdir,
                    kconfig, modulepath, modules, ufw):
    modules = genZephyrModules(modulepath, modules)
    overlay = [ findZephyrTransformer(ufw, buildconfig) ] + kconfig

    if (kconfig != None):
        overlay.extend(kconfig)

    cmd = [ buildtool(log, buildtool),
            sourceDir(sourcedir),
            binaryDir(builddir),
            compileCommands(),
            zephyrToolchain(tc),
            makeParam('CMAKE_BUILD_TYPE',       buildconfig),
            makeParam('CMAKE_INSTALL_PREFIX',   installdir),
            makeParam('BOARD',                  board),
            makeParam('ZEPHYR_MODULES',         modules),
            makeParam('OVERLAY_CONFIG',         overlay),
            makeParam('UFW_ZEPHYR_KERNEL',      kernel),
            makeParam('UFW_ZEPHYR_APPLICATION', sourcedir),
            makeParam('UFW_LOAD_BUILD_SYSTEM',  buildsys) ]

    if (args != None):
        cmd.extend(args)

    return cmd
