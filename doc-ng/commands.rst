.. _ch-command-reference:

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
