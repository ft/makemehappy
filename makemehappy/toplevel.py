def generateToplevel(fname):
    with open(fname, 'w') as fh:
        print("cmake_minimum_required(VERSION 3.1.0)", file = fh)
        print("project(ufw C CXX ASM)", file = fh)
        print('list(APPEND CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}/code-under-test/cmake/modules")', file = fh)
        print("include(CTest)", file = fh)
        print("include(Libtap)", file = fh)
        print("enable_testing()", file = fh)
        print("add_libtap(deps/libtap)", file = fh)
        print("add_subdirectory(code-under-test)", file = fh)
