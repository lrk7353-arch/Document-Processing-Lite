import httpx
from typing import Dict, Any, List, Optional
from agent.config import settings

class DeepSeekClient:
    def __init__(self):
        self.api_key = settings.deepseek_api_key
        self.base_url = "https://api.deepseek.com"

    async def chat(self, messages: List[Dict[str, str]], model: str = "deepseek-chat", temperature: float = 0.3) -> Optional[str]:
        if not self.api_key:
            return None
        payload = {"model": model, "messages": messages, "temperature": temperature}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{self.base_url}/v1/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content")

    async def extract_fields(self, prompt: str, model: str = "deepseek-chat") -> Optional[Dict[str, Any]]:
        answer = await self.chat([{"role": "user", "content": prompt}], model=model)
        if not answer:
            return None
        # 尝试简单解析结构化字段，实际可用正则/JSON格式约束
        return {"raw": answer}

deepseek_client = DeepSeekClient()