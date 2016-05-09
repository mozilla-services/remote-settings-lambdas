clean:
	rm -fr venv lambda.zip

virtualenv:
	virtualenv venv
	venv/bin/pip install -r requirements.pip

zip:
	zip lambda.zip lambda.py schemas.json
	cd venv/lib/python2.7/site-packages/; zip -r ../../../../lambda.zip *
