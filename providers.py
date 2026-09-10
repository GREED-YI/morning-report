"""어느 AI 모델을 쓸지 고르는 부분.

카드 문장을 만드는 일은 모델 하나에 묶여 있지 않다. 이 파일이 그 차이를 흡수해서,
바깥에서는 provider 이름만 바꾸면 다른 모델로 갈아탈 수 있게 한다.

  config.PROVIDER = "gemini"  ->  무료 한도 안에서 쓸 수 있다
  config.PROVIDER = "claude"  ->  크레딧을 충전해서 쓴다

두 모델 모두 "정해진 형식의 JSON 만 내놓아라" 는 기능을 지원한다.
그래서 응답을 받아 바로 딕셔너리로 쓸 수 있고, 형식이 틀어질 걱정이 없다.
"""

import json
import time
import urllib.error
import urllib.request

import config
import kakaolib

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 잠깐 붐벼서 나는 오류들. 조금 기다렸다 다시 부르면 대개 된다.
RETRYABLE = {429, 500, 502, 503, 504}


class ProviderError(RuntimeError):
    pass


def _env(key, hint):
    value = kakaolib.load_env().get(key, "")
    if not value:
        raise ProviderError(f".env 에 {key} 가 없습니다.\n  {hint}")
    return value


# ── Gemini ──────────────────────────────────────────────────────

def _gemini_once(system, user, schema, model, api_key, attempts=4):
    """모델 하나로 부른다. 붐벼서 나는 오류는 기다렸다 다시 부른다."""
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "temperature": 0.4,
        },
    }
    payload = json.dumps(body).encode("utf-8")

    for attempt in range(attempts):
        request = urllib.request.Request(
            GEMINI_URL.format(model=model),
            data=payload,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as res:
                data = json.loads(res.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            last = attempt == attempts - 1
            if e.code in RETRYABLE and not last:
                wait = 6 * (2 ** attempt)
                print(f"    서버가 붐빕니다 (HTTP {e.code}). {wait}초 뒤 다시 시도합니다.")
                time.sleep(wait)
                continue
            if e.code == 404:
                raise ProviderError(
                    f"'{model}' 모델을 찾을 수 없습니다. config.GEMINI_MODEL 을 확인하세요.\n  {detail}"
                )
            if e.code == 429:
                raise ProviderError(
                    f"Gemini 무료 한도를 넘었습니다. 내일 다시 시도하거나 "
                    f"config.GEMINI_MODEL 을 더 가벼운 모델로 바꾸세요.\n  {detail}"
                )
            raise ProviderError(f"Gemini 호출 실패 (HTTP {e.code}, {model})\n  {detail}")
        except urllib.error.URLError as e:
            if attempt == attempts - 1:
                raise ProviderError(f"Gemini 연결 실패: {e.reason}")
            time.sleep(6 * (2 ** attempt))

    try:
        return json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise ProviderError(f"Gemini 응답을 읽지 못했습니다: {e}\n  {str(data)[:400]}")


def _gemini(system, user, schema):
    api_key = _env(
        "GEMINI_API_KEY",
        "aistudio.google.com/apikey 에서 무료로 발급받아 넣으세요.",
    )
    try:
        return _gemini_once(system, user, schema, config.GEMINI_MODEL, api_key)
    except ProviderError as e:
        # 기본 모델이 계속 붐비면 예비 모델로 한 번 더 시도한다.
        # 아침 7시에 한 번뿐인 작업이라 실패하면 그날 브리핑이 통째로 없어진다.
        if not config.GEMINI_FALLBACK_MODEL or config.GEMINI_FALLBACK_MODEL == config.GEMINI_MODEL:
            raise
        print(f"    기본 모델이 계속 실패해 {config.GEMINI_FALLBACK_MODEL} 로 바꿔 시도합니다.")
        return _gemini_once(
            system, user, schema, config.GEMINI_FALLBACK_MODEL, api_key, attempts=2
        )


# ── Claude ──────────────────────────────────────────────────────

def _claude(system, user, schema):
    import anthropic

    client = anthropic.Anthropic(
        api_key=_env(
            "ANTHROPIC_API_KEY",
            "console.anthropic.com 에서 발급받아 넣으세요.",
        )
    )

    try:
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "format": {"type": "json_schema", "schema": schema},
                "effort": config.CLAUDE_EFFORT,
            },
            # 안전 분류기가 요청을 거절하면 자동으로 다른 모델로 넘긴다.
            # 무인으로 매일 도는 작업이라 멈추지 않게 해 두는 편이 낫다.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except Exception as e:
        raise ProviderError(f"Claude 호출 실패: {type(e).__name__} {e}")

    if response.stop_reason == "refusal":
        raise ProviderError("Claude 가 요청을 거절했습니다. 프롬프트를 확인하세요.")

    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ProviderError(f"Claude 응답을 읽지 못했습니다: {e}\n  {text[:400]}")


# ── 바깥에서 쓰는 함수 ──────────────────────────────────────────

BACKENDS = {"gemini": _gemini, "claude": _claude}


def generate_json(system, user, schema):
    """정해진 형식의 JSON 을 받아 딕셔너리로 돌려준다."""
    backend = BACKENDS.get(config.PROVIDER)
    if backend is None:
        raise ProviderError(
            f"config.PROVIDER 값 '{config.PROVIDER}' 를 모릅니다. "
            f"{' 또는 '.join(BACKENDS)} 중에서 고르세요."
        )
    return backend(system, user, schema)


def describe():
    """지금 어떤 모델을 쓰는지 한 줄로."""
    model = config.GEMINI_MODEL if config.PROVIDER == "gemini" else config.CLAUDE_MODEL
    return f"{config.PROVIDER} / {model}"
