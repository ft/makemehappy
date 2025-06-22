import makemehappy.utilities as mmh

from pathlib import Path

def verifyMode(sources):
    if len(sources) == 0:
        return 'default'
    if all(s.is_dir() == False for s in sources):
        return 'files'
    if all(s.is_dir() == True for s in sources):
        return 'directories'
    return 'invalid'

def verifyDirectory(log, args, d):
    rv = True
    bn = args.basename
    for variant in [ 'md5', 'sha256', 'sha512' ]:
        basename = bn + '.' + variant
        checksumfile = Path(d) / basename
        print(f'  Verifying checksums: {str(basename)}...', end = '')
        failed = mmh.checksumVerify(checksumfile,
                                    root = d,
                                    variant = variant)
        if len(failed) > 0:
            rv = False
            print(' failed!')
            errors.append((None, variant, failed))
        else:
            print(' ok.')
    return rv


def verifyDirectories(log, args, sources):
    rv = True
    for src in sources:
        print(f'Checking {src}...')
        current = verifyDirectory(log, args, src)
        rv = rv and current
    return rv

def verifyFile(log, args, file):
    errors = mmh.checksumVerify(file, root = args.root_directory)
    return len(errors) == 0

def verifyFiles(log, args, sources):
    rv = True
    for src in sources:
        current = verifyFile(log, args, src)
        print(f'Checking {src}...', 'ok' if current else 'failed')
        rv = rv and current
    return rv

def mmh_verify(log, args):
    sources = list(map(Path, args.sources))
    mode = verifyMode(sources)
    # mode can be one of:
    #
    # - default: Called without parameters
    # - files: One or more files as parameters
    # - directories: One or more directories as parameters.
    # - invalid: Directories and files mixed.
    if mode == 'invalid':
        log.error('verify: Invalid parameters, ' +
                  'cannot mix files and directories.')
        return False
    if mode == 'default':
        mode = 'directories'
        sources = [ Path('.') ]

    # Now mode is either 'directories' or 'files'.
    if mode == 'files':
        return verifyFiles(log, args, sources)
    return verifyDirectories(log, args, sources)
