# Blue Band — quick guide for the commissaires' panel

This is the half hour it takes to run the app trackside. It does not explain the
regulations: it explains where to click and what happens when you do.

> **The rule that always holds:** nothing is lost. Every save keeps the previous
> version, reloading the browser deletes nothing, and the Excel entry file is
> **never written to by the app**.

The app speaks Italian on screen - it is a console for an Italian jury - so the
page and button names below are given as they appear, with the English in
brackets.

---

## 1. The six pages

Picked in the left-hand column. They are used roughly in this order.

| Page | What for | When |
|---|---|---|
| **Verifica** (check-in) | Check the licences, correct the data, enter riders in their events | The day before, and in the morning |
| **Documenti** (documents) | Entry lists, batch printing, per-team recaps, the comunicato register | Before every event, and at the end of the day |
| **Gare** (races) | Runs a race: results, classification, comunicato | During the racing |
| **Decisioni** (decisions) | The panel's own log of what it decided | Whenever the panel decides something |
| **Programma** (programme) | Defines what is ridden and when each comunicato goes out | Before the championship |
| **Impostazioni** (settings) | Entry file, team, output folder, signature, letterhead, backup | Once, at the start (the import is reloaded whenever a new file arrives) |

---

## 2. First thing: the settings

Done once, and it stays. The page is ordered top to bottom by how often you come
back to it:

1. **Manifestazione** (competition) — which championship is open. Problems in
   the programme show up here in yellow.
2. **Elenco iscritti** (entry list) — the file the federation sends, and the
   *Importa / Ricarica* button. Either shape works: the flat ksport export
   (`Iscritti_NNNNNN_KSPORT.xlsx`, one row per rider) or the workbook with a
   sheet per category — the app tells them apart on its own.
   **Reloading breaks nothing**: the file is never written to, and everything
   the panel types in the app (bibs, teams, event entries, check-in ticks) is
   recorded separately against the **UCI ID**, which never changes, and
   re-applied on top of the new file. An edit that no longer applies is
   reported on Verifica instead of being silently dropped.
   Under it sits the **Tieni le modifiche a parte** (keep the edits aside)
   switch. Turning it off reverses the direction: Verifica **writes the
   workbook itself**. Fix a bib, a club or an event entry in the grid, press
   *Salva nel file iscritti*, and the cell is changed in the real file, which
   is re-read straight away. A copy of the previous file goes to
   `.snapshots/entries_source/` before every write. This is the way to work
   when the xlsx is the master and you want it kept up to date.
   **Checked-in and NP** go into the file too, but only where there is a column
   for them: the federal layout has none, so you add it by hand (headed
   `Verificato` and `NP`) on the category sheets and/or on the `KSPORT` sheet,
   and declare it in the programme under `entries.check_in`. The app writes
   `SI` on every sheet that has the column, so a re-import reads the tick back
   whichever one it looks at; where the column is missing it says so and the
   checkbox stays greyed out.
   One limit remains: rows are matched on the **UCI ID** — if the file was
   edited by hand meanwhile, the app stops and asks for a reload rather than
   write over the wrong line. Edits already recorded aside are not lost: they
   come back when the switch goes on again.
3. **Squadra** (team) — what a team is at this competition: *region* (the
   selection, at an Italian championship), *club*, *province* or *nation*, and
   **what it is called on the documents** ("Squadra" by default: the word
   changes in every printed heading). It also decides how the per-team recap in
   Documenti is grouped.
   *Deroga — two regions, one squadra*: where two selections are authorised to
   field a joint team (Piemonte and Valle d'Aosta in the team pursuit at
   CITA26), declare it in `programme.yaml` under `entries:`:

   ```yaml
   team_merge:
     "PIEMONTE": "PIEMONTE - V.D.A"
     "VALLE D'AOSTA": "PIEMONTE - V.D.A"
   team_merge_events: [ins_squadre]   # empty: every team event
   ```

   It changes one thing only: how the squadre (and the coppie) of those events
   are composed, and the name they race under on startlists and results. Each
   rider keeps their own region everywhere else — individual events, quotas,
   per-team recap.
