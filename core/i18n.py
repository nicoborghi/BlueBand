"""Italian display vocabulary for an English domain - the only file with Italian in it.

The code speaks UCI English (competition, event, round, bib, club, region); the
jury reads Italian. **Every word that reaches a screen or a printed sheet lives
here, once**, keyed by an English name: column headings, statuses, document
kinds, the label of every widget, the help text of every field, and the wording
of every warning, error and confirmation the app can produce.

Nothing under `core/`, `render/` or `ui/` writes Italian of its own. Translating
the app - or correcting a wording the jury does not like - is editing one entry
in one of the five dictionaries below, never a search through the code.

    from core.i18n import label, ui, msg, help_text

    label("bib")                        -> "Dors."
    ui("save_pdf")                      -> "Salva PDF"
    msg("bib_not_entered", bib=17)      -> "Dorsale 17 non è tra i partenti."
    help_text("status_dns", "bibs_csv")

The five dictionaries, by what they name:

    FIELDS    a column of the entry list (a property of a rider)
    RACE      a column or a word of a race sheet
    DOCS      a kind of document, and the words a sheet is titled with
    STATUSES  the decisions a jury takes on an entrant
    UI        what a control is called: pages, buttons, fields, options
    HELP      what a field says when you hover it
    MSG       the prose shown when something needs saying

`label` never raises: an unknown key comes back capitalised, so a new column
shows up readable and the missing entry is obvious. `ui` and `msg` do raise on
an unknown key - a missing label is a bug to fix, not a word to invent - and
both take keyword arguments, formatted into the template with `str.format`.
"""

from __future__ import annotations

import re


# ── accents ─────────────────────────────────────────────────────────────────
#
# The federation types an apostrophe where an accent belongs - VELOCITA',
# NICOLO', CITTA' - because that is what an Italian keyboard gives in capitals.
# Nothing printed by this app repeats it: the workbook is read through here
# (`entries._s`) and so is the programme (`config.load_competition`).

_ACCENTED = {"A": "À", "E": "È", "I": "Ì", "O": "Ò", "U": "Ù",
             "a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù"}

# Only at the end of a word - an elision is followed by another letter
# (DELL'ORSO, D'AMICO) - and only past the third letter, which leaves the real
# truncations alone: VO', PO', VA' are written with an apostrophe and keep it.
_APOSTROPHE = re.compile(r"(?<=\w\w\w)([AEIOUaeiou])['’](?!\w)")


def fix_accents(text: str) -> str:
    """VELOCITA' -> VELOCITÀ, CITTA' -> CITTÀ, DELL'ORSO unchanged."""
    return _APOSTROPHE.sub(lambda m: _ACCENTED[m.group(1)], text)


# ── field / column labels ───────────────────────────────────────────────────

FIELDS = {
    "bib": "Dors.",
    "last_name": "Cognome",
    "first_name": "Nome",
    "full_name": "Atleta",
    "uci_id": "UCI ID",
    "fci_code": "Cod. FCI",
    "cat": "Cat.",
    "nation": "Naz",
    "club": "Società",
    "club_code": "Cod. Soc.",
    "region": "Regione",
    "province": "Prov.",
    "sex": "Sesso",
    "birth_date": "Nato/a il",
    "certificate_date": "Certificato",
    "checked_in": "Ver.",
    "not_starting": "NP",
    "n_events": "N.sp",
    "note": "Note",
    # the two columns of the PUIS, read on the Decisioni page
    "infringement": "Infrazione",
    "sanction": "Sanzione",
}


# ── race sheets ─────────────────────────────────────────────────────────────

RACE = {
    "rank": "Ris.",
    "group": "Gruppo",
    "team": "Squadra",
    "teams": "squadre",   # counted on the sheet: "3 squadre al via"
    "pair": "Coppia",
    "pairs": "coppie",
    "heat": "Batteria",
    "heat_no": "Batt.",
    # where one team starts at a time (velocità a squadre) the column counts
    # starts, not heats
    "start_no": "Ord.",
    "round": "Fase",
    "time": "Tempo",
    "points": "Punti",
    "laps": "Giri",
    "total": "Tot.",
    "sprint": "Sprint",
    "qualified": "Qual.",
    # where a rider lines up for the next prova of an omnium: the standings are
    # its ordine di partenza, and they start alternately at the balustrade and
    # at the rail, in the order the sheet ranks them
    "lane_balustrade": "Balau.",
    "lane_rail": "Corda",
    "points_total": "Punti Totali",
    "points_of": "Punti",        # "Punti Scratch" - + the name of the prova
    "reserve_short": "ris",       # marks the rider a reserve replaced
    "final": "Finale",
    "champion_team": "SQUADRA CAMPIONE D'ITALIA",
    "champion_m": "CAMPIONE D'ITALIA",
    "champion_f": "CAMPIONESSA D'ITALIA",
    # velocità: two runs and a decider that is often not ridden
    "run_1": "Prova 1",
    "run_2": "Prova 2",
    "run_3": "ev. bella",
    "day": "Giorno",
    "event": "Specialità",
    "competition": "Manifestazione",
    "distance": "Km",
    # what a head count counts, and the two words a sheet is numbered by
    "starters": "partenti",
    "entered": "iscritti",
    "athletes": "atleti",
    "number": "Num.",            # a squadra's or a coppia's number, not a bib
    "team_en": "Team",           # the entrant a rider rides for, on a sheet
    "general_classification": "CLASSIFICA GENERALE",
    "final_classification": "Classifica Finale",
}


# ── documents ───────────────────────────────────────────────────────────────

DOCS = {
    "partenti": "Partenti",
    "risultati": "Risultati",
    "classifica": "Classifica",
    # the omnium prove: the sheet the jury scores the race on, and the standings
    # after it - which are the ordine di partenza of the prova that follows
    "gara": "Gara",
    "classifica_parziale": "Classifica Parziale",
    "risultati_recuperi": "Ris. recuperi",
    "risultati_5-8": "Ris. 5°-8°",
    # a keirin publishes the ordine di partenza of its recuperi on a comunicato
    # of its own, and rides a second final whose places depend on how many ride
    # it: the picker names it with the range it is actually run for
    "partenti_recuperi": "Recuperi",
    "risultati_finale_b": "Ris. finale B",
    # the risultati of a finals round rank the four who rode the two finals:
    # "Risultati" alone does not say which sheet it is next to the 5°-8°
    "risultati_1-4": "Ris. 1°-4°",
    "repechages": "Recuperi",
    "final_5_8": "Finale 5°-8° Posto",
    # what each final rides for, as it is written on the sheet: the slash is
    # the two places one race decides, the dash a range of them
    "final_1_2": "1°/2°",
    "final_3_4": "3°/4°",
    "final_5_8_short": "5°-8°",
    "entry_list": "ELENCO ISCRITTI",
    "startlist": "Elenco Partenti",
    "start_order": "Ordine di Partenza",
    "classification": "Classifica",
    "communique": "Comunicato",
    "communique_no": "Comunicato n.",
    "register": "Registro comunicati",
    "register_col_n": "N.",
    "register_col_day": "G.",
    "register_title": "REGISTRO COMUNICATI",
    "issued": "Emesso",
    "issued_at": "Quando",
    "decision": "Decisione",
    "document": "Documento",
    "signature": "Per la giuria:",
    "printed_at": "Emesso il",
    "off_plan": "fuori programma",
    "draft": "bozza",           # file-name prefix of a non-definitive sheet
    # the sheet a squadra asks for: who of ours rides what, and in which heat
    "team_recap": "RIEPILOGO ISCRITTI",
    "team_recap_slug": "riepilogo",
    "team_recap_all_slug": "riepiloghi-squadre",
    # the tabella specialità: how many riders each categoria fields in what
    "speciality_table": "TABELLA SPECIALITÀ",
    "speciality_table_slug": "tabella-specialita",
    "entry_list_slug": "iscritti",
    "startlist_slug": "partenti",
    "register_slug": "registro-comunicati",
    "document_slug": "documento",
}


# ── statuses ────────────────────────────────────────────────────────────────

