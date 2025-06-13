import math
import os
import re
import makemehappy.cmake as cmake
import makemehappy.git as git
import makemehappy.utilities as mmh
from pathlib import Path

# Implementation  note: This  was  initially implemented  using python  3.13.x,
# where pathlib classes  support subclassing (which they do  since 3.12.x). Un-
# fortunately, the author still has the  requirement to run mmh on debian book-
# worm for at least a year, which features python 3.11.x, where pathlib classes
# do NOT  support subclassing  out of the  box. It is  possible to  work around
# this, but this  work around breaks down  in 3.12.x and newer.  To support all
# versions of python, the implementation abandons deriving from Path. Instead a
# Path object is  a member of its path-like  classes (InputFile, BuildDirectory
# and SourceDirectory),  and just  enough of  the Path  API was  implemented to
# require almost no changes in the rest of the code.

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

    def update(self):
        self.valid = git.isWorktree(self.path)
        if not self.valid:
            return
        self.dirty = git.isDirty(self.path)
        self.commit = git.commitHash(self.path)
        self._tag = git.latestTag(self.path, self.tagpattern)
        if self._tag is None:
            self.tag = 'noversion'
            self.increment = git.commitsSinceTag(
                self.path, '4b825dc642cb6eb9a060e54bf8d69288fbee4904')
        else:
            if self.tagprefix != '':
                self.tag = re.sub(f'^{self.tagprefix}', '', self._tag)
            else:
                self.tag = self._tag
            self.increment = git.commitsSinceTag(self.path, self._tag)
        self.author = git.author(self.path)
        self.committer = git.committer(self.path)

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

# A SourceDirectory is a pathlike object that references a directory, and
# optional additional version-control information.
class SourceDirectory:
    def __init__(self, p, tagprefix = 'v'):
        if isinstance(p, InputFile):
            self.path = p.path
        elif isinstance(p, Path):
            self.path = p
        else:
            self.path = Path(p)
        self.vcs = GitInformation(p, tagprefix)

    def __truediv__(self, rhs):
        return self.path.__truediv__(rhs)

    def __repr__(self):
        s = str(self.path)
        return f'SourceDirectory({s})'

# A BuildDirectory is a pathlike object that references a directory, and
# optional additional build-system state (via CMake's cache file).
class BuildDirectory:
    def __init__(self, root, subdir, log):
        self.prefix = Path(root)
        self.subdir = Path(subdir)
        self.path = self.prefix / self.subdir
        self.cmakeCache = None
        self.cmakeCacheFile = None
        self.log = log

    def __truediv__(self, rhs):
        return self.path.__truediv__(rhs)

    def __repr__(self):
        s = str(self.path)
        return f'BuildDirectory({s})'

    def __str__(self):
        return str(self.path)

    def cmake(self, force = False):
        if not force and self.cmakeCache is not None:
            return self.cmakeCache

        self.cmakeCacheFile = self / Path('CMakeCache.txt')
        self.log.info(f'Reading cmake-cache: {self.cmakeCacheFile}')
        self.cmakeCache = cmake.readCMakeCache(self.log, self.cmakeCacheFile)

        return self.cmakeCache

# An InputFile is a pathlike object that references a file, and optional
# additional pattern matcher state for the file produced. Generator functions
# for ManifestEntry objects produce lists of these.
class InputFile:
    def __init__(self, p, matchobj = None):
        if isinstance(p, InputFile):
            self.path = p.path
        elif isinstance(p, Path):
            self.path = p
        else:
            self.path = Path(p)
        self.matchobj = None

    def group(self, n):
        if self.matchobj is None:
            return None
        return self.matchobj.group(n)

    def is_file(self):
        return self.path.is_file()

    def __repr__(self):
        s = str(self.path)
        return f'InputFile({s})'

    def __str__(self):
        return str(self.path)

    @property
    def stem(self):
        return self.path.stem

    @property
    def name(self):
        return self.path.name

