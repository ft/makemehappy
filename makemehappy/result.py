import re

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

def show(cfg, args):
    input = args.file[0]
    table = []
    lastline = None

    for line in open(input):
        lastline = line
        if (re.match(marker, line)):
            entry = re.sub(strip, '', line)
            table = [ entry ]
        elif (len(table) > 0):
            entry = re.sub(strip, '', line)
            table += [ entry ]
        if (args.full_result and len(table) == 0):
            stripped = re.sub(strip, '', line)
            print(stripped, end='')

    lastline = re.sub(strip, '', lastline)
    if (re.match(nobuild, lastline)):
        print(lastline, end = '')
        return True

    if (len(table) < 2):
        if (args.quiet_result == False):
            print('Could not find result table in log: {}'.format(input))
            print('Scanning for ERROR markers:')
            for line in open(input):
                entry = re.sub(stripSome, '', line)
                if (re.match(error, entry)):
                    print(entry, end = '')
        return False

    lst = table[-2:]

    if (args.quiet_result == False):
        if (args.short_result == False):
            for line in table:
                print(line, end='')
        else:
            printMatches(lst, outcome)
            if (cfg.lookup('fatal-dependencies')):
                printMatches(lst, deperror)

    buildSuccess = any(map(lambda x: re.match(success, x), lst))
    depSuccess = True
    if (cfg.lookup('fatal-dependencies')):
        depSuccess = not any(map(lambda x: re.match(deperror, x), lst))

    return (buildSuccess and depSuccess)
