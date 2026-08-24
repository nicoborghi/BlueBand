"""Write the fictional elenco iscritti that ships with the repo.

    python competitions/example/make_entries.py

The real entry lists are minors' personal data: names, dates of birth, licence
numbers and UCI IDs of a few hundred under-18s. They live on the commissaire's
Drive folder, they are not in this repo, and the tests that need one used to
skip everywhere but on the laptop that has the folder mounted - which is every
machine that matters, CI included.

So this writes one. Not a censored copy of a real file - nothing here is
derived from a real rider - but a file with the *shape* of the federal export
(`Iscritti_NNNNNN.xls`, the `ksport` format in regulations/entry_formats.json):
one sheet, one row per rider, a Categoria column and no specialita' at all.

What is kept from a real export is what makes reading one hard, because that is
what the tests are about:

  * one rider with no dorsale - a half-numbered file is one somebody has been
    editing, and `entry_book.has_bibs` has to say so
  * a leading non-breaking space on every `Nome`, which is how the federal
    system writes them and how every name would print with a hole in front
  * a blank `Nazionalita'` and a blank `NomeSocieta`, which arrive blank
  * two riders whose `Regione` cell is empty, so their rappresentativa can
    only be read off the "Iscrizione CR. ..." note - the fallback the importer
    keeps for the exports that carry no column of their own
  * the columns the export carries and never fills (IdGara, CodiceFiscale,
    Riserva ...) - present and empty, exactly as they come

Every identifier is out of a range no real licence uses, so a code from here
can never be mistaken for somebody's:

  * UCI ID     109xxxxxxxx   (Italian riders are 100.. / 101..)
  * CodiceFCI  Zxxxxxx       (the federal series is A.., B..)
  * Societa    99xxxxx       (99 is not a regional code)

`CodiceFiscale` is left empty on purpose: it is the one column that would still
identify a person even invented, and the app never reads it.

Deterministic: same seed, same file, so a rebuild is an empty diff and a test
can name a rider and mean it.
"""

from __future__ import annotations

import random
from pathlib import Path

#: Written next to this file: the export is part of the competition it belongs
#: to, and the script that writes it is the only documentation of where a code
#: in it came from. `.gitignore` tracks the two of them and ignores everything
#: the app writes into this folder afterwards.
OUT = Path(__file__).resolve().parent / "Iscritti_999999.xlsx"

SEED = 26

#: The export's own columns, in the order the federal system writes them.
COLUMNS = ["IdGara", "NomeGara", "DorsaleNumero", "NomeTesserato", "CodiceFCI",
           "Categoria", "CodiceUci", "Nazionalità", "DataNascita",
           "NomeSocieta", "CodiceSocieta", "CodiceFiscale", "Sesso", "Regione",
           "Note", "Cognome", "Nome", "Riserva", "Scadenza Certificato",
           "Provincia"]

#: How many riders in each categoria: a real regional final's field, which is
#: lopsided - the Allievi are half the meeting and the Juniores donne are eight.
FIELD = {"AL": 46, "DA": 26, "ES": 24, "JU": 20, "ED": 16, "DJ": 8}

#: The categorie the girls ride, which is what `Sesso` is written from.
WOMEN = ("ED", "DA", "DJ")

#: Year of birth by categoria for a 2026 season: esordienti 13-14, allievi
#: 15-16, juniores 17-18.
BORN = {"ES": (2012, 2013), "ED": (2012, 2013),
        "AL": (2010, 2011), "DA": (2010, 2011),
        "JU": (2008, 2009), "DJ": (2008, 2009)}

#: Rappresentative and how many riders each one brought, plus the province the
#: export writes next to them. Regioni are not personal data - they are what a
#: squadra is composed by here (`team_group: region`) - so they are the real
#: ones, in sizes that leave the big ones able to field a quartetto and the
#: small ones unable to, which is the case a jury actually meets.
REGIONS = {
    "Lombardia": (41, ["MI", "BG", "BS", "VA"]),
    "Sicilia": (24, ["PA", "CT", "RG"]),
    "Emilia Romagna": (19, ["BO", "RE", "RN"]),
    "Toscana": (15, ["FI", "LU", "PI"]),
    "Lazio": (15, ["RM", "VT"]),
    "Piemonte": (11, ["TO", "CN"]),
    "Umbria": (11, ["PG", "TR"]),
    "Veneto": (2, ["VR", "PD"]),
    "Campania": (2, ["NA", "SA"]),
}

#: Societa. Invented, and audibly so: a real club that never entered this
#: meeting has no business being named in a file that ships with the code.
CLUBS = ["A.S.D. VELO ALFA", "G.S. CICLI BRAVO", "TEAM CHARLIE PISTA",
         "A.S.D. DELTA CYCLING", "U.C. ECHO", "POL. FOXTROT",
         "A.S.D. GOLF RUOTE", "G.S. HOTEL VELODROMO", "TEAM INDIA TRACK",
         "A.S.D. JULIET BIKE", "U.C. KILO", "G.S. LIMA PEDALE",
         "A.S.D. MIKE CICLISMO", "TEAM NOVEMBER", "POL. OSCAR SPRINT",
         "A.S.D. PAPA VELOCE", "U.C. QUEBEC", "G.S. ROMEO PISTA",
         "A.S.D. SIERRA RUOTE", "TEAM TANGO TRACK", "U.C. UNIFORM",
         "G.S. VICTOR CICLI", "A.S.D. WHISKEY BIKE", "POL. XRAY VELODROMO",
         "U.C. YANKEE", "A.S.D. ZULU PISTA"]

