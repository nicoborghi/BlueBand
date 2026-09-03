# Blue Band documentation.
#
#   make html      the English site        (_build/html)
#   make html-it   the Italian site        (_build/html-it)
#   make gettext   extract strings         (_build/gettext)
#   make update    gettext + merge into locales/it
#
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

.PHONY: help html html-it gettext update clean

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS)

html:
	@$(SPHINXBUILD) -b html -D language=en "$(SOURCEDIR)" "$(BUILDDIR)/html" $(SPHINXOPTS)

html-it:
	@$(SPHINXBUILD) -b html -D language=it "$(SOURCEDIR)" "$(BUILDDIR)/html-it" $(SPHINXOPTS)

gettext:
	@$(SPHINXBUILD) -b gettext "$(SOURCEDIR)" "$(BUILDDIR)/gettext" $(SPHINXOPTS)

# Re-extract and merge: run after editing any .rst, then translate the fuzzy
# and empty entries left in locales/it/LC_MESSAGES/.
update: gettext
	sphinx-intl update -p "$(BUILDDIR)/gettext" -l it

clean:
	rm -rf "$(BUILDDIR)"