4. **Cartella dei comunicati** (output folder) — where the PDFs land. It can be
   a Drive folder shared with the whole panel, or a USB stick. **Set it before
   the first comunicato.**
5. **Aspetto dei comunicati** (appearance) — letterhead and footer (the images
   with venue and dates), the secretary's signature, and whether a rider prints
   in one column or two. With the single column there is also how wide you want
   it: whatever the «Nome» column does not take goes to the columns the sheet is
   read for — sprints, points, club. **How decisions appear on a comunicato**
   is here as well (§ 6): the colour a disqualification, a relegation, a fine
   and a warning are printed in, and whether the box opens with the compact UCI
   code (`A1`, `C3`) — normally not. The note stays grey: it sanctions nobody.
6. **Programma** — read-only: what the competition file says, with the distances
   and laps worked out. The comunicato register is no longer here: it lives in
   *Documenti → Registro comunicati*, which also says which ones have gone out,
   and prints it.
7. **Backup** — a copy of everything, and the log of every operation.
8. **Azzera una gara** (reset a race) — the only thing on the page that deletes
   anything. It sits at the bottom, alone, and asks for an explicit
   confirmation.

---

## 3. Licence check

The page reads from the top: the four counters (**Atleti, Verificati, Squadre,
Coppie**), then the **Tabella specialità** — how many riders each category
fields in each event, and how far the check has got — then the findings, then
the grid you correct. The same table prints from *Documenti → Serie di
documenti → Tabella specialità*.

With the flat ksport export the events are **not in the file**: the programme
says which are ridden, and the panel says who rides them, in the grid's event
columns. Those entries survive every reload.

**You tick who is there, not who is missing.** The `Ver.` column means "licence
checked, rider present": what stays unticked is the work still to do, and the
counter at the top says how much.

- `NP` is a different thing: it declares that the rider **does not start**, and
  takes them off startlists and classifications.
- The two tickboxes need no reason. **Every other edit does**: changing a bib, a
  surname or a club asks you to write why.
- The **Da verificare** (to check) filter plus the *Segna verificati i N atleti
  filtrati* button check a whole region in two clicks.

**The check goes on all day and the races follow it.** A rider entered (or set
NP) after a race has already been opened joins or leaves its startlist the next
time that race is opened.

The **Controlli** (checks) box at the top lists what does not add up, at two
levels:

- 🔴 **to fix** — missing bib, duplicate bib, missing UCI ID, a team that does
  not field the right number of riders;
- 🟡 **warnings** — quotas exceeded, old medical certificates, madison pairs the
  app formed by itself that need confirming.

---

## 4. Documenti

Everything that is printed and is not a race sheet. Top left you pick **which of
the three groups**:

### Elenchi iscritti (entry lists)

One sheet at a time, the one that actually goes out: it carries the comunicato
number, the note under the title and the filters. Three ways: by category, by
event, or every event of a category in one go.

- The **⚡ Stampa tutti gli iscritti** button produces the four entry lists —
  the opening comunicati of every championship — already numbered from the
  register.
- **Non definitivo** (draft) prints a provisional sheet: an orange box instead
  of the comunicato number, and the file is saved as `bozza_`.
- **Solo verificati** (checked-in only) prints only those who passed the licence
  check.

### Serie di documenti (batches)

A pile of sheets already decided, to reprint or file in one go. Six ways to
group them:

- **by category**, **by event**, **by day** — everything that category, that
  event or that day produces;
- **by comunicato** — exactly the documents the register says that number
  carries, more than one where that is the case: the results of a round and the
  start order of the round they compose come out as a single PDF;
