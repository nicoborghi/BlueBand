# A meeting that never happened

`example` is a complete, entirely fictional competition, and the only one in
this folder that is in the repository. Open it like any other:

    streamlit run app.py

and pick *Trofeo di Esempio 2026* in Impostazioni, then build the elenco
iscritti from **Programma → Gara**: the file to import is
`Iscritti_999999.xlsx`, in this folder. The five pages about the riders open
once there are some.

    programme.yaml          a one-day regional final: 6 categorie,
                            6 specialità, 84 comunicati
    Iscritti_999999.xlsx    the federal export it is built from:
                            140 riders, one row each
    make_entries.py         what wrote that export

It exists because a real one cannot. An entry list is a few hundred under-18s'
names, dates of birth, licence numbers and UCI IDs; those files live on the
commissaire's Drive folder, they are not in this repository, and everything
that needs one — the tour of the app, a screenshot, `tests/test_entry_book.py`
— used to work only on the one laptop that has the folder mounted.

Work in it freely: `.gitignore` tracks the four files above and ignores
everything the app writes here afterwards — races, comunicati, PDFs, the
journal — so running the example never dirties the checkout.

## Nothing here belongs to anybody

Every rider is generated: a surname drawn from one list, a given name from
another, no correspondence between them and none with any real entry. The
società are invented and named so they cannot be mistaken for real clubs. The
identifiers are all out of ranges no licence uses:

| field | here | in a real file |
| --- | --- | --- |
| UCI ID | `109…`, 11 digits | Italian riders are `100…` / `101…` |
| CodiceFCI | `Z000001…` | the federal series is `A…`, `B…` |
| Codice Società | `99…` | `99` is not a regional code |
| Codice Fiscale | empty | the one column that identifies a person even invented — and the app never reads it |

What *is* real is the shape of the file, because that is the part worth having:
the columns of the ksport export in the order the federal system writes them,
the leading non-breaking space it puts in front of every `Nome`, a rider with
no dorsale, a blank nazionalità, a blank società, and two riders whose
rappresentativa can only be read off the "Iscrizione CR. …" note. Each of those
is a case the importer has to survive, and each one is a test.

The rappresentative and the province are the real ones: a squadra is composed
by regione here (`team_group: region`), the big ones have to be able to field a
quartetto and the small ones not to, and a regione is nobody's personal data.

## Rebuilding the entry list

    python competitions/example/make_entries.py

Deterministic — same seed, same file — so a rebuild that changes nothing shows
up as an empty diff. Change the field, the rappresentative or the malformed
rows in `make_entries.py`, not in Excel: a fixture edited by hand is a fixture
nobody can regenerate.
