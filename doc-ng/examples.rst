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