- **by team** — one recap sheet per regional selection (or club: you decide in
  Impostazioni), split by category, with all of its riders, the events each of
  them rides and — where the panel has already composed them — **the heat they
  are in**. They come out all together, one per page: this is the pile to hand
  to the team managers. The *Squadra* picker is there to reprint a single one;
- **tabella specialità** — a single sheet: how many riders each category fields
  in each event, with the totals. It is the table Verifica shows, and the sheet
  to read out at the briefing.

Those last two — the only ones with a column per event — carry a *Nomi brevi al
posto delle sigle* (short names instead of the sigle) tick: the columns are
headed «Ins. Individuale», «Madison» rather than «IP», «MD», and the key under
the table goes away because nothing is left to look up. The columns get wider,
though: with many events the sigle are the better bargain.

### Registro comunicati (the register)

Which are planned, which have been issued, what the next free number is. If a
number has been used twice it says so in red. **Salva il registro in PDF**
prints it. It is the one part of the page that works before anything has been
imported.

---

## 5. Gare

This is the working page. At the top you pick **Categoria · Specialità · Fase**
(category, event, round), and the choice survives reopening the app.

### How a result is entered

It depends on the event, and the page asks for it the way the race is actually
ridden:

| Event | What you type |
|---|---|
| Points race, tempo race, madison | One field per sprint, the bibs in finishing order |
| Scratch | A single field: the finishing order |
| Elimination | The bibs **in the order they were eliminated** (the first out is last) |
| Pursuit, team sprint | Compose the heats by picking the teams, then type the times |
| Sprint | After the 200 m there are no times: **you press who won** |
| Keirin | The panel composes the heats, then the finish of each one |
| Omnium | The four events, one inside the other |

### The heats the panel composes (madison and omnium)

Where the programme schedules **qualifying heats**, who rides which one is not
produced by a result: the panel decides it, in a round that is not ridden -
*Composizione coppie* in a madison, *Composizione batterie* in an omnium. Pick
it from the **Fase** menu like any other round.

The page is a grid, one line per pair (or per rider) with its heat beside it.
**Distribuisci nelle batterie** deals them out 1, 2, 1, … - the list is in
region or bib order, and halving it would put half the alphabet in one heat -
and every line can then be corrected by hand. A madison also hands out the pair
numbers here; an omnium does not, its riders keep their own bib.

Under the grid, **Non si qualificano le ultime N**: how many pairs (or riders)
go out of *each* heat, counted among those who started (UCI 3.2.157, never
fewer than two). It opens on what the programme says - `eliminate` on the
composition round - and the panel can move it.

Everything else follows from there: each heat starts only its own entrants, the
sheets say by themselves how many go out and how many go through, and once the
heats are ridden *Carica in finale* (madison) / *Carica nelle prove* (omnium)
carries the qualifiers into the races that follow - all four prove of an
omnium - dealt across the heats: 1st of heat 1, 1st of heat 2, 2nd of heat 1, …
**Whoever does not go through is not in the classification of the event.**

**Two at a time, or one at a time.** In a race against the clock, above the
composition grid, *Come si corre* asks how this round is ridden: **two at a
time (batterie)**, as a pursuit normally is — one rider per straight — or
**one at a time**, a start order like the team sprint. It is the panel's call
on *this* round: it is saved with the race and the sheets follow, counting
starts instead of heats. Switching keeps what is already composed in the same
order — only how many share a line changes. The finals never ask: they are
ridden two against two whatever the qualifying did.

**Finals that are not ridden.** Under the times of a finals round there is
*Finali non disputate*: for the 1°/2° and for the 3°/4°, a dropdown with
**Disputata** (the default - the time ridden in the final decides), **Pari
merito** and **Tempi qualifiche**.

- *Pari merito*: neither place is assigned on its own, the two entrants share
  the lower one - both 2°, or both 4°, and **with no time**: that final was
  not ridden. On the 1°/2° first place stays empty and the classification
  names no champion.
