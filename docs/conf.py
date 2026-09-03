"""Sphinx configuration for the Blue Band documentation.

The docs are built in two languages from one English source: `locales/it/`
holds the Italian catalogue, and Read the Docs builds each language as its own
version of the project. Nothing here is translated by hand twice.
"""

import os
import sys
from importlib.metadata import PackageNotFoundError, version as _version

sys.path.insert(0, os.path.abspath(".."))

try:
    __version__ = _version("blueband")
except PackageNotFoundError:  # a checkout that was never pip-installed
    __version__ = "unknown version"

# ── General ─────────────────────────────────────────────────────────────────

project = "Blue Band"
author = "Nicola Borghi"
copyright = "2026, Nicola Borghi — GPLv3"
version = release = __version__

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "myst_parser",
]

myst_enable_extensions = ["colon_fence", "deflist"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
master_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "locales"]

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# ── Translations ────────────────────────────────────────────────────────────
#
# `language` is what Read the Docs passes per translation build; locally,
# `make html` is English and `make html-it` is Italian.

language = os.environ.get("READTHEDOCS_LANGUAGE", "en")
locale_dirs = ["locales/"]
gettext_compact = False
gettext_uuid = True

# ── HTML ────────────────────────────────────────────────────────────────────

html_theme = "sphinx_book_theme"
html_title = "Blue Band"
html_logo = "_static/wordmark.svg"
html_favicon = "_static/favicon.svg"
templates_path = ["_templates"]
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_copy_source = True
html_show_sourcelink = True
html_theme_options = {
    "path_to_docs": "docs",
    "repository_url": "https://github.com/nicoborghi/BlueBand",
    "repository_branch": "main",
    "use_edit_page_button": True,
    "use_issues_button": True,
    "use_repository_button": True,
    "home_page_in_toc": True,
    # the EN | IT switcher sits before the theme and search buttons
    "article_header_end": ["language-switcher.html", "article-header-buttons.html"],
}
