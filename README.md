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
> [!NOTE]
> **Beta version** - used at the Italian Youth Track Championships (2025, 2026) and at the Trofeo delle Regioni 2026. Much of the codebase is AI-generated.

The competition is described in a single YAML file, which is read by BlueBand at startup. The app is a single-page web app, which can be run on a laptop or a tablet. The app is designed to be used by the commissaires at the trackside to manage the competition, including checking licences, managing events, and generating results and communiqués. The app is designed to be easy to use, with a simple interface that allows the commissaires to quickly access the information they need.

## Install

Python ≥ 3.11, from this repository:

```bash
git clone https://github.com/nicoborghi/BlueBand.git
cd BlueBand
pip install -e .
streamlit run app.py          # or: python launcher.py
```

> **Packaging is not implemented yet.** There is no installer and no release to
> download: the app runs from a checkout. `packaging/` holds a work-in-progress
> PyInstaller spec and Inno Setup script, neither of which ships a build today.

`competitions/example/` is a fictional meeting that ships with the repo. It is also what
the tests run on.

```bash
python -m pytest tests -q
```

## Documentation

**[blueband.readthedocs.io](https://blueband.readthedocs.io/)** - built with
Sphinx in English and Italian.

| | |
|---|---|
| [Running a competition](https://blueband.readthedocs.io/en/latest/guide.html) | What to click, at the trackside |
| [Glossary](https://blueband.readthedocs.io/en/latest/glossary.html) | The vocabulary, and every result code |
| [Install and run](https://blueband.readthedocs.io/en/latest/install.html) | Install paths, the tests, the example |
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

GPLv3 - see [LICENSE](LICENSE).