- *Tempi qualifiche*: the final is not ridden but is still decided, on the
  qualifying time - the only one they rode, and the one the sheet carries.
  There is still a first and a second.

Either way nothing below moves: the fifth is still fifth.

### The panel's own decisions, in the sidebar

Under the status fields (`DNS`, `DNF`, `ABD`, `DSQ`, `REL`) there is
**Decisioni**. It opens with the **recap of the event** - what has been decided
in each of its rounds - and with who is already carrying a warning. Then the
**➕ Nuova decisione** button, which opens the form:

- the **dorsale**, picked among the starters and shown with the name
  (`12 ROSSI Mario`) rather than typed from memory (`Altro...` for anybody the
  entry list does not know);
- the **compact UCI code**: the degree (A, B, C, D) and the article of the UCI
  table, which together make `A1`, `C3`, `D5`;
- the **text**: **Ricomponi** proposes it from the fields above, in the wording
  of the decisions already filed, and it stays editable - it is a proposal, the
  panel decides.

Category, event, round and day are the open race's own; the app fills them in.
Under the panel are the decisions already filed **in this round**: bib, code and
text are corrected there, or deleted, without leaving the race. See § 6 for what
a warning does after that.

The tick **Ammonizioni (W) sui fogli** puts (or keeps) the W of a warned rider
on the sheets of this event.

`ABD` is offered in bunch races only: the rider who came down of her own accord,
who is ranked behind the ritirati and whose points are not printed.

### While the race is on

Over the preview, in red, the app calls out what has just been typed - the same
banner in both cases, because it is read for the same thing:

- in a bunch race, the **last sprint** as it was called, the scoring four in
  bold;
- in a race against the clock, the **time just taken**: the time in bold, the
  bib and the name, and the place it stands in *for now*.

The page also comes back to the sheet it was left on: leave Gare on the
*Risultati* of a race and it opens there, not on the ordine di partenza.

### The red marks under the fields

Every field where bibs are typed checks what was written and says so **straight
away, under the field itself**, in red. The notation is the same everywhere:

| Mark | Means |
|---|---|
| `?7` | bib 7 is not among the starters of this race (or this heat) |
| `!3` | bib 3 is written twice |
| `-2` | 2 bibs are still missing from the line |
| `<4` | fewer than four placed: a sprint scores four |
| `?` | the line cannot be read (a letter where a number should be) |

Hovering over the mark shows the whole key.

**They block nothing.** They are there to make you look at the line while there
is still time, not to stop you working.

### The button that sends the race on

It sits **on the sheet that publishes the next round**, next to *Salva PDF*, and
it is the only button on the page that changes another race:

- *Carica Turno 1*, *Carica Quarti*, *Carica Semifinali*, *Carica Finali* in the
  sprint and the keirin;
- *Carica in finale* in a madison ridden in heats, *Carica nelle prove* in an
  omnium with qualifying heats;
- *Carica Finali* in the pursuit and the team sprint.

If a result is still missing it says so and composes nothing.

### Saving

- **💾 Salva** (at the foot of the left-hand column) writes the race to disk.
- **💾 Salva batterie** / **Salva ordine di partenza** are inside the
  composition box: you save from where you are working.
- **↩ Ripristina versione precedente** puts the race back as it was at the last
  save.

### Printing the comunicato

Above the preview: the **Documento** picker (Partenti / Risultati /
Classifica…), the **comunicato number** already proposed by the register, and
**Salva PDF**. The file lands in the configured folder and opens by itself.

A sheet the register does not plan is numbered `-1`: it shows in the field and
is corrected by hand.

---

## 6. Decisioni

Every decision is a **row of a register**: day, category, event, round, bib,
the **compact UCI code** (`A1`, `C3`, `D5` - degree and article) and the text
that goes out on the comunicato. It stays with the competition
(`decisions.json`), numbered in the order it was taken.

