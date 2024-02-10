import bz2
import gzip
import json
import lzma
import re

import itertools as it
import makemehappy.utilities as mmh

marker = re.compile(
    r'\[\d+-\d+-\d+\s+\d+:\d+:\d+.\d+\]\s+[A-Z]+:\s+MakeMeHappy:\s+Build\s+Summary:$')
strip = re.compile(
    r'\[\d+-\d+-\d+\s+\d+:\d+:\d+.\d+\]\s+[A-Z]+:\s+MakeMeHappy:\s')
stripSome = re.compile(
    r'\[\d+-\d+-\d+\s+\d+:\d+:\d+.\d+\]\s+')
s = r'All \d+ builds succeeded\.'
f = r'\d+ build\(s\) out of \d+ failed\.'

success = re.compile(s)
outcome = re.compile('(' + s + '|' + f + ')')
deperror = re.compile(r'Dependency Evaluation contained errors!')
error = re.compile('^ERROR: ')
nobuild = re.compile(r'Module type is \'nobuild\'\. Doing nothing\.')

def toolchain_to_category(tc):
    if tc.startswith('ti-'):
        return 'texas-instruments'
    if re.match('^.*clang', tc):
        return 'clang'
    return 'gnu'

# Data types being produced by scanners

def inc2dict(inc):
    return {
        'kind':      inc.kind,
        'file-name': inc.fname,
        'line':      inc.line,
        'column':    inc.column,
        'category':  inc.category,
        'text':      inc.text,
        'data':      inc.data,
    }

class Information:
    def __init__(self):
        self.data = []

    def push(self, line):
        return self.data.append(line)

class CompilerIncident(Information):
    def __init__(self, kind = None, fname = None,
                 line = None, column = None,
                 category = None, text = ""):
        super().__init__()
        self.kind = kind
        self.fname = fname
        self.line = line
        self.column = column
        self.category = category
        self.text = text

    def __hash__(self):
        rep = ""
        if self.kind is not None:
            rep += self.kind
        if self.fname is not None:
            rep += self.fname
        if self.line is not None:
            rep += str(self.line)
        if self.column is not None:
            rep += str(self.column)
        if self.category is not None:
            rep += self.category
        if self.text is not None:
            rep += self.text

        return hash(rep)

    def __eq__(self, other):
        return (self.kind     == other.kind     and
                self.fname    == other.fname    and
                self.line     == other.line     and
                self.column   == other.column   and
                self.category == other.category and
                self.text     == other.text)

    def __lt__(self, other):
        return (self.fname < other.fname)

# Scanner state

class ScannerState:
    # In full logs, we can determine the active toolchain from the phase marker
    # log entries. This allows us to dispatch to different sets of scanners
    # depending on our position in the log.
    def __init__(self, scanners):
        self.scanners = scanners
        self.name = 'prologue'
        self.toolchain = None
        self.current = None
        self.active = scanners['always']

    def updatePhase(self, phase, toolchain):
        self.name = 'active'
        self.toolchain = toolchain
        category = toolchain_to_category(toolchain)

        if phase == 'compile' and category in self.scanners['toolchain']:
            self.active = ([self.scanners['toolchain'][category]] +
                           self.scanners['always'])
        else:
            self.active = self.scanners['always']

    def reset(self):
        self.current = None

    def finish(self):
        self.name = 'epilogue'

# Scanner types

class Scanner:
    def __init__(self, regex):
        self.regex = re.compile(regex)
        self.result = None

    def match(self, line):
        return re.match(self.regex, line)

    def process(self, state, matchData, line):
        return state

    def done(self):
        return True

    def keep(self):
        return False

class ResultTableScanner(Scanner):
    def __init__(self):
        Scanner.__init__(self, r'^Build Summary:$')
    def process(self, state, matchData, line):
        state.finish()

class PhaseScanner(Scanner):
    def __init__(self):
        Scanner.__init__(self, r'^Phase: (([a-zA-Z0-9+_@-]+/)+[a-zA-Z0-9+_@-]+): ([a-zA-Z0-9+_@-]+)$')
    def process(self, state, matchData, line):
        part = matchData.group(1).split('/')
        phase = matchData.group(3)
        tc = None
        if len(part) == 4 and part[0] == 'boards':
            # system-build type board
            tc = part[2]
        elif len(part) == 5 and part[0] == 'zephyr':
            # system-build type zephyr
            tc = part[3]
        elif len(part) == 6 and (part[0] == 'zephyr' or part[0] == 'cmake'):
            # module build
            tc = part[3]
        if tc is not None:
            state.updatePhase(phase, tc)

class TexasInstrumentsCompilerScanner(Scanner):
    def __init__(self):
        Scanner.__init__(self, r'^"([^"]+)", line ([0-9]+): ([a-z]+): (.*)$')
    def process(self, state, matchData, line):
        (fname, line, kind, desc) = matchData.groups()
        self.result = CompilerIncident(kind, fname, line, None, None, desc)

class GnuCompilerScanner(Scanner):
    def __init__(self):
        Scanner.__init__(self, r'^([^:]+):([0-9]+):([0-9]+): ([a-z]+): (.*)$')
    def process(self, state, matchData, line):
        (fname, line, column, kind, desc) = matchData.groups()
        cat = None
        catm = re.match(r'^.*\[(-W[^]]+)\]$', desc)
        if catm is not None:
            cat = catm.group(1)
        self.result = CompilerIncident(kind, fname, line, column, cat, desc)


