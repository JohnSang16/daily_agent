"""Real LLM client. Prompt in, text out. Sends no tools, goes only through the guarded client."""

from app.llm.client import LlmResult

URL = "https://api.anthropic.com/v1/messages"


class AnthropicClient:
    def __init__(self, http, api_key: str, model: str, max_tokens: int = 400):
        self.http, self.api_key, self.model, self.max_tokens = http, api_key, model, max_tokens

    def complete(self, prompt: str) -> LlmResult:
        r = self.http.request(
            "anthropic",
            "POST",
            URL,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            json={
                "model": self.model,
                "max_tokens": self.max_tokens,
                "thinking": {
                    "type": "disabled"
                },  # a two sentence summary needs no hidden reasoning
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        j = r.json()
        if j.get("stop_reason") == "max_tokens":
            raise ValueError("response cut off")
        text = "".join(b.get("text", "") for b in j["content"] if b.get("type") == "text")
        return LlmResult(text.strip(), j["usage"]["input_tokens"], j["usage"]["output_tokens"])
