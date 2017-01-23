# amo2kinto Lambda

Use this script to generate a zip for Amazon Lambda:

    make clean virtualenv zip upload-to-s3

Or if you want to build it on a Lambda instance:

    make remote-zip

You must run this script on a linux x86_64 arch, the same as Amazon Lambda.
