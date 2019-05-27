import os
import subprocess

def allofthem():
    olddir = os.getcwd()
    subprocess.run(['cat', 'CMakeLists.txt'])
    os.chdir('build')
    subprocess.run(['cmake', '-GUnix Makefiles', '..'])
    subprocess.run(['cmake', '--build', '.'])
    subprocess.run(['ctest', '-VV'])
    os.chdir(olddir)
