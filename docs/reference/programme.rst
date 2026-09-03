.. _programme-yaml:

``programme.yaml``
==================

One file per competition, and everything the app does comes out of it: the
track, the categories, the events each contests, the rounds of every event with
their distances, the running order of each day, the entry-file layout and the
communiqué register.

It is edited from the Programme page and written by an emitter of our own
(``core/programme.py``) with a **stable layout**: saving the same programme
twice gives the same bytes, and read → write → read returns the same
``Competition``.

.. warning::

   A hand-written ``#`` comment is lost on the next write. Notes belong in the
   ``note:`` fields — on a programme item, on a round — which round-trip like
   everything else.


Top level
---------

.. code-block:: yaml

   name: Trofeo di Esempio 2026        # printed on every sheet
   short: example                      # a filename-safe handle
   id: "999999"                        # the federation's competition id
   location: Velodromo di Esempio
   dates: ["2026-09-02"]               # one entry per day; index 0 = day 1
   track_len: 0.3333                   # km. Laps are derived from it
   kind: championship                  # championship | ordinary | trofeo_regioni
   day_start: {1: "9:00"}              # the one clock time per day that is typed
   number_on_classification: true

   categories: {...}
   events: {...}
   programme: [...]
   communiques: [...]
   checks: [...]
   merge: {...}
   entries: {...}
   branding: {...}

``kind`` decides what a classification prints under the winner: a *championship*
names a champion, an *ordinary* meeting does not, and a *trofeo_regioni* adds
the team points classification to the statistics page.


``categories``
--------------

.. code-block:: yaml

   categories:
     ES: {name: ESORDIENTI MASCHI, sex: M, order: 1}
     OM: {name: OPEN MASCHILE, sex: M, order: 7, accepts: [EL, UN, "M*"]}

``accepts`` is what makes a category *open*: the licence codes admitted into it,
``M*`` taking every master code. Riders keep their own licence code beside the
name. Standard codes come from ``regulations/categories.json``; anything else is
declared here.


``events``
----------

.. code-block:: yaml

   events:
     ins_squadre:
       name: INSEGUIMENTO A SQUADRE    # printed as written, in any language
       short: Ins. Squadre
       order: 2
       # everything below is optional: it defaults from regulations/events.json
       abbr: TP                        # UCI code, for narrow column headings
       fmt: timed_team
       team_size: 4
       teams_per_start: 2
       entry_columns: ["Ins. Squadre"] # heading(s) in the entry workbook
       startlist_note: "..."           # the line every start order opens on

**What an event *is*** — code, abbreviation, format, riders per team, how many
start together — is the same at every meeting and lives in
``regulations/events.json``. The programme writes back only what it does
*differently*. The ``name`` always stays here, because it is what gets printed.

``fmt`` is one of ``group``, ``points``, ``tempo``, ``scratch``, ``madison``,
``elimination``, ``timed``, ``timed_team``, ``bracket``, ``derny``. See
:ref:`formats`.


``programme``
-------------

One entry per **(category, event)** pair — one event, whatever number of days it
spans:

.. code-block:: yaml

   programme:
     - cat: AL
       event: velocita
       day: 1                    # the default for its rounds
       scheme: "12"              # how many the 200 m qualifies
       final_5_8: true
       note: "..."               # service note, never printed
       rounds:
         - {key: Qualificazioni, seq: 3, distance: 0.2, start: "9:30",
            docs: [partenti, risultati], duration: 20, day: 1}
         - {key: Turno 1, seq: 9, heat_size: 2, qualify: 1,
            docs: [partenti, risultati, partenti_recuperi]}

.. note::

   The document kinds — ``partenti``, ``risultati``, ``classifica`` and the
   rest — and the round keys are **stored values**, not labels: they are what
   is written in this file and what race files are named after, so they are
   reproduced here exactly as they must be typed. Translating one would stop
   the app finding its own race. What the jury reads instead comes from
   ``core.i18n``; see :ref:`i18n`.

Round fields
~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Field
     - Meaning
   * - ``key``
     - The round's name. Written as it prints.
   * - ``label``
     - Display override, where the key is a technical one.
   * - ``seq``
     - Position in the day's running order.
   * - ``day``
     - Which day this round is on. An event split across days is one entry with
       rounds on different days.
   * - ``duration``
     - Minutes. **Start times are computed** from ``day_start`` plus the
       durations before it, not typed.
   * - ``distance`` / ``laps`` / ``sprints``
     - km, laps and number of sprints. An explicit value wins over the one
       derived from ``regulations/distances.json`` and the track length: some
       races do not follow the formula.
   * - ``docs``
     - Which sheets this round files. See :ref:`communiques`.
   * - ``heat_size``, ``qualify``
     - Sprint and keirin: riders per heat, how many advance.
   * - ``eliminate``
     - Madison and omnium qualifying heats: how many go out of each. UCI
       3.2.157 puts the floor at 2.
   * - ``kind``
     - ``setup`` for a round that is composed rather than ridden; ``pause`` for
       a break in the running order.
   * - ``note`` / ``sheet_note`` / ``results_note``
     - A service note (not printed), and the lines the start order and the
       results sheet open on (printed).

