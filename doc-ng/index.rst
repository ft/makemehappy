MakeMeHappy — Build Orchestration
#################################

Synopsis
********

``mmh [OPTION(s)...] SUBCMD [SUBOPTION(s)...] [++ CMAKE-PARAM(s)...]``


Description
***********

``mmh`` is an orchestration tool to automatically arrange a build-environment
to build modular software projects, that use CMake as their build system. It is
mostly aimed for embedded projects. It requires the use of the ``ufw`` library
for its additional cmake modules. What makes ``mmh`` an orchestration tool is
its emphasis on mostly just calling out to applications like ``cmake`` or
``git`` to achieve its goals. These goals are specified in a declarative manner
via files in YAML format. It is meant to perform many tedious and repetitive
tasks, that occur when building portable, modular software with many
toolchains, build configurations, build tools, build configurations and the
like.

MakeMeHappy derives its name from answering the question if a piece of software
can be build an tested with as many such combinations as possible, thus
delivering happy news to the user.


Motivation
==========

One possible approach to assemble larger software projects is to split logical
parts into modules, create APIs and use multiple modules that, in combination,
create a larger, more complex application or library. The Git version control
system allows the assembly of precise states of such modules via its submodule
system.

Building such super projects is mostly trivial, because — **by** **design** —
the super project incorporates *all* required modules with all of their
dependencies. Using CMake at the top-level of the super project makes it
possible (albeit sometimes a little cumbersome, due to cmake-command lines
becoming unwieldy; but see ``mmh``'s system build mode later about that) use
the different modules, as instantiated by Git's submodule system, as well. The
approach is very flexible and has the upside of enforcing API discipline as
well.

A problem, that arises from this approach however, is the building a *single*
module. This is very common, especially with version control and continuous
integration in place, where it is desirable to build a module and run its test
suite any time a developer pushes/commits into the module's repository.

This is where ``mmh``'s module build mode comes into play. You can think of it
as a tool that, given enough information, does this:

- Generate an ephemeral kind of a super project:

  - …that includes the current state of a module itself (via symbolic link).
  - …with all its dependencies (as well as all recursive dependencies)
  - …with a generated top-level CMakeLists.txt able to run the build.

- Configure the build-tree from the ephemeral source tree.
- Builds all dependencies and finally the module itself.
- Runs any tests it can.
- Does this for **many** build variants.
- Finally print a summary of the collected build-statistics.

The last point is routed with ``mmh``'s origin as a continuous integration
driver. As such, it makes a point in exercising its ephemeral super project
using a combination of ``toolchains``, ``architectures``, ``buildconfigs`` and
``buildtools``. All of that is powered by a layered configuration approach,
that allows for fine-grained control of all of these parameters as well as
module sources.


General Operation
=================

``mmh`` has two modes of operation:

- Module build mode
- System build mode

In module build mode, it does exactly what is described in the ``Movivation``
section. The system build mode was added later. It is similar to module build
mode, but instead of generating a top-level ``CMakeLists.txt`` file and
downloading dependencies, it works in a repository that solves these problems
beforehand, like a larger system's super-project that references all
dependencies as git-submodules (or any other means, ``mmh`` does not really
care how the source tree came to be).

Calling ``mmh`` without arguments causes it to choose one of these modes,
depending on whether a file exists:

- ``module.yaml``: Use module build mode, with its ``build`` command.
- ``system.yaml``: Use system build mode, with its ``build`` command.
- Otherwise, error out.

Beyond these two modes, ``mmh`` has a couple of smaller, additional features,
that will be described later in this document.


Top-Level Options
*****************

.. option:: -h, --help

   Show help message and exit.

.. option:: -d DIRECTORY, --directory DIRECTORY

   Specify the build-root directory.

.. option:: -m MODULE, --module MODULE

   Specify the file that contains the module description. Defaults to
   ``module.yaml``.

.. option:: -y SYSTEM_SPEC, --system SYSTEM_SPEC

   Specify the file that contains the system description. Defaults to
   ``system.yaml``.

.. option:: -p, --preserve

   Preserve build root instead of deleting it. In combination with -d, delete
   build root before termination.

.. option:: -q, --quiet

   Disable informational output:

.. option:: -R, --raise-exceptions

   Raise toplevel exceptions in case of errors.

.. option:: -P, --show-phases

   Show build phases even with --log-to-file.

.. option:: -L, --log-all

   Send all output to logging facility.

.. option:: -l, --log-to-file

   Log output to file (implies ``--log-all``).

.. option:: -f LOG_FILE, --log-file LOG_FILE

   Specify log-file name to use.

.. option:: -T TOOLCHAINS, --toolchains TOOLCHAINS

   Select toolchains to include in build.

.. option:: -B BUILDTOOLS, --buildtools BUILDTOOLS

   Select buildtools to include in build.

.. option:: -C BUILDCONFIGS, --buildconfigs BUILDCONFIGS

   Select build configurations to include in build.

.. option:: -A ARCHITECTURES, --architectures ARCHITECTURES

   Select architectures to include in build.

.. option:: -Q QUERY, --query QUERY

   Query aspects about the program.

.. option:: -c CONFIG, --config CONFIG

   Add configuration to config-stack.

.. option:: -U, --disable-user-directory

   Disable use of files in user-configuration directory.

.. option:: -r REVISION, --revision REVISION

   Add a revision-override specification.

.. option:: -s SOURCE, --source SOURCE

   Add a module source definition.

.. option:: -S, --succeed

   Force successful program termination.

.. option:: -e, --environment-overrides

   Allow mmh to override existing environment variables.

.. option:: -E, --ignore-dep-errors

   Ignore errors in dependency evaluation.

.. option:: -V, --version

   Show program version and exit.

.. option:: -v, --verbose

   Produce verbose output.

.. option:: --load-insecure-files

   Load world-writeable files that contain code.


Command Reference
*****************

All system mode commands are sub-commands to the `system` command. Module build
mode commands are top-level commands. This is due to the fact that module build
mode was the only mode of operation in `mmh` for a while. Other features are
also top-level commands.

Module Build Mode
=================

.. option:: build

  Build a module in many variants.

.. option:: build-tree-init

   Initialise a build tree. This command has a shorter alias: ``init``

.. option:: fetch-dependencies

   Download dependencies of a module. This command has a shorter alias:
   ``deps``

.. option:: focus-instance

   Focus a module instance's build-tree. This command has a shorter alias:
   ``focus``

.. option:: generate-toplevel

   Generate toplevel of module build-tree. This command has a shorter alias:
   ``top``

.. option:: list-instances

   List instances available in build-tree. This command has a shorter alias:
   ``list``

.. option:: prepare

   Generate toplevel of module build-tree

.. option:: run-instance

   Run previously configured build-tree. This command has a shorter alias:
   ``run``


System Build Mode
=================

All of these commands are sub-commands to the `system` command.

.. option:: build

   Build all or specified build instances.

.. option:: clean

   Clean all or specified build instances.

.. option:: db

   Link compile command db to system root.

.. option:: list

   List all specified build instances.

.. option:: rebuild

   Rebuild all or specified build instances.


Additional Features
===================

.. option:: download-source

   Download sources for a module. This command has a shorter alias: ``get``.

.. option:: download-sources

   Download sources for ALL module.

.. option:: dump-description

   Show parsed instruction file data. This command has a shorter alias:
   ``dump``.

.. option:: reset-setup

   Reset build-tree meta-data. This command has a shorter alias: ``reset``.

.. option:: revision-overrides

   Show and test revision overrides. This command has a shorter alias:
   ``revs``.

.. option:: show-result

   Show result table from log-file. This command has a shorter alias:
   ``result``.

.. option:: show-source

   Show source location for module(s). This command has a shorter alias:
   ``show``.


Program Setup
*************

Configuration Data
==================

TBD.

Source Data
===========

TBD.


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


Hook Subsystem
**************

TBD.


Examples
********

Building a module is predicated on the existence of a file called
``module.yaml``. With it in place, you can run a combined build of all build
instances like this:

.. code:: shell-session

  % mmh

…which is exactly equivalent to this:

.. code:: shell-session

   % mmh build

With that, the default behaviour will run the builds, summarise how the process
went and remove the build tree created afterwards. In order to keep the build
tree around, you can name a specific directory to use instead:

.. code:: shell-session

    % mmh -d ci

…which does the same operation as before, but instead of using a temporary
directory that gets removed afterward, use the directory named ``ci`` and keep
it around after running all instances.

If this is done with all default settings and the ``ufw`` library as the target
module, ``mmh`` will try and run forty(!) build instances. This exercised the
code base with a lot of compilers, build-tools and build settings, but can take
a bit of time. ``mmh`` allows users to optionally pick the respective sets of
all these parameters. For example, to only use ``ninja`` as a build tool,
``gnu`` and ``clang`` as toolchains and ``debug`` and ``release``, you can do
the following:

.. code:: shell-session

    % mmh -d ci -T gnu,clang -B ninja -C release,debug

…bringing down the number of instances to four instead of forty. You can also
hand additional parameters to each configuration call to ``cmake`` using ``++``
followed by a list of such parameters at the end of a ``mmh build`` call:

.. code:: shell-session

    % mmh -d ci -T gnu,clang -B ninja -C release,debug ++ -DAAA=aaa -DBBB=bbb

With calls like this, ``mmh`` records the set of parameters used in a file in
the generated build-tree, so that re-running the same build is as easy as this:

.. code:: shell-session

    % mmh -d ci run-instance


See Also
********

:manpage:`cmake(1)`,
:manpage:`cmake-variables(7)`,
:manpage:`ctest(1)`,
:manpage:`git(1)`,
:manpage:`gitworkflows(7)`,
:manpage:`make(1)`,
:manpage:`ninja(1)`


Copyright
*********

.. include:: ../LICENCE


.. toctree::
   :maxdepth: 2
   :caption: Contents:
