import os
import subprocess

class Trace:
    def __init__(self, init):
        self.data = init

class Stack:
    def __init__(self, init):
        self.data = init

    def empty(self):
        return (len(self.data) == 0)

    def has(self, needle):
        return (needle in (entry[0] for entry in self.data))

    def delete(self, needle):
        self.data = list((x for x in self.data
                          if (lambda y: y['name'] != needle)(x)))

    def push(self, entry):
        self.data = [entry] + self.data

def fetch(log, st, trace):
    if (st.empty() == True):
        return trace

    for dep in st.data:
        log.info("Fetching revision {} of module {}"
                 .format(dep['revision'], dep['name']))
        # TODO: Actually fetch! Then read module.yaml; and push new dependen-
        #       cies to nst. Only new ones, though. Check trace for dependen-
        #       cies that have been processed already. All dependencies from
        #       all module.yaml files are added to trace.
        if ('source' in dep.keys()):
            subprocess.run(['git', 'clone',
                            dep['source'],
                            os.path.join('deps', dep['name'])])
        st.delete(dep['name'])

    # And recurse with the new stack and trace; we're done when the new stack
    # is empty.
    fetch(log, st, trace)
