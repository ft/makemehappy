import re

import makemehappy.utilities as mmh

def toplevel(path):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'rev-parse', '--show-toplevel'])
    return stdout if (rc == 0) else None

def isWorktree(path):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'rev-parse', '--is-inside-work-tree'])
    return (rc == 0) and (stdout == 'true')

def isDirty(path):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'status', '--porcelain=v1'])
    return (rc == 0) and (stdout != '')

def latestTag(path, pattern):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path,
         'describe', '--tags', '--abbrev=0', '--match=' + pattern])
    return stdout if (rc == 0) else None

def commitsSinceTag(path, tag):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'rev-list', '--count', f'{tag}..HEAD'])
    return int(stdout) if (rc == 0) else None

def commitHash(path, commit = 'HEAD'):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'rev-parse', commit])
    return stdout if (rc == 0) else None

def _authorish(path, getname, getmail, commit):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'show', '--quiet',
         f'--format=%{getname}\n%{getmail}', commit])

    if (rc == 0):
        rv = stdout.split('\n')
        return (rv[0], rv[1])

    return None

def author(path, commit = 'HEAD'):
    return _authorish(path, 'an', 'ae', commit)

def committer(path, commit = 'HEAD'):
    return _authorish(path, 'cn', 'ce', commit)

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
