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
**********

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
*****************

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
