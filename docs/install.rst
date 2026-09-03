.. _install:

Install and run
===============

.. note::

   **Packaging is not implemented yet.** There is no installer and no release
   to download, so there is one way in: a checkout. ``packaging/`` holds a
   work-in-progress PyInstaller spec and Inno Setup script, and neither ships
   a build today. Where this page says what the packaged program *would* do,
   it is describing intent, not something you can install.


From a checkout
---------------

Python ≥ 3.11.

.. code-block:: bash

   git clone https://github.com/nicoborghi/BlueBand
   cd BlueBand
   pip install -e .
   streamlit run app.py

``python launcher.py`` is the other way in: it picks a free port, starts
Streamlit in-process and opens the browser. It is what a packaged build would
run, so it is also how that behaviour gets tested.

Dependencies are **pinned, not ranged** (see ``pyproject.toml``): a version
that drifts between the laptop something was tested on and the one it is run on
is a version nobody tested.


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


Packaging
---------

Not implemented yet — see the note at the top of this page.
