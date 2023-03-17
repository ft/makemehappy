import bz2
import gzip
import lzma
import re

import makemehappy.utilities as mmh

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
    result = Result(cfg, args)

    if (cfg.lookup('page-output')):
        mmh.pager(cfg, result.run)
    else:
        result.run()

    return result.result
