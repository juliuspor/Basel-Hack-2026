"""Slot fingerprints in DynamoDB: one item per camera.

    {"camera_id": "cam-south-a", "fingerprints": {"1": 18311250231734132751}}
"""

from decimal import Decimal


class DynamoFingerprintStore:
    def __init__(self, dynamodb, table_name: str) -> None:
        """dynamodb is a boto3 DynamoDB service resource."""
        self._table = dynamodb.Table(table_name)

    def get(self, camera_id: str) -> dict[int, int]:
        item = self._table.get_item(Key={"camera_id": camera_id}).get("Item") or {}
        return {int(number): int(value) for number, value in item.get("fingerprints", {}).items()}

    def put(self, camera_id: str, fingerprints: dict[int, int]) -> None:
        self._table.put_item(Item={
            "camera_id": camera_id,
            "fingerprints": {str(number): Decimal(value) for number, value in fingerprints.items()},
        })