# The input to a Manifest is a list of these. Each of these can generate any
# number of InputFile objects.
class ManifestEntry:
    def __init__(self, generator, string, destination = None, expect = False):
        # This is a callable, that produces a list of InputFile objects.
        self.generator = generator
        # This is a string representation of the producer. There is no
        # technical reason to have this, but it is useful to be able to refer
        # to it when reporting errors.
        self.string = string
        # List of predicates InputFile → Bool, which can weed out the list of
        # files produced by the generator.
        self.filters = []
        # List of functions that are applied to all files produced by the
        # generator. These functions are InputFile → InputFile.
        self.transformers = []
        # If set, this is an integer that reflects the number of matches the
        # generator function should produce. This is useful with the "rename"
        # method, which is most useful with constructoes like "file()" where
        # the generator produces exactly the one file that was handed to the
        # constructor. Make sure expectedMatches is checked in run().
        self.expectedMatches = expect
        # Local subdirectory to deploy matched files into. The way this works
        # is that a manifest is applied to a global destination directory. This
        # is a directory where "mmh system deploy" is supposed to produce a
        # deployment tree. The local subdirectory is a directory within that.
        # Say the global directory is '/foo/bar' and the local directory of a
        # file "README" is 'baz', then the final file name will be
        # '/foo/bar/baz/README'. If destination was None, then the final file
        # name would have been '/foo/bar/README'.
        self.destinationDir = destination

    def expect(self, e):
        self.expectedMatches = e
        return self

    def __xor__(self, e):
        return self.expect(e)

    def destination(self, d):
        self.destinationDir = d
        return self

    def __gt__(self, d):
        return self.destination(d)

    def transform(self, t):
        self.transformers.append(t)
        return self

    def rename(self, name):
        if callable(name):
            self.transformers = [ name ]
        else:
            self.transformers = [ lambda _: name ]
        return self

    def filter(self, f):
        self.filters.append(f)
        return self

    def _transform(self, f):
        new = Path(f.name)
        for t in self.transformers:
            new = t(new)

        final = Path(new)
        if self.destinationDir is not None:
            final = self.destinationDir / final

        return final

    def run(self, idx):
        # Generate, filter, transform.
        files = list(self.generator())

        for f in self.filters:
            files = list(filter(f, files))

        final = list(map(self._transform, files))

        # This matches up input files with output files.
        pairs = list(zip(files, final))

        # This returns the ManifestEntry itself, so it is possible to provide
        # the user with meaningful error messages in case something goes wrong.
        # This also yields access to details like expectedMatches.
        return (idx, self, len(pairs), pairs)

# This is raised, when an entry in a Manifest is not a ManifestEntry.
class InvalidManifestEntry(Exception):
    pass

# This is raised when an operation on a Manifest object that did not call its
# collect operation yet.
class BareManifest(Exception):
    pass

# Some manifest generators may produce input files that do not exist. That is
# obviously an issue.
class ManifestEntryMissing:
    def __init__(self, idx, entry, file):
        self.index = idx
        self.entry = entry
        self.file = file

    def __str__(self):
        return (f'Index {self.index} ({self.entry.string}) yielded ' +
                f'missing file: {str(self.file)}')

# This issue is used when a ManifestEntry yields no files at all.
class ManifestEntryEmpty:
    def __init__(self, idx, entry, actual):
        self.index = idx
        self.entry = entry
        self.actual = actual

    def __str__(self):
        return f'Index {self.index} ({self.entry.string}) yielded no files.'

# This issue is used when a ManifestEntry specifies the exact number of files
# it should produce, but the generation process produced another number.
class ManifestEntryMismatch:
    def __init__(self, idx, entry, expected, actual):
        self.index = idx
        self.entry = entry
        self.expected = expected
        self.actual = actual

    def __str__(self):
        return (f'Index {self.index} ({self.entry.string}) yielded ' +
                f'{self.actual} files, but {self.expected} were expected.')

# In Manifests, the destination file names specified have the property that
# they must be unique. Otherwise there would be more than one input mapped to
# the same output, resulting in at least one source file not being represented
# in the resulting deploy tree. This class represents one such error.
class UniquenessViolation:
    def __init__(self, path, occurances):
        self.path = path
        self.occurances = occurances

    def __str__(self):
        return (f'{str(self.path)} is used as an ' +
                f'output file {len(self.occurances)} times')

    def strlist(self):
        rv = []
        for (index, me) in self.occurances:
            rv.append(f'Manifest index {index} ({me.string})')
        return rv

