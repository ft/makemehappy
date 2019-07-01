import makemehappy.utilities as mmh

defaultCMakeVersion = "3.1.0"
defaultProjectName = "MakeMeHappy"
defaultLanguages = "C CXX ASM"

def generateHeader(fh):
    for s in ["cmake_minimum_required(VERSION {})".format(defaultCMakeVersion),
              "project({} {})".format(defaultProjectName, defaultLanguages)]:
        print(s, file = fh)

def generateCMakeModulePath(fh, moddirs):
    for p in moddirs:
        print("list(APPEND CMAKE_MODULE_PATH \"{}\")".format(p), file = fh)

def generateTestHeader(fh):
    print("include(CTest)", file = fh)
    print("enable_testing()", file = fh)

def insertInclude(fh, name, tp):
    if (name in tp):
        inc = tp[name]['include']
        if (isinstance(inc, str)):
            print("include({})".format(tp[name]['module']), file = fh)
            print("{}(deps/{})".format(inc, name), file = fh)
    else:
        print("add_subdirectory(deps/{})".format(name), file = fh)

def generateDependencies(fh, deps, thirdParty):
    for item in deps:
        insertInclude(fh, item, thirdParty)

def generateFooter(fh):
    print("message(STATUS \"Configured interface: ${INTERFACE_TARGET}\")",
          file = fh)
    print("add_subdirectory(code-under-test)", file = fh)

def isTLDep(cut, needle):
    return (needle in (entry['name'] for entry in cut))

def mergeDependencies(cut, further):
    rest = list((x for x in further if not(isTLDep(cut, x['name']))))
    return cut + rest

class Toplevel:
    def __init__(self, log, thirdParty, modulePath, trace, deporder):
        self.log = log
        self.thirdParty = thirdParty
        self.trace = trace
        self.modulePath = modulePath
        self.deporder = deporder
        self.filename = 'CMakeLists.txt'

    def generateToplevel(self):
        with open(self.filename, 'w') as fh:
            generateHeader(fh)
            generateCMakeModulePath(fh, self.modulePath)
            generateTestHeader(fh)
            tp = {}
            for entry in self.trace.data:
                if ('cmake-extensions' in entry):
                    tp = { **tp, **entry['cmake-extensions'] }
            tp = { **tp, **self.thirdParty }
            generateDependencies(fh, self.deporder, tp)
            generateFooter(fh)
