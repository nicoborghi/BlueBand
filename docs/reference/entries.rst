.. _entries:

Entry lists and communiqués
===========================

.. _entry-lists:

Entry lists
-----------

Three files, three jobs.

the federation's export
   What arrived. **Never written to**, unless the competition explicitly asks.
   Copied into the competition folder as proof of what was received.

``entry_list.xlsx``
   The workbook the competition is actually run from: an archive sheet plus one
   sheet per category, with a column per event. Written by the app.

``entries_import.json`` / ``entries_overlay.json``
   The read-only import snapshot, and the jury's edits as explicit patches.


The shapes an entry file arrives in
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``regulations/entry_formats.json`` is the table of them; ``core.entry_formats``
reads it. A third shape is a block in that JSON file, not a branch in the code.

``ksport`` (default)
   The flat federal export — one row per rider, no event columns at all. Which
   events a rider contests is not in it: the programme says which columns a
   category has, and the jury ticks them at the licence check.

``master``
   The workbook this app writes: an archive sheet plus one printable sheet per
   category, whose event columns hold ``X`` (starter), ``R`` (reserve) or a
   pairing letter.

**Column headings are never hard-coded.** ``entries.columns`` and
``entries.ksport`` in ``programme.yaml`` map the file's headings to the field
names used here, matched **by name rather than by position**, so a shifted
column does not silently import garbage and a differently-worded export is a
config change. What a competition states wins over the format's own table.

``entries.check_in`` is the third mapping and the odd one out: the two columns
of the licence check are not in the federation's layout at all — the jury adds
them to the workbook. Wherever they are, they are read on import and written
back by ``write_back``; where they are not, the check lives in the overlay.

Where the automatic match does not cover a file, the Programme page opens a
mapping dialog. It is how a file that puts the **region inside a "Note" column**
is read correctly. The mapping is saved into that competition's
``programme.yaml`` (``mapped: true``), and once answered the app stops reporting
missing columns — the question has an answer, including "none". The fields
without which nothing can be built are ``uci_id``, ``last_name``, ``cat`` and
``bib``.


The overlay
~~~~~~~~~~~

Every edit made in the app is a ``Patch`` in ``entries_overlay.json``, re-applied
on top of each new import. Patches are keyed by **UCI ID**, the one code that
does not change: a bib or a region corrected in the app survives any number of
reloads. A patch that no longer applies is reported at the check-in page rather
than silently dropped. Every edit but a check-in tick carries a reason and a
date.

.. code-block:: python

   from core import entries as E

   el, stale = E.effective_entries(store, comp)   # import + overlay applied
   E.save_overlay(store, E.load_overlay(store) + patches)
   E.overlay_on(store)                            # False → write to the workbook

With ``use_overlay: false`` in ``settings.json``, check-in writes **directly
into the entry workbook**: the cell is changed in the real file and the file is
re-imported straight away, with a copy taken into ``.snapshots/`` first. Rows
are matched by UCI ID; if the file changed on disk in the meantime the app stops
and asks for a reload rather than writing to the wrong row. Edits already in the
overlay are not lost — they stay, and come back when the setting is switched on.
There is no control for this on any page: it is a key in the settings file.


The workbook the app writes
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``core/entry_book.py`` builds and maintains ``entry_list.xlsx``.

.. code-block:: python

   from core import entry_book as B

   B.build(entries, comp, path)      # the workbook, from an imported list
   B.sync(path, comp)                # the same workbook, after the programme moved
   B.merge(old, new)                 # a corrected file, over the work already done
   B.numbered(entries, comp, how)    # bibs, when the export has none

**The programme comes first.** A sheet per category with a column per event
cannot be written before somebody has said which categories ride and what each
rides, which is why the page that calls this refuses to run until the programme
says so.

**The federal sheet is kept whole** — the export as it arrived, plus the two
columns of the licence check that the federation has no place for. Keeping it
means a re-import can be checked against what was actually received.

``merge`` shows what will change before it writes — new, no longer entered,
modified, ticks preserved — and then applies one rule: the **file** wins for
what the file knows (category, bib, club, federal data); the **workbook** wins
for what only the jury knows (the entry marks and the licence check). Bibs
already assigned are not cleared by an export that sends none. Riders are
matched by UCI ID, so one who changes category is still the same rider and keeps
their ticks.

