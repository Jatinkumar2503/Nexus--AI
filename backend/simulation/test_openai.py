rate 
import os
import sys
import unittest
from unittest.mock import patch

# Add backend directory to path if needed to run directly
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.openai_client import get_openai_client, get_openai_model

class TestOpenAIClient(unittest.TestCase):
    def setUp(self):
        # Reset internal global client cache before each test
        import services.openai_client
        services.openai_client._client = None

    @patch.dict(os.environ, {}, clear=True)
    def test_client_missing_key(self):
        with self.assertRaises(ValueError) as context:
            get_openai_client()
        self.assertIn("OpenAI API key is missing", str(context.exception))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-123", "OPENAI_BASE_URL": "http://mock-url"})
    def test_client_initialization(self):
        client = get_openai_client()
        self.assertEqual(client.api_key, "test-key-123")
        # OpenAI SDK normalizes base_url with a trailing slash
        self.assertEqual(str(client.base_url), "http://mock-url/")

    @patch.dict(os.environ, {"OPENAI_MODEL": "gpt-4o-mini"})
    def test_get_openai_model(self):
        model = get_openai_model()
        self.assertEqual(model, "gpt-4o-mini")

if __name__ == "__main__":
    unittest.main()
