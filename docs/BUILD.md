# Building the Windows installer

The console ships as an `.exe` a jury installs by double-clicking: no Python,
no command line, an icon on the desktop. This is how it is made, and - more
usefully - which parts of it are load-bearing.

```bash
python packaging/make_icon.py                 # header/track.svg -> .ico
pyinstaller packaging/blueband.spec --noconfirm
iscc packaging/blueband.iss                   # Windows only, Inno Setup 6
```

Out comes `dist/BlueBand-<version>-setup.exe`. CI does the same on every `v*`
tag (`.github/workflows/build.yml`) and attaches it to the release.

## What it weighs, and why

The app installs at **about 435 MB**, and most of that is three packages the
console never imports by name:

| | installed |
|---|---|
| pandas, numpy, pyarrow (+ altair, pydeck) | ~334 MB |
| Streamlit, Pillow, tornado and the rest | ~87 MB |
| CPython and the bootloader | ~20 MB |
| the app, its regulations and its templates | ~1 MB |

They are there because `st.dataframe` and `st.data_editor` are made of them:
Streamlit serialises every table through Arrow, and `dataframe_util` imports
pandas unconditionally to work out what it has been handed. There is no
middle setting - pyarrow without pandas does not run, and `pip install
streamlit` declares all five as hard dependencies.

**This was measured, not assumed, and the alternative was built and rejected.**
The tables and the grids were once hand-written as HTML (`ui/table.py`,
`ui/grid.py`, and a custom component) and the installation came down to 108 MB.
It was worse to use: rows twice as tall, a select too narrow to show whether a
specialità was ticked, and none of what `st.dataframe` gives for free - sorting
by column, resizing, full screen, search, copy. A console used at a
championship is worth more than 300 MB of disk, so the widgets came back.

Keep that in mind before "optimising" the dependency list: the size is a
decision that has already been taken, once, with numbers.

## The three awkward things about freezing Streamlit

All three are solved in `packaging/blueband.spec`, and each was a build that
succeeded and then failed at runtime:

1. **Streamlit reads its own version from its installed metadata.** Without
   the `.dist-info` in the bundle it raises at import. `copy_metadata`.
2. **Its frontend is data.** `streamlit/static/` is the compiled React app.
   `collect_data_files`.
3. **The app is never imported.** The analysis starts at `launcher.py`, which
   hands Streamlit `app.py` as a *path* - so `core`, `ui` and `render` are in
   no import graph, and a bundle without them starts, serves a page, and dies
   on `No module named 'core'` at the first render. `collect_submodules`, with
   the repository put on `sys.path` first: without that, `collect_submodules`
   finds nothing and returns an empty list **with only a warning**.

`BlueBand.exe --check` is the guard against all three: it imports every module
and looks for every data file, and it fails at the door instead of on the
jury's first click.

## Where things end up

| | path | survives an uninstall |
|---|---|---|
| the program | `%LOCALAPPDATA%\Programs\Blue Band` | no |
| the championships | `Documenti\BlueBand` | **yes** |
| the comunicati | wherever Impostazioni points, usually Drive | **yes** |

The install is **per-user on purpose**, twice over: no administrator prompt on
a laptop nobody has the password for, and the program's folder stays writable -
Streamlit serves the last saved PDFs out of `static/` inside it, which is what
the "Apri il PDF" link follows (`core.paths.served`).

`core.paths` is the only module that knows any of this. Run from a checkout it
answers with the repository, exactly as before, which is why nothing else in
the codebase had to learn about `sys._MEIPASS`.

## Building on Linux

The whole recipe except the `.ico` and the installer works on Linux, and that
is worth doing before pushing a tag - it catches everything except the Windows
packaging itself:

```bash
python -m venv /tmp/bb && /tmp/bb/bin/pip install -e ".[build]"
/tmp/bb/bin/pyinstaller packaging/blueband.spec --noconfirm
dist/BlueBand/BlueBand --check
```

Build it in a **clean virtual environment**, never in a working scientific one:
PyInstaller bundles what it finds, and the `excludes` in the spec are a safety
net rather than a guarantee - matplotlib, astropy and a Qt or two are exactly
what a research machine would otherwise post to a jury.
