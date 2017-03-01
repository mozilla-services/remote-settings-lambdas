SPHINX_BUILDDIR = docs/build

AMO_BLOCKLIST_UI_SCHEMA = "https://raw.githubusercontent.com/mozilla-services/amo-blocklist-ui/master/amo-blocklist.json"

clean:
	rm -fr venv lambda.zip ami-built-lambda.zip

virtualenv:
	virtualenv venv --python=python2.7
	venv/bin/pip install -r requirements.pip

zip: clean virtualenv
	zip lambda.zip lambda.py schemas.json
	touch venv/lib/python2.7/site-packages/zope/__init__.py
	touch venv/lib/python2.7/site-packages/repoze/__init__.py
	cd venv/lib/python2.7/site-packages/; zip -r ../../../../lambda.zip *

update-schemas:
	wget -O schemas.json $(AMO_BLOCKLIST_UI_SCHEMA)

docs: virtualenv
	venv/bin/pip install -r docs/requirements.txt
	venv/bin/sphinx-build -a -n -b html -d $(SPHINX_BUILDDIR)/doctrees docs/source $(SPHINX_BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(SPHINX_BUILDDIR)/html/index.html"

remote-zip: clean virtualenv
	venv/bin/pip install boto boto3 paramiko
	venv/bin/python make_zip_on_aws.py
	venv/bin/python upload_to_s3.py

upload-to-s3:
	venv/bin/python upload_to_s3.py
