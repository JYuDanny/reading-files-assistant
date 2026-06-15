import os
import base64
import json
import mimetypes
import httpx

from backend.config import settings


def image_to_base64(image_source: str) -> str:
    if image_source.startswith(("http://", "https://")):
        with httpx.Client(proxy=None, timeout=30) as c:
            resp = c.get(image_source)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/png")
            raw_bytes = resp.content
    else:
        mime, _ = mimetypes.guess_type(image_source)
        content_type = mime or "image/png"
        with open(image_source, "rb") as f:
            raw_bytes = f.read()

    b64 = base64.b64encode(raw_bytes).decode("utf-8")
    return f"data:{content_type};base64,{b64}"


class LLMClient:
    def __init__(self):
        os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")
        os.environ.setdefault("no_proxy", "localhost,127.0.0.1,::1")
        self.base_url = settings.lm_studio_base_url.rstrip("/")
        self.model = settings.lm_studio_model
        self.timeout = settings.llm_timeout_seconds

    def _build_request(self, messages: list, max_tokens: int = None,
                       temperature: float = 0.7, stream: bool = False) -> dict:
        if max_tokens is None:
            max_tokens = settings.llm_max_tokens
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

    async def chat(self, messages: list, max_tokens: int = None,
                   temperature: float = 0.7) -> str:
        async with httpx.AsyncClient(proxy=None, timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=self._build_request(messages, max_tokens, temperature),
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError(f"LM Studio returned no choices: {data}")
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if not content:
                raise RuntimeError(f"LM Studio returned empty content: {data}")
            return content

    async def chat_stream(self, messages: list, max_tokens: int = None,
                          temperature: float = 0.7):
        async with httpx.AsyncClient(proxy=None, timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=self._build_request(messages, max_tokens, temperature, stream=True),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            yield delta["content"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(proxy=None, timeout=5) as client:
                resp = await client.get(f"{self.base_url}/models")
                return resp.status_code == 200
        except Exception:
            return False

    def warmup(self):
        import asyncio

        async def _warmup():
            await self.chat([{"role": "user", "content": "ping"}], max_tokens=1)

        try:
            asyncio.get_event_loop().run_until_complete(_warmup())
        except RuntimeError:
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.get_event_loop().run_until_complete(_warmup())


llm_client = LLMClient()
