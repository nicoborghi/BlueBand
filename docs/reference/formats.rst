.. _formats:

Race formats
============

A format takes the start list plus whatever the jury typed and returns an
ordered list of ``Placing``. Sorting is the same everywhere: classified
entrants by their own result, then ``REL``, ``DNF``, ``DNS``, ``NS``, ``DSQ``
— one convention (``core/formats/base.py``), not a sentinel scheme per format.

Everything a format needs lives in the persisted ``RaceState.payload``, so a
browser reload or a crash loses nothing. ``core.race`` is the service layer
above them: who is entered, which format applies, how a bracket composes the
round after it.

.. list-table::
   :header-rows: 1
   :widths: 20 30 30 20

   * - ``fmt``
     - Events
     - What the jury types
     - Module
   * - ``points`` / ``tempo`` / ``scratch``
     - points race, tempo race, scratch, omnium races
     - sprint order: ``3,7,1,9-7,3,9,1``
     - ``formats/group.py``
   * - ``madison``
     - madison
     - as a points race, scored by pair
     - ``formats/group.py``
   * - ``elimination``
     - elimination
     - bibs in the order they went out
     - ``formats/group.py``
   * - ``timed`` / ``timed_team``
     - individual and team pursuit, km, 500 m, team sprint
     - heats ``1,2,3,4-5,6,7,8/…`` and the times
     - ``formats/timed.py``
   * - ``bracket`` (sprint)
     - sprint
     - scheme picked on the 200 m, then who won each run
     - ``formats/sprint.py``
   * - ``bracket`` (keirin)
     - keirin
     - heats composed by the jury, then each finish
     - ``formats/keirin.py``
   * - ``omnium``
     - omnium
     - the four races, summed
     - ``formats/omnium.py``
   * - ``derny``
     - derny
     - called live, one button per passage
     - ``formats/derny.py``


The jury's shorthand
--------------------

Three separators, everywhere (``core/parse.py``):

.. code-block:: text

   sprints   2,3,4,5-1,2,3,4      -  separates sprints,  ,  the finish order
   heats     1,2-3,4/5,6-7,8      /  separates heats, - opponents, , a team
   bibs      7, 12, 3             a flat list

Errors raise ``ParseError`` rather than blanking the page. Whatever is typed is
checked inline by ``core.checks.bib_line``, which produces the ``?7`` / ``!3``
/ ``-2`` / ``<4`` flags — one implementation, so one notation holds in every
field.


Bunch races
-----------

points race / madison
   5-3-2-1 to the first four of each sprint, 10-6-4-2 in the final sprint. A
   lap gained is +20, a lap lost −20. Ties broken by the placing in the last
   sprint.

tempo race
   1 point to the winner of each sprint. The ±20 lap rule applies.

scratch
   No points: the finishing order is the classification.

elimination
   Riders are entered in the order they are eliminated; the first one out is
   last, the winner is the last number typed.

A ``DNF`` keeps the points it scored; an ``ABD`` does not. Riders still in an
elimination print with a **blank position**, so the same sheet works as a live
provisional. A rider is never placed by the app for not having been typed.


Timed races
-----------

Entrants are individual riders or whole teams, and a team has **one** time — not
a time typed on an arbitrary rider row.

Finals are loaded from qualifying: the first four qualified ride two finals, 3rd
against 4th first and 1st against 2nd last. Each final assigns the places it
rides for; whoever did not qualify keeps the order — and the time — of
qualifying. A final that is not ridden is closed from the sidebar, either as a
dead heat (the two share the lower place, no champion named, no time) or on the
qualifying times.

**Two at a time or one at a time** is a jury choice on *this* event, saved with
it: pursuits normally run two per heat, but a category may be sent off one at a
time like a team sprint. The sheets follow, counting starts instead of heats.


Sprint
------

Composition follows the UCI tables in Part 3.

* Heats are seeded **serpentine** on the current ranking. With two riders per
  heat that is the familiar mirror pairing ``N1-N24, N2-N23, …``; with seven it
  reproduces the keirin table ``A: R1 R8 R9 R16 R17 R24 R25``.
* The riders who do not qualify go to the repechages, composed the same way over
  the losers in order.
