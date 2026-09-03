.. _reference:

Architecture
============

.. note::

   The technical reference is maintained in English, like the code it
   describes: the vocabulary here — ``competition``, ``event``, ``round`` — is
   the vocabulary of the source. The jury-facing pages are translated. See the
   :ref:`glossary` for the terms.

Three layers, in one direction only.

.. code-block:: text

   ui/       Streamlit. Widgets, session state, page flow.
      │      Imports core and render. Nothing imports it.
      ▼
   render/   Document / Table / Column → HTML → PDF.
      │      Imports core. Knows nothing about Streamlit.
      ▼
   core/     The domain. Plain Python, JSON-round-trippable data,
             no Streamlit anywhere. Tested headless.

``core.store`` is the only module in ``core/`` that touches the filesystem;
``core.paths`` is the only one that knows whether the app is a checkout or an
installed program.


Ground rules
------------

These hold everywhere in the codebase, and most of this reference is a
consequence of one of them.

**Nothing under** ``core/`` **imports Streamlit.** The domain — scoring,
composition tables, the register, the medal count — is plain Python and is
tested headless.

**Nothing outside** ``core/i18n/`` **writes prose.** Every word that reaches a
screen or a sheet is a catalogue lookup. ``tests/test_i18n.py`` enforces it.

**Nothing is ever lost.** Every write is atomic, keeps the previous content as a
snapshot, and is recorded in an append-only journal. The federation's entry
workbook is not written to at all unless the competition explicitly asks for it.

**The regulation is data.** Distances, event definitions, category codes, sheet
notes, communiqué merge rules and penalty tables are JSON files under
``regulations/``, not code. A rule that changes next year is a file edit.

**A proposal is not a decision.** What the regulation suggests — a round's
distance, a communiqué number, the wording of a decision — is filled in and
stays editable. Nothing the app proposes is more true than what the jury types
over it.


``core/`` — the domain
----------------------

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Module
     - What it owns
   * - ``config.py``
     - ``programme.yaml`` → dataclasses: ``Competition``, ``Category``,
       ``Event``, ``Round``, ``ProgrammeItem``, ``CommuniqueSpec``,
       ``Branding``, ``EntrySheet``, ``Check``. The vocabulary of everything
       else.
   * - ``programme.py``
     - The other direction: ``Competition`` → text, in a stable layout, plus
       the validation that runs before a save.
   * - ``models.py``
     - ``Rider``, ``Team``, ``Pair``, ``RaceState``, ``Status``,
       ``EntryList``. Plain data, ``to_dict`` / ``from_dict``.
   * - ``store.py``
     - Atomic JSON, snapshots, the journal, backup, the race files.
   * - ``paths.py``
     - Checkout or installed program: where the data and read-only files are.
   * - ``race.py``
     - The service layer between the UI and the formats: who is entered, which
       format applies, how a round ranks, how a bracket composes the next one.
   * - ``formats/``
     - ``base``, ``group``, ``timed``, ``sprint``, ``keirin``, ``omnium``,
       ``derny``. One module per family of race.
   * - ``rounds.py``
     - What a format runs: the rounds proposed from the regulation, with
       distance, laps, sprints and the documents each files.
   * - ``distances.py``
     - How long a race is, and how often it sprints.
   * - ``catalogue.py``
     - The event definitions and category codes, ready to add to a programme.
   * - ``entries.py`` / ``entry_book.py`` / ``entry_formats.py``
     - Excel import, the overlay of jury edits, validation, write-back, and the
       competition's own workbook.
   * - ``checks.py``
     - The one implementation of the inline bib flags, and the ``Issue`` shape
       every validation reports in.
   * - ``parse.py``
     - The jury's shorthand: sprints, heats, bibs, times.
   * - ``communiques.py``
     - Planning, merge rules, autonumbering, the issued register.
   * - ``decisions.py``
     - The jury's decision log, and the read-only UCI and federal tables.
   * - ``notes.py``
     - Which regulation line opens which sheet.
   * - ``medals.py`` / ``trofeo.py`` / ``recap.py``
     - The medal table, the team points classification, and the per-team
       recaps.
   * - ``i18n/``
     - One catalogue per language. The only place with prose in it.


``render/`` — the printed sheet
-------------------------------

``documents.py`` turns entry lists, race states and survey results into
``Document``\ s; ``render.py`` turns a ``Document`` into HTML, either a fragment
to embed in the app or a self-contained page for the archive; ``pdf.py`` runs a
headless Chromium over it. ``markup.py`` is the four-construct markdown the
letterhead sheet accepts. See :ref:`printing`.


``ui/`` — the app
-----------------

Seven pages under ``ui/pages/``, plus shared pieces that exist because the same
thing was being done four different ways: ``state.py`` (the only place that
knows about ``st.session_state``), ``notify.py`` (the only way the app says
anything), ``savebar.py``, ``publish.py``, ``download.py``, ``style.py``,
``icons.py`` (SVG paths — nothing is fetched from a CDN, because the app runs
at a velodrome, often off the network) and ``scroll.py``.

**The savebar records; it does not save.** The strip is drawn at the *top* of
the run, before the page body has read a single field, so a race saved there
would be the race as it was when the run started. ``savebar.render()`` leaves a
request behind and the page picks it up after everything has been built:

.. code-block:: python

   savebar.render(label=ui("save"), restore_label=ui("restore_previous"))
   ...                                     # the whole page
   if savebar.requested() == savebar.SAVE:
       store.save_race(state)

``app.py`` is the Streamlit entry point. ``launcher.py`` is what the desktop
icon starts: pick a free port, run Streamlit **in this process** through
``bootstrap.run`` (the packaged program has no ``streamlit`` on any ``PATH`` to
re-exec), open the browser once the server answers. A competition folder with no
``programme.yaml`` opens on ``ui/pages/setup.py``, which uses the *same widgets*
as the Programme page rather than a second form that would drift from the first.


Testing
-------

``tests/`` runs against ``competitions/example/``, a fictional meeting that
ships with the repository. UI tests drive the real pages through Streamlit's
``AppTest``, which is why input widgets that cannot be driven headless are not
used: an input this app cannot test is an input it does not keep.
