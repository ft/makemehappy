# In order to deploy a specific set of desired artefacts from a number of
# different sub-build-trees into a consistent and reproducible structure, mmh
# uses the notion of a manifest to specify this mapping, execute and verify it.
#
# This module defines two data types: ManifestEntry and Manifest. The former
# represents a way to generate input files, filter them down, and transform
# their names for deployment, and the latter is a class that combines a number
# of ManifestEntry objects and implements a number of operations upon them.
# Notably the process of copying input files into a deployment tree file
# structure.
#
# The module has a top-level "manifest" object that is an instance of the
# Manifest class. This one specific object is used by mmh's "deploy" sub-
# command.
#
# The rest of the module is a number of function that represent an EDSL for
# specifying manifests in mmh's deploy process: Ways to specify ManifestEntry
# objects, filter predicates, as well as transformation functions.

import contextlib
import hashlib
import math
import os
import re
import shutil
import makemehappy.cmake as cmake
import makemehappy.git as git
import makemehappy.pathlike as p
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
        new = p.InputFile(str(f), f.matchobj)
        for t in self.transformers:
            new = t(new)

        if isinstance(new, p.InputFile):
            final = Path(new.name)
        elif isinstance(new, Path):
            final = new.name
        else:
            final = Path(new).name

        if self.destinationDir is not None:
            final = Path(self.destinationDir) / final
        else:
            final = Path(final)

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

# Manifest entries can also throw. Depending on how the deployment system was
# configured (strict vs lenient), this may fail the deployment process.
class ManifestException:
    def __init__(self, idx, exception):
        self.index = idx
        self.exception = exception

    def __str__(self):
        return (f'Index {self.index} raised {self.exception}')

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
        self._prefix = None
        self._subdir = None
        self.spec = None
        self.installcb = None
        self.checksumName = 'contents'

    def __call__(self, *args):
        return self.extend(list(args))

    def withChecksumName(self, name):
        self.checksumName = name

    def withInstallCallback(self, cb):
        self.installcb = cb

    def withSpecification(self, file):
        self.spec = file

    def specification(self):
        return self.spec

    def prefix(self, path):
        self._prefix = Path(path)

    def subdir(self, d):
        self._subdir = Path(d)

    def final(self):
        if self._subdir is not None:
            return self._prefix / self._subdir
        else:
            return self._prefix

    def extend(self, entries):
        self.entries.extend(mmh.flatten(entries))

    def collect(self, log):
        self.collection = []
        for n, entry in enumerate(self.entries):
            try:
                new = entry.run(n)
                self.collection.append(new)
            except Exception as e:
                log.warning(f'Exception in collector at index {n}')
                self.collection.append((n, entry, 0, ManifestException(n, e)))

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
            if isinstance(pairs, ManifestException):
                rv.append(pairs)
                continue
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
            if isinstance(pairs, ManifestException):
                continue
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
        if len(self.entries) == 0:
            return None
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

        if len(self.collection) == 0:
            return None

        tindex = 'Index'
        tfile = 'Input/Output'
        width = max(math.floor(math.log10(len(self.collection)) + 1),
                    len(tindex))
        maxfile = len(tfile)

        for (idx, entry, n, pairs) in self.collection:
            if isinstance(pairs, list) == False:
                print(pairs)
                continue
            for (infile, outfile) in pairs:
                n = max(len(str(infile)), len(str(outfile)))
                if n > maxfile:
                    maxfile = n

        hl = ('-' * (width + 2) + '+' +
              '-' * (maxfile + 4))

        rv = [ hl, f' {tindex:{width}} | {tfile}', hl ]

        for (idx, entry, n, pairs) in self.collection:
            if isinstance(pairs, list) == False:
                continue
            j = 0
            for (infile, outfile) in pairs:
                rv.append(f' {idx if j == 0 else "":{width}} |   {infile}')
                rv.append(f' {"":{width}} | → {outfile}')
                j += 1
            rv.append(hl)

        return rv

    def destinationExists(self):
        finalDestination = self.final()
        if finalDestination.is_dir():
            return True
        if finalDestination.exists():
            raise FileExistsError
        return False

    def removeDestination(self):
        shutil.rmtree(self.final())

    def deploy(self, verbose = False, raiseException = False):
        if self.collection is None:
            raise BareManifest

        if len(self.collection) == 0:
            return [ 'Manifest yielded empty collection' ]

        finalDestination = self.final()

        print('Deploying based on specification:', self.spec)
        outfiles = []
        errors = []
        for (idx, entry, n, pairs) in self.collection:
            if verbose:
                print()
            print(f'Index {idx}: {entry.string}, {n} file' +
                  ('' if n == 1 else 's'), 'to deploy...')
            if isinstance(pairs, ManifestException):
                if verbose:
                    print(f'  {pairs}')
                continue
            for (infile, outfile) in pairs:
                outfiles.append(outfile)
                if verbose:
                    print(f'  in : {str(infile)}')
                    print(f'  out: {str(outfile)}')
                try:
                    mmh.install(infile.path,
                                finalDestination / outfile,
                                self.installcb)
                except Exception as e:
                    if (len(e.args) > 0):
                        error = f'{type(e).__name__}: {e}'
                    else:
                        error = f'{type(e).__name__}'

                    if raiseException:
                        raise e
                    else:
                        errors.append(
                            mmh.FileCopyError(infile, outfile, error))

        if len(errors) == 0:
            # We didn't see any errors while copying. Next: checksums.
            outfiles.sort()
            variants = [ (hashlib.md5,    'md5'),
                         (hashlib.sha256, 'sha256'),
                         (hashlib.sha512, 'sha512') ]
            for (construct, extension) in variants:
                out = Path(self.checksumName + '.' + extension)
                print('Generating checksums:', out)
                try:
                    with contextlib.chdir(finalDestination):
                        mmh.checksum(outfiles, out, variant = construct)
                except Exception as e:
                    if (len(e.args) > 0):
                        error = f'{type(e).__name__}: {e}'
                    else:
                        error = f'{type(e).__name__}'

                    if raiseException:
                        raise e
                    else:
                        errors.append(mmh.FileAccessError(out, error))

        if len(errors) == 0:
            for variant in [ 'md5', 'sha256', 'sha512' ]:
                basename = self.checksumName + '.' + variant
                checksumfile = finalDestination / basename
                print(f'Verifiying checksums: {str(basename)}...',
                      end = '')
                failed = mmh.checksumVerify(checksumfile, finalDestination,
                                            variant)
                if len(failed) > 0:
                    print(' failed!')
                    errors.extend(failed)
                else:
                    print(' ok.')

        return errors

