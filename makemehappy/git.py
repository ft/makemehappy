import re

import makemehappy.utilities as mmh
import makemehappy.version as v

def toplevel(path = '.'):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'rev-parse', '--show-toplevel'])
    return stdout if (rc == 0) else None

def isWorktree(path):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'rev-parse', '--is-inside-work-tree'])
    return (rc == 0) and (stdout == 'true')

def isDirty(path):
    mmh.devnullProcess(['git', '-C', path, 'update-index', '-q', '--refresh'])
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path,
         'diff-index', '--name-only', 'HEAD', '--'])
    return (stdout != '')

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

def commitDateHuman(path, commit = 'HEAD'):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'show', '-s',
         '--date=format:%Y-%m-%d',
         '--format=%cd', commit])
    return stdout if (rc == 0) else None

def commitDateUnix(path, commit = 'HEAD'):
    (stdout, stderr, rc) = mmh.stdoutProcess(
        ['git', '-C', path, 'show', '-s', '--format=%ct', commit])
    return int(stdout) if (rc == 0) else None

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

def remoteHasBranch(path, rev):
    rc = mmh.devnullProcess(['git', '-C', path,
                             'rev-parse', '--verify', 'origin/' + rev])
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

# This is an implementation of a git-version-information store. It delays
# getting the information as much as possible. So only when the information is
# accessed will it be queried.
class GitInformation:
    def __init__(self, path, tagprefix = 'v', tagpattern = None):
        self.path = path
        self.tagprefix = tagprefix
        if tagpattern is not None:
            self.tagpattern = tagpattern
        else:
            self.tagpattern = tagprefix + '*'
        self.valid = None
        self.dirty = None
        self.commit = None
        self.tag = None
        self._tag = None
        self.increment = None
        self.author = None
        self.committer = None

    def _ensure(self):
        if self.valid is None:
            self.update()

    def _isRelease(self):
        return (self.dirty == False       and
                self.tag   != "noversion" and
                self.increment == 0)

    def update(self):
        self.valid = isWorktree(self.path)
        if not self.valid:
            return
        self.dirty = isDirty(self.path)
        self.commit = commitHash(self.path)
        self.dateHuman = commitDateHuman(self.path)
        self.dateUnix = commitDateUnix(self.path)
        self._tag = latestTag(self.path, self.tagpattern)
        if self._tag is None:
            self.tag = 'noversion'
            self.increment = commitsSinceTag(
                self.path, '4b825dc642cb6eb9a060e54bf8d69288fbee4904')
        else:
            if self.tagprefix != '':
                self.tag = re.sub(f'^{self.tagprefix}', '', self._tag)
            else:
                self.tag = self._tag
            self.increment = commitsSinceTag(self.path, self._tag)
        self.author = author(self.path)
        self.committer = committer(self.path)

    def dict(self):
        self.version_data = v.Version(self.version())
        digits = self.version_data.digits
        if digits is not None:
            (major, minor, patch) = (digits[0], digits[1], digits[2])
        else:
            (major, minor, patch) = (0, 0, 0)

        return {
            'valid':      self.valid,
            'release':    self._isRelease(),
            'dirty':      self.dirty,
            'commit':     self.commit,
            'human-date': self.dateHuman,
            'unix-date':  self.dateUnix,
            'tag':        self.tag,
            'major':      major,
            'minor':      minor,
            'patch':      patch,
            'increment':  self.increment,
            'author':     self.author,
            'committer':  self.committer
        }

    def version(self):
        self._ensure()
        if not self.valid:
            return 'noversion'
        else:
            rv = f'v{self.tag}' if self._tag else self.tag
            if self.increment > 0:
                rv += f'-{self.increment}'
                rv += f'-g{self.commit[:12]}'
            if self.dirty:
                rv += '-dirty'
            return rv
