# Fetching dependencies. Here is the plan:
#
# - Fetch all dependencies.
# - Check out the desired revision.
# - Record all these module/revision pairs.
#
# Then do the same  for all the dependencies for the  previous level of de-
# pendencies. Lower  level modules do  not get  to change the  revision re-
# quirements of higher level modules.  However, harsh conflicts can trigger
# warnings and errors:
#
# - If the major version of a module differs between two modules requesting
#   the same  dependency, this will almost  certain break the build  and an
#   error will  be triggered. An option  should make it possible  to demote
#   these errors to warnings.
#
# - Similarly, with  minor versions, there is  a chance that a  build might
#   pass despite the mismatch. So conditions like that trigger warnings. An
#   option should make it possible to promote such warnings to errors.
#
# - Mismatches  in patch  levels  of a  semantic  versioning triplet,  will
#   likely work out. These conditions  will merely trigger an informational
#   notice during operation.  There should, again, be an  option to promote
#   situations such as this to warnings or even errors.
#
# While fetching dependencies like this,  keep a dictionary of modules that
# where pulled in as dependencies and map them to lists of pairs:
#
#     (dependant revision)
#
# This  way, after  all dependencies  have been  pulled in,  it is  easy to
# assess whether or  not one of the mismatch  conditions, detailed earlier,
# are met.
#
# To determine  a bottom case for  the recursive nature of  this algorithm,
# keep a stack of dependencies that still need to be processed. Add to that
# stack each time the recursion shifts  to the next level of the dependency
# tree. Only add modules to that stack,  if they have not yet been fetched.
# Pop off modules from that stack as soon as they have been fetched. Opera-
# tion has finished when the stack runs empty.
#
# The entry into the recursion is  a stack filled with (dependant revision)
# pairs from the  CodeUnderTest top-level module. These  pairs also initia-
# lise the dependency dictionary as well.
import os
import subprocess

import makemehappy.utilities as mmh

def extendPath(root, lst, datum):
    new = os.path.join(root, datum)
    if (isinstance(datum, str)):
        lst.append(new)
    elif (isinstance(datum, list)):
        lst.extend(new)
    else:
        raise(Exception())

class CMakeExtensions:
    def __init__(self, mod, trace):
        self.modulepath = []
        self.toolchainpath = []
        midx = 'cmake-modules'
        tidx = 'cmake-toolchains'
        if (midx in mod.data):
            extendPath(mod.data['root'], self.modulepath, mod.data[midx])
        if (tidx in mod.data):
            extendPath(mod.data['root'], self.toolchainpath, mod.data[tidx])
        for entry in trace.data:
            if (midx in entry):
                extendPath(entry['root'], self.modulepath, entry[midx])
            if (tidx in entry):
                extendPath(entry['root'], self.toolchainpath, entry[tidx])

    def modulePath(self):
        return self.modulepath

    def toolchainPath(self):
        return self.toolchainpath

class Trace:
    def __init__(self):
        self.data = []

    def has(self, needle):
        return (needle in (entry['name'] for entry in self.data))

    def deps(self):
        return list((({'name': entry['name'],
                       'revision': entry['version'] } for entry in self.data)))

    def push(self, entry):
        self.data = [entry] + self.data

class Stack:
    def __init__(self, init):
        self.data = init

    def empty(self):
        return (len(self.data) == 0)

    def delete(self, needle):
        self.data = list((x for x in self.data
                          if (lambda y: y['name'] != needle)(x)))

    def push(self, entry):
        self.data = [entry] + self.data

def fetch(log, src, st, trace):
    if (st.empty() == True):
        return trace

    for dep in st.data:
        log.info("Fetching revision {} of module {}"
                 .format(dep['revision'], dep['name']))
        if ('source' in dep.keys()):
            source = dep['source']
        else:
            source = src.lookup(dep['name'])['repository']

        if (source == False):
            log.error("Module {} has no source!".format(dep['name']))
            return False

        p = os.path.join('deps', dep['name'])
        newmod = os.path.join(p, 'module.yaml')
        subprocess.run(['git', 'clone',
                        source, p])

        # Check out the requested revision
        olddir = os.getcwd()
        os.chdir(p)
        subprocess.run(['git', 'checkout', dep['revision']])
        os.chdir(olddir)

        newmodata = None
        if (os.path.isfile(newmod)):
            newmodata = mmh.load(newmod)
            newmodata['version'] = dep['revision']
        else:
            newmodata = {}
            newmodata['name'] = dep['name']
            newmodata['version'] = dep['revision']

        if not('dependencies' in newmodata):
            newmodata['dependencies'] = []

        trace.push(newmodata)
        for newdep in newmodata['dependencies']:
            if (trace.has(newdep['name']) == False):
                st.push(newdep)

        st.delete(dep['name'])

    # And recurse with the new stack and trace; we're done when the new stack
    # is empty.
    return fetch(log, src, st, trace)
