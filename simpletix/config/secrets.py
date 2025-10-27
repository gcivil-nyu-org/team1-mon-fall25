import boto3
import json


def get_secret(secret_name: str, region_name: str = "us-east-1") -> dict:
    """
    Retrieves the given secret from AWS Secrets Manager

    :param secret_name str: the name of the secret to get
    :param region_name: the name of the AWS region, defaults to us-east-1
    :return dict: {secret_name: secret}
    """
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])
