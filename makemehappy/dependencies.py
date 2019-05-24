import os
import subprocess

import makemehappy.utilities as mmh

class Trace:
    def __init__(self, init):
        self.data = init

    def has(self, needle):
        return (needle in (entry[0] for entry in self.data))

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
        subprocess.run(['git', 'clone', source, p])
        # TODO: Need to check out the right revision!

        if (os.path.isfile(p)):
            newdeps = mmh.load()
            for newdep in newdeps:
                if (trace.has(newdep['name']) == False):
                    st.push(newdep)

        st.delete(dep['name'])

    # And recurse with the new stack and trace; we're done when the new stack
    # is empty.
    return fetch(log, src, st, trace)
