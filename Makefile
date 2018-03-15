SPHINX_BUILDDIR = docs/build

clean:
	rm -fr venv lambda.zip

virtualenv:
	virtualenv venv --python=python3.6
	venv/bin/pip install -r requirements.pip

zip: clean virtualenv
	zip lambda.zip aws_lambda.py
	touch venv/lib/python3.6/site-packages/zope/__init__.py
	touch venv/lib/python3.6/site-packages/repoze/__init__.py
	cd venv/lib/python3.6/site-packages/; zip -r ../../../../lambda.zip *
	zip lambda.zip
	venv/bin/pip freeze > requirements.txt

docs: virtualenv
	venv/bin/pip install -r docs/requirements.txt
	venv/bin/sphinx-build -a -n -b html -d $(SPHINX_BUILDDIR)/doctrees docs/source $(SPHINX_BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(SPHINX_BUILDDIR)/html/index.html"
