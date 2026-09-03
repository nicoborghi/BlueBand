Files, printing and packaging
=============================

.. _storage:

Storage
-------

One folder per competition. Everything the jury makes is in it, and it copies to
a memory stick at the end of the day.

.. code-block:: text

   competitions/CITA26/
     programme.yaml         track, categories, events, rounds, distances, register
     entry_list.xlsx        the competition's own workbook
     entries_import.json    snapshot of the entry workbook (read-only)
     entries_overlay.json   jury edits, each with a reason and a date
     races/<race_id>.json   the state of every race
     communiques.json       the communiqués actually issued
     decisions.json         the jury's decision log
     settings.json          local choices (output folder, language, team grouping)
     out/<NNN>_<slug>.pdf   produced communiqués (folder configurable)
     .snapshots/<rel>/<ts>.json   previous content of every file written
     journal.jsonl          append-only log of every write

The root is ``competitions/`` in a checkout and ``Documents\BlueBand`` when
installed, overridden by ``COMMISSAIRE_TRACK_DATA`` either way. Competition
folders are the jury's work and stay out of the repository — the one exception
is ``competitions/example/``.

Nothing is lost
~~~~~~~~~~~~~~~

Every write is atomic — temp file plus ``os.replace`` — and keeps the previous
content as a snapshot. Nothing typed by the jury can be lost by a crash, a bad
edit or a browser reload.

.. code-block:: python

   store.write_json(rel, data, action="save_race")   # atomic + snapshot + journal
   store.snapshots(rel)                              # every previous version
   store.restore(rel)                                # roll back one
   store.backup(dest)                                # the whole folder
   store.read_journal(limit=200)

``journal.jsonl`` is append-only and never rewritten: one line per write, with
the action, the target and the time. It is what answers *what happened at 14:30*
— including why a PDF came out as HTML.

``races/<race_id>.json`` is a ``RaceState``, and everything a format needs lives
in its ``payload``. The race id is ``race.race_key(cat, event, round_key)``, and
round keys are the strings written in ``programme.yaml`` — which is why
translating a round name would orphan its race file.

``settings.json`` holds the choices of *this machine and this competition*:
``language``, ``out_dir``, ``use_overlay``, the letterhead in progress, and
various UI keys. Anything that is a statement about the **competition** — what a
team is, the entry-file layout, the branding — lives in ``programme.yaml``, not
here.

``core.paths``
~~~~~~~~~~~~~~

Run from the repository, every path answers with the repository. Installed, two
different places, and conflating them is how a jury loses a championship.

``bundle()``
   **What the program is** — regulations, templates, stylesheet. Read-only,
   replaced wholesale by the next version, and under PyInstaller it lives in
   ``sys._MEIPASS``.

``data()``
   **What the jury made** — competitions, results, communiqués. It must outlive
   an uninstall, be findable without a file manager, and be easy to copy to a
   stick, so it goes in the user's Documents and never inside the installation.

``served()``
   The copies of the last saved PDFs that Streamlit serves out of ``static/``.

``core.paths`` is the only module that knows any of this, which is why nothing
else in the codebase had to learn about ``sys._MEIPASS``.


.. _regulations:

Regulation files
----------------

Eight JSON tables under ``regulations/``. **The regulation is data, not code**:
a rule that changes next year is a file edit, and none of it needs a release.

Two kinds live here, maintained differently: **ours**, written by the app as
well as read by it (``distances.json``, ``events.json``, ``categories.json``,
``notes.json``, ``communiques.json``, ``entry_formats.json``); and **theirs**,
read-only and replaced wholesale by a newer version (``penalties.json`` from the
UCI, ``PUIS.json`` from the federation).

.. list-table::
   :header-rows: 1
   :widths: 26 24 50

   * - File
     - Read by
     - What it holds
   * - ``events.json``
     - ``core.catalogue``
     - What an event *is*: code, name per language, UCI abbreviation, format,
       riders per team, how many start together, the entry-column headings.
   * - ``categories.json``
     - ``core.catalogue``
     - The standard category codes, with sex and name per language.
   * - ``distances.json``
     - ``core.distances``
     - How long a race is, how often it sprints.
   * - ``entry_formats.json``
     - ``core.entry_formats``
     - How each shape of entry file is read.
   * - ``notes.json``
     - ``core.notes``
     - Which regulation line opens which sheet.
   * - ``communiques.json``
     - ``core.communiques``
     - Which sheets share a number, per format.
   * - ``penalties.json``
     - ``core.decisions``
     - The UCI wording of track offences, in four languages, numbered as the
       UCI numbers them.
   * - ``PUIS.json``
     - ``core.decisions``
     - The federal table of what each infringement costs.

Every file carries ``_last_updated_``, and most carry ``_about_``. Neither is
read by the code.

