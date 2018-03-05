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
- [Click here][bugzilla-stage-link] to open a ticket to get it deployed to stage and [here][bugzilla-prod-link] to prod

[bugzilla-stage-link]: https://bugzilla.mozilla.org/enter_bug.cgi?comment=Please%20upgrade%20the%20lambda%20functions%20to%20use%20the%20last%20release%20of%20amo2kinto-lambda.%0D%0A%0D%0A%5BInsert%20a%20short%20description%20of%20the%20changes%20here.%5D%0D%0A%0D%0Ahttps%3A%2F%2Fgithub.com%2Fmozilla-services%2Famo2kinto-lambda%2Freleases%2Ftag%2FX.Y.Z%0D%0A%0D%0AThanks%21&component=Operations%3A%20Storage&product=Cloud%20Services&qa_contact=chartjes%40mozilla.com&short_desc=Please%20deploy%20amo2kinto-lambda-X.Y.Z%20lambda%20function%20to%20STAGE

[bugzilla-prod-link]: https://bugzilla.mozilla.org/enter_bug.cgi?comment=Please%20upgrade%20the%20lambda%20functions%20to%20use%20the%20last%20release%20of%20amo2kinto-lambda.%0D%0A%0D%0A%5BInsert%20a%20short%20description%20of%20the%20changes%20here.%5D%0D%0A%0D%0Ahttps%3A%2F%2Fgithub.com%2Fmozilla-services%2Famo2kinto-lambda%2Freleases%2Ftag%2FX.Y.Z%0D%0A%0D%0AThanks%21&component=Operations%3A%20Storage&product=Cloud%20Services&qa_contact=chartjes%40mozilla.com&short_desc=Please%20deploy%20amo2kinto-lambda-X.Y.Z%20lambda%20function%20to%20PROD
