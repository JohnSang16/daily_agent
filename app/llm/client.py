from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LlmResult:
    text: str
    input_tokens: int
    output_tokens: int


class LlmClient(Protocol):
    """Prompt in, text out. No tools. Real client arrives with an API key and spec 06."""

    def complete(self, prompt: str) -> LlmResult: ...
