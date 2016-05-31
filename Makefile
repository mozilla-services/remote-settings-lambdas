SPHINX_BUILDDIR = docs/build

AMO_BLOCKLIST_UI_SCHEMA = "https://raw.githubusercontent.com/mozilla-services/amo-blocklist-ui/master/amo-blocklist.json"

clean:
	rm -fr venv lambda.zip

virtualenv:
	virtualenv venv
	venv/bin/pip install -r requirements.pip

zip: clean virtualenv
	zip lambda.zip lambda.py schemas.json
	cd venv/lib/python2.7/site-packages/; zip -r ../../../../lambda.zip *

update-schemas:
	wget -O schemas.json $(AMO_BLOCKLIST_UI_SCHEMA)

docs: virtualenv
	venv/bin/pip install -r docs/requirements.txt
	venv/bin/sphinx-build -a -n -b html -d $(SPHINX_BUILDDIR)/doctrees docs/source $(SPHINX_BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(SPHINX_BUILDDIR)/html/index.html"
