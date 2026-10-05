"""Deterministic provider for tests and evals. No network."""

import time

from app.ai.gateway import ModelRequest, ProviderError, ProviderResult


class FakeProvider:
    """Echoes the last message. Tokens are counted by whitespace.

    `fail_times`: the first N calls raise ProviderError (use `fail_times=2` to exhaust the retry).
    `delay_s`: sleep before answering, to exercise the gateway timeout.
    `calls`: number of times `complete` was invoked.
    """

    def __init__(self, *, fail_times: int = 0, delay_s: float = 0.0) -> None:
        self.fail_times = fail_times
        self.delay_s = delay_s
        self.calls = 0

    def complete(self, req: ModelRequest) -> ProviderResult:
        self.calls += 1
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.calls <= self.fail_times:
            raise ProviderError("fake provider failure")
        text = req.messages[-1].content if req.messages else ""
        return ProviderResult(
            text=text,
            model=req.model,
            input_tokens=sum(len(m.content.split()) for m in req.messages),
            output_tokens=len(text.split()),
        )
