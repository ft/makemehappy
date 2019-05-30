defaultCMakeVersion = "3.1.0"
defaultProjectName = "MakeMeHappy"
defaultLanguages = "C CXX ASM"

def generateHeader(fh):
    for s in ["cmake_minimum_required(VERSION 3.1.0)".format(defaultCMakeVersion),
              "project({} {})".format(defaultProjectName, defaultLanguages)]:
        print(s, file = fh)

def generateCMakeModulePath(fh, moddirs):
    for p in moddirs:
        print("list(APPEND CMAKE_MODULE_PATH \"{}\")".format(p), file = fh)

def generateTestHeader(fh):
    # TODO: Check if it's benign to have this in unconditionally
    print("include(CTest)", file = fh)
    print("enable_testing()", file = fh)

def generateDependencies(fh, deps, thirdParty):
    for dep in deps:
        name = dep['name']
        if (name in thirdParty):
            print("include({})".format(thirdParty[name]['module']), file = fh)
            print("{}(deps/{})".format(thirdParty[name]['include'],
                                       name),
                  file = fh)
        else:
            print("add_subdirectory(deps/{})".format(name), file = fh)

def generateFooter(fh):
    print("message(STATUS \"Configured interface: ${INTERFACE_TARGET}\")",
          file = fh)
    print("add_subdirectory(code-under-test)", file = fh)

def isTLDep(cud, needle):
    return (needle in (entry['name'] for entry in cud))

def mergeDependencies(cud, further):
    rest = list((x for x in further if not(isTLDep(cud, x['name']))))
    return cud + rest

def generateToplevel(log, cfg, src, trace, ext, mod, fname):
    with open(fname, 'w') as fh:
        generateHeader(fh)
        generateCMakeModulePath(fh, ext.modulePath())
        generateTestHeader(fh)
        tp = {}
        for entry in trace.data:
            if ('cmake-third-party' in entry):
                tp = { **tp, **entry['cmake-third-party'] }
        tp = { **tp, **mod.cmake3rdParty() }
        generateDependencies(fh,
                             mergeDependencies(mod.dependencies(),trace.deps()),
                             tp)
        generateFooter(fh)
