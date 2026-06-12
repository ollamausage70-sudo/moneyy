import logging
import time
from typing import Optional

import google.genai as genai
from groq import Groq
from openai import OpenAI

import config

logger = logging.getLogger("agent.brain")


class LLMBrain:
    def __init__(self):
        self.providers = []
        self._setup_providers()

    def _setup_providers(self):
        if config.GEMINI_API_KEY:
            self.providers.append(GeminiProvider(config.GEMINI_API_KEY))
        if config.GROQ_API_KEY:
            self.providers.append(GroqProvider(config.GROQ_API_KEY))
        if config.GITHUB_TOKEN:
            self.providers.append(GitHubModelsProvider(config.GITHUB_TOKEN))
        if not self.providers:
            raise RuntimeError(
                "No LLM providers configured. "
                "Set GEMINI_API_KEY, GROQ_API_KEY, or GITHUB_TOKEN in environment variables."
            )

    def think(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        last_error = None
        for provider in self.providers:
            try:
                logger.info(f"Trying {provider.name}...")
                return provider.generate(prompt, system_prompt)
            except Exception as e:
                logger.warning(f"{provider.name} failed: {e}")
                last_error = e
                time.sleep(1)
        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    def decide(self, prompt: str) -> dict:
        result = self.think(
            prompt,
            system_prompt="You are AGENT007, an autonomous earning agent. "
            "Analyze the situation and decide the best action. "
            "Respond in JSON format with keys: 'decision', 'reason', 'confidence'.",
        )
        import json
        try:
            return json.loads(result.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError:
            return {"decision": result, "reason": "raw response", "confidence": 0.5}


class GeminiProvider:
    def __init__(self, api_key: str):
        self.name = "Gemini"
        self.client = genai.Client(api_key=api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        response = self.client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=(
                genai.types.GenerateContentConfig(system_instruction=system_prompt)
                if system_prompt
                else None
            ),
        )
        return response.text


class GroqProvider:
    def __init__(self, api_key: str):
        self.name = "Groq"
        self.client = Groq(api_key=api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
        )
        return response.choices[0].message.content


class GitHubModelsProvider:
    def __init__(self, token: str):
        self.name = "GitHub Models"
        self.client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=token,
        )

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
        )
        return response.choices[0].message.content
