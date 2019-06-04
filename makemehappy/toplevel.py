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
        print("include({})".format(tp[name]['module']), file = fh)
        print("{}(deps/{})".format(tp[name]['include'], name), file = fh)
    else:
        print("add_subdirectory(deps/{})".format(name), file = fh)

def isSatisfied(deps, done, name):
    lst = list(x['name'] for x in deps[name])
    for dep in lst:
        if not(dep in done):
            return False
    return True

def generateDependencies(fh, deps, thirdParty):
    lst = list(deps.keys())
    none = list(name for name in lst if (len(deps[name]) == 0))

    for entry in none:
        insertInclude(fh, entry, thirdParty)

    done = none
    rest = list(name for name in lst if (len(deps[name]) > 0))

    while (len(rest) > 0):
        lastdone = len(done)
        for item in rest:
            if (isSatisfied(deps, done, item)):
                insertInclude(fh, item, thirdParty)
                done = [item] + done
                rest = list(x for x in rest if (x != item))
        newdone = len(done)
        if (newdone == lastdone):
            # Couldn't take a single item off of the rest in the last
            # iteration. That means that dependencies can't be satisfied.
            raise Exception()

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
        generateDependencies(fh, trace.modDependencies(), tp)
        generateFooter(fh)
