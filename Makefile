SPHINX_BUILDDIR = docs/build

clean:
	rm -fr venv lambda.zip

virtualenv:
	virtualenv venv --python=python3.6
	venv/bin/pip install -r requirements.pip -c requirements.txt

zip:
	docker build -t amo2kinto-lambda .
	docker cp `docker create amo2kinto-lambda /bin/true`:/lambda.zip lambda.zip

docs: virtualenv
	venv/bin/pip install -r docs/requirements.txt
	venv/bin/sphinx-build -a -n -b html -d $(SPHINX_BUILDDIR)/doctrees docs/source $(SPHINX_BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(SPHINX_BUILDDIR)/html/index.html"
