"""Reads encrypted values from AWS Systems Manager Parameter Store."""

import boto3


def read_secure_string(name: str) -> str:
    response = boto3.client("ssm").get_parameter(Name=name, WithDecryption=True)
    return response["Parameter"]["Value"]
