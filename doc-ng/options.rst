.. _sec-toplevel-options:

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
