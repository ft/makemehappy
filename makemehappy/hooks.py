import re

class Hook:
    def __init__(self, pattern, callback):
        self.pattern = pattern
        self.callback = callback

    def is_applicable(self, kind):
        return re.match(self.pattern, kind)

    def run(self, kind, **kwargs):
        self.callback(kind, **kwargs)

class UnknownHook(Exception):
    pass

class Registry:
    def __init__(self):
        self.hooks = []

    def register(self, pattern, *cbs):
        for cb in cbs:
            self.hooks.append(Hook(pattern, cb))

    def run(self, kind, **kwargs):
        for hook in self.hooks:
            if hook.is_applicable(kind):
                hook.run(kind, **kwargs)

hooks = Registry()

def checkpoint_hook(cp, **kwargs):
    hooks.run(f'checkpoint/{cp}', **kwargs)

def phase_hook(phase, **kwargs):
    hooks.run(f'phase/{phase}', **kwargs)

def startup_hook(**kwargs):
    checkpoint_hook('startup', **kwargs)

def finish_hook(**kwargs):
    checkpoint_hook('finish', **kwargs)
