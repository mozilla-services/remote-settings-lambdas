from __future__ import print_function

import time
import os
import sys

from boto.ec2 import connect_to_region
from paramiko.client import SSHClient, AutoAddPolicy
from paramiko.sftp_client import SFTPClient
from paramiko.ssh_exception import NoValidConnectionsError

# http://docs.aws.amazon.com/lambda/latest/dg/current-supported-versions.html
AWS_REGION = "us-west-2"
AMI_ID = "ami-f0091d91"
KEY_PAIR = "loads"
SECURITY_GROUP = "loads"
INSTANCE_TYPE = "t2.micro"
INSTANCE_NAME = "amo2kinto-lambda-zip-builder"
INSTANCE_PROJECT = "amo2kinto-lambda"

# 1. Connect on the AWS region
print("Connecting to %s" % AWS_REGION)
conn = connect_to_region(AWS_REGION, is_secure=True)

# 2. Create a Amazon Lambda AMI EC2 instance
print("Starting an new instance of %s" % AMI_ID)
reservations = conn.run_instances(AMI_ID,
                                  min_count=1, max_count=1,
                                  key_name=KEY_PAIR,
                                  security_groups=[SECURITY_GROUP],
                                  instance_type=INSTANCE_TYPE)

instance = reservations.instances[0]

# 3. Tag the instance
conn.create_tags([instance.id], {
    "Name": INSTANCE_NAME,
    "Projects": INSTANCE_PROJECT,
})
print("Instance Name:", "amo2kinto-lambda-zip-builder")

# 4. Wait for running
while instance.state != "running":
    print("\rInstance state: %s" % instance.state, end="")
    sys.stdout.flush()
    time.sleep(10)
    instance.update()

print("\rInstance state: %s" % instance.state)
print("Instance IP:", instance.ip_address)

# 5. Connect to the instance
client = SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(AutoAddPolicy())

connected = False
while not connected:
    try:
        client.connect(instance.ip_address,
                       username="ec2-user",
                       key_filename=os.path.expanduser("~/.ssh/loads.pem"))
    except NoValidConnectionsError:
        print("\rSSH connection not yet available", end="")
        time.sleep(10)
        pass
    else:
        print()
        connected = True

print("\rSSH connection now sucessfully established.")

# 6. Install dependencies
print("Installing dependencies...")
stdin, stdout, stderr = client.exec_command(
    'sudo yum install -y '
    'git gcc '
    'libxml2-devel '
    'libxslt-devel '
    'libffi-devel '
    'openssl-devel ',  get_pty=True)
print(stdout.read())
print(stderr.read(), file=sys.stderr)

# 7. Clone amo2kinto-lambda
print("Cloning git repository...")
stdin, stdout, stderr = client.exec_command(
    'git clone https://github.com/mozilla-services/amo2kinto-lambda.git')

print(stdout.read())
print(stderr.read(), file=sys.stderr)

# 8. Create the zip file
print("Creating the zip file...")
stdin, stdout, stderr = client.exec_command(
    'cd amo2kinto-lambda; make zip')

print(stdout.read())
print(stderr.read(), file=sys.stderr)

# 9. Download the zip file
print("Downloading the zip file...")
sftp_client = SFTPClient.from_transport(client.get_transport())
sftp_client.get("amo2kinto-lambda/lambda.zip", "ami-built-lambda.zip")
sftp_client.close()

client.close()

# 10. Remote instance
conn.terminate_instances(instance.id)