The **name of an event is per language**, because it is not a label: it is
written into ``programme.yaml`` and printed on the sheets exactly as it stands
there. Adding an event to an English competition writes the English name, and it
prints in English next year too, whoever opens the file. An event the table does
not know is still declared by hand in the programme.

Distances are matched loosely on three levels — **event → category → round**. A
round is looked up by its own name first, then by the family it belongs to, then
by ``*``. Nothing here is invented: the file ships seeded from a programme that
was actually run, and an event the table says nothing about proposes no distance
at all — a blank field on the page rather than a wrong number on a sheet.

``notes.json`` holds two things. **Which line goes on which sheet** is ``rules``,
and it ships filled in, because it is the regulation — one rule per sentence,
naming the format, the round, the document and the condition. **The numbers are
the programme's**: a rule names the field it reads, and the placeholder is filled
from the round as the jury typed it. ``texts`` is the installation's own wording
of any catalogue entry, and it ships empty.


.. _printing:

Printing
--------

One pipeline for every sheet the app produces.

.. code-block:: text

   core state          render/documents.py      render/render.py       render/pdf.py
   entry list,   ───►  Document(title, ...)  ─►  HTML fragment    ─►   headless
   race state,         Table(Column, rows)       or standalone page    Chromium
   survey                                        (print.css inlined)   → PDF bytes

.. code-block:: python

   Document(title, subtitle, info, legend, communique, draft, date,
            body, tables=[Table], notes=[Note], decision="", landscape=False)
   Table(columns=[Column], rows=[dict], font_size=9, title="")
   Column(key, label=None, align="l", w=10, bold=False, wrap=False,
          muted=False, tight=False, min_mm=0)
   Note(text, kind="note", title="")

**``w`` is a weight, not a width.** The table normalises its columns' weights to
percentages summing to 100, so no sheet can starve a column into a
two-character sliver.

**``min_mm`` is the one thing a weight cannot express**: how narrow a column may
actually get *on paper*. A name that loses its last letters is still a name;
``DNF`` truncated to ``DN…`` and a UCI ID missing two digits are not the thing
they are printed for. Those columns declare the millimetres they need and the
table gives them, out of what the others were sharing.

**Notes are tinted by kind.** A disqualification and "the first two go through
to the final" are both prose in a box, and they are not the same thing: one is a
sanction a team may appeal, the other is how the tournament is run. The plain
note prints last and keeps its grey, because a colour on it would say somebody
had been sanctioned.

**Landscape is opt-in, never automatic.** Chrome does not repeat a table header
group across the pages of a named page, so a landscape communiqué loses its
letterhead on every continuation sheet — the one thing these documents must not
lose.

The sheets carry a full-width letterhead and footer repeated on every page —
they are the ``thead`` and ``tfoot`` of one table, which is how a browser repeats
them. Around the table, six slots, each holding one of ``communique``,
``printed_at`` or nothing; an element lives in one place, so putting it elsewhere
removes it from where it was. A provisional sheet (``draft=True``) prints a
"not final" box where the number goes.

``render/print.css`` is one file used in two places: inlined into the standalone
page that Chromium prints, and injected into the Streamlit app so the previews
look like the sheet. Everything in it is scoped to ``.cmsr`` except the ``@media
print`` block, which hides the sidebar and the toolbar when the jury prints
straight from the browser.

.. note::

   The CSS goes in through ``st.markdown``, not ``st.html``: the latter
   sanitises what it is handed and throws away its ``<style>``. The same
   sanitiser drops the whole SVG namespace, which is why the derny charts are
   drawn with ``st.markdown`` too.

``render/pdf.py`` runs a headless Chromium — the same engine the jury would
print with by hand, so the PDF is what the browser's own print produces minus
its date and URL header. No extra Python dependency.

**Where Chromium works is not where the document ends up.** The browser has to
*read* the page and *write* the PDF, and a sandboxed Chromium can do neither
under ``/tmp`` nor on the network mount the communiqués folder usually is. So
``work_dirs`` tries the caller's directory first, then local candidates, and only
the finished bytes are written to the destination. A directory that has worked
once goes to the front — printing a whole day must not pay for the same failed
attempt on every sheet.

``out_name`` produces ``018_classification_madison_final.pdf`` — the communiqué
number, then a slug of the title.

``render/markup.py`` is four constructs of markdown — headings, bold, italic,
code, bullets, numbers, a rule, paragraphs — for the one place in the app that
takes prose rather than a field. **Everything is escaped before anything is
read.** What the jury types is text, never markup: a sheet that renders an
``<img>`` somebody pasted into the box is a sheet that can be made to say
anything.


.. _i18n:

Translations
------------

The code speaks UCI English — competition, event, round, bib, club, region. What
reaches a screen or a printed sheet is a **lookup, never a literal**.