* Riders knocked out in a round rank below those knocked out later, and among
  themselves by the 200 m qualifying time.

Two schemes ship, picked on the 200 m: ``12`` (the default — 12 qualify, four
rounds, with repechages) and ``8`` (8 qualify, three rounds, none). Nothing is
hard-coded to a bracket: the number of heats and how many advance come from the
programme, so a category with fewer entries runs a shorter bracket without a
code change.


Keirin
------

A keirin is not seeded off a qualifying race: there is no time to rank anybody
on, so the jury composes the first round itself. What the app supplies is the
**shape** of the tournament, from the number of entries, off UCI table 3.2.135.

Two matrices do the composing, and neither is guessed:

* the **repechages** take the riders each heat did not qualify and spread them
  so that as few as possible meet again — firsts left behind in heat order,
  seconds backwards, thirds backwards from one place further round. With four
  heats of seven that reproduces the UCI 28-rider table line for line.
* the **round that follows** deals the qualifiers one *place* at a time — all
  the winners, then all the seconds, then the repêchés — snaking each block and
  turning it round between blocks, so a heat winner and the rider it beat do not
  line up together again.


Omnium
------

Four races, one classification: **scratch, tempo race, elimination, points
race**, in that order.

.. warning::

   The four keys those races are scheduled under in ``programme.yaml`` and saved
   under in ``races/<id>.json`` are programme vocabulary, not labels.
   Translating them would stop the app finding a race. What the jury *reads*
   comes from ``core.i18n``.

The first three are scored on the UCI placing scale — **40 for the win, then −2
per place down to 2 for 20th, 1 from 21st on**. The points race is different:
the points actually scored in it are **added** to the running total, so the
standings can still be overturned in the last race.

Ties are broken by the passage at the last sprint of the points race; where that
race has not been ridden, by the placing in the last race ridden.

An omnium's partial standings *are* the next race's start order, which is why a
rider taking ``DNS`` / ``DNF`` / ``ABD`` / ``DSQ`` in one race drops out of
every later partial and out of the final classification. They stay on the sheet
of the race where the status was written, which is where the decision is
published.


Derny
-----

Called, not written up. The only thing stored is the call itself:

.. code-block:: python

   payload["passages"] = [{"bib": 5, "at": 1756...}, ...]

The lap chart, who has lost a lap, the standings, the lap times and the outliers
are all derived from that list, every time it is drawn. Nothing is cached and
nothing is written twice, so a number typed by mistake is undone by dropping its
line.

**How the laps are cut.** The head makes the lap: a new column opens the moment
a number is called that has already been called in the column now open. It needs
no button pressed at the right instant.

**How a lap is lost.** A lapped rider does not pass in the column where the
leader passed twice — the number simply is not in it — and shows up again in the
column after. So a bib missing from the columns between two of its own passages
lost a lap there: the chart prints it back in grey where it should have been and
marks the reappearance in red.

``?`` is the passage nobody read: it fills its place in the chart, never cuts a
lap (two ``?`` in one column are two different riders), is nobody's lap and is
in no classification, until the jury turns it into a bib.

Outliers: from the third lap time onward, mean and σ per rider; a lap outside
the jury's threshold (default 3σ) is flagged on the chart and on the passage
table.


Composed rounds (``kind: setup``)
---------------------------------

A madison and an omnium ridden in qualifying heats are composed by the jury, not
by a result. The programme declares a round with ``kind: setup`` — pair
composition for a madison (which also holds the pair numbers), heat composition
for an omnium — with ``eliminate: N`` on it. It is not on any day and it
produces no communiqué. The load control then deals the qualifiers across what
follows — in an omnium, across all four races, interleaved by heat: 1st of heat
1, 1st of heat 2, 2nd of heat 1, …


What a round files
------------------

``core.rounds`` proposes, for each round of a format: its distance, its laps
(from the track length), its sprints, how many qualify, how many are eliminated
(UCI 3.2.157), and the documents it may file (``docs_for``).

Everything it returns is a **proposal**. ``propose_round`` re-proposes one
round, which is what the ↩ control on the Programme page restores; a value that
differs from the proposal is simply a value the jury chose. What it cannot know
it leaves empty — a keirin states its laps and no distance, because no table
here says how long a keirin is.
