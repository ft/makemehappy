import makemehappy.cmake as cmake
import makemehappy.git as git
from pathlib import Path

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
        self.vcs = git.GitInformation(p, tagprefix)

    def __truediv__(self, rhs):
        return self.path.__truediv__(rhs)

    def __repr__(self):
        s = str(self.path)
        return f'SourceDirectory({s})'

    def __str__(self):
        return str(self.path)

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

    def _cmake(self, key = None):
        if key is None:
            return self.cmakeCache

        if key in self.cmakeCache:
            return self.cmakeCache[key]

        return None

    def cmake(self, key = None, force = False):
        if not force and self.cmakeCache is not None:
            return self._cmake(key)

        self.cmakeCacheFile = self / Path('CMakeCache.txt')
        self.log.info(f'Reading cmake-cache: {self.cmakeCacheFile}')
        self.cmakeCache = cmake.readCMakeCache(self.log, self.cmakeCacheFile)

        return self._cmake(key)

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
        self.matchobj = matchobj

    def group(self, n):
        if self.matchobj is None:
            return None
        return self.matchobj.group(n)

    def is_file(self):
        return self.path.is_file()

    def __lt__(self, rhs):
        return self.path < rhs.path

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
