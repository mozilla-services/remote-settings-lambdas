FROM python:3.7-slim
RUN apt-get update && apt-get install -y zip
WORKDIR /lambda

# Install the requirements.
# Since we don't want to install the whole Pyramid ecosystem just to reuse its canonical
# serialization, install it with ``--no-deps``.
ADD requirements.txt constraints.txt /tmp/
RUN pip install --disable-pip-version-check --quiet --target /lambda -r /tmp/requirements.txt -c /tmp/constraints.txt && \
    pip install --disable-pip-version-check --quiet --target /lambda --no-deps kinto-signer -c /tmp/constraints.txt && \
    find /lambda -type d | xargs chmod ugo+rx && \
    find /lambda -type f | xargs chmod ugo+r

# Add your source code
ADD *.py /lambda/
RUN find /lambda -type d | xargs chmod ugo+rx && \
    find /lambda -type f | xargs chmod ugo+r

# compile the lot.
RUN python -m compileall -q /lambda

RUN zip --quiet -9r /lambda.zip .

# Add entrypoint
ENTRYPOINT ["./aws_lambda.py"]
CMD ["help"]
