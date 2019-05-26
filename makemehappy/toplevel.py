defaultCMakeVersion = "3.1.0"
defaultProjectName = "MakeMeHappy"
defaultLanguages = "C CXX ASM"

def generateHeader(fh):
    for s in ["cmake_minimum_required(VERSION 3.1.0)".format(defaultCMakeVersion),
              "project({} {})".format(defaultProjectName, defaultLanguages)]:
        print(s, file = fh)

def generateCMakeModulePath(fh):
    print('list(APPEND CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}/code-under-test/cmake/modules")', file = fh)

def generateTestHeader(fh):
    print("include(CTest)", file = fh)
    print("enable_testing()", file = fh)

def generateDependencies(fh):
    print("include(Libtap)", file = fh)
    print("add_libtap(deps/libtap)", file = fh)

def generateFooter(fh):
    print("add_subdirectory(code-under-test)", file = fh)

def generateToplevel(log, cfg, src, fname):
    with open(fname, 'w') as fh:
        generateHeader(fh)
        generateCMakeModulePath(fh)
        generateTestHeader(fh)
        generateDependencies(fh)
        generateFooter(fh)
