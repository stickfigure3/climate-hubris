"""DynamoDB access.

Single-table design. Every item is addressed by (pk, sk):

    pk                 sk               payload
    PIOMAS_MONTHLY     "1979"           values: 12 monthly volumes (10^3 km^3)
    PIOMAS_DAILY       "1979"           values: 365 daily volumes (10^3 km^3)
    OHC_700 / OHC_2000 "1955"           value, se (ZJ)
    RAIN#<region>      "2025-06"        total_mm, days
    FINDING#<region>   "<date>#<hash>"  one agent finding
    SEEN               "<hash>"         documents the agent already processed (TTL)
    IMD                "latest"         state-wise rainfall rows, when reachable
    META               "<dataset>"      freshness record

Each dataset is a single partition, so a read is one Query.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from .config import settings


def _to_dynamo(value: Any) -> Any:
    # boto3 rejects floats; round-tripping through JSON converts them to Decimal.
    return json.loads(json.dumps(value), parse_float=Decimal)


def _from_dynamo(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: _from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    return value


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    def __init__(self, table=None):
        if table is None:
            resource = boto3.resource(
                "dynamodb",
                region_name=settings.aws_region,
                endpoint_url=settings.dynamodb_endpoint,
            )
            table = resource.Table(settings.table_name)
        self.table = table

    def put(self, pk: str, sk: str, **attrs: Any) -> None:
        self.table.put_item(Item={"pk": pk, "sk": sk, **_to_dynamo(attrs)})

    def put_many(self, pk: str, items: dict[str, dict[str, Any]]) -> None:
        with self.table.batch_writer() as batch:
            for sk, attrs in items.items():
                batch.put_item(Item={"pk": pk, "sk": sk, **_to_dynamo(attrs)})

    def get(self, pk: str, sk: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key={"pk": pk, "sk": sk}).get("Item")
        return _from_dynamo(item) if item else None

    def query(self, pk: str, sk_from: str | None = None) -> list[dict[str, Any]]:
        """All items in a partition, ascending by sk, optionally from sk_from onwards."""
        condition = Key("pk").eq(pk)
        if sk_from is not None:
            condition = condition & Key("sk").gte(sk_from)
        kwargs: dict[str, Any] = {"KeyConditionExpression": condition}
        items: list[dict[str, Any]] = []
        while True:
            page = self.table.query(**kwargs)
            items.extend(page["Items"])
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        return [_from_dynamo(i) for i in items]

    def put_meta(self, dataset: str, **info: Any) -> None:
        self.put("META", dataset, last_ingested_at=utcnow_iso(), **info)

    def get_meta(self) -> dict[str, dict[str, Any]]:
        return {i["sk"]: {k: v for k, v in i.items() if k not in ("pk", "sk")} for i in self.query("META")}


def create_table(resource=None, table_name: str | None = None):
    """Create the table. Used by local dev and tests; AWS creates it via CloudFormation."""
    resource = resource or boto3.resource(
        "dynamodb", region_name=settings.aws_region, endpoint_url=settings.dynamodb_endpoint
    )
    name = table_name or settings.table_name
    existing = [t.name for t in resource.tables.all()]
    if name in existing:
        return resource.Table(name)
    table = resource.create_table(
        TableName=name,
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table