**It is normally written in the race it was taken in**: in the Gare sidebar
(§ 5), where category, event and round are the open race's own. The same form is
here too, behind **➕ Nuova decisione**, with the round to pick as well - for
when the panel realises afterwards, or the race is not on screen.

The page reads the register three ways:

- **Decisioni della specialità** - with a category and an event chosen, what was
  decided in each round. It is the recap the panel signs off;
- **Registro delle decisioni** - the table of everything, filtered, and the one
  button that **prints it as a PDF**;
- **Decisioni registrate** - one by one, in the order they were taken, with
  *Correggi* to put a bib, a code or the text right, and to delete.

The four degrees are **A** warning, **B** fine, **C** relegation,
**D** disqualification.

### How they appear on the comunicato

On the sheet of the race each decision is a **tinted box** under the table,
with the sentence in full. The colour says what it is from across the room:

| | |
|---|---|
| **Disqualification** | red |
| **Relegation** | light orange |
| **Fine** | violet |
| **Warning** | yellow |
| **Note** | grey, as before |

The **note** is the other thing, and stays separate: it is what says how the
tournament is run, who is qualified, how many go through. It is written in the
sheet's *Decisione / note* field and prints last.

Tints and code are set in **Impostazioni → Aspetto dei comunicati → Decisioni
sui comunicati** (§ 2). The **compact UCI code** (`A1`, `C3`) at the head of the
box is **off**: what goes out to the teams is the sentence, written in full, and
the article stays in the jury's own register. A panel that quotes it on paper
turns it on there, once per competition.

A decision goes out **once**, with the **results** of the round it was taken in
- not on the start order, which is published before the race is ridden, and
**not on the classifica**, which is the final order of the event and not a fresh
list of sanctions. The one exception is an event filed as a classification and
nothing else: there the classifica *is* the sheet of the round, and carries
them.

### A warning travels

The warning (degree **A**) is the one decision that does not end with the race
it was given in:

- the rider carries a **W** on the dorsale itself (`1 W`) on **every sheet of
  every round that follows, in the same event** — not on the sheets of the
  round it was given in, which carry the decision itself, and not on the
  classifica, which is no race to enter carrying a warning. The tick
  *Ammonizioni (W) sui fogli*, in the Gare sidebar, keeps it off the paper;
- **two warnings in the same round are a disqualification**: the app says so and
  writes the bib into the race's `DSQ` field, where it stays editable.

The tick *Includi le ammonizioni* decides whether they go into the printed
register: leave it off for the decisions that are meant to be published.

Below, two tables that are there to be consulted and nothing more:

- **Penalità UCI** — the official wording of each offence, numbered as the UCI
  numbers it: the number is the one in the compact code, and the wording is what
  *Ricomponi* proposes — `AL 1 ROSSI MARIO: RETROCESSIONE (C) per essere
  transitato sulla fascia azzurra.`
- **Cosa prevede il PUIS** — the federal penalty table, in the column of the
  categories being ridden, with a search box over infringement and sanction.
  The panel decides.

---

## 7. Programma

This is the page used **before** the championship: it defines what is ridden and
when each comunicato goes out. It touches no race and writes nothing until you
press *Salva*.

At the top: **Gara** (name, venue, dates, track, categories), **Specialità**
(the catalogue: how each one is ridden), and then **one tab per day**.

The dates decide the days: three dates, three tabs. A one-day meeting has a
single tab.

Inside a day there are two things:

**Gare della giornata** — which categories ride which events, and in which
rounds. Every round declares distance, laps, sprints and **which documents it
produces**.

> For the keirin and the sprint, which rounds are actually ridden is decided on
> the day — the number of entries for the keirin (UCI table), the scheme chosen
> on the 200 m for the sprint. Here you declare which ones are *possible*.

**Comunicati della giornata** — the order of this table **is** the order they go
out in. You reorder it, renumber it, and there is a button that proposes a
comunicato for every document planned (a proposal to tidy up: the real order
interleaves the events).

### One comunicato with two documents

