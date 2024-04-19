import unittest
from unittest.mock import patch, MagicMock
from app import app, process_initial_evaluation, encrypt_data, decrypt_data


class TestGPTAPIInteraction(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

    def tearDown(self):
        self.app_context.pop()

    @patch("app.client.chat.completions.create")
    def test_api_call_success(self, mock_completions):
        # Setup the mock to return a structured response expected by your function
        mock_completions.return_value = MagicMock(
            choices=[
                {
                    "message": {
                        "content": "Condition Name: Flu. Urgency Level: Low. Justification: Common symptoms match."
                    }
                }
            ]
        )
        with self.app.test_request_context():
            response = process_initial_evaluation(1, "Flu symptoms")
            self.assertIsNone(
                response
            )  

    @patch("app.client.chat.completions.create")
    def test_api_call_failure(self, mock_completions):
        mock_completions.side_effect = Exception("API Error")
        with self.app.test_request_context():
            response = process_initial_evaluation(1, "Flu symptoms")
            # Verify that response is None due to the exception
            self.assertIsNone(response)

    @patch("app.client.chat.completions.create")
    def test_api_rate_limiting(self, mock_completions):
        # Setup the mock to simulate a failure followed by a success
        mock_completions.side_effect = [
            Exception("Rate limited"),
            MagicMock(
                choices=[
                    {
                        "message": {
                            "content": "Condition Name: Flu. Urgency Level: Low. Justification: Common symptoms match."
                        }
                    }
                ]
            ),
        ]
        with self.app.test_request_context():
            response = process_initial_evaluation(1, "Flu symptoms", attempt=1)
            # Check if the retry was successful
            self.assertIsNone(
                response
            )  

    @patch("app.encrypt_data")
    @patch("app.decrypt_data")
    def test_encryption_and_decryption(self, mock_decrypt, mock_encrypt):
        mock_encrypt.side_effect = lambda x: f"encrypted_{x}"
        mock_decrypt.side_effect = lambda x: x.replace("encrypted_", "")
        encrypted = encrypt_data("test data")
        decrypted = decrypt_data(encrypted)
        self.assertEqual(decrypted, "test data")


if __name__ == "__main__":
    unittest.main()
