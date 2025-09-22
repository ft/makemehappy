import mako.template as mako
import re

import makemehappy.utilities as mmh

defaultCMakeVersion = "3.12.0"
defaultProjectName = "MakeMeHappy"
defaultLanguages = "C CXX ASM"

def deprecatedTemplate(inc):
    return re.match(r'^[0-9a-z_]+$', inc) is not None

class InvalidVariant(Exception):
    pass

def lookupVariant(table, name):
    for key in table:
        if (isinstance(table[key], str)):
            regex = table[key]
            if re.match(regex, name) is not None:
                return key
        elif (isinstance(table[key], list)):
            if (name in table[key]):
                return key
        else:
            raise InvalidVariant(name, key, table[key])
    return name

def getMergedDict(data, what, more):
    d = {}
    for entry in data:
        if (what in entry):
            d = { **d, **entry[what] }
    return { **d, **more }

class Toplevel:
    def __init__(self, log, moduleType, var, targets, defaults, thirdParty,
                 cmakeVariants, zephyrBoardRoot, zephyrDTSRoot, zephyrSOCRoot,
                 modulePath, trace, deporder):
        self.log = log
        self.thirdParty = thirdParty
        self.cmakeVariants = cmakeVariants
        self.zephyrBoardRoot = zephyrBoardRoot
        self.zephyrDTSRoot = zephyrDTSRoot
        self.zephyrSOCRoot = zephyrSOCRoot
        self.trace = trace
        self.modulePath = modulePath
        self.moduleType = moduleType
        self.deporder = deporder
        self.variables = var
        self.targets = targets
        self.defaults = defaults
        self.filename = 'CMakeLists.txt'

    def generateHeader(self, fh):
        langs = defaultLanguages
        if (self.moduleType == 'zephyr'):
            langs = 'NONE'
        for s in ["cmake_minimum_required(VERSION {})".format(defaultCMakeVersion),
                "project({} {})".format(defaultProjectName, langs)]:
            print(s, file = fh)

    def generateCMakeModulePath(self, fh, moddirs):
        for p in moddirs:
            print("list(APPEND CMAKE_MODULE_PATH \"{}\")".format(p), file = fh)

    def generateZephyrInit(self, fh):
        if (self.moduleType == 'zephyr'):
            print('include(SetupUFW)', file = fh)
            print('ufw_toplevel(ROOT ${CMAKE_SOURCE_DIR}/deps/ufw)', file = fh)

    def generateTestHeader(self, fh):
        print("include(CTest)", file = fh)
        print("enable_testing()", file = fh)

    def expandIncludeTemplate(self, inc, name):
        moduleroot = 'deps/{}'.format(name)
        if deprecatedTemplate(inc):
            new = inc + '(${moduleroot})'
            self.log.warn(
                'Deprecated inclusion clause: "{}", use "{}" instead!'
                .format(inc, new))
            inc = new
        exp = mako.Template(inc).render(
            moduleroot = moduleroot,
            cmake = mmh.renderCMakeVariable)
        return exp

    def insertTemplate(self, fh, name, tp, variants, section, default = None):
        realname = name
        if (not name in tp):
            name = lookupVariant(variants, name)

        if (name in tp and section in tp[name]):
            tmpl = tp[name][section]
            if ('module' in tp[name] and ('included' not in tp[name])):
                tp[name]['included'] = True
                print("include({})".format(tp[name]['module']), file = fh)
            if (isinstance(tmpl, str)):
                print(self.expandIncludeTemplate(tmpl, realname), file = fh)
        else:
            if default is not None:
                default(name)

    def generateVariables(self, fh, variables):
        for key in variables.keys():
            print('set({} "{}")'.format(key, variables[key]), file = fh)

    def generateDefaults(self, fh, defaults):
        for key in defaults.keys():
            print('if (NOT DEFINED {})'.format(key), file = fh)
            print('  set({} "{}")'.format(key, defaults[key]), file = fh)
            print('endif()', file = fh)

    def generateDependencies(self, fh, deps, thirdParty, variants):
        for item in deps:
            self.insertTemplate(fh, item, thirdParty, variants, 'basic')
        for item in deps:
            self.insertTemplate(fh, item, thirdParty, variants, 'include',
                                lambda name:
                                print("add_subdirectory(deps/{})".format(name),
                                      file = fh))
        for item in deps:
            self.insertTemplate(fh, item, thirdParty, variants, 'init')

    def generateFooter(self, fh):
        print("add_subdirectory(code-under-test)", file = fh)

    def generateZephyr(self, fh, boardroot, dtsroot, socroot):
        for entry in boardroot:
            print('list(APPEND BOARD_ROOT "{}")'.format(entry), file = fh)
        for entry in dtsroot:
            print('list(APPEND DTS_ROOT "{}")'.format(entry), file = fh)
        for entry in socroot:
            print('list(APPEND SOC_ROOT "{}")'.format(entry), file = fh)
        print('''
enable_language(C)
enable_language(CXX)
enable_language(ASM)''',
              file = fh)

    def generateToplevel(self):
        with open(self.filename, 'w') as fh:
            self.generateHeader(fh)
            self.generateCMakeModulePath(fh, self.modulePath)

            var = getMergedDict(self.trace.data, 'variables', self.variables)
            self.generateVariables(fh, var)

            defaults = getMergedDict(self.trace.data, 'defaults', self.defaults)
            self.generateDefaults(fh, defaults)

            self.generateZephyrInit(fh)
            self.generateTestHeader(fh)

            if (self.moduleType == 'zephyr'):
                self.generateZephyr(fh,
                                    self.zephyrBoardRoot,
                                    self.zephyrDTSRoot,
                                    self.zephyrSOCRoot)

            tp = getMergedDict(self.trace.data, 'cmake-extensions',
                               self.thirdParty)

            variants = getMergedDict(self.trace.data,
                                     'cmake-extension-variants',
                                     self.cmakeVariants)

            self.generateDependencies(fh, self.deporder, tp, variants)
            self.generateFooter(fh)
