# 모닝 리포트

평일 아침 7시, 가족 카카오톡으로 관심 종목 브리핑 카드뉴스를 보낸다.

제작 SH.YI · 카카오 앱 `finance_report_project` (앱 ID 1573509)

---

## 어떻게 돌아가나

```
run.py
 ├ 1 수집   야후 파이낸스에서 시세, 구글 뉴스 RSS 에서 기사 제목
 ├ 2 요약   Gemini 또는 Claude 가 카드에 들어갈 문장을 쓴다
 ├ 3 조립   숫자와 문장을 합쳐 카드 14장을 만든다
 ├ 4 렌더   카드뉴스 웹페이지와 카톡용 800x800 PNG
 └ 5 발송   카카오톡 나에게 보내기
```

카드 구성은 이렇다.

| 묶음 | 카드 |
|---|---|
| 시장 전체 | 커버 · 밤새 지표 · 거시 이슈 2장 · 오늘 일정 |
| 종목별 (구독 종목마다) | 헤드라인 · 뉴스 2장 · 최근 닷새 흐름 |
| 마무리 | 오늘 체크 3가지 |

### 설계에서 지킨 두 가지

**숫자는 AI 가 만들지 않는다.** 종가, 등락률, 지표 값은 시세 API 가 가져온 것을
그대로 쓴다. 모델은 문장만 쓴다. 없는 수치를 지어낼 방법이 없다.

**기사 주소도 AI 가 쓰지 않는다.** 기사에 번호를 붙여 보여주고 번호만 고르게 한다.
코드가 그 번호를 실제 주소로 바꾼다. 가짜 링크가 생길 수 없다.

---

## 실행

```bash
python run.py              # 평소. 만들고 카톡으로 보낸다
python run.py --no-send    # 만들기만
python run.py --reuse      # 지난번 문장을 다시 써서 모델을 안 부른다
python run.py --force      # 휴장일에도 강제로
python demo.py             # 미리 적어둔 문장으로 디자인만 확인 (API 안 씀)
```

휴장일에는 알아서 건너뛴다. 주말은 확실하고, 공휴일은 최근 종가 날짜로 짐작한다.

---

## 설정

### `config.py`

| 항목 | 뜻 |
|---|---|
| `STOCKS` | 종목 코드, 이름, 야후 티커, 뉴스 검색어 |
| `SUBSCRIBERS` | 누가 어떤 종목을 받을지 |
| `MARKET_INDICATORS` | 밤새 지표 카드에 넣을 값들 |
| `MACRO_KEYWORDS` | 거시 뉴스를 찾을 검색어 |
| `PROVIDER` | `"gemini"`(무료) 또는 `"claude"`(유료) |
| `SITE_URL` | 카드뉴스가 올라간 주소. 비면 카톡에 글자만 간다 |

### `.env`

`.env.example` 을 복사해서 채운다. 절대 공유하지 않는다.

| 키 | 발급처 | 필요도 |
|---|---|---|
| `KAKAO_REST_API_KEY` | 카카오 개발자 > 플랫폼 키 > REST API 키 > 수정 | 필수 |
| `KAKAO_CLIENT_SECRET` | 같은 화면 아래쪽 | 필수 |
| `GEMINI_API_KEY` | aistudio.google.com/apikey | 필수 (무료) |
| `ANTHROPIC_API_KEY` | console.anthropic.com | Claude 로 바꿀 때만 |
| `PIXABAY_API_KEY` | pixabay.com/api/docs | 사진 창고 만들 때만 |

토큰 세 줄은 `step1_auth.py` 가 자동으로 채운다.

---

## 배경 사진

주제별로 미리 골라 둔 사진을 `assets/library/` 에 두고 거기서 꺼낸다.
카드는 주제 이름만 고르고, 날짜와 카드 번호를 섞어 돌려 쓰므로
날마다 다른 그림이 나온다. **운영 중에는 인터넷도 API 키도 쓰지 않는다.**

주제 14개: `oil` `centralbank` `geopolitics` `semiconductor` `datacenter`
`trading` `exchange` `currency` `seoul` `factory` `electronics` `schedule`
`sunrise` `checklist`

마음에 안 드는 주제만 다시 받으려면:

