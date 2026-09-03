.PHONY: run test lint docs docs-serve docs-clean build

run:
	streamlit run app.py

test:
	python -m pytest tests -q

lint:
	ruff check .

docs:
	mkdocs build --strict

docs-serve:
	mkdocs serve

docs-clean:
	rm -rf site

# the frozen program, without the Windows installer (see docs/reference/build.md)
build:
	pyinstaller packaging/blueband.spec --noconfirm
