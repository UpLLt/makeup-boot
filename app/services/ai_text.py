"""AI 文本生成工具：调用 OpenAI chat-completions，降级用模板."""
import sys
import io
from typing import Optional
import httpx
import random

from app.config import get_settings

# 修复中文乱码：确保 stdout 使用 UTF-8 编码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

settings = get_settings()

# 调试：打印配置加载情况
print(f"[AI Config] API Key configured: {bool(settings.openai_api_key)}")
print(f"[AI Config] API Key length: {len(settings.openai_api_key) if settings.openai_api_key else 0}")
print(f"[AI Config] Model: {settings.openai_model}")
print(f"[AI Config] Base URL: {settings.openai_base_url}")


def generate_text(prompt: str, max_tokens: int = 80, temperature: float = 0.7) -> str:
    """使用 OpenAI chat-completions 生成文本；失败则从内置候选随机返回，避免回显原提示."""
    # 重新获取配置（避免缓存问题）
    current_settings = get_settings()
    print(f"[AI] Checking config: API Key exists={bool(current_settings.openai_api_key)}, length={len(current_settings.openai_api_key) if current_settings.openai_api_key else 0}")
    print(f"[AI] Model: {current_settings.openai_model}, Base URL: {current_settings.openai_base_url}")
    
    if not current_settings.openai_api_key or current_settings.openai_api_key.strip() == "":
        print(f"[AI] ERROR: No API key configured! Please create .env file with OPENAI_API_KEY")
        print(f"[AI] Using fallback signature")
        # fallback：避免直接返回 prompt，用内置签名池随机取（英文）
        fallback_signatures = [
            "Beauty enthusiast exploring new looks every day ✨",
            "Makeup lover sharing daily inspiration and tips 💄",
            "Colorful soul expressing myself through makeup 🎨",
            "Gentle yet vibrant, making life beautiful and fun 🌸",
            "Light makeup lover, balancing natural and elegant ✨",
            "Style explorer, every makeup is a small adventure 🚀",
            "Keeping smiles and curiosity, brightening daily life 😊",
            "Love both fresh and bold looks, colors tell my mood 🌈",
        ]
        return random.choice(fallback_signatures)
    
    try:
        url = f"{current_settings.openai_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {current_settings.openai_api_key}"}
        body = {
            "model": current_settings.openai_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        print(f"[AI] ===== Starting OpenAI API Call =====")
        print(f"[AI] Request URL: {url}")
        print(f"[AI] Request headers: Authorization=Bearer {current_settings.openai_api_key[:20]}...")
        print(f"[AI] Request body: {body}")
        resp = httpx.post(
            url,
            json=body,
            headers=headers,
            timeout=30,
        )
        print(f"[AI] Response status: {resp.status_code}")
        print(f"[AI] Response headers: {dict(resp.headers)}")
        data = resp.json()
        print(f"[AI] Response body: {data}")
        resp.raise_for_status()
        choices = data.get("choices")
        if choices:
            content: Optional[str] = choices[0].get("message", {}).get("content")
            if content:
                result = content.strip()
                print(f"[AI] Success: generated text={result}")
                return result
        print(f"[AI] No content in response: {data}")
    except httpx.HTTPStatusError as exc:
        print(f"[AI] HTTP error: status={exc.response.status_code}, response={exc.response.text}")
    except httpx.RequestError as exc:
        print(f"[AI] Request error: {exc}")
    except Exception as exc:
        print(f"[AI] Unexpected error: {type(exc).__name__}: {exc}")
        import traceback
        print(f"[AI] Traceback: {traceback.format_exc()}")
    # fallback：避免直接返回 prompt，用内置签名池随机取（英文）
    fallback_signatures = [
        "Beauty enthusiast exploring new looks every day ✨",
        "Makeup lover sharing daily inspiration and tips 💄",
        "Colorful soul expressing myself through makeup 🎨",
        "Gentle yet vibrant, making life beautiful and fun 🌸",
        "Light makeup lover, balancing natural and elegant ✨",
        "Style explorer, every makeup is a small adventure 🚀",
        "Keeping smiles and curiosity, brightening daily life 😊",
        "Love both fresh and bold looks, colors tell my mood 🌈",
    ]
    return random.choice(fallback_signatures)

