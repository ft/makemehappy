MakeMeHappy — Build Orchestration
#################################

Synopsis
********

``mmh [OPTION(s)…] SUBCMD [SUBOPTION(s)…] [++ CMAKE-PARAM(s)…]``

The set of top-level ``OPTION(s)…`` is documented in
:ref:`sec-toplevel-options`. A reference for all possibile uses of ``SUBCMD``
can be found in :ref:`ch-command-reference`. All ``SUBOPTION(s)…`` are specific
to the active ``SUBCMD``. ``OPTION(s)…`` and ``SUBOPTION(s)…`` cannot be mixed;
the former go right after the ``mmh`` program and the latter have to be used
after the ``SUBCMD``. If ``SUBCMD`` has further sub-sub-commands, this is also
true here: All options always have to follow the level of command they are
intended for. All parameters found after the literal word ``++`` will be passed
verbatim to ``cmake`` processes in configuration phases.


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
   :hidden:

   description.rst
   commands.rst
   buildspec.rst
   examples.rst
   options.rst
   configuration.rst
   miscellaneous.rst
