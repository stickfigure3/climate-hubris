import os

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")

import boto3
import pytest
from moto import mock_aws

from app.store import Store, create_table


@pytest.fixture
def store():
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        yield Store(create_table(resource, "test-table"))
