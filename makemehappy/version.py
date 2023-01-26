import re

class InvalidVersion(Exception):
    pass

class Version:
    def __init__(self, s):
        self.seps = re.compile('[-:/!_]')
        self.dots = re.compile('[.]')
        self.prefix = None
        self.suffix = None
        self.elements = None
        self.kind = None
        self.string = s

        if (s == None):
            return

        self.matcher = re.match(r'^[0-9A-Fa-f]+$', s)
        if (self.matcher != None):
            self.kind = 'hex'
            return

        self.matcher = re.match(r'([^0-9]*)([0-9]+\.([0-9]+\.?)*)(.*)', s)
        if (self.matcher != None):
            self.kind = 'version'
            self.elements = re.split(self.dots, self.matcher.group(2))
            self.prefix = list(
                filter(lambda x: x != '',
                       re.split(self.seps, self.matcher.group(1))))
            self.suffix = list(
                filter(lambda x: x != '',
                       re.split(self.seps, self.matcher.group(4))))
            if ('' in self.elements):
                raise InvalidVersion(s,
                                     self.prefix,
                                     self.elements,
                                     self.suffix)
            return

        self.kind = 'symbol'

    def render(self):
        if (self.kind == 'version'):
            return '.'.join(self.elements)
        elif (self.kind in ['hex', 'symbol']):
            return self.string
        else:
            return None
