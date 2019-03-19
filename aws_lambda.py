#!/usr/bin/env python
import glob
import importlib
import os
import sys

import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
from decouple import config

SENTRY_DSN = config("SENTRY_DSN", default=None)

if SENTRY_DSN:
    # Note! If you don't do `sentry_sdk.init(DSN)` it will still work
    # to do things like calling `sentry_sdk.capture_exception(exception)`
    # It just means it's a noop.
    sentry_sdk.init(SENTRY_DSN, integrations=[AwsLambdaIntegration()])


def help_(**kwargs):
    """Show this help.
    """

    def white_bold(s):
        return f"\033[1m\x1B[37m{s}\033[0;0m"

    entrypoints = [
        os.path.splitext(os.path.basename(f))[0]
        for f in glob.glob("./commands/[a-z]*.py")
    ]
    commands = [
        getattr(importlib.import_module(f"commands.{entrypoint}"), entrypoint)
        for entrypoint in entrypoints
    ]
    func_listed = "\n - ".join(
        [f"{white_bold(f.__name__)}: {f.__doc__}" for f in commands]
    )
    print(
        f"""
Remote Settings lambdas.

Available commands:

 - {func_listed}
    """
    )


def run(command):
    event = {"server": os.getenv("SERVER", "http://localhost:8888/v1")}
    context = {"sentry_sdk": sentry_sdk}
    # Note! If the sentry_sdk was initialized with
    # the AwsLambdaIntegration integration, it is now ready to automatically
    # capture all and any unexpected exceptions.
    # See https://docs.sentry.io/platforms/python/aws_lambda/
    command(event, context)


def main(*args):
    # Run the function specified in CLI arg.
    #
    # $ AUTH=user:pass python aws_lambda.py refresh_signature
    #

    if not args or args[0] in ("help", "--help"):
        help_()
        return
    entrypoint = args[0]
    try:
        mod = importlib.import_module(f"commands.{entrypoint}")
        command = getattr(mod, entrypoint)
    except (ImportError, ModuleNotFoundError):
        print(f"Unknown function {entrypoint!r}", file=sys.stderr)
        help_()
        return 1
    run(command)


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
