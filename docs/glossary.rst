.. _glossary:

Glossary
========

The one place the vocabulary is fixed. Every term below is the name used in the
code, in the file names and throughout this documentation; what reaches a
screen or a printed sheet is a catalogue lookup in :ref:`core/i18n <i18n>`,
never a literal, so the interface may say it in another language while the code
says it here.

.. note::

   Two renamings are worth calling out, because older stored files still carry
   the previous spelling and the app reads both:

   * a non-starter declared at the licence check is **NS**, not ``NP``;
   * what a title is awarded in is an **event**, never a *race*. A race is one
     start on the track; an event is the whole thing, over however many rounds
     it takes.


The structure of a meeting
--------------------------

.. glossary::

   competition
      The meeting itself — one championship, one trophy, one open. It is one
      folder on disk and one ``programme.yaml``. Everything else in this
      glossary belongs to exactly one competition.

   category
      A field of riders that ranks among itself, by age and sex. A competition
      contests its events separately per category, and the medal table counts
      them separately too.

   event
      What a title is awarded in: madison, omnium, sprint, team pursuit, points
      race. One event per category is one title. An event is **not** a block of
      time — a sprint that qualifies on Saturday and rides its finals on Sunday
      is one event across two days.

   round
      One stage of an event: qualifying, repechages, quarter-finals, final. An
      event runs a list of rounds, and the day belongs to the round, not to the
      event.

   heat
      One start inside a round, when the round does not fit on the track at
      once: heat 1, heat 2. A round with a single start has one heat.

   race
      One start on the track — a single heat of a single round. Used in the
      code for the stored state of a ``(category, event, round)`` triple, which
      is the unit the app saves and reloads.

   day
      A day of the running order, numbered from 1. Derived from the
      competition's dates.

   running order
      The sequence the rounds are ridden in across the days, with start times.
      It is what the communiqué register is planned from.


The people
----------

.. glossary::

   rider
      One entrant, identified by UCI ID. The identity that survives a corrected
      entry list, a changed bib and a re-import.

   bib
      The number pinned on a rider, unique within a category. Dealt out at
      import where the entry file does not carry them.

   club
      The club that holds the rider's licence.

   region
      The regional selection that entered the rider, where the competition is
      contested between selections rather than clubs.

   team
      Whichever grouping the competition is scored on — region, club, province
      or nation. Declared by the programme, overridable in the settings, and it
      decides the medal table, the per-team recap sheets and the quota checks
      alike.

      Distinct from a *team in a race* — the four of a team pursuit, the pair
      of a madison — which is a single entrant made of several riders.

   jury
      The panel of commissaires running the competition. The app is theirs:
      everything it proposes stays editable, and nothing it proposes is more
      true than what the jury types over it.


Result codes
------------

The status of one rider in one round. ``OK`` is the absence of a code and is
never printed.

.. list-table::
   :header-rows: 1
   :widths: 12 30 58

   * - Code
     - Meaning
     - In the classification
   * - ``OK``
     - Classified
     - Placed on the result.
   * - ``REL``
     - Relegated
     - **Stays classified**, at the back: prints as ``8° REL``.
   * - ``DNF``
     - Did not finish — started, did not reach the line
     - Not placed. **Keeps the points** already scored.
   * - ``ABD``
     - Abandoned — left the track of their own accord (bunch races only)
     - Not placed, **and scores nothing**.
   * - ``DNS``
     - Did not start — entered the round, did not take the start
     - Not placed; the code is printed.
   * - ``DSQ``
     - Disqualified
     - Not placed, behind everyone.
   * - ``NS``
     - Not starting — declared before the competition, at the licence check
     - Never appears on a start list at all.
   * - ``W``
     - Warned
     - Not a status: it comes from the decisions register, and prints as a
       **W** beside the bib (``1 W``) until the end of the event.

Two rules follow from the table and are worth stating separately.

**Order of leaving.** In bunch races the riders who left are written *in the
order they left the race*: the last to leave is the first of them, because that
is the one who got furthest. It holds for ``DNF`` and for ``ABD``, each in its
own field.

**Whoever is out, is out.** The four codes that close an event for a rider —
``DNS``, ``DNF``, ``ABD``, ``DSQ`` — close it for real: the rider is on no
later round's start list, and the app asks for no result. They stay in the
event's classification with their code, which is what a classification is for.
Removing the code from the round it was written in puts the rider back.

.. warning::

   In an omnium they disappear from the standings too. A partial standing *is*
   the start order of the next race, and a name there is a rider who starts. A
   rider who takes one of the four codes in one race drops out of the standings
   that follow and out of the final classification, staying only on the sheet
   of the race the decision was written in — which is where it is published.

``REL`` does not travel: it decides who won *that* heat and ends there; in the
event's classification the rider is placed where they finished. A ``DNS`` in an
intermediate sprint round does not travel either — the 200 m is the one race
everybody rides, so a rider with a time took a start, and a later no-show loses
that round but is still placed on the 200 m time. A ``DSQ`` travels all the
way.


What is published
-----------------

.. glossary::

   sheet
      One printed table: the start order of a round, its results, the
      classification of an event. Which sheets a round files comes from its
      format.

   communiqué
      A **number**, not a sheet. More than one sheet can go out under one
      number — as the sprint and the keirin have always done. Numbers run
      continuously across the whole competition and are never reused; an
      annulled document keeps its number and prints ``NN RET``. A sheet riding
      under another's number prints no number at all.

   decision
      One ruling of the jury: a UCI code, the riders concerned, and the
      sentence published under it.

   classification
      The ranking of an event, across all its rounds. Distinct from a
      *result*, which is the finishing order of one round.