Where the export sends no bibs, ``numbered`` assigns them one of three ways:
``1…N`` as they stand in the file, ``1…N`` per category consecutively, or from
``1`` for each category — the last only where two categories never take the
track together.

``core.checks.Issue`` is the shape every finding takes, wherever it is raised, so
they all render the same way. Nothing at the licence desk blocks: a rule set to
``error`` is red and counts in the summary; the meeting runs regardless.


.. _communiques:

Communiqués
-----------

A communiqué is a **number on paper**. More than one sheet can go out under it —
as the sprint and the keirin have always done — so the register is not a list of
documents, it is a list of numbers with documents attached. Numbers run
continuously across the whole competition and are **never reused**; an annulled
document keeps its number and prints ``NN RET``.

Two files, answering different questions: ``programme.yaml``'s ``communiques:``
block is what is **planned**; ``communiques.json`` is what has been **issued**,
written when a sheet is actually printed. At print time a document takes its
planned number; one that was not planned gets the next free one and is recorded,
so the register always reflects what went out.

A ``Sheet`` is ``(cat, event, round_key, doc)`` — one printed table. Which
sheets a round files comes from its format (``core.rounds.docs_for``) and is
written into the round's ``docs:`` list.


Not every sheet has a number
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``core.communiques.UNNUMBERED`` is the empty string, and it means exactly that:
nothing in the field, nothing in the register cell, nothing at the head of the
sheet, nothing in the filename. Two cases produce it.

* The register does not plan the sheet at all. The results of the qualifying
  heats of a bunch event are the usual case.
* The sheet **rides under another's number** — ``number_on_classification:
  true``, the default: where a round's results and the event's classification go
  out on one communiqué, the number prints on the classification only. It is the
  sheet that closes the event and the one people look for.


Merge rules
~~~~~~~~~~~

Which sheets share a number is **not written in the code**. It is five rules,
each generic, each on or off per format, in ``regulations/communiques.json``; a
competition overrides any of them in its own ``merge:`` block.

.. list-table::
   :header-rows: 1
   :widths: 32 48 20

   * - Rule
     - What it does
     - On by default for
   * - ``results_are_classification``
     - Where **one race** decides the event, the finishing order *is* the
       classification: one sheet. A madison, a scratch, an elimination. Not a
       team sprint, which is decided across two finals.
     - always
   * - ``results_with_next_startlist``
     - The next round is composed from those results and goes out right after.
       Not in timed events, where half a day passes between qualifying and the
       finals.
     - sprint, keirin
   * - ``partial_is_next_startlist``
     - An omnium's partial standings after a race *are* the start order of the
       next one: one number, two titles. Not before the first race.
     - omnium
   * - ``partial_is_results_of_first``
     - In the first race the finishing order *is* the partial standings — there
       is nothing to add to yet.
     - omnium
   * - ``last_results_with_classification``
     - Two tables on one sheet, because the second comes out of the first with
       nothing in between. What the omnium's points race does.
     - omnium


Autonumbering
~~~~~~~~~~~~~

``communiques.autonumber`` reads the programme, decides which sheets travel
together, and assigns every number **in the order the sheets can be published**
— which is not the order they are ridden. A sheet is ready when the results it
is made of have gone out; a start order is needed before its round runs. Move a
round in the running order and its communiqués move with it.

Three things it never touches, and it renumbers around them: a number **already
issued** (it is on paper), a number **typed by hand** (``pinned``), and an
**annulled** number (``ret``).

Numbers never move on their own. Recomputing is a button: it shows every change
— moved from N to M, new, dropped, held — and writes nothing until the jury
applies it.

The title of a communiqué names **everything it carries**, once. A communiqué
that publishes two things and names one is the reason a start order could not be
found in the register.

.. code-block:: python

   from core import communiques as C

   C.planned(comp)                    # the register, sorted by number
   C.number_for(comp, cat, event, round_key, doc)   # "" when unnumbered
   C.bundles(comp)                    # sheets grouped by the number they share
   C.merge_rules(comp, fmt)           # which rules apply to a format here
   C.autonumber(comp, register)       # the whole renumbering, as a proposal
   C.changes(comp, register)          # what autonumber would do, row by row
   C.issue(store, comp, cat=..., event=..., round_key=..., doc=...)
