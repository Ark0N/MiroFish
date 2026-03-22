"""
LLM客户端封装
支持 OpenAI 格式和 Anthropic 原生 API
"""

import json
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config


def _is_anthropic_key(api_key: str) -> bool:
    """Check if the API key is an Anthropic key."""
    return api_key.startswith("sk-ant-")


class LLMClient:
    """LLM客户端 - 自动检测 Anthropic key 并使用原生 SDK"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")

        self._use_anthropic = _is_anthropic_key(self.api_key)

        if self._use_anthropic:
            import anthropic
            anthropic_kwargs = {"api_key": self.api_key}
            if self.base_url and "openai" not in self.base_url.lower():
                anthropic_kwargs["base_url"] = self.base_url
            self.anthropic_client = anthropic.Anthropic(**anthropic_kwargs)
            self.client = None
        else:
            self.anthropic_client = None
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        发送聊天请求

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式（如JSON模式）

        Returns:
            模型响应文本
        """
        if self._use_anthropic:
            content = self._chat_anthropic(messages, temperature, max_tokens, response_format)
        else:
            content = self._chat_openai(messages, temperature, max_tokens, response_format)

        # 部分模型会在content中包含<think>思考内容，需要移除
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content

    def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict]
    ) -> str:
        """OpenAI SDK path"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _chat_anthropic(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict]
    ) -> str:
        """Anthropic native SDK path"""
        # Separate system message from user/assistant messages
        system_text = ""
        non_system_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text += msg["content"] + "\n"
            else:
                non_system_messages.append(msg)

        # If JSON format requested, add instruction to system prompt
        if response_format and response_format.get("type") == "json_object":
            json_instruction = "\n\nIMPORTANT: You must respond with valid JSON only. No markdown, no code blocks, no extra text."
            system_text = (system_text.rstrip() + json_instruction) if system_text else json_instruction.strip()

        kwargs = {
            "model": self.model,
            "messages": non_system_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_text.strip():
            kwargs["system"] = system_text.strip()

        response = self.anthropic_client.messages.create(**kwargs)
        return response.content[0].text

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            解析后的JSON对象
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # 清理markdown代码块标记
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"LLM返回的JSON格式无效: {cleaned_response}")