STATUSES = {
    "OK": "",
    "REL": "REL",          # declassato
    "DNF": "DNF",          # non ha finito
    "DNS": "DNS",          # non partito
    "DSQ": "DSQ",          # squalificato
    "NP": "NP",            # non partente (dichiarato prima della gara)
}

STATUS_NAMES = {
    "REL": "Declassato",
    "DNF": "Ritirato",
    "DNS": "Non partito",
    "DSQ": "Squalificato",
    "NP": "Non partente",
}


# ── penalties ───────────────────────────────────────────────────────────────
#
# The four degrees a penalty is given in (`core.decisions.CLASSES`), in
# increasing gravity. The letter is what the jury writes and what the UCI
# tables use; this is what it means.

PENALTIES = {
    "A": "Ammonizione",
    "B": "Ammenda",
    "C": "Retrocessione",
    "D": "Squalifica",
}


# ── issue codes ─────────────────────────────────────────────────────────────
#
# What a finding is *about*, one word, shown in bold in front of it. The code
# itself is English and is what the tests match on; this is the word the jury
# reads (`ui.notify.issues`).

CODES = {
    "teams": "Squadre",
    "pairs": "Coppie",
    "total": "Totale",
    "speciality_table": "Tabella specialità",
    "import": "Import",
    "uci": "UCI ID",
    "region": "Regione",
    "bib": "Dorsale",
    "bib_dup": "Dorsale doppio",
    "certificate": "Certificato",
    "quota_rider": "Limite specialità",
    "event_not_run": "Specialità non in programma",
    "quota_region": "Quota regione",
    "quota_club": "Quota società",
    "quota_club_region": "Quota società per squadra",
    "quota_teams": "Quota squadre",
}


# ── controls: what every page, button and field is called ───────────────────
#
# One entry per control. Keys read as English domain names, so a control can be
# found from the code that draws it without knowing what it says in Italian.

