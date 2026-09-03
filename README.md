<p align="center">
  <img src="ui/track_text_ink.svg" alt="Blue Band" width="370">
</p>

<p align="center">
  <a href="https://github.com/nicoborghi/BlueBand/"><img src="https://img.shields.io/badge/GitHub-BlueBand-9e8ed7" alt="GitHub"></a>
  <a href="https://github.com/nicoborghi/BlueBand/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-GPLv3-blue" alt="License: GPLv3"></a>
  <a href="https://github.com/nicoborghi/BlueBand/actions/workflows/tests.yml"><img src="https://github.com/nicoborghi/BlueBand/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="https://codecov.io/gh/nicoborghi/BlueBand"><img src="https://img.shields.io/codecov/c/github/nicoborghi/BlueBand" alt="Coverage"></a>
  <a href="https://blueband.readthedocs.io/"><img src="https://readthedocs.org/projects/blueband/badge/?version=latest" alt="Documentation Status"></a>
  <a href="https://claude.ai"><img src="https://img.shields.io/badge/built_with-Claude-orange?logo=anthropic&logoColor=white" alt="Built with Claude"></a>
</p>

**Commissaire console for track cycling competitions.** Licence check, race
management, classifications, jury decisions, numbered communiqués. Built on
Streamlit.

> [!NOTE]
> **Experimental** — used at the Italian Youth Track Championships (2025, 2026)
> and nowhere else. Much of the codebase is AI-generated.

One YAML file per competition says what is being run — the track, the categories,
which events each contests, the rounds of every event, the running order of each
day, the communiqué register. Everything the jury does is written to plain files
in one folder, atomically, with the previous version kept.

## Install

On a jury laptop, install
[the latest `BlueBand-setup.exe`](https://github.com/nicoborghi/BlueBand/releases)
and start it from the desktop. No Python, no command line; the competitions it
writes live in `Documenti\BlueBand` and an uninstall does not touch them.

From a checkout:

```bash
pip install -e .
streamlit run app.py          # or: python launcher.py, as the .exe runs it
```

`competitions/example/` is a fictional meeting that ships with the repo — open
it to see the console working without holding a real entry list. It is also what
the tests run on.

```bash
python -m pytest tests -q
```

## Documentation

**[blueband.readthedocs.io](https://blueband.readthedocs.io/)** — built with
Sphinx in two languages from one English source.

| | |
|---|---|
| [Running a competition](https://blueband.readthedocs.io/en/latest/guide.html) | What to click, at the trackside |
| [Glossary](https://blueband.readthedocs.io/en/latest/glossary.html) | The vocabulary, and every result code |
| [Install and run](https://blueband.readthedocs.io/en/latest/install.html) | Both install paths, the tests, the example |
| [Reference](https://blueband.readthedocs.io/en/latest/reference/index.html) | Architecture, `programme.yaml`, formats, storage, the build |

To build the docs locally:

```bash
pip install -e ".[docs]"
cd docs
make html        # English  -> docs/_build/html
make html-it     # Italian  -> docs/_build/html-it
```

After editing any `.rst`, re-extract and merge the translation catalogues, then
fill in what `make update` leaves empty or fuzzy under `docs/locales/it/`:

```bash
make update
```

## Licence

GPLv3 — see [LICENSE](LICENSE).