# This is a collection of ManifestEntry objects with associated operations.
# Deployment is split into two phases: collecting in/out file pairs from
# ManifestEntry processing, and the actual deployment process. This allows for
# additional things to happen in between, like checking the manifest for
# possible issues.
class Manifest:
    def __init__(self):
        self.entries = []
        self.collection = None

    def __call__(self, *args):
        return self.extend(list(args))

    def extend(self, entries):
        self.entries.extend(mmh.flatten(entries))

    def collect(self):
        self.collection = []
        for n, entry in enumerate(self.entries):
            new = entry.run(n)
            self.collection.append(new)

    def validate(self):
        for n, entry in enumerate(self.entries):
            if not isinstance(entry, ManifestEntry):
                raise InvalidManifestEntry(n, entry)

    def issues(self):
        # This scans for common issues in a collection of files from a mani-
        # fest: Each entry must be there for a reason, so an entry producing
        # zero files is an issue. Furthermore, if an entry explicitly states
        # the number of entries it expects to produce, failing to do so is also
        # an issue.
        if self.collection is None:
            raise BareManifest

        rv = []
        for (idx, entry, n, pairs) in self.collection:
            exp = entry.expectedMatches
            if exp:
                if exp != n:
                    rv.append(ManifestEntryMismatch(idx, entry, exp, n))
            else:
                if n == 0:
                    rv.append(ManifestEntryEmpty(idx, entry, n))
            for file, _ in pairs:
                if not file.is_file():
                    rv.append(ManifestEntryMissing(idx, entry, file))

        return rv

    def uniquenessViolations(self):
        # It is imperative, that a manifest's destination file names are
        # unique. It may be tolerable (depending on the situation), that an
        # entry does not produce files (and those cases are covered by
        # issues()), but this property cannot be violated.
        if self.collection is None:
            raise BareManifest

        check = {}
        for entry in self.collection:
            (index, me, n, pairs) = entry
            for pair in pairs:
                (_, file) = pair
                if file not in check:
                    check[file] = [ (index, me) ]
                else:
                    check[file].append((index, me))

        errors = []
        for key, occurances in check.items():
            if len(occurances) > 1:
                errors.append(UniquenessViolation(key, occurances))

        return errors

    def listSpec(self):
        tindex = 'Index'
        tgen = 'Generator'
        tdest = 'Destination'
        width = max(math.floor(math.log10(len(self.entries)) + 1),
                    len(tindex))
        maxstring = len(tgen)
        maxdest = len(tdest)
        for spec in self.entries:
            n = len(spec.string)
            if n > maxstring:
                maxstring = n
            m = len('.'
                    if spec.destinationDir is None
                    else spec.destinationDir)
            if m > maxdest:
                maxdest = m
        hl = ('-' * (width + 2) + '+' +
              '-' * (maxstring + 2) + '+' +
              '-' * (maxdest + 2))
        rv = [ hl, f' {tindex:{width}} | {tgen:{maxstring}} | {tdest}', hl ]
        for n, spec in enumerate(self.entries):
            d = ('.'
                 if spec.destinationDir is None
                 else spec.destinationDir)
            rv.append(f' {n:{width}} | ' +
                      f'{spec.string:{maxstring}} | ' +
                      f'{d}')

        rv.append(hl)
        return rv

    def listCollection(self):
        if self.collection is None:
            raise BareManifest

        tindex = 'Index'
        tfile = 'Input/Output'
        width = max(math.floor(math.log10(len(self.collection)) + 1),
                    len(tindex))
        maxfile = len(tfile)

        for (idx, entry, n, pairs) in self.collection:
            for (infile, outfile) in pairs:
                n = max(len(str(infile)), len(str(outfile)))
                if n > maxfile:
                    maxfile = n

        hl = ('-' * (width + 2) + '+' +
              '-' * (maxfile + 4))

        rv = [ hl, f' {tindex:{width}} | {tfile}', hl ]

        i = 0
        for (idx, entry, n, pairs) in self.collection:
            j = 0
            for (infile, outfile) in pairs:
                rv.append(f' {i if j == 0 else "":{width}} |   {infile}')
                rv.append(f' {"":{width}} | → {outfile}')
                j += 1
            rv.append(hl)
            i += 1

        return rv

    def deploy(self):
        # TODO: Implement the actual deployment process. Luckily, this is most-
        # ly just copying files around. But we should also add md5sum files,
        # and maybe also other checksums like sha256 and sha512. Luckily, py-
        # thon has hashlib. But we should generate files that can be processed
        # by the associated command line tools, like md5sum(1). And of course,
        # at the end of the deployment process, mmh should verify all files by
        # processing those files.
        if self.collection is None:
            raise BareManifest

        return True

# Helpers for ManifestEntry constructors.

def _someroot(root):
    # This is a function introduced when the workaround for python 3.11 and
    # older was put in place. When we abandon support for these python ver-
    # sions, this function can be removed and the old code can be put into
    # place. Check the commit that adds this comment for details.
    if isinstance(root, SourceDirectory):
        return root.path
    elif isinstance(root, BuildDirectory):
        return root.path
    elif isinstance(root, Path):
        return root
    else:
        return Path(root)

def genFile(g, root):
    realroot = _someroot(root)
    f = InputFile(realroot / g)
    return [ f ] if f.is_file() else []

def genFromFile(f, file_root, spec_root):
    spec = _someroot(spec_root) / f
    if not spec.is_file():
        # This will cause an ignorable issue to be flagged.
        return [ InputFile(spec) ]
    rv = [ ]
    with open(spec, mode = 'r', encoding = 'utf-8') as sp:
        for n, string in enumerate(sp):
            line = string.strip()
            if line.startswith('#'):
                continue
            if line == "":
                continue
            rv.append(InputFile(_someroot(file_root) / line))
    return rv

