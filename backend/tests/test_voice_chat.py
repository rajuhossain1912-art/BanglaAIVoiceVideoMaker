import io
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from backend import app as video_app


class VoiceChatTests(unittest.TestCase):
    def test_chat_reuses_existing_cloudflare_token_and_returns_reply(self):
        response = io.BytesIO(json.dumps({
            "result": {"response": "আপনাকে কীভাবে সাহায্য করতে পারি?"}
        }).encode("utf-8"))
        response.__enter__ = lambda: response
        response.__exit__ = lambda *args: False
        with patch.dict("os.environ", {
            "CLOUDFLARE_ACCOUNT_ID": "test-account",
            "CLOUDFLARE_AI_API_TOKEN": "existing-token",
            "CLOUDFLARE_AI_MODEL": "@cf/meta/llama-3.2-3b-instruct",
        }), patch.object(video_app.urllib.request, "urlopen", return_value=response) as request:
            result = video_app.chat({"messages": [{"role": "user", "content": "তুমি কী করতে পারো?"}]})
        self.assertEqual(result["reply"], "আপনাকে কীভাবে সাহায্য করতে পারি?")
        sent = json.loads(request.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(sent["messages"][-1]["content"], "তুমি কী করতে পারো?")
        self.assertEqual(request.call_args.args[0].get_header("Authorization"), "Bearer existing-token")

    def test_chat_rejects_missing_messages(self):
        with self.assertRaises(HTTPException) as error:
            video_app.chat({"messages": []})
        self.assertEqual(error.exception.status_code, 400)

    def test_chat_rejects_missing_existing_token_without_calling_provider(self):
        with patch.dict("os.environ", {}, clear=True), patch.object(video_app.urllib.request, "urlopen") as request:
            with self.assertRaises(HTTPException) as error:
                video_app.chat({"messages": [{"role": "user", "content": "হ্যালো"}]})
        self.assertEqual(error.exception.status_code, 503)
        request.assert_not_called()

    def test_chat_rejects_oversized_message(self):
        with self.assertRaises(HTTPException) as error:
            video_app.chat({"messages": [{"role": "user", "content": "ক" * 3001}]})
        self.assertEqual(error.exception.status_code, 413)


if __name__ == "__main__":
    unittest.main()
