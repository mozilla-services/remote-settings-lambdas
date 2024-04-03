FROM python:3.12-slim

WORKDIR /lambda

# Install the requirements.
ADD requirements.txt /tmp/
RUN pip install -U pip && \
    pip install --disable-pip-version-check --quiet -r /tmp/requirements.txt

# Add your source code
ADD *.py /lambda/
RUN mkdir /lambda/commands
ADD commands/*.py /lambda/commands/

# Add entrypoint
ENTRYPOINT ["./aws_lambda.py"]
CMD ["help"]
