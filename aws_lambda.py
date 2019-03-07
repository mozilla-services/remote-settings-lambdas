#!/usr/bin/env python
import glob
import importlib
import os
import sys


def help(**kwargs):
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


if __name__ == "__main__":
    # Run the function specified in CLI arg.
    #
    # $ AUTH=user:pass python aws_lambda.py refresh_signature
    #
    event = {"server": os.getenv("SERVER", "http://localhost:8888/v1")}
    context = None

    entrypoint = sys.argv[1]
    if entrypoint == "help":
        help()
        sys.exit(0)

    try:
        mod = importlib.import_module(f"commands.{entrypoint}")
        getattr(mod, entrypoint)(event, context)
    except (ImportError, ModuleNotFoundError):
        print(f"Unknown function '{entrypoint}'")
        help()
        sys.exit(1)