UI = {
    # -- the app shell -------------------------------------------------------
    # The page names carry their own icon: the sidebar list is styled into a
    # nav (`ui/style.py`), and an icon put there by CSS would be one more
    # thing to keep in step with this dictionary.
    "page": "Pagina",
    "page_races": "❊ Gare",
    "page_check_in": "☑ Verifica",
    "page_decisions": "⚖ Decisioni",
    "page_documents": "🖨 Documenti",
    "page_programme": "🗓 Programma",
    "page_settings": "⚙ Impostazioni",
    "programme_problems": "{n} problemi nel programma",

    # -- pickers shared by several pages -------------------------------------
    "competition": "Manifestazione",
    "category": "Categoria",
    "categories": "Categorie",
    "event": "Specialità",
    "round": "Fase",
    "day": "Giornata",
    "region": "Regione",
    "state": "Stato",
    "all_f": "(tutte)",          # feminine: categorie, specialità, regioni
    "all_days": "tutte",
    "table_font": "Corpo tabella",
    "table_font_pdf": "Corpo tabella .pdf",
    "table_font_screen": "Corpo tabella a schermo",
    "landscape": "Stampa orizzontale",
    "title_suffix": "Aggiunta al titolo",
    "title_suffix_hint": "es. versione aggiornata",
    "signature_tick": "Firma «Per la giuria»",
    "save_pdf": "Salva PDF",
    "save_pdf_all": "Salva PDF (tutti)",
    "print_hint": "{n} {what} - stampa con Ctrl+P",
    "document_one": "documento",
    "document_many": "documenti",

    # -- entry file: chosen and reloaded in Impostazioni ----------------------
    "entries": "Elenco iscritti",
    "entries_source": "File iscritti (di sola lettura)",
    "import_reload": "Importa / Ricarica",
    "export_effective": "Esporta XLSX (elenco effettivo)",
    "overlay_kept": "{n} modifiche della giuria vengono riapplicate a ogni ricarica.",

    # -- check-in ("Verifica") ----------------------------------------------
    "entry_list_title": "Elenco iscritti",
    "athletes": "Atleti",
    "verified": "Verificati",
    "todo": "Da fare",
    "teams": "Squadre",
    "pairs": "Coppie",
    "total": "Totale",
    "speciality_table": "Tabella specialità",
    "check_in_progress": "Verifica licenze: {done} su {total}",
    "check_in_left": "-{n} da fare",
    "check_in_complete": "completa",
    "state_all": "Tutti",
    "state_todo": "Da verificare",
    "state_done": "Verificati",
    "state_np": "NP",
    "checks_summary": "Controlli - {errors} da risolvere, {warnings} avvisi",
    "stp_exemptions": "Deroghe autorizzate STP: {list}",
    "edit_reason": "Motivo della modifica (obbligatorio)",
    "save_edits": "Salva modifiche",
    "mark_verified": "Segna verificati i {n} atleti filtrati",
    "check_in_reason": "verifica licenze",
    "edits_recorded": "Modifiche registrate ({n})",
    "undo_last_edit": "Annulla l'ultima modifica",
    "edit_when": "quando",
    "edit_rider": "atleta",
    "edit_op": "operazione",
    "edit_field": "campo",
    "edit_value": "valore",
    "edit_reason_col": "motivo",
    "last_import": "Ultimo import: {when}",
    "import_summary": "{n} atleti · {file}",
    "reading_entries": "Lettura del file iscritti...",

    # -- documents ("Documenti"): which group of the page --------------------
    "document_group": "Documenti",
    "docs_entries": "Elenchi iscritti",
    "docs_batch": "Serie di documenti",
    "docs_register": "Registro comunicati",

    # -- documents: entry lists ("Elenchi iscritti") -------------------------
    "print_mode": "Stampa",
    "mode_by_category": "Per categoria",
    "mode_by_event": "Per specialità",
    "mode_all_events": "Tutte le specialità di una categoria",
    "mode_by_day": "Per giornata",
    "mode_by_communique": "Per comunicato",
    "mode_by_team": "Per squadra",
    "mode_speciality_table": "Tabella specialità",
    "communique_carries": "Comunicato {n} · {title} — {docs}",
    "row_number": "Numero di riga",
    "event_matrix": "Matrice specialità",
    "include_np": "Includi NP",
    "include_reserves": "Includi riserve",
    "only_verified": "Solo verificati",
    "minimal_columns": "Colonne essenziali",
    "not_final": "Non definitivo",
    "decision_note": "Decisione / note",
    "print_all_entries": "⚡ Stampa tutti gli iscritti ({n} comunicati)",
    "building_documents": "Creazione dei documenti...",
    "check_in_line": "{cat}: {done}/{total} verificati · {left} ancora da verificare",

    # -- documents: batches and register -------------------------------------
    "documents": "Documenti",
    "planned": "Previsti",
    "issued": "Emessi",
    "next_free": "Prossimo libero",
    "title": "Titolo",
    "team": "Squadra",
    "team_group": "Che cos'è una squadra",
    "team_group_region": "Regione (rappresentativa)",
    "team_group_club": "Società",
    "team_group_province": "Provincia",
    "team_group_nation": "Nazione",
    "team_name": "Come si chiama sui documenti",
    "save_register_pdf": "Salva il registro in PDF",
    "print_preview": "Anteprima di stampa",

    # -- decisions ("Decisioni") ---------------------------------------------
    "decision_new": "Nuova decisione",
    "decision_body": "Decisione",
    "decision_save": "💾 Registra la decisione",
    "decision_none": "-",              # no penalty: a decision, not a sanction
    "penalty": "Penalità",
    "penalty_quick": "Penalità rapide",
    "penalty_reason": "Motivo (tabella UCI)",
    "penalty_add": "Aggiungi al testo",
    "penalty_class": "Provvedimento",
    "puis_panel": "Cosa prevede il PUIS",
    "puis_column": "Colonna del prontuario",
    "puis_search": "Cerca",
    "puis_updated": "PUIS aggiornato al {when} · {n} voci",
    "penalties_updated": "Tabella UCI aggiornata al {when}",
    "decisions_taken": "Decisioni registrate ({n})",
    "decision_head": "n. {n} · {when}",
    "decision_delete": "🗑 Elimina",
    "decision_edit": "Correggi",
    "decision_context": "Contesto",

    # -- races ("Gare"): the sheet being prepared ----------------------------
    "race_line": "{n} partenti · {info} · formato: {fmt} · ultimo salvataggio: {saved}",
    "never_saved": "-",
    "save": "💾 Salva",
    "save_heats": "💾 Salva batterie",
    "save_start_order": "💾 Salva ordine di partenza",
    "save_pairing": "💾 Salva composizione",
    "restore_previous": "↩ Ripristina versione precedente",
    "club_column": "Colonna società",
    "lane_column": "Colonna balaustra / corda",
    "points_race_detail": "Dettaglio corsa a punti",
    "time_column": "Colonna tempi",
    "bib_column": "Colonna dorsale",

    # -- races: result entry -------------------------------------------------
    "eliminations": "Eliminazioni",
    "elimination_order": "Dorsali in ordine di eliminazione",
    "sprints": "Sprint",
    "sprint_n": "{n}º sprint",
    "sprint_mark": "{n}ª",
    "sprint_mark_final": "{n}ª (×2)",
    "arrival_order": "Ordine di arrivo",
    "sprint_string_box": "Stringa",
    "volata_n": "{n}ª volata",
    "times": "Tempi",
    "laps_gained": "Giri guadagnati",
    "laps_lost": "Giri persi",
    "statuses": "Stati",
    "heats": "Batterie",
    "heat_composition": "Composizione",
    "heat_order_by_heat": "Ordine di arrivo per batteria",
    "heat_n": "{n}ª batteria",
    "heat_one": "Batteria",
    "heat_short": "Batt. {n}",
    "heat_bibs": "dorsali separati da virgola",
    "arrival": "ordine di arrivo",
    "lane_n": "Corsia {n}",
    "bibs": "Dorsali",
    "reserves_are": "riserve: {bibs}",

    # -- races: heat / start-order builder ----------------------------------
    "build_start_order": "Composizione ordine di partenza",
    "build_heats": "Composizione batterie",
    "fill_in_entry_order": "Riempi in ordine di iscrizione",
    "start_n": "{n}ª partenza",
    "notation_is": "Notazione: `{text}`",
    "not_placed_yet": "Non ancora inseriti ({n}): {who}",
    "all_in_heats": "Tutti gli iscritti sono in batteria.",
    "all_in_start_order": "{who} sono nell'ordine di partenza.",
    "everyone_teams": "tutte le squadre",
    "everyone_riders": "tutti gli atleti",
    "not_in_heat_yet": "Non ancora in batteria ({n}): {who}",
    "all_in_heat": "Tutti in batteria.",
    "heats_not_composed": "Batterie non ancora composte.",

    # -- races: velocità -----------------------------------------------------
    "next_rounds": "Fasi successive",
    # the two ways a velocità is run, as the dropdown offers them
    "scheme_12": "12 qualificati - turno 1 - quarti - semifinali - finali",
    "scheme_8": "8 qualificati - quarti - semifinali - finali",
    "scheme_line": "{qualified} qualificati · {rounds}",
    "scheme_repechages": " · recuperi nel 1° turno",
    "winners_round_1": "Vincitori 1° turno",
    "repechages": "Recuperi",
    "finals_1_4": "Finali 1°-4°",
    "final_5_8": "Finale 5°-8°",
    "runs": "Prove",
    "place_n": "{n}°",
    "final_n_place": "{name} posto",
    "wins": "→ vince **{who}**",
    "load_round_1": "Carica Turno 1",
    "load_quarters": "Carica Quarti di finale",
    "load_semifinals": "Carica Semifinali",
    "load_finals": "Carica Finali",
    "load_repechages": "Carica Recuperi",
    "load_generic": "Carica {round}",
    "update_finals": "Aggiorna Finali",
    "load_madison_final": "Carica in finale",
    "compose_heats": "Componi batterie",

    # -- races: keirin -------------------------------------------------------
    "keirin_shape": "{n} iscritti · tabella UCI {lo}-{hi}",
    "keirin_stage": "{round}: {heats} batterie",
    "keirin_stage_rep": " + {n} recuperi",
    "compose_race": "Composizione · {race}",
    "arrivals_of": "Arrivi · {race}",
    "final_named": "Finale {name} posto",
    "round_repechages": "{round} - Recuperi",
    # the block a results sheet composes underneath itself is named after the
    # round it is the start order of: the register calls these two by their
    # full name, which is not the key the programme schedules them under
    "quarters_full": "Quarti di Finale",
    "semifinals_full": "Semifinali",
    "finals_full": "Finali",

    # -- races: madison ------------------------------------------------------
    "pairing_line_heats": "{n} coppie · {heats} batterie in programma",
    "pairing_line_direct": "{n} coppie · finale diretta, senza batterie",
    "number_1_to_n": "Numera 1..N",
    "spread_into_heats": "Distribuisci nelle batterie",
    "pair_number": "N. coppia",
    "head_number": "**Num.**",
    "head_heat": "**Batt.**",
    "head_pair": "**Coppia**",
    "head_black": "**Nero**",
    "head_red": "**Rosso**",
    "eliminate_last": "Non si qualificano le ultime",
    "eliminate_line": "{sizes} partenti → **{through} coppie in finale**",
    "eliminate_track_limit": " · limite pista: {n}",
    "pairs_in_heat": "**{round}** - {n} coppie",
    "heat_qualified": "{n}ª batteria: {through} qualificate, {out} eliminate",

    # -- races: omnium -------------------------------------------------------
    "partial_after_scratch": "Risultati {scratch} e Ordine di Partenza {next}",
    "partial_standings": "Classifica Parziale e Ordine Partenza {next}",
    "results_of": "Risultati {round}",
    "round_results": "{round} - Risultati",
    "round_repechage_results": "{round} - Recuperi - Risultati",
    "final_5_8_results": "Finale 5°-8° posto - Risultati",
    "finals_1_2_3_4_results": "Finali {a} e {b} posto - Risultati",
    "results_short": "Ris. {what}",

    # -- programme ("Programma") ---------------------------------------------
    "prog_tab_competition": "Gara",
    "prog_tab_events": "Specialità",
    "save_programme": "💾 Salva programme.yaml",
    "reload_programme": "↩ Ricarica dal file",
    "programme_counts": "{events} gare in programma · {communiques} comunicati · `{path}`",
    "yaml_preview": "Anteprima del file",
    "competition_name": "Nome",
    "competition_short": "Sigla",
    "competition_id": "ID FCI",
    "competition_location": "Sede",
    "track_len": "Lunghezza pista (km)",
    "dates": "Date (una per giornata, separate da virgola)",
    "dates_caption": "Le date decidono quante giornate ha la manifestazione: "
                     "una data, una scheda «Giorno».",
    "categories_caption": "Le categorie in gara, nell'ordine in cui compaiono "
                          "ovunque nell'app.",
    "events_caption": "Il catalogo delle specialità: si tocca di rado. Quali "
                      "categorie le corrono si decide nelle schede Giorno.",
    "event_notes": "Note di partenza",
    "event_notes_caption": "La riga da cui parte il campo «Decisione / note» di "
                           "ogni ordine di partenza.",
    "note_startlist": "Su ogni ordine di partenza",
    "note_qualifying": "Solo sulle qualificazioni",
    "note_finals": "Solo sulle finali",
    "feminine": "femminile",
    "code": "Codice",
    "short_name": "Nome breve",
    "abbr": "Sigla UCI",
    "format": "Formato",
    "team_size": "Atleti/squadra",
    "per_start": "Per partenza",
    "entry_columns": "Colonne file iscritti",
    "order": "Ordine",
    "day_line": "Giornata {day} · {date}",
    "races_of_day": "Gare della giornata",
    "races_of_day_caption": "Quali categorie corrono quali specialità, e in "
                            "quali fasi. L'ordine è quello in cui si corrono.",
    "rounds_of": "Fasi · {cat} {event}",
    "n_rounds": "{n} fasi",
    "add_race": "Aggiungi una gara alla giornata",
    "add": "Aggiungi",
    "round_default": "Finale",
    "qualify": "Qualif.",
    "eliminate": "Elimina",
    "setup_round": "Composiz.",
    "communiques_of_day": "Comunicati della giornata",
    "communiques_of_day_caption": "L'ordine di questa tabella è l'ordine in cui "
                                  "escono. **Righe vicine con lo stesso numero "
                                  "sono lo stesso foglio**: è così che un "
                                  "comunicato porta un ordine di partenza e una "
                                  "classifica insieme.",
    "propose_register": "Proponi dalla programmazione",
    "renumber_all": "Rinumera tutto 1..N",
    "register_range": "comunicati {first}-{last} ({n} documenti)",

    # -- settings ("Impostazioni") ------------------------------------------
    "track": "Pista",
    "races_scheduled": "Gare in programma",
    "communiques_planned": "Comunicati previsti",
    "competition_line": "{name} - {location} - {dates}",
    "programme_path": "Programma: `{path}`",
    "out_folder": "Cartella dei comunicati",
    "path": "Percorso",
    "save_folder": "Salva cartella",
    "restore_default": "Ripristina predefinita",
    "documents_in_folder": "{n} documenti nella cartella attuale",
    "folder_will_be_created": "La cartella verrà creata al primo salvataggio.",
    "produced_documents": "Documenti prodotti",
    "file": "File",
    "modified": "Modificato",
    "programme_table": "Programma gare",
    "appearance": "Aspetto dei comunicati",
    "letterhead": "Testata e piè di pagina",
    "header_img": "Testata",
    "footer_img": "Piè di pagina",
    "save_named": "Salva {what}",
    "advanced": "Impostazioni avanzate",
    "signature": "Firma",
    "signature_how": "Come firmare",
    "signature_file": "File della firma",
    "save_signature": "Salva firma",
    "signature_name": "Nome del segretario di giuria",
    "save_name": "Salva nome",
    "signature_where": "Dove applicarla",
    "sig_mode_image": "Immagine della firma",
    "sig_mode_text": "Nome e cognome (testo in grassetto)",
    "sig_scope_always": "Ovunque",
    "sig_scope_results": "Solo in risultati e classifiche",
    "sig_scope_never": "Mai",
    "name_style": "Nome",
    "name_style_how": "Come si stampa un atleta",
    "name_split": "Cognome + Nome (due colonne)",
    "name_full": "Nome completo (una colonna)",
    "name_split_example": "ROSSI · Mario Luigi",
    "name_full_example": "ROSSI Mario Luigi - una sola colonna «Nome»",
    "reset_event": "Azzera una gara",
    "reset_confirm": "Confermo: cancella {n} gare di {cat} · {event}",
    "reset_with_results": " ({n} con risultati)",
    "reset_button": "Azzera la gara",
    "backup": "Backup",
    "backup_dest": "Destinazione copia",
    "backup_button": "Crea copia di backup",
    "journal": "Registro operazioni (ultime {n})",
    "final_band": "FINALE {name} POSTO",
    "col_results": "Risultati",
    "col_starters": "Partenti",
    "col_last_saved": "Ultimo salvataggio",
    "yes_short": "sì",
    "none_short": "-",
}