# Helpers for ManifestEntry constructors.

def _someroot(root):
    # This is a function introduced when the workaround for python 3.11 and
    # older was put in place. When we abandon support for these python ver-
    # sions, this function can be removed and the old code can be put into
    # place. Check the commit that adds this comment for details.
    if isinstance(root, p.SourceDirectory):
        return root.path
    elif isinstance(root, p.BuildDirectory):
        return root.path
    elif isinstance(root, Path):
        return root
    else:
        return Path(root)

def genFile(g, root):
    realroot = _someroot(root)
    f = p.InputFile(realroot / g)
    return [ f ] if f.is_file() else []

def genFromFile(f, file_root, spec_root):
    spec = _someroot(spec_root) / f
    if not spec.is_file():
        # This will cause an ignorable issue to be flagged.
        return [ p.InputFile(spec) ]
    rv = [ ]
    with open(spec, mode = 'r', encoding = 'utf-8') as sp:
        for n, string in enumerate(sp):
            line = string.strip()
            if line.startswith('#'):
                continue
            if line == "":
                continue
            rv.append(p.InputFile(_someroot(file_root) / line))
    return rv

def genGlob(pat, root):
    d = _someroot(root)
    return list(d.glob(pat))

def genRegex(pat, root):
    pattern = re.compile(pat)
    realroot = _someroot(root)
    files = os.listdir(realroot)
    rv = []
    for f in files:
        m = pattern.search(f)
        if m:
            rv.append(p.InputFile(realroot / f, m))
    return rv

def genZephyr(builddir):
    cmake = builddir.cmake()
    files = []
    byproducts = re.compile('BYPRODUCT_KERNEL_')
    for key, value in cmake.items():
        if byproducts.match(key):
            files.append(p.InputFile(value))

    if len(files) == 0:
        return []

    base = files[0].stem

    more0 = list(map(lambda ext: p.InputFile(builddir /
                                             Path('zephyr') /
                                             Path(base + '.' + ext)),
                     [ 'dts', 'lst', 'map', 'stat', 'symbols' ]))

    more1 = [ builddir / Path('zephyr/include/generated/zephyr/autoconf.h'),
              builddir / Path('zephyr/.config') ]

    for file in more0 + more1:
        f = p.InputFile(file)
        if f.is_file():
            files.append(f)

    return files

def renameZephyr(name):
    def _rename(f):
        if isinstance(f, p.InputFile):
            fp = f.path
        elif isinstance(f, Path):
            fp = f
        else:
            fp = Path(f)
        # 'autoconf.h' and '.config' are a little weird. The other zephyr style
        # file names are easy to rename.
        if fp.name == 'autoconf.h':
            return name + '-config.h'
        elif fp.name == '.config':
            return name + '.config'
        else:
            return fp.with_stem(name)
    return _rename

def basenameZephyr(builddir):
    cmake = builddir.cmake()
    byproducts = re.compile('BYPRODUCT_KERNEL_')
    for key, value in cmake.items():
        if byproducts.match(key):
            fp = Path(value)
            return fp.stem
    return 'zephyr'

# Here are constructors for ManifestEntry instances: file, glob, regex, and
# zephyr. You should not construct ManifestEntry instances yourself.

def file(g, root = '.'):
    return ManifestEntry(lambda: genFile(g, root),
                         f'file({g}, root = {root})',
                         None, 1)

def fromFile(f, file_root = '.', spec_root = '.'):
    return ManifestEntry(lambda: genFromFile(f, file_root, spec_root),
                         'fromFile(' + f + ')')

def glob(pat, root = '.'):
    return ManifestEntry(lambda: map(p.InputFile, genGlob(pat, root)),
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
        for pat in ps:
            if re.search(pat, string):
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
        if isinstance(f, p.InputFile):
            f = f.path
        elif not isinstance(f, Path):
            f = Path(f)
        old = f.stem
        return f.with_stem(old + '-' + string)
    return _transform

def withVersion(vcs):
    return withDashString(vcs.version())

# Here's a function that turns a result of a ManifestEntry to a list of matched
# files. The machinery of matching files can be useful elsewhere, and this is a
# utility to help with that.
#
# Example:
#
#     % ls *.txt
#     bar.txt foo.txt some-garbage.txt zool.txt
#
#     import makemehappy.manifest as m
#     m.matches(m.glob('*.txt').filter(m.remove('garbage')))
#   → [ 'bar.txt', 'foo.txt', 'zool.txt' ]
def matches(mentry):
    (a, b, c, lst) = mentry.run(0)
    return list(map(lambda x: x[0], lst))

# pairs() is similar to matches, but it returns the list of full input/output
# file pairs. This allows users to meaningfully use .transform() as well as
# .filter().
def pairs(mentry):
    (a, b, c, lst) = mentry.run(0)
    return lst

manifest = Manifest()
