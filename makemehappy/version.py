import re

class InvalidVersion(Exception):
    pass

def maybeTuple(i, a, b):
    an = len(a.elements)
    bn = len(b.elements)
    if (i < an and i < bn):
        return (a.elements[i], b.elements[i])
    elif (i < an):
        return (a.elements[i], None)
    elif (i < bn):
        return (None, b.elements[i])
    else:
        return (None, None)

class VersionComparison:
    def __init__(self):
        self.kind = None
        self.compatible = False
        self.elements = (None, None)
        self.major = (None, None)
        self.minor = (None, None)
        self.patch = (None, None)

    def compare(self, a, b):
        self.elements = (a.elements, b.elements)

        an = len(a.elements)
        bn = len(b.elements)

        if (an == bn):
            self.compatible = True

        for i in range(0, min(an, bn, 3)):
            if (i == 0):
                self.major = maybeTuple(i, a, b)
            elif (i == 1):
                self.minor = maybeTuple(i, a, b)
            elif (i == 2):
                self.patch = maybeTuple(i, a, b)

        for i in range(0, min(an, bn)):
            if (a.elements[i] != b.elements[i]):
                if (i == 0):
                    self.kind = 'major'
                    break
                elif (i == 1):
                    self.kind = 'minor'
                    break
                elif (i == 2):
                    self.kind = 'patch'
                    break
                else:
                    self.kind = 'miniscule'
                    break

        if (self.kind == None):
            if (self.compatible):
                self.kind = 'same'
            else:
                self.kind = 'same-ish'

def compare(a, b):
    result = VersionComparison()
    result.compare(a, b)
    return result

class Version:
    def __init__(self, s, origin = None):
        self.seps = re.compile('[-:/!_]')
        self.dots = re.compile('[.]')
        self.prefix = None
        self.suffix = None
        self.elements = None
        self.kind = None
        self.string = s
        self.origin = origin

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

    def __lt__(self, other):
        return (self.string < other.string)

    def render(self):
        if (self.kind == 'version'):
            return '.'.join(self.elements)
        elif (self.kind in ['hex', 'symbol']):
            return self.string
        else:
            return None