# ── help texts ──────────────────────────────────────────────────────────────
#
# What a field says when you hover it. Here and not next to the widget for the
# same reason as the labels: an English build must be one dictionary to write,
# not a search through ui/. Compose several with `help_text("a", "b")`.

HELP = {
    # -- notation ------------------------------------------------------------
    "bibs_csv": "Dorsali separati da virgola.",
    "teams_pick": "Si sceglie la squadra, non il dorsale.",
    "status_dns": "Non partiti: non hanno preso il via.",
    "status_dnf": "Ritirati: partiti, non arrivati.",
    "status_dsq": "Squalificati: fuori dalla classifica.",
    "status_rel": "Declassati: restano in classifica, in coda.",
    "sprint_order": "Ordine di arrivo dello sprint, dorsali separati da virgola.",
    "sprint_final": "Sprint finale: vale 10-6-4-2.",
    "sprint_string": ("Tutti gli sprint in una riga: «,» separa i dorsali, "
                      "«-» gli sprint. Es. 3,7,1,9-7,3,9,1"),
    "heat_bibs": "Dorsali della batteria, separati da virgola.",
    "heat_order": ("Ordine di arrivo della batteria: dorsali separati da "
                   "virgola, il vincitore per primo."),
    "heat_notation": ("Composizione batterie: `,` atleti della stessa squadra, "
                      "`-` avversari nella stessa batteria, `/` batteria "
                      "successiva. Es. `1,2,3,4-5,6,7,8/9,10,11,12-13,14,15,16`"),
    "heat_notation_same": "Stessa notazione: `/` separa le batterie.",
    "laps_csv": ("Dorsali separati da virgola. Un dorsale ripetuto conta un "
                 "giro per volta: `3, 3` = due giri."),
    "elimination_order": "Il primo eliminato è l'ultimo in classifica.",
    "time_format": "Tempo in m:ss,mmm.",
    # The one legend of the inline flags, shared by every field that shows them
    # (see `core.checks.FLAGS`): one notation, one explanation.
    "flags": ("?N il dorsale N non è tra i partenti · !N il dorsale N è "
              "ripetuto · -N mancano N dorsali · <N meno di N classificati · "
              "? riga non leggibile."),

    # -- races ---------------------------------------------------------------
    "sprint_scheme": ("Decide quanti atleti qualifica il 200 m e quali fasi si "
                      "corrono dopo. È la riga che va sull'ordine di partenza "
                      "qui sotto."),
    "reserve_bibs": ("Sostituisci il numero di chi non parte con quello della "
                     "riserva."),
    "fill_pairs": "Accoppia gli iscritti a due a due, poi correggi quello che serve.",
    "fill_start_order": ("Mette {who} in ordine di iscrizione, poi correggi "
                         "quello che serve."),
    "number_pairs": ("Rinumera le coppie nell'ordine di questo elenco "
                     "(regione, poi coppia)."),
    "spread_pairs": ("Assegna le coppie a giro: 1ª batteria, 2ª batteria, 1ª, "
                     "... L'ordine è per regione, e dividerlo a metà "
                     "metterebbe mezzo alfabeto in una batteria sola."),
    "eliminate_pairs": ("Coppie eliminate da OGNI batteria, tra quelle partite "
                        "(regolamento UCI 3.2.157: mai meno di 2)."),
    "compose_next": "Compone «{round}»{extra} da questi risultati.",
    "compose_next_uci": ("Compone «{round}» da questi risultati, secondo la "
                         "tabella UCI."),
    "load_finals": ("Porta la classifica in «{round}»: le finali si compongono "
                    "dai primi qualificati."),
    "load_madison_final": ("Porta in «{round}» le coppie qualificate da tutte "
                           "le batterie."),
    "compose_from_previous": "Compone questa fase dalla classifica della precedente.",

    # -- sheet options -------------------------------------------------------
    "signature_tick": ("Stampa la firma del segretario di giuria in fondo al "
                       "documento. Il valore predefinito si imposta in "
                       "Impostazioni → avanzate."),
    "club_column": ("Aggiunge la società di appartenenza di ogni atleta e il "
                    "codice società, oltre alla rappresentativa."),
    "lane_column": ("La classifica parziale è l'ordine di partenza della prova "
                    "successiva: aggiunge una colonna senza titolo che alterna "
                    "Balau. e Corda."),
    "points_race_detail": ("Punti portati in corsa a punti dalle prime tre "
                           "prove, tutte le volate e i giri, oltre al totale."),
    "time_column": "I tempi restano sui risultati di ogni fase.",
    "bib_column": "Aggiunge il dorsale «classico» accanto al numero di coppia.",
    "font_pdf": "Corpo del testo nel PDF da stampare.",
    "font_screen": ("Solo l'anteprima qui sotto: è la pagina che legge lo "
                    "speaker durante la gara."),
    "landscape": ("Più spazio per le colonne, ma su un foglio orizzontale il "
                  "browser non ripete la testata nelle pagine successive."),
    "landscape_short": ("Su foglio orizzontale il browser non ripete la testata "
                        "nelle pagine successive."),
    "title_suffix": ("Testo aggiunto in coda al titolo di ogni documento "
                     "stampato - «versione aggiornata», «rettifica». Il nome "
                     "del file e il numero di comunicato non cambiano."),

    # -- startlists ----------------------------------------------------------
    "row_number": ("Contatore grigio a sinistra della tabella: dice quanti sono "
                   "e dà alla giuria un riferimento da indicare sul foglio."),
    "event_matrix": ("Colonne a destra con le sigle delle specialità e la X di "
                     "chi vi è iscritto."),
    "only_verified": ("Stampa solo chi ha passato la verifica licenze (spunta "
                      "Ver. nella pagina Verifica)."),
    "draft": ("Foglio provvisorio: al posto del numero di comunicato stampa un "
              "riquadro arancione NON DEFINITIVO, e il file si salva come "
              "bozza_."),
    "print_all_entries": ("Salva l'elenco iscritti di ogni categoria nella "
                          "cartella dei comunicati."),

    # -- entry file ----------------------------------------------------------
    "entries_source": ("Il file mandato dalla federazione: l'export ksport "
                       "(Iscritti_NNNNNN_KSPORT.xlsx) o il workbook con un "
                       "foglio per categoria. Non viene mai modificato: si "
                       "può ricaricare quando ne arriva uno nuovo."),

    # -- team recap ----------------------------------------------------------
    "team_group": ("Come si raggruppano gli atleti in classifica e nel "
                   "riepilogo per squadra: la rappresentativa che li iscrive, "
                   "la società a cui sono tesserati, la provincia o la "
                   "nazione. A un campionato italiano è la regione."),
    "team_name": ("La parola stampata sui documenti al posto di «Squadra» - "
                  "per esempio «Rappresentativa», «Società» o «Team»."),
    "team_recap": ("Un foglio per squadra: tutti gli atleti in una tabella "
                   "sola, una colonna per specialità con X, R o la lettera "
                   "dell'accoppiamento e, dove la giuria l'ha già composta, "
                   "la batteria."),

    # -- decisions -----------------------------------------------------------
    "decision_body": ("Quello che la giuria ha deciso, scritto come andrà "
                      "letto fra un mese: chi, cosa, e in base a quale "
                      "articolo. È l'unico campo obbligatorio."),
    "decision_bibs": ("Dorsali a cui si riferisce, separati da virgola. "
                      "Servono a comporre la riga della penalità con nome e "
                      "categoria."),
    "penalty_class": ("A ammonizione, B ammenda, C retrocessione, "
                      "D squalifica."),
    "penalty_quick": ("Compone la riga della penalità - atleta, "
                      "provvedimento, motivo UCI - e la aggiunge in fondo al "
                      "testo, dove resta modificabile."),
    "puis_panel": ("Prontuario Unico Infrazioni Sportive: quanto prevede la "
                   "federazione per ogni infrazione, nella colonna delle "
                   "categorie in gara. Si consulta, non decide."),
    "decision_context": ("Facoltativo: a quale gara si riferisce. Serve a "
                         "ritrovarla, non entra nel testo."),

    # -- check-in ------------------------------------------------------------
    "checked_in": "Licenza verificata: l'atleta è presente.",
    "not_starting": "Non partente: non prende parte alle gare.",
    "n_events": "Specialità come titolare{reserves}.",
    "n_events_reserves": " o riserva",
    "edit_reason": "Le spunte Ver./NP non richiedono un motivo.",
    "event_flag": "{event}: X iscritto, R riserva",
    "event_flag_group": ("{event}: X iscritto, R riserva; una lettera "
                         "(A, B, C, ...) la {what} della regione, la stessa "
                         "lettera con R (AR, BR, ...) la sua riserva"),

    # -- programme -----------------------------------------------------------
    "save_programme": ("Riscrive `programme.yaml`. La versione precedente resta "
                       "in `.snapshots/`. Non tocca gare, iscritti o comunicati "
                       "già emessi."),
    "reload_programme": "Butta via le modifiche non salvate e rilegge il file.",
    "track_len": ("Da qui si calcolano i giri di ogni distanza che non li "
                  "dichiara."),
    "dates": "Es. 2026-08-04, 2026-08-05",
    "category_sex": ("Decide CAMPIONE / CAMPIONESSA e le forme femminili sui "
                     "fogli."),
    "event_format": ("Decide come si corre e come si conta: gruppo, "
                     "eliminazione, a cronometro, velocità, keirin, omnium, "
                     "madison."),
    "team_size": "Atleti che schiera una squadra (0 se è individuale).",
    "per_start": ("Quanti partono insieme in una fase a cronometro: 2 "
                  "l'inseguimento, 1 la velocità a squadre e i 200 m."),
    "entry_columns": ("Come si chiama la colonna nel file iscritti, se non "
                      "coincide col nome. Più varianti separate da virgola."),
    "note_feminine": ("La stessa riga scritta al femminile. Vuota: si usa "
                      "quella accanto."),
    "programme_note": ("Nota tua sulla gara: sopravvive al salvataggio, un "
                       "commento nel file no."),
    "move_up": "Sposta prima",
    "move_down": "Sposta dopo",
    "remove_race": "Togli questa gara dalla giornata",
    "round_distance": "Km. Vuoto: la fase non ha una distanza dichiarata.",
    "round_laps": ("Vuoto: si calcolano dalla lunghezza della pista. Scrivili "
                   "solo se la gara non segue la formula."),
    "round_qualify": "Quanti passano alla fase successiva.",
    "round_eliminate": "Madison: coppie eliminate da OGNI batteria (3.2.157).",
    "round_setup": ("Fase che non si corre: la giuria compone (numeri e "
                    "batterie della madison)."),
    "round_docs": "Documenti separati da virgola. Per questa specialità:",
    "communique_number": ("Ripeti lo stesso numero sulla riga dopo per mettere "
                          "due documenti sullo stesso foglio."),
    "communique_doc": "Quale foglio della fase.",
    "ret": "Comunicato annullato: il numero resta occupato e stampa «N RET».",
    "propose_register": ("Propone un comunicato per ogni documento previsto "
                         "dalle gare di oggi. È una proposta da riordinare: "
                         "l'ordine vero intreccia le specialità."),
    "renumber_all": ("Rinumera 1..N tutti i comunicati, nell'ordine in cui "
                     "stanno. Attenzione se ne hai già emessi."),

    # -- settings ------------------------------------------------------------
    "competition_folder": ("Cartella dati sotto `competitions/`. Si sceglie una "
                           "volta: resta impostata anche alla riapertura."),
    "out_folder": ("Dove vengono salvati i PDF dei comunicati. Può essere una "
                   "cartella condivisa (Drive, chiavetta): viene creata se "
                   "manca."),
    "signature_file": "PNG o SVG della firma scansionata.",
    "signature_name": ("Si stampa in grassetto al posto dell'immagine. Nessuna "
                       "riga sotto."),
    "signature_scope": ("Imposta la spunta «Firma «Per la giuria»» nelle pagine "
                        "Gare e Documenti. Resta una spunta: la giuria può "
                        "sempre cambiarla sul singolo foglio."),
    "header_img": "Banner in cima al comunicato: manifestazione, sede e date.",
    "footer_img": "Striscia in fondo al foglio: sponsor, loghi federali.",
}


