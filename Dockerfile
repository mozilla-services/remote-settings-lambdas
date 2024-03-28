FROM python:3.12-slim
RUN apt-get update && apt-get install -y zip
WORKDIR /lambda

# Install the requirements.
ADD requirements.txt /tmp/
RUN pip install -U pip && \
    pip install --disable-pip-version-check --quiet --target /lambda -r /tmp/requirements.txt

# Add your source code
ADD *.py /lambda/
RUN mkdir /lambda/commands
ADD commands/*.py /lambda/commands/
RUN chmod -R ugo+rx /lambda

# compile the lot.
RUN python -m compileall -q /lambda

RUN zip --quiet -9r /lambda.zip .

# Add entrypoint
ENTRYPOINT ["./aws_lambda.py"]
CMD ["help"]
