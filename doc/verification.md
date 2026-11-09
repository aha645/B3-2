# 기능 검증 기록

## 최신: llama.cpp + Hugging Face 전환

### 환경 준비

- 기존 Ollama 프로세스를 종료하고 실행 파일·모델·캐시를 제거했다. 기존 포트 11434가 닫힌 것을 확인했다.
- 고정 llama.cpp 소스 `7d7f0287530bc8981690f361d8c1627dbae1c99a`를 Intel Mac에서 빌드했다.
- `llama-server --version`: 0.9.0-dev, build 12211, commit 7d7f02875, AppleClang 17, Darwin x86_64.
- Hugging Face 공식 Qwen 모델을 고정 리비전에서 다운로드했다. 모델 크기 4,683,073,536바이트.
- SHA-256 `509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c` 일치.
- `scripts/setup_inference.py --build` 재실행 성공, `--download` 캐시 재사용 및 해시 확인 성공.

### 구현·자동 검증

- OpenAI 호환 `/v1/chat/completions` 요청, temperature/max_tokens, JSON 출력, finish_reason 검증.
- `AI_API_KEY`를 환경변수에서만 읽고 서버에 `LLAMA_API_KEY`로 전달한다. 명령 인자나 파일에 키를 넣지 않는다.
- 서버 자동 시작·준비 대기·종료, 기존 서버 재사용, 인증 없는 서버 거부.
- 웹 UI 비활성화, loopback 바인딩, 슬롯 1개, context shift 비활성화.
- 자동 테스트 79개: 기존 Git·안전·형식·HTTP 테스트 외에 gh 경로, 서버 소유권·정리·시작 실패·키·인증·모델 alias, 설치 스크립트의 리비전·해시·로컬 변경 보호를 검증한다.

### 실제 생성 검증

현재 저장소를 임의로 stage/commit하지 않고, 별도 임시 저장소에서 calculator.py의 divide 함수에 0 검사와 ValueError를 추가했다(변경 파일 1개, diff 9줄). 인증 키는 테스트 프로세스의 환경변수에만 임시 생성했다.

| 실행 | 결과 | 생성 POST 횟수 | 서버 시작·종료 포함 시간 |
| --- | --- | --- | --- |
| commit, max-tokens 600 | 종료 코드 0, 형식 검증 통과 | 1 | 26.9초 |
| pr, max-tokens 600 | 종료 코드 0, 형식 검증 통과 | 1 | 32.8초 |
| 연결 확인 스크립트, max-tokens 64 | 한국어 message JSON | 1 | 8.9초 |

최종 PR 출력:

```markdown
feat: calculator.py에서 0으로 나누는 오류 처리 추가

## Why
- 0으로 나누는 입력에 명확한 오류를 제공

## What
- divide 함수에 0 검사 추가 및 ValueError 발생

## How to Test
- divide 함수를 호출하여 0으로 나누는 경우 ValueError가 발생하는지 확인
```

추가 실검증:

- 두 CLI 종료 후 포트 8080이 닫혔다. 자신이 시작한 서버가 종료됨을 확인했다.
- 실제 서버에서 인증 누락 및 잘못된 Bearer 키에 HTTP 401이 반환됐다.
- 기존 서버 재사용 컨텍스트를 종료해도 외부 서버는 계속 실행됐다. 소유한 상위 컨텍스트 종료 시에만 정리했다.
- 표준 출력·오류에 실제 테스트 키가 없는지 검사했다.

### 남은 제한

- 작은 diff의 동작 사례이며 일반적인 요약 정확도·긴 입력 성능을 보장하지 않는다. 초기 실제 출력 중 한국어 문장에 중국어 단어가 섞인 사례가 있어 최종 문구의 사람 검토가 필요하다.
- Windows·ARM64·Python 3.10 실기기 검증은 하지 않았다.
- 엔진 소스와 모델은 clone에 동봉하지 않으며 설치 스크립트로 최초 다운로드한다.
- 외부 AI 서비스는 사용하지 않는다. 로컬 서버의 실제 인증으로 환경변수 Key를 사용한다.
- 컨텍스트 제한은 보수적인 바이트 예산이다. 정밀 토큰 계산을 하지 않는다.
- 모델별 품질 비교, 보너스 컨벤션·안전 모드 고도화, 원격 push·PR 등록은 이번 전환에서 수행하지 않았다.

---

## 이하: 과거 1차 Ollama 검증 기록

