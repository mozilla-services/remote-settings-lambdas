VENV := $(shell echo $${VIRTUAL_ENV-.venv})
INSTALL_STAMP := $(VENV)/.install.stamp

clean:
	rm -fr .venv lambda.zip

$(INSTALL_STAMP): requirements.txt constraints.txt
	virtualenv $(VENV) --python=python3
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/pip install --use-deprecated=legacy-resolver -r requirements.txt -c constraints.txt
	$(VENV)/bin/pip install therapist pytest
	touch $(INSTALL_STAMP)

lint: $(INSTALL_STAMP)
	$(VENV)/bin/therapist run --use-tracked-files .

test:
	PYTHONPATH=. $(VENV)/bin/pytest

build:
	docker build -t remote-settings-lambdas .

zip: build
	docker cp `docker create remote-settings-lambdas /bin/true`:/lambda.zip remote-settings-lambdas-`git describe --tags --abbrev=0`.zip
