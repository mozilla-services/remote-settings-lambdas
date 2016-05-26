AMO_BLOCKLIST_UI_SCHEMA = "https://raw.githubusercontent.com/mozilla-services/amo-blocklist-ui/master/amo-blocklist.json"

clean:
	rm -fr venv lambda.zip

virtualenv:
	virtualenv venv
	venv/bin/pip install -r requirements.pip

zip:
	zip lambda.zip lambda.py schemas.json
	cd venv/lib/python2.7/site-packages/; zip -r ../../../../lambda.zip *

update-schemas:
	wget -O schemas.json $(AMO_BLOCKLIST_UI_SCHEMA)
