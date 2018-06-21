FROM python:3.6
RUN apt-get update && apt-get install -y zip
WORKDIR /lambda

# Add the requiremts
ADD requirements.pip requirements.txt /tmp/
RUN pip install --quiet -t /lambda -r /tmp/requirements.pip -c /tmp/requirements.txt && \
    find /lambda -type d | xargs chmod ugo+rx && \
    find /lambda -type f | xargs chmod ugo+r

# Add your source code
ADD aws_lambda.py /lambda/
RUN find /lambda -type d | xargs chmod ugo+rx && \
    find /lambda -type f | xargs chmod ugo+r

# compile the lot.
RUN python -m compileall -q /lambda

RUN zip --quiet -9r /lambda.zip .
