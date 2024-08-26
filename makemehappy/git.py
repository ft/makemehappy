import re

import makemehappy.utilities as mmh

def latestTag(path, pattern):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path,
         'describe', '--always', '--abbrev=12', '--match=' + pattern])
    if (rc != 0):
        return None
    return re.sub(r'-\d+-g?[0-9a-fA-F]+$', '', stdout)

def remoteHasBranch(rev):
    rc = mmh.devnullProcess(['git', 'rev-parse', '--verify', 'origin/' + rev])
    return (rc == 0)

def detectRevision(log, path):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path,
         'describe', '--always', '--abbrev=12', '--exact-match'])
    if (rc == 0):
        return stdout
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'rev-parse', '--abbrev-ref', 'HEAD'])
    if (rc == 0 and stdout != 'HEAD'):
        return stdout
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'rev-parse', 'HEAD'])
    if (rc == 0):
        return stdout
    log.info("Could not determine repository state: {}".format(stderr))
    return None
