# Blue Band

[![GitHub](https://img.shields.io/badge/GitHub-BlueBand-9e8ed7)](https://github.com/nicoborghi/BlueBand/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/nicoborghi/BlueBand/blob/main/LICENSE)
[![Coverage](https://img.shields.io/codecov/c/github/nicoborghi/BlueBand)](https://codecov.io/gh/nicoborghi/BlueBand)
[![Built with Claude](https://img.shields.io/badge/built_with-Claude-orange?logo=anthropic&logoColor=white)](https://claude.ai)

Web application for track cycling competitions: entry-list verification, UCI-compliant event management, result editing, and communiqué generation. Based on streamlit.

> [!NOTE]
> **Experimental** - Validated only at the 2025 Italian Youth Track Championships. Caution: Most of the codebase relies heavily on AI-generated code and remains unverified.

```bash
cd BlueBand
streamlit run app.py
```

Guide: [`docs/GUIDA.md`](docs/GUIDA.md) (italiano) ·
[`docs/GUIDE.md`](docs/GUIDE.md) (English)

## Pages

| Page | What it does |
|---|---|
| **Gare** (races) | Runs a race: result entry, classification, printing. Every save is durable. |
| **Verifica** (check-in) | Licence check and entry-list editing: counters, tabella specialità, quota checks, edits recorded as patches. |
| **Decisioni** (decisions) | The jury's own log: free text, with quick penalties (A warning, B fine, C relegation, D disqualification) and the federal PUIS table at hand. |
| **Documenti** (documents) | Everything printed that is not a race sheet: *Elenchi iscritti* (one sheet at a time, with its number, note and filters), *Serie di documenti* (batches: by category, event, day, comunicato, one recap per team, or the tabella specialità), *Registro comunicati*. |
| **Programma** (programme) | Defines the competition: days, events per category, rounds and the comunicato register. Writes `programme.yaml`. |
| **Impostazioni** (settings) | The entry file and its reload, what a team is and what it is called, output folder, how the sheets look, backup. |

Definitions - `competition` is the meeting, `event` the title being contested, `round` the phase.


## Where things live

```
core/       the domain, without streamlit: all of it testable headless
  i18n.py     THE TRANSLATION DOCUMENT: every Italian word, once
  checks.py   what is checked in what the jury types
  config.py   programme.yaml -> dataclass
  programme.py  ... and back: dataclass -> programme.yaml, stable layout
  models.py   Rider, Team, Pair, RaceState, Status
  store.py    atomic JSON, snapshots, journal, backup
  entries.py  Excel import (both shapes), overlay of jury edits, validation
  decisions.py  the jury's decision log + the UCI and PUIS penalty tables
  recap.py    who a team is, and which heat each of its riders is in
  parse.py    the jury's shorthand: sprints, heats, times
  race.py     service layer: who is entered, which format applies, ranking
  communiques.py  the comunicato register
  formats/    base, group, timed, sprint, keirin, omnium
render/     Document/Table/Column -> HTML -> PDF (headless Chromium)
ui/         streamlit
  notify.py   HOW THE APP SAYS SOMETHING: error / warn / info / ok / flag
  state.py    the only place that knows about st.session_state
  style.py    print.css on the app's own page, and the sidebar nav
  pages/      races, check_in, decisions, documents, programme, settings
              documents.py only dispatches the page's three groups:
              startlists.py (entry lists), printing.py (batches, register)
```

### Two shared layers

**`core/i18n.py` is the only file with translations in it.** Column headings,
button names, help texts, warnings and errors: all there, in a handful of
dictionaries keyed in English (`FIELDS`, `RACE`, `DOCS`, `UI`, `HELP`, `MSG`).
Variable names stay English everywhere; translating the app - or fixing a
wording the jury dislikes - is editing one line in one dictionary.

```python
label("bib")                    # "Dors."     a column
ui("save_pdf")                  # "Salva PDF" a control
msg("bib_not_entered", bib=17)  # a message
help_text("status_dns")         # a field's tooltip
```

`ui`, `msg` and `help_text` raise on an unknown key: a missing label is a bug,
not a word to invent on the spot. `label` falls back to the key instead, so a
new column still comes out readable. Two guards in `tests/test_i18n.py` check
that every key the code asks for exists, and that no module goes back to
writing Italian of its own.

**`ui/notify.py` is the only way the app says anything.** An error is red and
means "fix this"; a warning is yellow and means "look at this"; a blue `info`
says what to do next; a toast is a save. The short marks under a field
(`notify.flag`) all use one notation, which lives in `core/checks.py`:

| Mark | Meaning |
|---|---|
| `?7` | bib 7 is not among the starters of this race / heat |
| `!3` | bib 3 appears twice |
| `-2` | 2 bibs missing from the line |
| `<4` | fewer than four placed (a sprint scores four) |
| `?` | the line cannot be read |

None of them blocks the work: they are there to be looked at while there is
still time. They appear on every field where bibs are typed - sprints,
scratch, elimination, laps gained and lost, heats (composition and finish),
reserve bibs, and the status fields.

## Data layout

One folder per championship under `competitions/` (override with
`COMMISSAIRE_TRACK_DATA`):

```
competitions/CITA26/
  programme.yaml        # track, categories, events, rounds, distances, register
  entries_import.json   # snapshot of the entry workbook (read-only)
  entries_overlay.json  # jury edits, each with a reason and a date
  races/<id>.json       # the state of every race
  comunicati.json       # the comunicati actually issued
  decisions.json        # the jury's decision log
  settings.json         # local choices (output folder, what a team is)
  out/<NNN>_<slug>.pdf  # produced comunicati (folder configurable)
  .snapshots/           # the previous content of every file written
  journal.jsonl         # append-only log of every write
```

**The Excel entry list is never modified.** The import takes a copy of it;
every edit made in the app is a separate patch keyed by UCI ID, re-applied on
top of each new import, so reloading a fresh export keeps bibs, teams, event
entries and check-in ticks. Both shapes are read and told apart automatically:
the flat ksport export (`Iscritti_NNNNNN_KSPORT.xlsx`, no event columns - the
programme says which events a category rides and the jury enters them at the
check-in) and the master workbook with a sheet per category. Importing and the
XLSX export of the effective list are in Impostazioni → Elenco iscritti.

## The programme

Edited from the **Programma** page, one tab per day, and saved to
`programme.yaml`. The file is written by an emitter of our own with a stable
layout (`core/programme.py`): saving the same programme twice gives the same
bytes, and read-write-read returns the same competition — the guarantee
everything else rests on, checked by tests against the championship's real
file. Notes go in the `note:` fields, which survive a save; a comment in the
file does not.

### One comunicato can carry several documents

A comunicato is a *number on paper*, and more than one document can be printed
under that number: it is what the sprint and the keirin have always done — the
results of a round and the start order of the round they compose go out
together. The register declares it with `with:`:

```yaml
# one document: the usual shape
- {n: 7, day: 1, cat: AL, event: ins_squadre, round: "Qualificazioni", doc: partenti}

# two documents on the same sheet; the second inherits what it does not say
- {n: 95, day: 3, cat: AL, event: velocita, round: "Turno 1", doc: risultati,
   with: [partenti_recuperi]}

# ... and an explicit `round` is a choice: the classification belongs to the
# event and to no round of it
- {n: 25, day: 1, cat: AL, event: vel_squadre, round: "Finali", doc: risultati,
   with: [{round: "", doc: classifica}]}
```

On the Programma page they are **adjacent rows with the same number**; in
Documenti → *Serie di documenti* → *Per comunicato* they are built into one
PDF.

`programme.yaml` describes everything that changes from one competition to the
next: track length, categories, which events each contests, the rounds of every
race with distance / laps / sprints, the order of the days, entry quotas and
the comunicato register. Running next year's edition means editing one file.

Distances and laps, where written explicitly, win over the value derived from
the track length: some races do not follow the formula (the ES madison
qualifier is 8 km in 25 laps, not 24).

## Formats

| Format | Events | Entry |
|---|---|---|
| `points` / `tempo` / `scratch` | points race, tempo race, scratch, omnium heats | sprint order: `3,7,1,9-7,3,9,1` |
| `elimination` | elimination | bibs in the order they were eliminated |
| `timed` / `timed_team` | individual and team pursuit, team sprint | heats `1,2,3,4-5,6,7,8/…` plus the times |
| `madison` | madison | like a points race, but the pair is scored |
| `bracket` (sprint) | sprint | scheme chosen on the 200 m, then who won each run |
| `bracket` (keirin) | keirin | heats composed by the jury, then the finish of each |
| `omnium` | omnium | the four events summed (40-38-36…, the points race adds up) |

Statuses: `DNS`, `DNF`, `DSQ`, `NP` are not placed; `REL` stays in the
classification, at the back, and prints as `8° REL`.

Heats and rounds are composed with the serpentine distribution of the UCI
tables (Part 3): with two riders per heat that is the pairing `1-8, 2-7, 3-6,
4-5`; with seven it reproduces the keirin table `A: R1 R8 R9 R16 R17 R24 R25`.

The **keirin** is seeded from no race at all: the number of entries picks a row
of UCI table 3.2.135 (`core/formats/keirin.py`), which decides how many heats
the first round has, how many go through, whether repechages and quarters are
ridden, and how many riders make the two finals. The jury composes the first
round; repechages, semifinals and finals come from the tables and stay
editable.

## Printing

**Salva PDF** writes the file straight into the output folder, with the
comunicato number in the name (`018_classifica-es_madison_finale.pdf`), and
offers it for download. The PDF is produced by a headless Chromium: it is
exactly what Ctrl+P would give, without the band of date and URL the browser
adds.

The **destination folder is chosen in Impostazioni**: by default `out/` inside
the competition, but it can point anywhere - a Drive folder shared with the
jury, a USB stick. It is created on the first save, and the choice stays in
`settings.json` (local, not part of the race programme).

If Chromium is not installed - or the competition folder sits somewhere the
browser cannot read, such as `/tmp` for a snap Chromium - the self-contained
HTML is saved instead and the reason goes into `journal.jsonl`. The preview
still prints with Ctrl+P.

Layout:

- **full-width letterhead and footer**, repeated on every page - the sheet is
  a `<table>` with the letterhead in `thead` and the footer in `tfoot`, which
  browsers repeat at every page break;
- **one line per rider**: column widths come from weights normalised to 100%,
  and values that are too long are truncated with `…` rather than wrapping and
  inflating the row;
- title centred under the comunicato number, as on jury sheets;
- signature at the foot: "Per la giuria:" and the signature, small but legible;
- teams, pairs and heats are separated by a rule, not by blank rows;
- past four events the headings are abbreviated (`VS`, `IS`, …) with the key
  under the title.

Landscape is available but **opt-in**: on a named page Chrome does not repeat
the letterhead on continuation pages, so portrait stays the default.

In the browser's print dialog turn off *Headers and footers*, or Chrome adds
the date and the URL above the document.

## Tests

```bash
python -m pytest tests -q
```

The entry-list tests run against the competition's real workbook and are
skipped when it cannot be reached.