# ── messages ────────────────────────────────────────────────────────────────
#
# Everything the app says when something needs saying. Grouped by what raises
# it, and worded the same way throughout: an *error* names something the jury
# has to fix, a *warning* something to look at, an *info* something to do next.

MSG = {
    # -- programme / configuration ------------------------------------------
    "no_programme": "'{name}' non contiene un programme.yaml.",
    "no_competitions": "Nessuna manifestazione in {path}",
    "cfg_no_categories": "Nessuna categoria definita.",
    "cfg_no_events": "Nessuna specialità definita.",
    "cfg_no_columns": "Nessuna colonna dichiarata in `entries.columns`.",
    "cfg_bad_track_len": "track_len non valido.",
    "cfg_unknown_cat": "Programma: categoria sconosciuta '{cat}'.",
    "cfg_unknown_event": "Programma: specialità sconosciuta '{event}'.",
    "cfg_no_rounds": "Programma: {cat} {event} non ha fasi.",
    "cfg_duplicate_communique": "Comunicato n. {n} duplicato ({a} / {b}).",

    # -- parsing the jury's shorthand ---------------------------------------
    "parse_missing_number": "Numero mancante{context}.",
    "parse_bad_bib": "'{token}' non è un dorsale valido{context}.",
    "parse_in_sprint": " (sprint {n})",
    "parse_in_heat": " (batteria {n})",
    "parse_missing_time": "Tempo mancante.",
    "parse_bad_time": "Tempo non valido: {text} (usa mm:ss,mmm).",
    "parse_seconds_over_60": "Tempo non valido: {text} (secondi ≥ 60).",

    # -- entry list: reading the workbook ------------------------------------
    "xls_sheet_missing": "Foglio '{sheet}' assente dal file iscritti.",
    "xls_no_ksport": "Foglio 'KSPORT' assente: dati federali non integrati.",
    "xls_column_missing": "[{cat}] colonna '{column}' assente in riga {row}.",
    "xls_unknown_event_column": "[{cat}] colonna specialità sconosciuta: {column}.",
    "xls_duplicate_rider": "[{cat}] atleta duplicato (riga {row}): {name} {key}.",
    "xls_missing_region": "[{cat}] regione mancante: {name}.",
    "xls_bad_flag": "[{cat}] {name}: {event} -> {note}",
    "xls_unknown_flag": "valore non riconosciuto: {value}",
    "xls_unknown_cat": "[{file}] categoria non riconosciuta riga {row}: {value}",
    "ksport_not_in_category": ("[KSPORT] iscritto non presente nei fogli di "
                               "categoria: {name} ({uci})."),
    "ksport_missing": ("{n} atleti nei fogli di categoria non risultano in "
                       "KSPORT (iscrizione aggiunta a mano): {who}{more}"),
    "flat_column_missing": ("Colonna '{header}' ({field}) assente nel file "
                            "iscritti: il dato non è stato importato."),

    # -- entry list: teams and pairs -----------------------------------------
    "team_loose_x": ("{where}: {n} atleti con X fuori dalle squadre ({bibs}): "
                     "assegna la lettera (o {letter}R per la riserva)."),
    "team_wrong_size": "{where}: {n} titolari invece di {size} ({bibs}).",
    "team_region_wrong_size": "{where}: {n} atleti invece di {size} ({bibs}){hint}",
    "team_compose_hint": ": componi le squadre con A, AR, B, BR, ...",
    "pair_wrong_size": "[{cat} {event}] coppia {who}: {n} atleti invece di 2.",
    "pairs_guessed": ("[{cat} {event}] {region}: {n} atleti con X e nessuna "
                      "coppia indicata ({bibs}) - le coppie sono state formate "
                      "per ordine di dorsale, da confermare."),
    "pairs_guessed_page": ("**{region}**: {n} atleti con X e nessuna coppia "
                           "indicata nell'elenco iscritti. Le coppie qui sotto "
                           "sono state formate per ordine di dorsale - "
                           "confermale, o correggi l'accoppiamento in Verifica "
                           "(colonna Madison: A, B, ...).  \n{who}"),

    # -- entry list: overlay of jury edits -----------------------------------
    "patch_rider_gone": "{op} su atleta assente ({target}): {reason}",
    "patch_unknown_field": "campo sconosciuto '{field}' ({target})",
    "patch_not_entered": "{target} non era iscritto a {event}",
    "patch_no_pair_entry": "{target} non è iscritto a {event} (coppia)",
    "patch_unknown_op": "operazione sconosciuta '{op}' ({target})",

    # -- entry list: validation ---------------------------------------------
    "rider_no_uci": "{cat} {bib} {name}: UCI ID mancante.",
    "rider_no_team": "{name}: {what} non determinata.",
    "rider_no_bib": "{name}: dorsale mancante.",
    "rider_event_not_run": ("{cat} {bib} {name}: iscritto a {event}, che il "
                            "programma non prevede per questa categoria."),
    "rider_over_events": "{cat} {bib} {name}: {n} specialità (max {max}) - {events}.",
    "rider_old_certificate": "{cat} {bib} {name}: certificato del {date}, da verificare.",
    "duplicate_bib": "[{cat}] dorsale {bib} assegnato a {a} e {b}.",
    "quota_region": "[{cat} {event}] {region}: {n} atleti (max {max}).",
    "quota_club": "[{cat} {event}] {club}: {n} atleti (max {max}).",
    "quota_club_region": ("[{cat} {event}] {region}: {n} atleti della stessa "
                          "società {club} (max {max}) - dorsali {bibs}."),
    "quota_teams": "[{cat} {event}] {region}: {n} squadre/coppie (max {max}).",
    "over_event_limit": "Oltre il limite di specialità ({limits}): {who}",
    "limit_of": "{cat} max {n}",

    # -- scoring: bunch races ------------------------------------------------
    "extra_sprints": ("Inseriti {n} sprint, previsti {planned}: gli extra sono "
                      "comunque conteggiati."),
    "sprint_duplicate_bib": "Dorsale {bib} ripetuto nello sprint {n}.",
    "sprint_unknown_bib": "Dorsale {bib} (sprint {n}) non è tra i partenti.",
    "sprint_too_few": ("Sprint {n}: solo {found} atleti classificati (attesi "
                       "almeno {expected})."),
    "lap_gained_unknown": "Dorsale {bib} (giro guadagnato) non è tra i partenti.",
    "lap_lost_unknown": "Dorsale {bib} (giro perso) non è tra i partenti.",
    "eliminated_twice": "Dorsale {bib} eliminato due volte.",
    "bib_not_entered": "Dorsale {bib} non è tra i partenti.",
    "too_many_eliminations": "Inserite {n} eliminazioni per {starters} partenti.",

    # -- scoring: timed and bracket rounds -----------------------------------
    "same_time": "Due concorrenti con lo stesso tempo ({ms} ms): verifica il fotofinish.",
    "bib_in_two_heats": "Dorsale {bib} presente in più batterie.",
    "key_in_two_heats": "{who} è presente in più batterie.",
    "not_in_any_heat": "Non inseriti in nessuna batteria: {bibs}.",
    "not_in_this_heat": "{who} non corre nella batteria {n}.",
    "heat_no_result": "Batteria {n}: risultato non inserito.",
    "partial_standings": ("Classifica parziale dopo {done} prove su {total}: "
                          "{rounds}."),

    # -- races: what the page says while a race is being entered -------------
    "import_entries_first": "Importa l'elenco iscritti nella pagina Verifica.",
    "import_entries_here": "Importa l'elenco iscritti per iniziare.",
    "import_entries_in_settings": ("Nessun elenco iscritti: importalo in "
                                   "Impostazioni → Elenco iscritti."),
    "entries_caption": ("Il file della federazione non viene mai modificato. "
                        "Ricaricalo quando ne arriva uno nuovo: le modifiche "
                        "fatte qui (dorsali, squadre, specialità) sono "
                        "registrate a parte sull'UCI ID e vengono riapplicate."),
    "team_caption": "Sui documenti la colonna si chiama «{name}» e contiene: {group}.",
    "no_race_for_category": "Nessuna gara in programma per questa categoria.",
    "no_pairs_entered": "Nessuna coppia iscritta in questa categoria.",
    "no_riders_for_filter": "Nessun atleta con questi filtri.",
    "no_riders_for_selection": "Nessun atleta per questa selezione.",
    "no_documents_for_selection": "Nessun documento per questa selezione.",
    "stale_patches": "Modifiche non più applicabili dopo il re-import:\n\n{list}",
    "no_edits_to_save": "Nessuna modifica da salvare.",
    "reason_required": "Indica il motivo della modifica.",
    "edits_saved": "{n} modifiche registrate.",
    "riders_verified": "{n} atleti verificati.",
    "entries_imported": "Importati {n} atleti da {file}.",
    "file_not_found": "File non trovato",
    "source_changed": "Il file è cambiato dall'ultimo import",
    "exported_to": "Scritto {path}",

    # -- races: flags shown under an input field -----------------------------
    "sprint_hole": "Sprint {list} vuoto: nel punteggio i successivi slittano.",
    "unplaced_riders": ("**{n} {who} non ancora nei risultati**: {bibs}. Vanno "
                        "nell'ordine di arrivo dell'ultima volata, oppure "
                        "dichiarati DNF / DNS / DSQ."),
    "pending_results": "{n} concorrenti ancora senza risultato.",
    "times_missing": "{n} senza tempo: la classifica non li piazza.",
    "no_previous_version": "Nessuna versione precedente.",
    "heat_wrong_size": ("{heat}ª batteria, corsia {lane}: {n} dorsali invece di "
                        "{size} ({bibs})."),
    "status_field_error": "{field}: {error}",
    "communique_already_issued": ("Comunicato {n} già emesso per «{title}»: "
                                  "riemetterlo lo sostituisce nel registro."),
    "communique_duplicates": "Numeri emessi più volte: {list}",
    "sheet_not_ready": "«{round}» non ha ancora un risultato: {doc} non entra nel comunicato.",

    # -- races: composition --------------------------------------------------
    "entrant_twice_start_order_f": "già inserita",
    "entrant_twice_start_order_m": "già inserito",
    "entrant_twice_heat": "già in un'altra batteria",
    "odd_field_first": "Iscritti in numero dispari: chi corre da solo va nella 1ª batteria.",
    "odd_field_must_be_first": ("Iscritti in numero dispari: una batteria deve "
                                "avere un solo concorrente, ed è la 1ª."),
    "heats_not_matched": ("Batterie non riconducibili agli iscritti di questa "
                          "gara: resta la notazione."),
    "heats_from_previous": ("Le batterie si compongono dalla classifica del "
                            "turno precedente con il pulsante qui sotto."),
    "duplicate_pair_numbers": ("Numeri di coppia ripetuti: {list}. Due coppie "
                               "con lo stesso numero non sono distinguibili "
                               "nell'ordine degli sprint."),
    "empty_heats": "Nessuna coppia nella {list}.",
    "heat_ordinal": "{n}ª batteria",

    # -- races: sending a race on --------------------------------------------
    "round_not_in_programme": "Fase non presente nel programma.",
    "first_round_no_previous": "È la prima fase: non c'è una classifica da cui partire.",
    "no_previous_ranking": "Nessuna classifica precedente disponibile.",
    "heats_composed_from": "Batterie composte da {n} qualificati.",
    "round_composed": "«{round}»: {n} batterie composte.",
    "missing_result": "Manca ancora un risultato: la fase successiva non si compone.",
    "missing_arrival": "Manca ancora un arrivo: la fase successiva non si compone.",
    "need_two_qualified_f": "Servono almeno due qualificate.",
    "need_two_qualified_m": "Servono almeno due qualificati.",
    "finals_loaded": "«{round}»: {n} {who}, finali {names} composte.",
    "qualified_teams": "squadre qualificate",
    "qualified_riders": "qualificati",
    "madison_heat_no_result": "«{round}»: nessun risultato, le sue coppie non sono in finale.",
    "madison_no_qualified": ("Nessuna coppia qualificata: inserisci prima i "
                             "risultati delle batterie."),
    "madison_final_loaded": "«{round}»: {n} coppie in finale.",

    # -- races: what has not been loaded yet ---------------------------------
    "finals_not_loaded": ("Finali non caricate dalla qualificazione. Apri "
                          "«{round}» → **Risultati** → **Carica Finali**: da lì "
                          "arrivano semina (3°/4° e 1°/2°), tempi e {who}."),
    "finals_not_loaded_keirin": ("Finali non caricate. Corri «{round}» → "
                                 "**Risultati** → **Carica Finali**: da lì "
                                 "arrivano le due finali con i loro partenti."),
    "qualifying_no_times": "«{round}» non ha ancora tempi salvati.",
    "teams_not_qualified": "squadre non qualificate",
    "riders_not_qualified": "atleti non qualificati",
    "keirin_round_not_ridden": ("Con {n} iscritti questa fase non si corre: la "
                                "tabella UCI porta «{last}» direttamente alle "
                                "finali."),
    "repechages_from_losers": ("I recuperi si compongono dai perdenti del 1° "
                               "turno, appena ogni batteria ha un risultato."),
    "final_5_8_from_quarters": "La finale 5°-8° si compone dai quarti.",

    # -- sheet notes the jury starts from ------------------------------------
    "note_scheme_12": "Si qualificano per il 1° turno i migliori 12 tempi.",
    "note_scheme_8": "Si qualificano direttamente ai quarti i migliori 8 tempi.",
    "team_letter": "{where} squadra {letter}",
    "note_madison_startlist": ("Non si qualificano per la finale le ultime {n} "
                               "coppie tra le partenti."),
    "note_madison_results": "Passano alla finale le prime {n} coppie classificate.",
    "note_sprint_round1_start": ("{winner} di ogni batteria passa ai quarti di "
                                 "finale, {others} ai recuperi."),
    "note_sprint_round1_results": ("{winner} di ogni batteria dei recuperi passa "
                                   "ai quarti di finale."),
    "note_sprint_repechage": ("Due prove + ev. bella. {winners} passano alle "
                              "semifinali, {others} alla finale 5°-8° posto."),
    "note_keirin_stage": "{round}: {heats} batterie. {first} di ogni batteria {to}{rest}",
    "note_keirin_repechages": ", {rest} ai recuperi.",
    "note_keirin_rep_stage": ("Recuperi: {heats} batterie. {first} di ogni "
                              "batteria {to}."),
    "winner_f": "La vincitrice",
    "winner_m": "Il vincitore",
    "winners_f": "Le vincitrici",
    "winners_m": "I vincitori",
    "others_f": "le altre",
    "others_m": "gli altri",
    "first_n_f": "Le prime {n} classificate",
    "first_n_m": "I primi {n} classificati",
    "goes_through_1": "passa",
    "goes_through_n": "passano",
    "to_semifinals": "alle semifinali",
    "to_quarters": "ai quarti di finale",
    "to_round": "a «{round}»",
    "to_next": "avanti",
    "to_final_one": "alla finale {top} posto",
    "to_final_two": "alla finale {top} posto, {rest} alla finale {low} posto",
    "and_final_5_8": " e la finale 5°-8° posto",

    # -- decisions -----------------------------------------------------------
    "no_decisions": "Nessuna decisione registrata.",
    "decision_empty": "Scrivi la decisione prima di registrarla.",
    "decision_saved": "Decisione n. {n} registrata.",
    "decision_removed": "Decisione n. {n} eliminata.",
    "decision_updated": "Decisione n. {n} aggiornata.",
    # the line a penalty goes on the sheet as, composed from the pickers:
    # "ES 12 ROSSI Mario: RETROCESSIONE (C) per aver pedalato sulla fascia
    # azzurra" - the wording after it comes from the UCI table itself
    "penalty_for": "{who}:",
    "penalty_rider": "{cat} {bib} {name}",
    "decision_of_race": "{cat} · {event}{round}",
    "decision_day": "giornata {day}",
    "no_penalties_table": "Tabella delle penalità non disponibile.",
    "no_puis_table": "Prontuario PUIS non disponibile.",

    # -- printing ------------------------------------------------------------
    "chromium_missing": ("Chromium non installato: verrà salvato l'HTML "
                         "(stampabile con Ctrl+P)."),
    "pdf_no_browser": "Nessun browser Chromium trovato: impossibile creare il PDF.",
    "pdf_failed": "Chromium non ha prodotto il PDF. {error}",
    "saved_as": "Salvato {name}",
    "saved_entry_lists": "Salvati {n} elenchi",
    "race_saved": "Gara salvata",
    "pairing_saved": "Composizione salvata",
    "open_document": "Apri {name}",

    # -- settings ------------------------------------------------------------
    "folder_not_a_dir": "{path} esiste ma non è una cartella.",
    "folder_no_parent": "Nessuna parte del percorso {path} esiste.",
    "folder_not_writable": "Permesso negato in scrittura su {path}.",
    "folder_confirm": "Premi «Salva cartella» per confermare.",
    "folder_saved": "I comunicati verranno salvati in {path}",
    "signature_file_missing": "File non trovato: i comunicati usciranno senza firma.",
    "signature_name_missing": "Senza nome i comunicati escono senza firma.",
    "image_missing": "File non trovato: il comunicato uscirà senza questa immagine.",
    "signature_caption": "Cosa si stampa sotto «{label}» in fondo al comunicato.",
    "appearance_caption": ("Vale per ogni foglio di questa manifestazione. Si "
                           "imposta una volta e resta: non fa parte del "
                           "programma gara."),
    "letterhead_caption": ("Immagini stampate in cima e in fondo a ogni foglio "
                           "dei comunicati (SVG, PNG o JPEG). A schermo non "
                           "compaiono."),
    "reset_caption": ("Cancella i risultati salvati di una specialità: **tutte "
                      "le fasi**, qualificazioni e batterie comprese. Non tocca "
                      "l'elenco iscritti né la verifica licenze; i comunicati "
                      "già emessi restano nel registro, con il loro numero."),
    "no_event_for_category": "Nessuna specialità in programma per {cat}.",
    "no_saved_race": "Nessuna gara salvata per questa specialità: niente da azzerare.",
    "races_reset": ("{n} gare cancellate ({cat} · {event}). Le versioni "
                    "precedenti restano in `.snapshots/`."),
    "backup_caption": ("Cartella dati: `{root}` - ogni salvataggio conserva la "
                       "versione precedente in `.snapshots/`. I comunicati "
                       "prodotti vanno in `{out}`."),
    "backup_done": "Copiato in {path}",
    "no_findings": "Nessun rilievo.",

    # -- the programme file --------------------------------------------------
    "yaml_header": ("# {name}\n"
                    "#\n"
                    "# Scritto dalla pagina Programma di Blue Band. Il layout è\n"
                    "# generato: le note vanno nei campi `note:`, che\n"
                    "# sopravvivono a un salvataggio - un commento no.\n"),
    "yaml_day": "giorno {n}",
    "yaml_competition": "manifestazione",
    "yaml_entries": "elenco iscritti: dove sta il file e come si chiamano le colonne",
    "yaml_branding": "testata, piè di pagina, firma",
    "yaml_categories": "categorie",
    "yaml_events": "specialità",
    "yaml_quotas": "quote di iscrizione (comunicato STP)",
    "yaml_programme": "programma gare",
    "yaml_communiques": "registro comunicati",
    "communique_gaps": "Numeri non usati nel registro: {list}{more}",
    "communique_moved": ("Comunicato {n} già emesso come «{was}»: nel programma "
                         "ora è «{now}». Il foglio in mano alla giuria e il "
                         "registro direbbero due cose diverse."),
    "no_communique_planned": "{cat} {event}: nessun comunicato previsto.",
    "programme_saved": "Programma salvato in {path}",
    "no_race_on_day": "Nessuna gara in programma nella giornata {day}.",
    "race_already_scheduled": "{cat} {event} è già in programma.",
    "declare_cats_and_events": ("Dichiara prima categorie e specialità nelle "
                                "schede Gara e Specialità."),
    "docs_not_of_format": ("Documenti non previsti da un formato {fmt}: {list}. "
                           "Il foglio resterà vuoto."),
    "rounds_decided_on_the_day": ("Quante di queste fasi si corrono davvero lo "
                                  "decide il numero di iscritti (keirin: "
                                  "tabella UCI 3.2.135; velocità: schema scelto "
                                  "sul 200 m). Qui si dichiara quali sono "
                                  "possibili."),

    # -- printed sheets ------------------------------------------------------
    "event_key": "Sigle specialità:  {list}",
    "count_entered_starters": "{entered} iscritti / {starters} partenti",
    "count_starters": "{n} partenti",
    "count_documents": "{n} documenti  ·  {issued} emessi",
    "count_recap": "{riders} atleti  ·  {entries} iscrizioni",
    "recap_legend": ("Sigle specialità:  {list}.    Nelle caselle: X iscritto, "
                     "R riserva, A/B la coppia o la squadra negli "
                     "accoppiamenti (AR = riserva della squadra A); il numero "
                     "che segue è la batteria, dove è già stata comunicata."),
    "no_teams": ("Nessuna squadra: gli atleti non hanno una regione o una "
                 "società."),
    "heats_count": "{n} batterie",
    "heat_one": "1 batteria",
}


