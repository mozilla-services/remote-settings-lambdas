from __future__ import print_function
import time
from boto.ec2 import connect_to_region

# http://docs.aws.amazon.com/lambda/latest/dg/current-supported-versions.html
AWS_REGION = "us-west-2"
AMI_ID = "ami-f0091d91"
KEY_PAIR = "loads"
SECURITY_GROUP = "loads"
INSTANCE_TYPE = "t1.micro"

# 1. Connect on the AWS region
conn = connect_to_region(AWS_REGION, is_secure=True)

# 2. Create a Amazon Lambda AMI EC2 instance
reservations = conn.run_instances(AMI_ID,
                                  min_count=1, max_count=1,
                                  key_name=KEY_PAIR,
                                  security_groups=[SECURITY_GROUP],
                                  instance_type=INSTANCE_TYPE)

instance = reservations.instances[0]

# 3. Tag the instance
conn.create_tags([instance.id], {
    "Name": "amo2kinto-lambda-zip-builder",
    "Projects": "amo2kinto-lambda",
})

# 4. Wait for running
while instance.state != "running":
    print("\rInstance state: %s" % instance.state, ends="")
    time.sleep(10)
    instance.update()

print(instance.ip_address)
# 5. Create zip


# 6. Download zip

# 10. Remote instance
# conn.terminate_instances(instance.id)
