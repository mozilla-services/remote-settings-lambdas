from kinto2xml.importer import main as importer

JSON2KINTO_ARGS = ['server', 'amo-server', 'schema-file', 'auth',
                   'certificates-bucket', 'certificates-collection',
                   'gfx-bucket', 'gfx-collection',
                   'addons-bucket', 'addons-collection',
                   'plugins-bucket', 'plugins-collection',
                   'certificates', 'gfx', 'addons', 'plugins']


def main(event, context):
    """Event will contain the json2kinto parameters:
         - server: The kinto server to write data to.
                   (i.e: https://addons.mozilla.org/)
         - amo-server: The amo server to read blocklists data from.
                       (i.e: https://addons.mozilla.org/)
         - schema: The JSON schema collection file to read schema from.
                   (i.e: schemas.json)
    """

    args = []

    for key, value in event.values():
        if key in JSON2KINTO_ARGS:
            args.append('--' + key)
            args.append(value)

    importer(args)
