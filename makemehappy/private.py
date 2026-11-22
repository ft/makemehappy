import os
from pathlib import Path

def gotConfigureStamp(d):
    f = Path(d) / '.mmh-configure-stamp'
    return f.exists()

def removeConfigureStamp(d):
    root = Path(d)
    if root.is_dir() == False:
        return
    f = root / '.mmh-configure-stamp'
    if f.exists():
        f.unlink()

def touchConfigureStamp(d):
    f = Path(d) / '.mmh-configure-stamp'
    f.touch(mode = 0o666, exist_ok = True)

def with_directory(data):
    return os.path.exists(data["directory"])

def with_build_system(data):
    if not data["with-directory"]:
        return False
    if gotConfigureStamp(data["directory"]):
        return True
    bd = Path(data["directory"])
    if data["build-tool"] == "make":
        f = bd / "Makefile"
        return f.exists()
    elif data["build-tool"] == "ninja":
        f = bd / "build.ninja"
        return f.exists()
    return False
