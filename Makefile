.PHONY: lint
lint: ## Check the code for linting, formatting, and typing issues with ruff and mypy
	ruff check
	ruff format --check
	mypy dangerzone tests

.PHONY: fix
fix: ## apply all the suggestions from ruff
	ruff check --fix
	ruff format

.PHONY: test
test: ## Run the tests
	# Make each GUI test run as a separate process, to avoid segfaults due to
	# shared state.
	# See more in https://github.com/freedomofpress/dangerzone/issues/493
	pytest --co -q tests/gui | grep -e '^tests/' | xargs -n 1 pytest -v
	pytest -v --cov --ignore dev_scripts --ignore tests/gui

Dockerfile: Dockerfile.env Dockerfile.in ## Regenerate the Dockerfile from its template
	poetry run jinja2 Dockerfile.in Dockerfile.env > Dockerfile

.PHONY: poetry-install
poetry-install: ## Install project dependencies
	poetry install

.PHONY: build-clean
build-clean:
	poetry run doit clean

.PHONY: build-macos-intel
build-macos-intel: build-clean poetry-install ## Build macOS intel package (.dmg)
	poetry run doit -n 8

.PHONY: build-macos-arm
build-macos-arm: build-clean poetry-install ## Build macOS Apple Silicon package (.dmg)
	poetry run doit -n 8 macos_build_dmg

.PHONY: build-linux
build-linux: build-clean poetry-install ## Build linux packages (.rpm and .deb)
	poetry run doit -n 8 fedora_rpm debian_deb

.PHONY: regenerate-reference-pdfs
regenerate-reference-pdfs: ## Regenerate the reference PDFs
	pytest tests/test_cli.py -k regenerate --generate-reference-pdfs
# Makefile self-help borrowed from the securedrop-client project
# Explaination of the below shell command should it ever break.
# 1. Set the field separator to ": ##" and any make targets that might appear between : and ##
# 2. Use sed-like syntax to remove the make targets
# 3. Format the split fields into $$1) the target name (in blue) and $$2) the target descrption
# 4. Pass this file as an arg to awk
# 5. Sort it alphabetically
# 6. Format columns with colon as delimiter.
.PHONY: help
help: ## Print this message and exit.
	@printf "Makefile for developing and testing dangerzone.\n"
	@printf "Subcommands:\n\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[0-9a-zA-Z_-]+:.*?## / {printf "\033[36m%s\033[0m : %s\n", $$1, $$2}' $(MAKEFILE_LIST) \
		| sort \
		| column -s ':' -t
