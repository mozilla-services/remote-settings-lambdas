VENV := $(shell echo $${VIRTUAL_ENV-.venv})
INSTALL_STAMP := $(VENV)/.install.stamp

clean:
	rm -fr .venv lambda.zip

$(INSTALL_STAMP): requirements.txt requirements-dev.txt
	virtualenv $(VENV) --python=python3
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip install -r requirements-dev.txt
	touch $(INSTALL_STAMP)

format: $(INSTALL_STAMP)
	$(VENV)/bin/isort --profile=black --lines-after-imports=2 commands tests --virtual-env=$(VENV)
	$(VENV)/bin/black commands tests

lint: $(INSTALL_STAMP)
	$(VENV)/bin/isort --profile=black --lines-after-imports=2 --check-only commands tests --virtual-env=$(VENV)
	$(VENV)/bin/black --check commands tests --diff
	$(VENV)/bin/flake8 --ignore=W503,E501 commands tests

test: $(INSTALL_STAMP)
	PYTHONPATH=. $(VENV)/bin/pytest

build:
	docker build -t remote-settings-lambdas .

zip: build
	docker cp `docker create remote-settings-lambdas /bin/true`:/lambda.zip remote-settings-lambdas-`git describe --tags --abbrev=0`.zip
