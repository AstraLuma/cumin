======
Cumin
======

Cumin contains a Python library and CLI scripts for accessing a remote
`salt-api`__ instance.

``cumin`` abstracts the HTTP calls to ``salt-api`` so existing Python
projects can easily integrate with a remote Salt installation just by
instantiating a class.

The ``cumin`` CLI script allows users to execute Salt commands from computers
that are external to computers running the ``salt-master`` or ``salt-minion``
daemons as though they were running Salt locally. The long-term goal is to add
additional CLI scripts maintain the same interface as Salt's own CLI scripts
(``salt``, ``salt-run``, ``salt-key``, etc).

It does not require any additional dependencies and runs on Python 2.5+ and
Python 3. (Python 3 support is new, please file an issue if you encounter
trouble.)

.. __: https://github.com/saltstack/salt-api

Installation
------------
.. code-block:: bash

    pip install salt-cumin

Usage
-----

Basic usage is in heavy flux.

.. code-block:: bash

    export SALTAPI_USER=saltdev SALTAPI_PASS=saltdev SALTAPI_EAUTH=pam
    cumin '*' test.ping
    cumin '*' test.kwarg hello=dolly

Examples leveraging the runner client.

.. code-block:: bash

    cumin --client runner reactor.list
    cumin --client runner reactor.add event='test/provision/*' reactors='/srv/salt/state/reactor/test-provision.sls'

Configuration
-------------

You can configure cumin through the command line, using environment variables
or in a configuration file ``$HOME/.pepperrc`` with the following syntax :

.. code-block::

  [main]
  SALTAPI_URL=https://localhost:8000/
  SALTAPI_USER=saltdev
  SALTAPI_PASS=saltdev
  SALTAPI_EAUTH=pam

Contributing
------------

Please feel free to get involved by sending pull requests or join us on the
Salt mailing list or on IRC in #salt or #salt-devel.

This repo follows the same `contributing guidelines`__ as Salt and uses
separate develop and master branches for in-progress additions and bug-fix
changes respectively.

.. __: https://docs.saltstack.com/en/latest/topics/development/contributing.html
