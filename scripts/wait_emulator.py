"""Wait until the AWS emulator answers, then report whether the state backend exists."""
import os
import sys
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError

s3 = boto3.client("s3")
for _ in range(60):
    try:
        buckets = [b["Name"] for b in s3.list_buckets()["Buckets"]]
        break
    except (BotoCoreError, ClientError):
        time.sleep(1)
else:
    sys.exit("emulator did not answer in 60s at " + os.environ.get("AWS_ENDPOINT_URL", "?"))

# exit 0: backend bucket exists; exit 3: emulator is up but backend is missing
sys.exit(0 if sys.argv[1] in buckets else 3)