아래 인증·환경 관련 제한은 당시 상태이며 현재 상태는 위 최신 기록을 따른다.

## 범위

Git 수집, 기본 안전 모드, Ollama 연결, commit/pr 초안 생성, 응답 검증, 터미널 출력 및 README를 구현했다. 자동 설치·컨벤션 옵션·GitHub 등록은 이번 구현 범위가 아니다.

## 자동 검증

```bash
uv sync --locked
uv run pytest -q
uv run python main.py --help
uv run python main.py commit --help
git diff --check
```

결과: pytest **49 passed** (17.61초), 도움말 종료 코드 0, diff 공백 검사 종료 코드 0.

주요 검증 사례:

- 임시 저장소의 변경 없음, staged/unstaged 동시 변경, rename, 삭제, 바이너리, 공백·줄바꿈 파일명, worktree.
- 모든 충돌 상태 코드에 대한 요청 전 차단.
- 마스킹, 파일명·배경의 민감정보 제거, UTF-8 64 KiB 경계, 모델 입력 예산 초과.
- 제목 50/51/72/73자 및 PR 80/81자 경계, JSON 오류·타입 오류·빈 필수 섹션.
- 모의 HTTP 정상·401·403·404·429·500·연결 실패·시간 초과·잘린 응답.
- CLI 출력·종료 코드, 성공/실패 시 요청 1회, 변경 없음/입력 초과/루트 오류 시 요청 0회.

단위 테스트는 실제 모델을 호출하지 않는다. 충돌 상태 파싱 테스트는 모든 코드에 대한 모의 status 바이트를 사용한다.

## 실제 모델 검증

장비: Intel Mac x86_64, RAM 32 GiB. Python 3.11.18, Ollama 0.40.15, qwen2.5-coder:7b Q4_K_M.

현재 저장소에 임의 stage/commit을 하지 않고 별도의 임시 Git 저장소를 만들었다. 초기 calculator.py를 커밋한 다음 divide 함수에 `b == 0`일 때 ValueError를 발생시키는 2줄을 추가했다. 변경 파일 1개, diff 9줄.

해당 임시 저장소 루트에서 다음과 동등한 명령을 프로젝트 가상환경 Python과 main.py의 절대경로로 실행했다.

```bash
python /path/to/B3-2/main.py commit --max-tokens 600 --reason "0으로 나누는 입력에 명확한 오류를 제공"
python /path/to/B3-2/main.py pr --max-tokens 600 --reason "0으로 나누는 입력에 명확한 오류를 제공"
```

최종 입력 예산 검사 반영 후 재실행 결과:

| 명령 | 종료 코드 | 요청 수 | 시간 |
| --- | --- | --- | --- |
| commit | 0 | 1 | 27.7초 |
| pr | 0 | 1 | 36.1초 |

commit 제목:

```text
feat(calculator.py): 0으로 나누는 입력에 대한 오류 처리 추가
```

commit 본문:

```text
- divide 함수에 0으로 나누는 입력에 대한 오류 처리를 추가하여 명확한 오류 메시지를 제공합니다.
```

PR 본문:

```markdown
## Why
- 0으로 나누는 입력에 명확한 오류를 제공

## What
- divide 함수에 예외 처리를 추가하여 0으로 나누는 경우 ValueError를 발생시킵니다.

## How to Test
- divide 함수를 호출하여 0으로 나누는 입력을 전달하고 ValueError가 발생하는지 확인합니다.
```

위 작은 사례에서는 변경 사실과 배경이 입력에 부합했고 테스트 성공을 주장하지 않았다. 일반적인 코드 이해 정확도, 긴 diff 품질 또는 다른 OS 지원을 입증하는 결과는 아니다.

## 미완료·제한

- 로컬 Ollama는 인증이 없으며 환경변수 API Key를 사용하는 외부 인증 API는 지원하지 않는다. 외부 인증 API 사용 자체가 필수라면 추가 작업 또는 허용 여부 확인이 필요하다.
- Python 3.10, Windows, ARM64 실기기 검증은 수행하지 않았다.
- 긴 컨텍스트는 정밀 토큰 계산 대신 보수적 바이트 예산으로 차단하므로 정상 입력도 거부될 수 있다.
- GitHub push 및 실제 PR 생성은 수행하지 않았다.
- 보너스 컨벤션 및 안전 모드 고도화와 배포 설치 자동화는 미구현이다.
