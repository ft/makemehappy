Build Specification
*******************

Module Specification
====================

Modules are specified in a file called ``module.yaml``. There are two different
kinds of modules in ``mmh``: ``generic`` and ``zephyr``. The generic type uses
CMake best-practices (like toolchain-files and build-type configuration), and
can build libraries as well as applications. This leans a lot on the ``ufw``
library, that implements a number of CMake modules, that ``mmh`` uses, as well
as supplies a number of toolchain files. The ``zephyr`` type is in support of
the Zephyr Real Time Operating System. Its builds are very much application
centric, and while its build-system is CMake as well, it solves a number of
problems differently from classic CMake; notably the way toolchains are set up
and build-type configuration is done.

TBD.

System Specification
====================

A system is specified by a number of builds to be performed. With ``mmh``, this
is done in a file called ``system.yaml``. There are two different kinds of
builds: ``board`` and ``zephyr`` builds. In ``board`` builds, the name of a
board is defined, along with one of (possibly) multiple toolchains, and
build-configurations. With these parameters the top-level build system is
invoked, building all code registered with this build variant. In ``zephyr``
builds, one build builds one application, using a certain toolchain, a certain
build-configuration, and a certain board, using a number of zephyr-modules.
Similarly to ``board`` builds, ``mmh`` allows you to specify multiple
toolchains, build-configurations, as well as target boards. ``mmh`` will build
all of these variants.

Note that in system mode, ``mmh`` will never attempt to fetch any sort of
source code. It only runs the build system with parameters specified in
``system.yaml``, possibly many times.

TBD.

Combination Builds
------------------

TBD.

System Deployment
-----------------

TBD.
