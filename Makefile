VENV := $(shell echo $${VIRTUAL_ENV-.venv})
INSTALL_STAMP := $(VENV)/.install.stamp

clean:
	rm -fr $(VENV)

$(INSTALL_STAMP): requirements.txt requirements-dev.txt
	python -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip install -r requirements-dev.txt
	touch $(INSTALL_STAMP)

.PHONY: lint
lint: $(INSTALL_STAMP)
	$(VENV)/bin/ruff check *.py commands tests
	$(VENV)/bin/ruff format --check *.py commands tests

.PHONY: format
format: $(INSTALL_STAMP)
	$(VENV)/bin/ruff check --fix *.py commands tests
	$(VENV)/bin/ruff format *.py commands tests

test: $(INSTALL_STAMP)
	PYTHONPATH=. $(VENV)/bin/pytest

build:
	docker build -t remote-settings-lambdas .

zip: build
	docker cp `docker create remote-settings-lambdas /bin/true`:/lambda.zip remote-settings-lambdas-`git describe --tags --abbrev=0`.zip
