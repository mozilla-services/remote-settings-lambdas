clean:
	rm -fr .venv lambda.zip

virtualenv:
	virtualenv .venv --python=python3.6
	.venv/bin/pip install -r requirements.txt -c constraints.txt
	.venv/bin/pip install --no-deps kinto-signer -c constraints.txt

zip:
	docker build -t remote-settings-lambdas .
	docker cp `docker create remote-settings-lambdas /bin/true`:/lambda.zip remote-settings-lambdas-`git describe --tags --abbrev=0`.zip