def genGlob(pat, root):
    p = _someroot(root)
    return list(p.glob(pat))

def genRegex(pat, root):
    pattern = re.compile(pat)
    realroot = _someroot(root)
    files = os.listdir(realroot)
    rv = []
    for f in files:
        m = pattern.search(f)
        if m:
            rv.append(InputFile(realroot / f, m))
    return rv

def genZephyr(builddir):
    cmake = builddir.cmake()
    files = []
    byproducts = re.compile('BYPRODUCT_KERNEL_')
    for key, value in cmake.items():
        if byproducts.match(key):
            files.append(InputFile(value))

    if len(files) == 0:
        return []

    base = files[0].stem

    more0 = list(map(lambda ext: InputFile(builddir /
                                           Path('zephyr') /
                                           Path(base + '.' + ext)),
                     [ 'dts', 'lst', 'map', 'stat', 'symbols' ]))

    more1 = [ builddir / Path('zephyr/include/generated/zephyr/autoconf.h'),
              builddir / Path('zephyr/.config') ]

    for file in more0 + more1:
        p = InputFile(file)
        if p.is_file():
            files.append(p)

    return files

def renameZephyr(name):
    def _rename(f):
        p = Path(f)
        # 'autoconf.h' and '.config' are a little weird. The other zephyr style
        # file names are easy to rename.
        if p.name == 'autoconf.h':
            return name + '-config.h'
        elif p.name == '.config':
            return name + '.config'
        else:
            return p.with_stem(name)
    return _rename

def basenameZephyr(builddir):
    cmake = builddir.cmake()
    byproducts = re.compile('BYPRODUCT_KERNEL_')
    for key, value in cmake.items():
        if byproducts.match(key):
            p = Path(value)
            return p.stem
    return 'zephyr'

# Here are constructors for ManifestEntry instances: file, glob, regex, and
# zephyr. You should not construct ManifestEntry instances yourself.

def file(g, root = '.'):
    return ManifestEntry(lambda: genFile(g, root), f'file({g})', None, 1)

def fromFile(f, file_root = '.', spec_root = '.'):
    return ManifestEntry(lambda: genFromFile(f, file_root, spec_root),
                         'fromFile(' + f + ')')

def glob(pat, root = '.'):
    return ManifestEntry(lambda: map(InputFile, genGlob(pat, root)),
                         f'glob({pat}, root = {root})')

def regex(pat, root = '.'):
    return ManifestEntry(lambda: genRegex(pat, root),
                         f'regex({pat}, root = {root})')

def zephyr(builddir, name = None):
    # Automatic manifest entry for zephyr-based firmware artefacts. "builddir"
    # has to be a BuildDirectory instance, to use for deployment. "name" should
    # be the user-facing base-name of the firmware. If it is not supplied, the
    # basename of the BYPRODUCT_KERNEL_* cmake variables will be used.
    #
    # These variables are also used to determine the basic set of artefacts
    # (those can be bin, elf, exe, hex, s19, and uf2).
    #
    # In addition, .dts, .lst, .map, .stat, .symbols files of the same basename
    # will be considered if they exist.
    #
    # Additionally "zephyr/include/generated/zephyr/autoconf.h" and
    # "zephyr/.config" are considered as well.
    me = ManifestEntry(lambda: genZephyr(builddir),
                       f'zephyr({str(builddir)})')
    if name is None:
        name = basenameZephyr(builddir)
    return me.rename(renameZephyr(name))

# Some common filter functions so not everybody has to write these.

def _regex_filter(patterns, ifmatch, ifnotmatch):
    ps = list(map(re.compile, patterns))

    def _filter(f):
        string = str(f)
        for p in ps:
            if re.search(p, string):
                return ifmatch
        return ifnotmatch
    return _filter

def only(*patterns):
    # This returns a filter function that will filter out all files that do not
    # match one of the provided regular expression patterns.
    return _regex_filter(patterns, True, False)

def remove(*patterns):
    # This returns a filter function that will filter out all files that DO
    # match one of the provided regular expression patterns.
    return _regex_filter(patterns, False, True)

# Similarly, some common transformation functions.

def withDashString(string):
    def _transform(f):
        if not isinstance(f, Path):
            f = Path(f)
        old = f.stem
        return f.with_stem(old + '-' + string)
    return _transform

def withVersion(vcs):
    def _transform(f):
        if not isinstance(f, Path):
            f = Path(f)
        old = f.stem
        return f.with_stem(old + '-' + vcs.version())
    return _transform

manifest = Manifest()
