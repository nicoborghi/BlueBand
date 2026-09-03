.. _install:

Install and run
===============

On a jury laptop
----------------

Install `the latest BlueBand-setup.exe
<https://github.com/nicoborghi/BlueBand/releases>`_ and start it from the
desktop icon. No Python, no command line, no administrator prompt — the
install is per-user.

.. list-table::
   :header-rows: 1
   :widths: 30 45 25

   * - What
     - Where
     - Survives an uninstall
   * - the program
     - ``%LOCALAPPDATA%\Programs\Blue Band``
     - no
   * - the competitions
     - ``Documents\BlueBand``
     - **yes**
   * - the communiqués
     - wherever Settings points, usually a shared drive
     - **yes**

Closing the console window stops the server. Closing the browser tab does not —
which is what lets the jury reopen the app from browser history mid-competition.


From a checkout
---------------

Python ≥ 3.11.

.. code-block:: bash

   git clone https://github.com/nicoborghi/BlueBand
   cd BlueBand
   pip install -e .
   streamlit run app.py

``python launcher.py`` is the other way in, and the one the installer runs: it
picks a free port, starts Streamlit in-process and opens the browser. Use it to
test the packaged behaviour without building an installer.

Dependencies are **pinned, not ranged** (see ``pyproject.toml``): the same list
is the Windows installer's manifest, and a version that drifts between the
laptop a release was tested on and the one it was built on is a version nobody
tested.


Where the data goes
-------------------

One folder per competition under ``competitions/``. Override the root with
``COMMISSAIRE_TRACK_DATA``:

.. code-block:: bash

   export COMMISSAIRE_TRACK_DATA=/mnt/g/My\ Drive/championships
   streamlit run app.py

Competition folders are the jury's work and stay out of the repository. See
:ref:`storage` for what is inside one.


The example competition
-----------------------

One competition *is* in the repository: ``competitions/example/``, a meeting
that never happened, with a fictional field of 140 riders. Open it to see the
console working without holding a real entry list — and note that it is what
the tests run on.

#. ``streamlit run app.py``
#. Settings → pick **Trofeo di Esempio 2026**
#. Programme → Entries → build the entry list from ``Iscritti_999999.xlsx``,
   in the same folder

The five pages about riders (check-in, races, decisions, documents,
statistics) do not appear until an entry list exists: they have nothing to
show. ``competitions/example/README.md`` says what is invented in it and what
is deliberately real.


PDF output
----------

PDFs come from a **headless Chromium** — the same engine the jury would print
with by hand. Nothing to install on Windows (Edge is found); on Linux any of
``chromium``, ``chromium-browser``, ``google-chrome``,
``google-chrome-stable``, ``chrome`` or ``msedge`` on ``PATH`` will do.

With no browser at all the app saves the self-contained HTML instead and writes
the reason to ``journal.jsonl``.


Tests
-----

.. code-block:: bash

   pip install -e ".[dev]"
   python -m pytest tests -q
   ruff check .

Roughly a third of the suite is skipped without the commissaire's shared
folder: those tests read the federation's real entry workbook, which carries
riders' personal data and is not in the repository. ``tests/conftest.py`` skips
them where the file is missing, so CI coverage is a floor rather than the whole
picture — read a drop, not the absolute number.


Building the installer
----------------------

See :ref:`build`.
