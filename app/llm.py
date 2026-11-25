"""线上大模型客户端：统一封装 OpenAI 兼容的 /chat/completions 接口。

可在 DeepSeek、通义千问（DashScope 兼容模式）、文心一言（千帆 v2）等厂商间
切换，仅需更换接口地址、模型与密钥；业务规则与金额计算完全留在本地。
"""
from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .config import PROVIDER_PRESETS, Settings


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    # ------------------------------------------------------------------ 配置
    def config(self) -> dict:
        return (self.settings.data.get("llm") or {}).copy()

    def configured(self) -> bool:
        config = self.config()
        return bool(config.get("enabled") and config.get("base_url") and config.get("api_key"))

    def endpoint(self) -> str:
        base = (self.config().get("base_url") or "").strip().rstrip("/")
        if not base:
            raise LLMError("未配置线上模型接口地址")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"

    def status(self) -> dict:
        config = self.config()
        return {
            "configured": self.configured(),
            "enabled": bool(config.get("enabled")),
            "provider": config.get("provider") or "custom",
            "provider_label": PROVIDER_PRESETS.get(config.get("provider") or "custom", {}).get("label", "自定义"),
            "base_url": config.get("base_url") or "",
            "model": config.get("model") or "",
            "has_api_key": bool(config.get("api_key")),
        }

    # ------------------------------------------------------------------ 调用
    def chat_json(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 4000) -> dict:
        if not self.configured():
            raise LLMError("线上模型未启用或未配置密钥")
        config = self.config()
        payload = {
            "model": config.get("model") or "",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(config.get("temperature") or 0.1),
            "max_tokens": max_tokens,
            "stream": False,
        }
        if config.get("json_mode", True):
            payload["response_format"] = {"type": "json_object"}

        request = urllib.request.Request(
            self.endpoint(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.get('api_key')}",
            },
            method="POST",
        )
        timeout = float(config.get("timeout") or 60)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise LLMError(f"模型接口返回 HTTP {exc.code}：{detail}") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            raise LLMError(f"模型接口连接失败：{exc}") from exc

        try:
            data = json.loads(body)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"模型返回格式异常：{body[:300]}") from exc
        return parse_json_content(content)

    def test(self) -> dict:
        if not self.configured():
            return {"ok": False, "message": "线上模型未启用或未配置密钥，当前使用本地规则抽取兜底。"}
        try:
            data = self.chat_json(
                "你是接口连通性测试助手。只输出 JSON：{\"ok\": true}。",
                "请返回 {\"ok\": true}。",
                max_tokens=32,
            )
            return {"ok": True, "message": "线上模型连通正常。", "response": data}
        except LLMError as exc:
            return {"ok": False, "message": str(exc)}


def parse_json_content(content: str) -> dict:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except ValueError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except ValueError as exc:
            raise LLMError(f"模型返回的 JSON 无法解析：{exc}") from exc
    raise LLMError("模型未返回可解析的 JSON")