IT: dict[str, str] = {**FIELDS, **RACE, **DOCS, **STATUSES}


# ── words this competition spells its own way ───────────────────────────────
#
# One word is not the same at every meeting: what a rider rides for is a
# *squadra* at a championship, a *rappresentativa* in some regions, a *team* on
# an international sheet. It is a name the jury chooses in Impostazioni, so it
# cannot be frozen in the dictionaries above - and it is still one word in one
# place, because everything asks for it by the same key.
#
# Set once per run, from the competition being loaded (`ui.state.competition`).

_OVERRIDES: dict[str, str] = {}


def set_overrides(values: dict[str, str]) -> None:
    """Replace the words this competition spells its own way ({} clears them)."""
    _OVERRIDES.clear()
    _OVERRIDES.update({k: v for k, v in (values or {}).items() if v})


def label(key: str, default: str | None = None) -> str:
    """Italian label for a domain key ('bib' -> 'Dors.')."""
    if key in _OVERRIDES:
        return _OVERRIDES[key]
    if key in IT:
        return IT[key]
    return default if default is not None else str(key).replace("_", " ").capitalize()


def ui(key: str, /, **kwargs) -> str:
    """What a control is called ('save_pdf' -> 'Salva PDF').

    Raises on an unknown key: a control with no name is a bug in the code, not
    a word to make up on the spot.
    """
    if key in _OVERRIDES and not kwargs:
        return _OVERRIDES[key]
    return UI[key].format(**kwargs) if kwargs else UI[key]


