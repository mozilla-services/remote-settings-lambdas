# amo2kinto Lambda

Use this script to generate a zip for Amazon Lambda:

    make clean virtualenv zip upload-to-s3

Or if you want to build it on a Lambda instance:

    make remote-zip

You must run this script on a linux x86_64 arch, the same as Amazon Lambda.

This now requires Python 3.6

# Releasing

- `git checkout -b prepare-x.y.z`
- `make zip`
- `git add requirements.txt; git commit`
- Open a PR
- Wait for approval
- `git checkout master`
- `git merge --no-ff prepare-x.y.z`
- `git tag x.y.z` (with `-a` if you are feeling fiesty)
- `git push origin master; git push --tags origin`
- Go to releases page on Github and create a release for x.y.z
- Attach the lambda.zip file from earlier (renaming it
  `amo2kinto-lambda-x.y.z.zip`).  If you don't have the lambda.zip
  file from earlier, you can rebuild it by changing `requirements.pip`
  in the Makefile to `requirements.txt` and rerunning `make zip`
