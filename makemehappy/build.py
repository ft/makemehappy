import os
import subprocess

def allofthem():
    subprocess.run(['cat', 'CMakeLists.txt'])
    subprocess.run(['cmake', '-GUnix Makefiles', '-S', '.', '-B', 'build'])
    subprocess.run(['cmake', '--build', 'build'])
