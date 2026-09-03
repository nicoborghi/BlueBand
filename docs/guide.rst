.. _guide:

Running a competition
=====================

What to click, and what happens when you do. It does not explain the
regulations — it explains the console.

.. tip:: **The rule that always holds**

   Nothing is lost. Every save keeps the previous version, reloading the
   browser erases nothing, and the federation's entry workbook is **never
   written by the app** unless you explicitly ask it to be.


The seven pages
---------------

Chosen from the left-hand column.

.. list-table::
   :header-rows: 1
   :widths: 18 52 30

   * - Page
     - What it is for
     - When
   * - **Programme**
     - Defines what is ridden, when, and when each communiqué goes out
     - Before the competition
   * - **Settings**
     - Output folder, letterhead, signature, team grouping, backup
     - Once, at the start
   * - **Check-in**
     - Licence check, corrections to rider data, entry to events
     - The day before, and each morning
   * - **Documents**
     - Entry lists, batch printing, per-team recaps, letterhead sheet, register
     - Before each event, and at the end of each day
   * - **Races**
     - Runs a race: results, classification, communiqué
     - During the racing
   * - **Decisions**
     - The jury's decision register
     - Whenever the panel rules on something
   * - **Statistics**
     - Medal table, podiums, and the team classification where there is one
     - End of day, and at the prize-giving

The five pages about riders — check-in, races, decisions, documents,
statistics — **do not appear until an entry list exists**: they have nothing to
show. The entry list is built in *Programme → Entries*.


The order to use them in
------------------------

1. :ref:`Programme <programme-yaml>` — categories, events, rounds, days, the
   communiqué register. It is the file everything else comes out of.
2. **Settings** — where the PDFs go, what they look like, what a team is.
3. **Check-in** — the desk: licences, bibs, who rides what.
4. **Races** — the working page, for the whole competition.


One folder per competition
--------------------------

Everything the jury writes lives in a single folder, copied to a memory stick
at the end of each day:

.. code-block:: text

   CITA26/
     programme.yaml        track, categories, events, rounds, register
     entry_list.xlsx       the competition's own entry workbook
     entries_import.json   the last import, read-only
     entries_overlay.json  the jury's corrections, each with its reason
     races/<id>.json       the state of every race
     communiques.json      the communiqués actually issued
     decisions.json        the decision register
     settings.json         local choices (output folder, language)
     out/                  the PDFs produced
     .snapshots/           the previous content of every file written
     journal.jsonl         the record of every write

See :ref:`storage` for what each of them holds.


When something goes wrong
-------------------------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Symptom
     - What to do
   * - No PDF, an ``.html`` instead
     - Chromium is not installed, or cannot read the folder. Print the HTML
       with :kbd:`Ctrl+P`. The reason is in ``journal.jsonl``.
   * - Saved a wrong result
     - *↩ Restore previous version*, in the Races sidebar.
   * - Got a whole event wrong
     - *Settings → Reset an event*. Clears every round of it; the previous
       versions stay in ``.snapshots/``.
   * - Corrected an edit badly at check-in
     - *Undo the last edit*, at the foot of the page.
   * - The browser closed
     - Reopen it. Everything saved is still there: the server is the console
       window, not the tab.
   * - No letterhead on the communiqué
     - *Settings → Communiqué appearance → Letterhead*: the image is missing.
   * - The communiqué register is out of date
     - *Programme → Planning → Recompute the numbers*. It shows what changes
       before writing anything.
   * - The five rider pages are not there
     - There is no entry list yet: *Programme → Categories*, at the bottom.

.. tip:: **Before leaving**

   *Settings → Data and backup → Create a backup*, and copy the folder to a
   shared drive.

The codes typed into results — ``DNS``, ``DNF``, ``ABD``, ``DSQ``, ``REL``,
``NS``, ``W`` — and what each does to a classification are in the
:ref:`glossary`.
