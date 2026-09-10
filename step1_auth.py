"""1단계: 카카오 로그인으로 메시지 발송 권한을 받는다.

실행하면 브라우저가 열린다. '동의하고 계속하기'를 누르면 끝이다.
받은 토큰은 .env 파일에 자동으로 저장되며 화면에는 표시되지 않는다.
"""

import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import kakaolib

PORT = 5000
REDIRECT_URI = f"http://localhost:{PORT}/oauth"
SCOPE = "talk_message,profile_nickname"

result = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        if "code" in query:
            result["code"] = query["code"][0]
            message = "동의가 완료되었습니다. 이 창을 닫고 터미널로 돌아가세요."
        elif "error" in query:
            result["error"] = query.get("error_description", query["error"])[0]
            message = f"동의가 취소되었습니다: {result['error']}"
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            f"<html><body style='font-family:sans-serif;padding:60px;text-align:center'>"
            f"<h2>{message}</h2></body></html>".encode("utf-8")
        )

    def log_message(self, *args):
        pass  # 서버 로그를 화면에 찍지 않는다


def main():
    env = kakaolib.load_env()
    kakaolib.require(
        env,
        "KAKAO_REST_API_KEY",
        "카카오 개발자 사이트 > 내 애플리케이션 > 앱 키 > REST API 키를 넣으세요.",
    )

    params = urllib.parse.urlencode({
        "client_id": env["KAKAO_REST_API_KEY"],
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
    })
    auth_url = f"{kakaolib.KAUTH}/oauth/authorize?{params}"

    print("브라우저에서 카카오 동의 화면을 엽니다.")
    print("창이 안 열리면 아래 주소를 직접 붙여넣으세요.\n")
    print(f"  {auth_url}\n")

    server = HTTPServer(("localhost", PORT), Handler)
    webbrowser.open(auth_url)
    print("동의를 기다리는 중...")
    server.handle_request()
    server.server_close()

    if "error" in result:
        raise SystemExit(f"\n실패: {result['error']}")
    if "code" not in result:
        raise SystemExit("\n인가 코드를 받지 못했습니다. 다시 실행해 주세요.")

    token = kakaolib.exchange_code(env, result["code"], REDIRECT_URI)
    kakaolib.store_tokens(token)

    print("\n완료. 토큰을 .env 에 저장했습니다.")
    print("이제 step2_send.py 를 실행하세요.")


if __name__ == "__main__":
    main()