resultScanners = {
    'always': [ PhaseScanner(), ResultTableScanner() ],
    'toolchain': {
        # The single line format for clang and GNU are compatible. We only need
        # another scanner when we try to tackle the multiline-information as
        # well.
        'clang':             GnuCompilerScanner(),
        'gnu':               GnuCompilerScanner(),
        'texas-instruments': TexasInstrumentsCompilerScanner()
    }
}

# A scanner has these main methods:
#
#    match()     This checks if the scanner is interested in the input line.
#    process()   This method is called if the scanner is interested. It returns
#                a possibly updated ScannerState.
#    done()      Current line was consumed. Next line open to all scanners.
#    keep()      Current line was consumed. Next line confined to the current
#                scanner.
#
# If neither of the latter two methods return True, the current line was NOT
# consumed. Run all scanners against it right now.

def runScanner(state, matchData, line):
    scanner = state.current
    scanner.process(state, matchData, line)

    if scanner.done():
        state.reset()
        return scanner.result

    if scanner.keep():
        return None

    state.reset()
    return scanLine(state, line)

# The scanLine() function runs active scanners against a line of logfile text.
# This is a little more complicated than one would initially think. The reason
# for this is the fact that a piece of diagnostic information may span more
# than one line of text.
def scanLine(state, line):
    if state.current is not None:
        return runScanner(state, None, line)

    for scanner in state.active:
        matchData = scanner.match(line)
        if matchData is not None:
            state.current = scanner
            return runScanner(state, matchData, line)

    return None

def scan(scanners, fname, accumulate = True):
    data = []
    state = ScannerState(scanners)

    # The scan function runs the scanning state machine for every line of
    # input. This strips some common prefix, and behaves a little different,
    # depending on whether or not the accumulate bit is active.
    for line in multiOpen(fname):
        if state.name == 'epilogue':
            break
        text = re.sub(strip, '', line)
        result = scanLine(state, text)
        if result is not None:
            if accumulate:
                data.append(result)
            else:
                print(text, end = '')

    return data if accumulate else True

def multiOpen(fn: str):
    if (fn.endswith('.xz') or fn.endswith('.lzma')):
        return lzma.open(fn, mode = 'rt')
    if (fn.endswith('.bz2')):
        return bz2.open(fn, mode = 'rt')
    if (fn.endswith('.gz') or fn.endswith('.z')):
        return gzip.open(fn, mode = 'rt')
    return open(fn)

def printMatches(lst, pattern):
    for line in lst:
        if (re.match(pattern, line)):
            print(line, end = '')

class Result:
    def __init__(self, cfg, args):
        self.cfg = cfg
        self.args = args
        self.result = False

    def run(self):
        input = self.args.file[0]
        table = []
        lastline = None

        for line in multiOpen(input):
            lastline = line
            if (re.match(marker, line)):
                entry = re.sub(strip, '', line)
                table = [ entry ]
            elif (len(table) > 0):
                entry = re.sub(strip, '', line)
                table += [ entry ]
            if (self.args.full_result and len(table) == 0):
                stripped = re.sub(strip, '', line)
                print(stripped, end='')

        lastline = re.sub(strip, '', lastline)
        if (re.match(nobuild, lastline)):
            print(lastline, end = '')
            self.result = True
            return

        if (len(table) < 2):
            if (self.args.quiet_result == False):
                print('Could not find result table in log: {}'.format(input))
                print('Scanning for ERROR markers:')
                for line in multiOpen(input):
                    entry = re.sub(stripSome, '', line)
                    if (re.match(error, entry)):
                        print(entry, end = '')
            self.result = False
            return

        lst = table[-2:]

        if (self.args.quiet_result == False):
            if (self.args.short_result == False):
                for line in table:
                    print(line, end='')
            else:
                printMatches(lst, outcome)
                if (self.cfg.lookup('fatal-dependencies')):
                    printMatches(lst, deperror)

        buildSuccess = any(map(lambda x: re.match(success, x), lst))
        depSuccess = True
        if (self.cfg.lookup('fatal-dependencies')):
            depSuccess = not any(map(lambda x: re.match(deperror, x), lst))

        self.result = (buildSuccess and depSuccess)

def show(cfg, args):
    if (args.report_incidents or args.json_incidents or args.grep_result):
        logfile = args.file[0]
        if (args.report_incidents or args.json_incidents):
            # --report, --json
            uniq = set(scan(resultScanners, logfile))
            if args.json_incidents:
                data = list(map(inc2dict, uniq))
                print(json.dumps(data, sort_keys = True, indent = 4))
                return True
            data = it.groupby(sorted(uniq),
                              key = lambda x: x.fname)
            for piece in data:
                (fname, lst) = piece
                print(f'Incidents for {fname}:')
                for inc in sorted(lst, key = lambda x: x.line):
                    if inc.column is not None:
                        print(f'  {inc.line}:{inc.column}: {inc.kind}: {inc.text}')
                    else:
                        print(f'  {inc.line}: {inc.kind}: {inc.text}')

            n = len(uniq)
            if n == 0:
                print(f'No compiler incidents found.')
            else:
                print(f'\nFound {n} compiler incident(s).')
            return True
        # --grep
        return scan(resultScanners, logfile, accumulate = False)

    # Other options showing result tables and such.
    result = Result(cfg, args)

    if (cfg.lookup('page-output')):
        mmh.pager(cfg, result.run)
    else:
        result.run()

    return result.result
