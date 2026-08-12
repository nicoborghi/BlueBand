from core.models import Heat, RaceState, race_id
from core.store import Store


def test_race_id_is_filename_safe():
    assert race_id("AL", "ins_squadre", "Finali") == "al_ins_squadre_finali"
    assert (race_id("ES", "madison", "Qualificazioni Batteria 1")
            == "es_madison_qualificazioni-batteria-1")
    assert race_id("DA", "velocita", "") == "da_velocita"


def test_save_load_roundtrip(store: Store):
    st = store.get_race("AL", "madison", "Finale", fmt="madison")
    st.entrants = ["a", "b"]
    st.heats = [Heat(number=1, entrants=["a", "b"], order=["b", "a"])]
    st.statuses = {"a": "DNF"}
    st.payload = {"sprints": [[1, 2], [2, 1]]}
    store.save_race(st)

    back = store.load_race(st.race_id)
    assert isinstance(back, RaceState)
    assert back.entrants == ["a", "b"]
    assert back.heats[0].order == ["b", "a"]
    assert back.status("a").value == "DNF"
    assert back.status("b").value == "OK"
    assert back.payload["sprints"] == [[1, 2], [2, 1]]
    assert back.updated_at


def test_snapshot_and_restore(store: Store):
    st = store.get_race("AL", "madison", "Finale")
    st.decision = "prima versione"
    store.save_race(st)

    st.decision = "seconda versione"
    store.save_race(st)
    assert store.load_race(st.race_id).decision == "seconda versione"

    rel = store.race_rel(st.race_id)
    assert len(store.snapshots(rel)) == 1
    store.restore(rel)
    assert store.load_race(st.race_id).decision == "prima versione"


def test_rapid_saves_never_lose_a_snapshot(store: Store):
    """Snapshots taken in the same millisecond must not overwrite each other."""
    st = store.get_race("AL", "velocita", "Finali 1-4")
    for i in range(6):
        st.decision = f"versione {i}"
        store.save_race(st)
    snaps = store.snapshots(store.race_rel(st.race_id))
    assert len(snaps) == 5
    assert len({p.name for p in snaps}) == 5


def test_journal_records_every_write(store: Store):
    st = store.get_race("DA", "keirin", "Finali")
    store.save_race(st)
    store.save_race(st)
    entries = store.read_journal()
    assert [e["action"] for e in entries] == ["save_race", "save_race"]
    assert entries[0]["target"].endswith("da_keirin_finali.json")


def test_backup_excludes_snapshots(store: Store, tmp_path):
    st = store.get_race("ES", "omnium", "Scratch")
    store.save_race(st)
    store.save_race(st)
    dest = store.backup(tmp_path / "bk")
    assert (dest / "races" / "es_omnium_scratch.json").exists()
    assert not (dest / ".snapshots").exists()


def test_delete_race_keeps_a_snapshot(store: Store):
    st = store.get_race("ED", "madison", "Finale")
    store.save_race(st)
    store.delete_race(st.race_id)
    assert store.load_race(st.race_id) is None
    assert store.snapshots(store.race_rel(st.race_id))


# ── output folder ───────────────────────────────────────────────────────────

def test_out_dir_defaults_inside_the_event(store: Store):
    assert store.out_dir == store.root / "out"
    assert store.settings == {}


def test_out_dir_can_be_moved_anywhere(store: Store, tmp_path):
    dest = tmp_path / "Drive" / "Comunicati"
    assert store.set_out_dir(dest) == dest
    assert store.out_dir == dest
    assert store.settings["out_dir"] == str(dest)

    # the folder is created on first write, not on configuration
    assert not dest.exists()
    p = store.write_out("001_prova.pdf", b"%PDF-1.4 x")
    assert p == dest / "001_prova.pdf"
    assert p.read_bytes().startswith(b"%PDF")


def test_out_dir_resets_to_the_default(store: Store, tmp_path):
    store.set_out_dir(tmp_path / "altrove")
    assert store.set_out_dir(None) == store.root / "out"
    assert "out_dir" not in store.settings

    # setting it explicitly to the default is stored as unset, not duplicated
    store.set_out_dir(store.root / "out")
    assert "out_dir" not in store.settings


def test_out_dir_expands_the_home_shortcut(store: Store):
    from pathlib import Path
    store.set_out_dir("~/comunicati-prova")
    assert store.out_dir == Path.home() / "comunicati-prova"


def test_write_out_is_journalled_with_the_full_path(store: Store, tmp_path):
    store.set_out_dir(tmp_path / "esiti")
    store.write_out("007_prova.html", "<p>x</p>")
    entry = [e for e in store.read_journal() if e["action"] == "archive_document"]
    assert entry and entry[-1]["target"].endswith("esiti/007_prova.html")


def test_the_races_last_worked_on_come_back_first(store):
    """What the pills on the Gare page offer: the sheets being worked on now.

    Read off the file times, because a race is written exactly when somebody
    is on it - and the jury moves between four or five fasi all afternoon.
    """
    import time

    from core.models import RaceState

    for cat, event, rnd in (("AL", "velocita", "Quarti"),
                            ("ES", "madison", "Finale"),
                            ("DA", "omnium", "Scratch")):
        store.save_race(store.get_race(cat, event, rnd))
        # a jury works on one race at a time, minutes apart; three saves inside
        # one clock tick is a test artefact, and what it would be testing is
        # the resolution of the filesystem
        time.sleep(0.02)

    recent = store.recent_races(6)
    assert all(isinstance(r, RaceState) for r in recent)
    assert [(r.cat, r.round_key) for r in recent] == [
        ("DA", "Scratch"), ("ES", "Finale"), ("AL", "Quarti")]
    # saving one again brings it back to the front: it is where the jury is
    time.sleep(0.02)
    store.save_race(store.get_race("AL", "velocita", "Quarti"))
    assert store.recent_races(1)[0].cat == "AL"
    assert len(store.recent_races(2)) == 2


def test_a_competition_with_no_races_offers_none(store):
    assert store.recent_races() == []