```bash
python build_photo_library.py --only exchange,electronics
python build_photo_library.py --sheet     # 눈으로 확인할 대조표
```

매일 검색해서 쓰는 방식은 접었다. '반도체 클린룸' 에 거실 사진이,
'월스트리트' 에 스페인 도로표지판이, '실리콘 웨이퍼' 에 바나나 디저트가 왔다.

---

## 자동 실행 (GitHub Actions)

`.github/workflows/morning.yml` 이 평일 06:45 KST 에 돈다.
GitHub 예약은 5~15분 늦는 일이 흔해서 7시보다 당겨 두었다.

### 저장소에 넣어야 할 Secrets

`Settings > Secrets and variables > Actions`

| 이름 | 값 |
|---|---|
| `KAKAO_REST_API_KEY` | `.env` 와 같은 값 |
| `KAKAO_CLIENT_SECRET` | `.env` 와 같은 값 |
| `KAKAO_REFRESH_TOKEN` | `.env` 와 같은 값 |
| `GEMINI_API_KEY` | `.env` 와 같은 값 |
| `SECRETS_PAT` | 아래 설명 |

`SECRETS_PAT` 는 카카오 토큰이 갱신됐을 때 그 값을 다시 저장하기 위한 것이다.
없으면 두 달쯤 뒤에 발송이 조용히 멈춘다. GitHub 의 fine-grained 토큰으로
**이 저장소 하나에만, Secrets 쓰기 권한만** 주어 만든다.

### Pages 설정

`Settings > Pages > Source` 를 **GitHub Actions** 로 바꾼다.
첫 배포가 끝나면 나오는 주소를 두 곳에 넣는다.

1. `config.py` 의 `SITE_URL`
2. 카카오 개발자 콘솔 `앱 > 제품 링크 관리 > 웹 도메인`
   (등록하지 않으면 카톡 메시지의 버튼이 동작하지 않는다)

---

## 파일

| 파일 | 역할 |
|---|---|
| `run.py` | 전체를 순서대로 실행 |
| `config.py` | 종목·지표·모델 설정 |
| `collect_market.py` | 시세 수집 (야후 파이낸스) |
| `collect_news.py` | 뉴스 제목 수집 (구글 뉴스 RSS) |
| `summarize.py` | 프롬프트와 출력 형식. 카드 문장 생성 |
| `providers.py` | Gemini / Claude 중 어느 것을 쓸지 |
| `assemble.py` | 숫자와 문장을 합쳐 카드 목록으로 |
| `render.py` | 카드뉴스 HTML |
| `capture.py` | 카드를 PNG 로 촬영 |
| `photos.py` | 사진 창고에서 꺼내기 |
| `send.py` | 카카오톡 발송 |
| `demo.py` | API 없이 디자인 확인 |
| `build_photo_library.py` | 사진 창고 만들기 (한 번만) |
| `step1_auth.py` `step2_send.py` | 카카오 로그인과 발송 시험 |

---

## 문제가 생기면

| 증상 | 해결 |
|---|---|
| `python` 을 못 찾음 | 터미널을 새로 연다 |
| Gemini `503` / `429` | 알아서 세 번까지 다시 시도한다. 계속 실패하면 `config.GEMINI_MODEL` 을 더 가벼운 모델로 |
| Gemini 무료 한도 초과 | 하루 한도가 있다. `gemini-3.5-flash-lite` 로 낮추거나 다음 날 |
| 카톡 발송 실패 | 토큰 만료. `python step1_auth.py` 로 다시 로그인 |
| 카톡 버튼이 안 눌림 | 카카오 콘솔 웹 도메인에 `SITE_URL` 을 등록했는지 확인 |
| 카드 내용이 이상함 | `out/texts.json` 에 모델이 쓴 원본이 남아 있다. 프롬프트 문제인지 렌더링 문제인지 여기서 갈린다 |
| 사진이 주제와 안 맞음 | `build_photo_library.py --only <주제>` 로 그 주제만 다시 받는다 |

---

## 아직 안 한 것

- 가족 온보딩 (사람마다 로그인, 사람별 종목 구독)
- 종목 선택 웹페이지
- DART 공시·실적 일정 카드
- 외국인·기관 수급 (야후에 없어서 뺐다. 공공데이터포털을 붙이면 된다)