#: The names. Common enough to print the way a real elenco prints - long ones,
#: short ones, an apostrophe, an accent - and dealt out at random, so a row is
#: nobody: any surname here meets any given name here.
SURNAMES = [
    "ROSSI", "RUSSO", "FERRARI", "ESPOSITO", "BIANCHI", "ROMANO", "COLOMBO",
    "RICCI", "MARINO", "GRECO", "BRUNO", "GALLO", "CONTI", "DE LUCA", "COSTA",
    "GIORDANO", "MANCINI", "RIZZO", "LOMBARDI", "MORETTI", "BARBIERI", "FONTANA",
    "SANTORO", "MARIANI", "RINALDI", "CARUSO", "FERRARA", "GALLI", "MARTINI",
    "LEONE", "LONGO", "GENTILE", "MARTINELLI", "VITALE", "LOMBARDO", "SERRA",
    "CODA", "D'ANGELO", "PALUMBO", "SANNA", "FARINA", "RIZZI", "MONTI",
    "CATTANEO", "MORELLI", "AMATO", "SILVESTRI", "MAZZA", "TESTA", "GRASSO",
    "PELLEGRINI", "PALMIERI", "SALA", "BENEDETTI", "SORRENTINO", "VILLA",
    "D'AMICO", "GATTI", "VALENTINI", "BERNARDI", "MESSINA", "FABBRI",
]

MEN = ["MARCO", "ALESSANDRO", "LORENZO", "MATTEO", "ANDREA", "FRANCESCO",
       "TOMMASO", "RICCARDO", "GABRIELE", "DAVIDE", "SIMONE", "NICOLO'",
       "FEDERICO", "PIETRO", "EDOARDO", "LEONARDO", "GIACOMO", "SAMUELE",
       "MATTIA", "FILIPPO", "DIEGO", "EMANUELE", "CHRISTIAN", "GIOELE"]

GIRLS = ["GIULIA", "SOFIA", "AURORA", "MARTINA", "CHIARA", "ALICE", "SARA",
         "BEATRICE", "GAIA", "NICOLE", "EMMA", "ANNA", "VITTORIA", "GRETA",
         "NOEMI", "ELISA", "REBECCA", "MATILDE", "LUDOVICA", "ARIANNA"]

#: The row whose dorsale is left blank. One, not none and not half the file:
#: `entry_book.missing_bibs` has to come back with exactly this rider.
NO_BIB = 76

#: The rows that arrive incomplete, as they do - a nazionalita' nobody typed,
#: a societa the export dropped, two rappresentative left to the note.
NO_NATION = 33
NO_CLUB = 58
NO_REGION_COLUMN = (12, 91)

#: Non-breaking space: what the federal export puts in front of every `Nome`.
NBSP = " "


def riders() -> list[dict[str, object]]:
    """The whole field, in the order the export lists it.

    Categoria and regione are dealt independently, each to its own total, so
    both columns come out with the counts stated above and nobody's regione
    follows from their categoria - which is how a real entry list reads.
    """
    rnd = random.Random(SEED)

    cats = [c for cat, n in FIELD.items() for c in [cat] * n]
    regions = [r for region, (n, _p) in REGIONS.items() for r in [region] * n]
    rnd.shuffle(cats)
    rnd.shuffle(regions)

    # a club belongs to a regione: three or four each, and everybody from that
    # regione rides for one of them
    clubs = list(CLUBS)
    rnd.shuffle(clubs)
    by_region, at = {}, 0
    for region, (n, _p) in REGIONS.items():
        take = 4 if n > 12 else 2 if n > 3 else 1
        by_region[region] = clubs[at:at + take]
        at += take

    out = []
    for i, (cat, region) in enumerate(zip(cats, regions)):
        given = GIRLS if cat in WOMEN else MEN
        last = SURNAMES[rnd.randrange(len(SURNAMES))]
        first = given[rnd.randrange(len(given))]
        club = by_region[region][rnd.randrange(len(by_region[region]))]
        year = rnd.choice(BORN[cat])
        out.append({
            "IdGara": None,
            "NomeGara": None,
            "DorsaleNumero": None if i == NO_BIB else i + 1,
            "NomeTesserato": f"{last} {first}",
            "CodiceFCI": f"Z{i + 1:06d}",
            "Categoria": cat,
            # 109 + a serial: eleven digits, and out of the Italian series
            "CodiceUci": f"109{40000000 + i * 137:08d}",
            "Nazionalità": None if i == NO_NATION else "ITA",
            "DataNascita": f"{year}-{rnd.randrange(1, 13):02d}-"
                           f"{rnd.randrange(1, 29):02d}",
            "NomeSocieta": None if i == NO_CLUB else club,
            "CodiceSocieta": f"99{CLUBS.index(club):05d}",
            "CodiceFiscale": None,
            "Sesso": "F" if cat in WOMEN else "M",
            "Regione": None if i in NO_REGION_COLUMN else region.upper(),
            "Note": f"Iscrizione CR. {region.upper()}",
            "Cognome": last,
            "Nome": NBSP + first,
            "Riserva": None,
            "Scadenza Certificato": None,
            "Provincia": rnd.choice(REGIONS[region][1]),
        })
    return out


def write(path: Path = OUT) -> Path:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(COLUMNS)
    for row in riders():
        ws.append([row[c] for c in COLUMNS])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


if __name__ == "__main__":
    written = write()
    print(f"{written}: {sum(FIELD.values())} riders")
