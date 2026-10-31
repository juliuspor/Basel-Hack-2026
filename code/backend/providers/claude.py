import base64
import json
import os

from .base import from_answer, prompt, result_schema, tagged_jpeg


class ClaudeProvider:
    """Asks a small Claude vision model which numbered slots hold a bike."""

    def __init__(self, model=None):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("VISION_MODEL") or os.environ.get("CLAUDE_MODEL",
                                                                              "claude-haiku-5-5")
        self.name = self.model

    def analyze(self, image, camera):
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": result_schema(camera)},
            },
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg",
                        "data": base64.standard_b64encode(tagged_jpeg(image, camera)).decode()}},
                    {"type": "text", "text": prompt(camera)},
                ],
            }],
        )
        if response.stop_reason != "end_turn":
            raise RuntimeError(f"model stopped with {response.stop_reason}")
        answer = json.loads(next(b.text for b in response.content if b.type == "text"))
        return from_answer(answer, camera, {"usage": {"input": response.usage.input_tokens,
                                                      "output": response.usage.output_tokens}})