def msg(key: str, /, **kwargs) -> str:
    """One message, with its values filled in ('bib_not_entered', bib=17)."""
    return MSG[key].format(**kwargs) if kwargs else MSG[key]


def help_text(*keys: str, **kwargs) -> str:
    """The tooltip for a field, one or more entries of HELP joined by a space.

    Raises on an unknown key, like `ui` and `msg`: a tooltip that silently came
    back empty is how a field ends up with no help at all and nobody notices.
    An empty key is skipped, which is what makes a conditional part readable:
    `help_text("n_events", reserves="")`.
    """
    parts = [HELP[k] for k in keys if k]
    return " ".join(p.format(**kwargs) if kwargs else p for p in parts)


def code_name(code: str) -> str:
    """What a finding is about, as the jury reads it ('bib_dup' -> 'Dorsale doppio')."""
    return CODES.get(code, str(code).replace("_", " ").capitalize())


def status_name(code: str) -> str:
    """Spelled-out status, for the pickers ('DNF' -> 'Ritirato')."""
    return STATUS_NAMES.get(str(code).upper(), str(code))


def penalty_name(code: str) -> str:
    """Spelled-out degree of a penalty ('C' -> 'Retrocessione')."""
    return PENALTIES.get(str(code).upper(), str(code))


def plural(n: int, one: str, many: str) -> str:
    """Pick the form that agrees with `n` ('passa' / 'passano')."""
    return one if n == 1 else many


def gendered(female: bool, key_m: str, key_f: str, **kwargs) -> str:
    """The form written about the riders in front of the jury.

    A sheet is written about who rides it: *la vincitrice* of a batteria in a
    categoria femminile, *il vincitore* in a maschile. `Competition.female`
    decides, and this picks the wording.
    """
    return msg(key_f if female else key_m, **kwargs)
