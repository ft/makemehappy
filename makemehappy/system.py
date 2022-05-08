import makemehappy.utilities as mmh

def makeZephyrVariants(zephyr):
    variants = []
    name = zephyr['application']
    for cfg in zephyr['build-configs']:
        for build in zephyr['build']:
            for tc in build['toolchains']:
                tcname = ''
                if (isinstance(tc, str)):
                    tcname = tc
                else:
                    tcname = tc['name']
                for board in build['boards']:
                    variants.extend(['zephyr/{}/{}/{}/{}'.format(
                        board, name, tcname, cfg)])
    return variants

def makeBoardVariants(board):
    variants = []
    for cfg in board['build-configs']:
        for tc in board['toolchains']:
            variants.extend(['boards/{}/{}/{}'.format(
                board['name'], tc, cfg)])
    return variants

def makeVariants(data):
    boards = []
    zephyr = []
    if ('zephyr' in data):
        for z in data['zephyr']:
            boards += makeZephyrVariants(z)
    if ('boards' in data):
        for b in data['boards']:
            boards += makeBoardVariants(b)
    rv = boards + zephyr
    rv.sort()
    return rv

def maybeCopy(thing, common, key):
    if (not key in thing and key in common):
        thing[key] = common[key]

def fill(thing, common):
    maybeCopy(thing, common, 'build-configs')

def fillData(data):
    if (not 'common' in data):
        return

    if ('zephyr' in data):
        for z in data['zephyr']:
            fill(z, data['common'])
    if ('boards' in data):
        for b in data['boards']:
            fill(z, data['common'])

class System:
    def __init__(self, log, cfg, args):
        self.log = log
        self.cfg = cfg
        self.args = args
        self.spec = 'system.yaml'

    def load(self):
        self.log.info("Loading system specification: {}".format(self.spec))
        self.data = mmh.load(self.spec)
        fillData(self.data)
        self.variants = makeVariants(self.data)

    def buildEverything(self):
        print("Not implemented yet")

    def buildVariants(self, variants):
        print("Not implemented yet")

    def build(self, variants):
        if (len(variants) == 0):
            self.log.info("Building full system.")
            self.buildEverything()
        else:
            self.log.info("Building selected variants:")
            for v in variants:
                self.log.info("  - {}".format(v))
            self.buildVariants(variants)

    def listVariants(self):
        self.log.info("Generating list of all system build variants:")
        for v in self.variants:
            print(v)