A **pause** is a round with ``kind: pause`` — no category, no event, no
communiqués. It exists because an hour the programme does not count is an hour
every time below it is wrong about.


``communiques``
---------------

The register. One entry per numbered sheet:

.. code-block:: yaml

   communiques:
     - {n: 7,  day: 1, cat: AL, event: ins_squadre, round: "Qualificazioni",
        doc: partenti, title: "AL Ins. Squadre Qualificazioni - Partenti"}
     - {n: 95, day: 3, cat: AL, event: velocita, round: "Turno 1",
        doc: risultati, with: [partenti_recuperi]}
     - {n: 25, day: 1, cat: AL, event: vel_squadre, round: "Finali",
        doc: risultati, with: [{round: "", doc: classifica}]}
     - {n: 31, ret: true}        # annulled: keeps the number, prints "31 RET"

``with:`` is how one number carries more than one sheet — a bare document kind
inherits the entry's own category, event and round; a mapping overrides what it
names. An empty ``round: ""`` means the sheet belongs to the *event*, not to any
round of it, which is what a classification is. ``pinned: true`` freezes a
number against recalculation. See :ref:`communiques`.


``checks``
----------

One row per sentence of the regulation's article on entries.

.. code-block:: yaml

   checks:
     - {cat: ES, event: omnium, unit: riders, per: region, max: 2,
        level: warn, note: "Art. 4 reg. 2026"}
     - {cat: "*", event: "*", unit: events, per: rider, max: 3, level: error}

``cat`` and ``event`` take a code or ``*``; ``unit`` is ``riders``, ``teams``,
``pairs`` or ``events``; ``per`` is ``region``, ``club``, ``club_in_region``,
``cat`` or ``rider`` (the last only with ``unit: events``); ``max: 0`` switches
the row off; ``level`` is ``error``, ``warn`` or ``off``; ``count_reserves``
says whether reserve entries count; ``note`` is the article, printed at the foot
of every finding the rule raises.

**Nothing here blocks.** A rule set to ``error`` is red at the licence desk and
counts in the summary; the meeting saves, prints and runs regardless. A
derogation is the jury's to grant, not the file's to refuse.


``entries``
-----------

How the entry file is read and what a team is at this meeting.

.. code-block:: yaml

   entries:
     source: Iscritti_999999.xlsx
     format: ksport               # a code from regulations/entry_formats.json
     header_row: 6
     first_data_row: 7
     columns: {"Dors.": bib, "UCI ID": uci_id, ...}
     check_in: {Verificato: checked_in, NP: not_starting}
     mapped: true                 # the jury has answered the mapping question
     team_group: region           # region | club | province | nation
     team_merge: {"VALLE D'AOSTA": "PIEMONTE - V.D.A"}
     team_merge_events: [ins_squadre]

Column headings are matched **by name, never by position**, so a shifted column
does not silently import garbage and a differently-worded export is a config
change rather than a code change. What a competition states here wins over the
format's own table.

.. note::

   The ``check_in`` keys are the literal column headings of the federation's
   workbook, which is why ``NP`` appears there: it is a heading in a file, not a
   result code. The code for a rider who will not start is ``NS`` — see the
   :ref:`glossary`.

``team_merge`` is the derogation where two regions field one team: it changes
how the teams of those events are composed and the name they race under, and
nothing else — every rider stays in their own region for individual events,
quotas and the per-team recap. See :ref:`entries`.


``branding`` and ``merge``
--------------------------

``branding`` is how a sheet looks: header and footer images and their fit, the
header-line and footer-line slots, the signature, the name style, the decision
colours, the fonts and the text colours. All of it is edited from the settings
page; see :ref:`printing`.

``merge`` names which of the five communiqué merge rules are in force for this
competition, **by exception only**: what is not named here follows
``regulations/communiques.json``.

.. code-block:: yaml

   merge:
     results_with_next_startlist: false


Validation
----------

``core.programme.validate`` runs before every save. The Programme page's save
control stays disabled while any finding is at ``error`` level: a duplicate
communiqué number, a communiqué already issued that now points at a different
sheet, a round on no day. Everything else is a warning and saves.
