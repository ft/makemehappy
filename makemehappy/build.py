import os
import subprocess

def allofthem():
    olddir = os.getcwd()
    subprocess.run(['cat', 'CMakeLists.txt'])
    subprocess.run(['cmake', '-GUnix Makefiles', '-S', '.', '-B', 'build'])
    subprocess.run(['cmake', '--build', 'build'])
    os.chdir('build')
    subprocess.run(['ctest', '-VV'])
    os.chdir(olddir)