It happens often: the results of a sprint round go out together with the start
order of the repechages they compose. To say so, **repeat the same number on the
row below**:

| N. | Cat. | Specialità | Fase | Documento |
|---|---|---|---|---|
| 95 | AL | Velocità | Turno 1 | risultati |
| 95 | AL | Velocità | Turno 1 | partenti_recuperi |

From there on number 95 covers both, and *Documenti → Serie di documenti → Per
comunicato* puts them on one sheet.

### Saving

*Salva programme.yaml* rewrites the file. The previous version stays in
`.snapshots/`, and under *Anteprima del file* you see exactly what you are about
to write. If something does not add up — a duplicate number, an already-issued
comunicato now pointing at another sheet — the button stays disabled until you
fix it.

**Notes go in the `note:` fields.** A comment typed into the file by hand does
not survive a save; a note in that field does.

Next year: copy the file, change the name, the dates and the venue, and correct
the few things that change.

---

## 8. What each code means

| Code | Meaning | In the classification |
|---|---|---|
| `REL` | Relegated | **Stays classified**, at the back: prints `8° REL` |
| `DNF` | Did not finish: started, did not arrive | Out of the classification, **keeps its points** |
| `ABD` | Came down of their own accord (bunch races only) | Out of the classification, **no points printed** |
| `DNS` | Did not start | **Not listed at all**: one line under the table |
| `DSQ` | Disqualified | Out of the classification, behind everybody |
| `NP` | Not starting, declared before the race | Does not appear among the starters |
| `W` | Warned (not a status: it comes from Decisioni) | A **W** on the dorsale (`1 W`), to the end of the event |

In a bunch race the riders who leave it are typed **in the order they leave**:
the last to leave heads them, being the one who went furthest. That is true of
`DNF` and of `ABD`, each in its own field.

Two points that matter:

- **A relegation does not travel.** `REL` decides who won *that* heat and stops
  there: in the classification of the event the rider is placed by where they
  finished.
- **In the sprint, a `DNS` in an intermediate round does not travel.** The 200 m
  is the one race everybody rides: whoever has a time took the start. If they
  then fail to appear for a round, they lost that round — it stays on that
  round's sheet, but in the final classification they are placed by their 200 m
  time. A `DSQ`, on the other hand, carries all the way through.

---

## 9. If something goes wrong

| Symptom | What to do |
|---|---|
| No PDF, an `.html` comes out instead | Chromium is not installed, or cannot read the folder. The HTML prints with Ctrl+P. The reason is in `journal.jsonl`. |
| I saved a wrong result | *↩ Ripristina versione precedente* on the Gare page. |
| I got a whole event wrong | *Impostazioni → Azzera una gara*. It deletes every round of the event; the previous versions stay in `.snapshots/`. |
| I made a wrong edit in Verifica | *Annulla l'ultima modifica*, at the foot of the page. |
| The browser closed | Reopen it. Everything that had been saved is still there. |
| The letterhead is missing from a comunicato | *Impostazioni → Aspetto dei comunicati → Testata*: the image is missing. |

**Before you leave**: *Impostazioni → Backup → Crea copia di backup*, and copy
the folder to Drive.

---

## 10. The words the app uses

Inside the code the app speaks UCI English; on screen everything is Italian.
The correspondences, in case you find yourself reading a file name:

| On screen | In the code / the files |
|---|---|
| Manifestazione | `competition` |
| Specialità | `event` |
| Fase | `round` |
| Dorsale | `bib` |
| Società | `club` |
| Regione | `region` |
| Verificato | `checked_in` |
| Non partente | `not_starting` |

Every wording lives in one catalogue per language under `core/i18n/`
(`it.py`, `en.py`): changing a word the panel does not like is editing one line
there, and it applies everywhere. Which language a competition is run in is set
in **Impostazioni → Lingua**; the names written out in `programme.yaml` -
categories, events, rounds - print as they stand there whatever is chosen.
