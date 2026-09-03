.. raw:: html

    <style media="screen" type="text/css">h1 {display:none;}</style>

**********
Blue Band
**********

**Commissaires' console for track cycling competitions.**

.. image:: https://img.shields.io/badge/GitHub-BlueBand-9e8ed7
    :target: https://github.com/nicoborghi/BlueBand/
    :alt: GitHub
.. image:: https://github.com/nicoborghi/BlueBand/actions/workflows/tests.yml/badge.svg
    :target: https://github.com/nicoborghi/BlueBand/actions/workflows/tests.yml
    :alt: Tests
.. image:: https://img.shields.io/codecov/c/github/nicoborghi/BlueBand
    :target: https://codecov.io/gh/nicoborghi/BlueBand
    :alt: Coverage
.. image:: https://img.shields.io/badge/license-GPLv3-fb7e21
    :target: https://github.com/nicoborghi/BlueBand/blob/main/LICENSE
    :alt: License

.. warning::

   Experimental. Used at the Italian Youth Track Championships (2025, 2026)
   and nowhere else. Much of the codebase is AI-generated. Feedback and
   contributions are welcome — open an
   `issue <https://github.com/nicoborghi/BlueBand/issues>`_ or a pull request.

Blue Band is what a commissaires' panel runs a track meeting from: licence
check, entry lists, results, classifications, jury decisions, and the numbered
communiqués that publish all of it. It is a Streamlit app that runs on a laptop
at the velodrome — often off the network — and writes everything it does to
plain files in one folder per competition.

One YAML file per competition (``programme.yaml``) says what is being run: the
track, the categories, which events each contests, the rounds of every event,
the running order of each day, and the communiqué register. Running next
year's edition means editing that file.


Quick start
===========

On a jury laptop, install `the latest BlueBand-setup.exe
<https://github.com/nicoborghi/BlueBand/releases>`_ and start it from the
desktop icon — no Python, no command line. From a checkout:

.. code-block:: bash

   git clone https://github.com/nicoborghi/BlueBand
   cd BlueBand
   pip install -e .
   streamlit run app.py

See :doc:`install` for both paths, the example competition, and where the data
lands.


What it does
============

Licence check
   Counters, the event-entry table, quota checks against the regulation. Jury
   edits are recorded as patches keyed by UCI ID; the entry workbook is never
   written unless you ask for it.

Races
   Every format track cycling runs: bunch races, pursuits, sprint and keirin
   brackets, omnium, madison, derny — with results typed in the jury's own
   shorthand.

Decisions
   One row per decision of the panel, with the UCI code and the sentence
   published under it. A warning follows the rider through the event.

Communiqués
   A numbered register planned from the running order, with the merge rules of
   the regulation applied: which sheets share a number, in what order they can
   be published.

Printing
   Headless Chromium to PDF, with the meeting's letterhead, footer and
   signature on every page. With no browser available, a self-contained HTML
   file instead — nothing is ever lost for want of a renderer.

Statistics
   The medal table and the podiums it is counted from, plus the team points
   classification where the meeting has one.

Everything under ``core/`` is plain Python — no Streamlit, no I/O beyond
``core.store`` — so the scoring, the composition tables and the register are
testable headless, and they are.


Documentation
=============

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   install
   guide
   glossary

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/index
   reference/programme
   reference/formats
   reference/entries
   reference/files


Licence
=======

GPLv3 — see `LICENSE
<https://github.com/nicoborghi/BlueBand/blob/main/LICENSE>`_.