.. code-block:: python

   from core.i18n import label, ui, msg, help_text

   label("bib")                        # "Dors."  /  "Bib"
   ui("save_pdf")
   msg("bib_not_entered", bib=17)
   help_text("status_dns")

Nothing under ``core/``, ``render/`` or ``ui/`` writes prose of its own. Adding
a language is adding one module and listing it in ``CATALOGUES``; correcting a
wording is editing one entry.

Each catalogue defines the same dictionaries, named by what they name:
``FIELDS`` (a column of the entry list), ``RACE`` (a column or word of a race
sheet), ``DOCS`` (a kind of document), ``STATUSES`` and ``STATUS_NAMES`` (the
result codes as printed and spelled out), ``PENALTIES``, ``NOTE_KINDS``,
``CODES``, ``UI``, ``HELP`` and ``MSG``.

``label(key)`` does **not** raise on an unknown key — it comes back capitalised,
so a new column still shows up readable. ``ui``, ``msg`` and ``help_text`` do: a
missing control label is a bug to fix, not a word to invent. A key the language
in force does not have is answered from the default catalogue, which is a good
deal better than an empty widget or a ``KeyError`` at the track.

The language is **per competition**, chosen in the settings and set once per
rerun before anything draws a word. It moves the **catalogue only**: what
``programme.yaml`` spells out — the names of the categories, the events and the
rounds — prints as it is written there, in any language. Those strings are also
the keys races are stored under.

To add a language: copy an existing catalogue, translate the values keeping every
key, set ``NAME``, and add it to ``CATALOGUES``. ``tests/test_i18n.py`` then
checks that every key the app asks for exists, that every language answers all of
them **with the same placeholders**, and that no module outside ``core/i18n/``
writes prose of its own.

The abbreviations a printed sheet uses are the **UCI** ones — see the
:ref:`glossary`.


.. _build:

Windows build
-------------

The console ships as an ``.exe`` a jury installs by double-clicking.

.. code-block:: bash

   python packaging/make_icon.py                 # ui/track.svg -> .ico
   pyinstaller packaging/blueband.spec --noconfirm
   iscc packaging/blueband.iss                   # Windows only, Inno Setup 6

Out comes ``dist/BlueBand-<version>-setup.exe``. CI does the same on every
``v*`` tag and attaches it to the release.

What it weighs, and why
~~~~~~~~~~~~~~~~~~~~~~~

The app installs at **about 435 MB**, and most of that is three packages the
console never imports by name: pandas, numpy and pyarrow (~334 MB), Streamlit
and its dependencies (~87 MB), CPython and the bootloader (~20 MB). The app
itself, with its regulations and templates, is about 1 MB.

They are there because ``st.dataframe`` and ``st.data_editor`` are made of them.
**This was measured, and the alternative was built and rejected**: hand-written
HTML tables brought the installation down to 108 MB and were worse to use — rows
twice as tall, a select too narrow to read, and none of the sorting, resizing,
full screen, search and copy that come free. Keep that in mind before
"optimising" the dependency list: the size is a decision that has already been
taken, once, with numbers.

The three awkward things about freezing Streamlit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All three are solved in ``packaging/blueband.spec``, and each was a build that
succeeded and then failed at runtime:

#. **Streamlit reads its own version from its installed metadata.** Without the
   ``.dist-info`` in the bundle it raises at import — ``copy_metadata``.
#. **Its frontend is data.** ``streamlit/static/`` is the compiled React app —
   ``collect_data_files``.
#. **The app is never imported.** The analysis starts at ``launcher.py``, which
   hands Streamlit ``app.py`` as a *path*, so ``core``, ``ui`` and ``render``
   are in no import graph: the bundle starts, serves a page, and dies on ``No
   module named 'core'`` at the first render. ``collect_submodules``, with the
   repository put on ``sys.path`` first — without that it finds nothing and
   returns an empty list **with only a warning**.

``BlueBand.exe --check`` is the guard against all three: it imports every module
and looks for every data file, and it fails at the door instead of on the jury's
first click.

The install is **per-user on purpose**, twice over: no administrator prompt on a
laptop nobody has the password for, and the program's folder stays writable —
Streamlit serves the last saved PDFs out of ``static/`` inside it.

Building on Linux
~~~~~~~~~~~~~~~~~

The whole recipe except the ``.ico`` and the installer works on Linux, and that
is worth doing before pushing a tag:

.. code-block:: bash

   python -m venv /tmp/bb && /tmp/bb/bin/pip install -e ".[build]"
   /tmp/bb/bin/pyinstaller packaging/blueband.spec --noconfirm
   dist/BlueBand/BlueBand --check

Build it in a **clean virtual environment**, never in a working scientific one:
PyInstaller bundles what it finds, and the ``excludes`` in the spec are a safety
net rather than a guarantee.
