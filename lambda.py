from __future__ import print_function
from tempfile import mkdtemp

from amo2kinto.generator import main as generator_main
from amo2kinto.importer import main as importer_main
from amo2kinto.verifier import main as verifier

JSON2KINTO_ARGS = ['server', 'auth', 'addons-server', 'schema-file', 'no-schema',
                   'certificates-bucket', 'certificates-collection',
                   'gfx-bucket', 'gfx-collection',
                   'addons-bucket', 'addons-collection',
                   'plugins-bucket', 'plugins-collection',
                   'certificates', 'gfx', 'addons', 'plugins']


def json2kinto(event, context):
    """Event will contain the json2kinto parameters:
         - server: The kinto server to write data to.
                   (i.e: https://kinto-writer.services.mozilla.com/)
         - amo-server: The amo server to read blocklists data from.
                       (i.e: https://addons.mozilla.org/)
         - schema: The JSON schema collection file to read schema from.
                   (i.e: schemas.json)
    """

    args = []

    for key, value in event.items():
        if key in JSON2KINTO_ARGS:
            args.append('--' + key)
            args.append(value)

    print("importer args", args)
    importer_main(args)


def xmlverifier(event, context):
    """xmlverifier takes local and remote parameter and validate that both
    are equals.

    """
    print("verifier args", event)
    response = verifier([event['local'], event['remote']])
    if response:
        raise Exception("There is a difference between: %r and %r" % (
            event['local'], event['remote']))


BLOCKPAGES_ARGS = ['server', 'bucket', 'addons-collection', 'plugins-collection']


def blockpages_generator(event, context):
    """Event will contain the blockpages_generator parameters:
         - server: The kinto server to write data to.
                   (i.e: https://kinto-writer.services.mozilla.com/)
         - s3bucket: S3 bucket to sync the files too.
         - bucket: The readonly public and signed bucket.
         - addons-collection: The add-ons collection name.
         - plugins-collection: The plugin collection name.
    """

    args = []
    s3uri = None

    for key, value in event.items():
        if key in BLOCKPAGES_ARGS:
            args.append('--' + key)
            args.append(value)
        elif key.lower() == 's3uri':
            s3uri = value

    args.append('--target-dir')
    args.append(mkdtemp())
    # if not s3uri:
    #     raise Exception('S3URI mandatory')

    print("Blocked pages generator args", args)
    generator_main(args)
    # sync_target_with_s3(os.path.abspath('results'), s3uri)
