import json
from django.test import SimpleTestCase
from unittest.mock import patch, MagicMock
from config.secrets import get_secret


class GetSecretTests(SimpleTestCase):
    @patch("config.secrets.boto3.session.Session")
    def test_get_secret_returns_parsed_secret(self, fake_boto3_session):
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"username": "admin", "password": "12345"})
        }
        mock_session_instance = MagicMock()
        mock_session_instance.client.return_value = mock_client
        fake_boto3_session.return_value = mock_session_instance

        actual_result = get_secret("fake-secret", region_name="us-east-1")

        self.assertEqual(actual_result, {"username": "admin", "password": "12345"})
        fake_boto3_session.assert_called_once()
        mock_session_instance.client.assert_called_once_with(
            service_name="secretsmanager", region_name="us-east-1"
        )
        mock_client.get_secret_value.assert_called_once_with(SecretId="fake-secret")
