"""카카오 API 공통 함수. 표준 라이브러리만 사용한다 (pip 설치 불필요)."""

import json
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

ENV_PATH = Path(__file__).parent / ".env"

KAUTH = "https://kauth.kakao.com"
KAPI = "https://kapi.kakao.com"


# ── .env 읽기/쓰기 ──────────────────────────────────────────────

def load_env():
    """.env 파일을 딕셔너리로 읽는다."""
    if not ENV_PATH.exists():
        raise SystemExit(
            ".env 파일이 없습니다.\n"
            "  .env.example 파일을 복사해서 .env 로 이름을 바꾸고,\n"
            "  카카오 REST API 키를 채운 뒤 다시 실행하세요."
        )
    env = {}
    # utf-8-sig 로 읽으면 메모장 같은 편집기가 파일 앞에 붙이는 BOM 이 걷힌다.
    for line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        # 값 안에 섞여 들어온 BOM 도 지운다. 눈에 안 보이는데 HTTP 헤더에 실리면
        # latin-1 인코딩 오류로 요청이 통째로 실패한다. 실제로 겪은 사고다.
        line = line.replace("﻿", "").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        # 값을 따옴표로 감싸도 동작하게 벗겨낸다
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key.strip()] = value
    return env


def save_env(updates):
    """.env 파일의 값을 갱신한다. 기존 주석과 순서는 그대로 둔다."""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"

    for key, value in remaining.items():
        lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def require(env, key, hint):
    value = env.get(key, "")
    if not value:
        raise SystemExit(f".env 의 {key} 값이 비어 있습니다.\n  {hint}")
    return value


# ── HTTP 요청 ───────────────────────────────────────────────────

def post(url, data, headers=None):
    """POST 요청을 보내고 JSON 응답을 돌려준다."""
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers or {}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"카카오 API 오류 (HTTP {e.code})\n  {detail}")
    except urllib.error.URLError as e:
        raise SystemExit(f"네트워크 연결 실패: {e.reason}")


# ── 토큰 ────────────────────────────────────────────────────────

def exchange_code(env, code, redirect_uri):
    """인가 코드를 액세스 토큰으로 교환한다."""
    data = {
        "grant_type": "authorization_code",
        "client_id": env["KAKAO_REST_API_KEY"],
        "redirect_uri": redirect_uri,
        "code": code,
    }
    if env.get("KAKAO_CLIENT_SECRET"):
        data["client_secret"] = env["KAKAO_CLIENT_SECRET"]
    return post(f"{KAUTH}/oauth/token", data)


def refresh(env):
    """리프레시 토큰으로 액세스 토큰을 새로 받는다."""
    data = {
        "grant_type": "refresh_token",
        "client_id": env["KAKAO_REST_API_KEY"],
        "refresh_token": require(
            env, "KAKAO_REFRESH_TOKEN", "먼저 step1_auth.py 를 실행하세요."
        ),
    }
    if env.get("KAKAO_CLIENT_SECRET"):
        data["client_secret"] = env["KAKAO_CLIENT_SECRET"]
    return post(f"{KAUTH}/oauth/token", data)


def store_tokens(token):
    """토큰 응답을 .env 에 저장한다. 토큰 값은 화면에 출력하지 않는다."""
    updates = {
        "KAKAO_ACCESS_TOKEN": token["access_token"],
        "KAKAO_TOKEN_EXPIRES_AT": str(int(time.time()) + token["expires_in"] - 60),
    }
    # 리프레시 토큰은 갱신 응답에 없을 때도 있다. 그때는 기존 값을 유지한다.
    if token.get("refresh_token"):
        updates["KAKAO_REFRESH_TOKEN"] = token["refresh_token"]
    save_env(updates)


def access_token(env):
    """유효한 액세스 토큰을 돌려준다. 만료됐으면 자동으로 갱신한다."""
    if not env.get("KAKAO_REFRESH_TOKEN"):
        raise SystemExit(
            "저장된 토큰이 없습니다.\n  step1_auth.py 를 먼저 실행해서 카카오 로그인을 마치세요."
        )

    expires_at = int(env.get("KAKAO_TOKEN_EXPIRES_AT") or 0)
    if env.get("KAKAO_ACCESS_TOKEN") and time.time() < expires_at:
        return env["KAKAO_ACCESS_TOKEN"]

    print("액세스 토큰이 만료되어 갱신합니다...")
    token = refresh(env)
    store_tokens(token)
    return token["access_token"]


# ── 메시지 발송 ─────────────────────────────────────────────────

def send_to_me(env, template):
    """나에게 보내기. template 은 카카오 메시지 템플릿 딕셔너리."""
    return post(
        f"{KAPI}/v2/api/talk/memo/default/send",
        {"template_object": json.dumps(template, ensure_ascii=False)},
        {"Authorization": f"Bearer {access_token(env)}"},
    )
