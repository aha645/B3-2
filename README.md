# AI Git 초안 생성기

Git 작업 트리의 변경으로 한국어 커밋 메시지와 PR 초안을 만드는 Python 터미널 프로그램입니다. **Ollama 없이 llama.cpp 소스를 빌드하고, Hugging Face에서 받은 Qwen GGUF 모델을 로컬로 실행합니다.** 생성 결과는 사용자가 검토하여 적용해야 합니다.

## 환경 구축

### 1. 준비 사항

- Python 3.10 이상, Git, [uv](https://docs.astral.sh/uv/)와 C/C++ 컴파일러가 필요합니다. CMake는 프로젝트 개발 의존성으로 설치됩니다.
- macOS: `xcode-select --install`로 Xcode Command Line Tools 준비.
- Windows x64: Visual Studio 2022 Build Tools의 C++ 데스크톱 개발·Windows SDK를 설치하고 Developer PowerShell 사용.
- Linux: C/C++ 컴파일러와 표준 빌드 도구 준비.
- 모델 파일은 **4,683,073,536바이트(약 4.7GB)**입니다. 다운로드 캐시·소스·빌드 결과를 위한 추가 디스크 공간과 별도 실행 메모리가 필요합니다.
- 최초 설치에는 인터넷이 필요합니다. 준비 후 로컬 추론은 외부 AI 서비스 없이 수행합니다.
- 현재 검증 환경: **Intel Mac x86_64, RAM 32GiB, Python 3.11.18**. Windows·ARM64는 실행 경로를 지원하지만 실기기 검증하지 않았습니다.

### 2. Python 가상환경

```bash
git clone https://github.com/aha645/B3-2.git
cd B3-2
uv python install 3.11
uv venv --python 3.11
uv sync --locked
```

이후 `uv run`으로 해당 가상환경을 사용합니다. 직접 활성화하려면 macOS/Linux에서 `source .venv/bin/activate`, Windows PowerShell에서 `.\.venv\Scripts\Activate.ps1`을 실행합니다.

### 3. 소스 빌드와 모델 다운로드

프로젝트 루트에서 실행합니다. 모델은 자동 생성 명령 중에 예고 없이 받지 않고 이 준비 단계에서만 다운로드합니다.

```bash
uv run python scripts/setup_inference.py --build --download
```

나눠서 실행할 수도 있습니다.

```bash
uv run python scripts/setup_inference.py --build --jobs 4
uv run python scripts/setup_inference.py --download
```

설치 스크립트는:

1. llama.cpp 소스를 `vendor/llama.cpp/`로 clone하고 고정 커밋을 checkout합니다. 기존 소스에 변경이 있으면 중단합니다.
2. CMake로 `.build/llama.cpp/`에 `llama-server`를 빌드합니다. Intel Mac은 Metal을 끄고 CPU로 빌드합니다.
3. Hugging Face에서 단일 GGUF 파일을 `models/qwen2.5-coder-7b/`에 받습니다.
4. 다운로드한 파일 전체의 SHA-256을 고정값과 비교합니다.

| 대상 | 고정 정보 |
| --- | --- |
| llama.cpp | `7d7f0287530bc8981690f361d8c1627dbae1c99a` |
| HF 저장소 | `Qwen/Qwen2.5-Coder-7B-Instruct-GGUF` |
| HF 리비전 | `13fb94bfda8c8cf22497dc57b78f391a9acb426a` |
| 모델 파일 | `qwen2.5-coder-7b-instruct-q4_k_m.gguf` |
| 모델 SHA-256 | `509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c` |

`.build/`, `models/`, `vendor/llama.cpp/`는 Git 추적에서 제외됩니다. **일반 clone에는 llama.cpp 소스나 모델이 포함되지 않으며**, 위 스크립트가 최초에 내려받습니다. 모델·엔진 재배포 시 해당 모델 카드와 라이선스를 확인하세요.

공개 모델은 로그인 없이 받을 수 있습니다. 인증이 필요하면 `HF_TOKEN` 환경변수를 사용합니다. 이는 모델 다운로드용이며 추론 API Key와 다릅니다. 기존 다운로드 캐시를 활용할 수 있으므로 네트워크 오류 해결 후 같은 명령을 재실행하세요.

참고: [llama.cpp](https://github.com/ggml-org/llama.cpp), [모델 카드](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF), [HF 다운로드](https://huggingface.co/docs/huggingface_hub/guides/download).

### 4. API Key 환경변수

**`AI_API_KEY`를 환경변수로만 관리합니다.** 외부 서비스 발급 키가 아니라 직접 생성하는 로컬 서버 인증용 비밀입니다. 자동 실행 서버는 이 값을 `LLAMA_API_KEY` 환경변수로 전달받고, Python은 Bearer 인증 헤더에 사용합니다. 키를 소스·명령 인자·파일에 넣지 않습니다.

macOS/Linux:

```bash
export AI_API_KEY="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Windows PowerShell:

```powershell
$env:AI_API_KEY = uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

키는 현재 터미널에서만 유지됩니다. 다른 터미널에서 기존 서버를 공유한다면 동일한 값을 안전하게 설정해야 합니다. 키를 커밋하거나 대화·로그에 붙여넣지 마세요. 이 구현은 실제 로컬 API 인증을 수행하지만, 과제가 **외부 AI 서비스 이용 자체**를 요구한다면 별도 확인이 필요합니다.

### 5. 로컬 연결 확인

```bash
uv run python scripts/check_local_model.py --temperature 0.2 --max-tokens 64
```

서버가 없으면 시작하고, 한국어 JSON 생성 요청 1회 후 자신이 시작한 서버를 종료합니다. 기본 준비 대기 시간은 120초, 생성 응답 대기 시간은 300초입니다. Intel CPU에서는 긴 입력이 느릴 수 있습니다.

## 실행

반드시 **분석할 Git 저장소 루트**에서 실행합니다.

```bash
uv run python main.py --help
uv run python main.py commit
uv run python main.py pr
uv run python main.py commit --temperature 0.2 --max-tokens 1000
uv run python main.py pr --reason "변경 배경" --requirements "입력 오류를 검증"
uv run python main.py pr --safe-mode
```

다른 저장소를 분석할 때는 그 저장소 루트에서 이 프로젝트의 가상환경 Python과 `main.py`의 전체 경로를 사용하세요.

```bash
/path/to/B3-2/.venv/bin/python /path/to/B3-2/main.py pr
```

| 옵션 | 기본값 / 제약 |
| --- | --- |
| `--model` | `qwen2.5-coder-7b-instruct`, 서버 모델 alias |
| `--model-path` | 프로젝트 내 기본 GGUF 경로, 다른 모델 파일 지정 가능 |
| `--server-path` | 프로젝트 빌드 결과 자동 탐색, 다른 실행 파일 지정 가능 |
| `--server-mode` | `auto`: 없으면 시작 / `existing`: 기존 서버만 사용 |
| `--temperature` | 0.2, 0~2 → API `temperature` |
| `--max-tokens` | 1000, 1~4096 → API `max_tokens` |
| `--reason`, `--requirements` | 선택적 배경·요구사항 |
| `--safe-mode` / `--no-safe-mode` | 기본 ON / 마스킹 해제 |

`-model`, `-temperature`, `-max-tokens`, `-safe-mode` 표기도 지원합니다. `--model`만 변경하면 다른 모델이 다운로드되지 않습니다. 새 서버에서 실제 가중치를 바꾸려면 `--model-path`도 지정하세요. 기존 서버를 재사용하면 해당 서버에 이미 로딩된 가중치를 사용하며 `--model-path`로 재로딩하지 않습니다. 낮은 temperature가 사실성을 보장하지는 않습니다.

### 서버 실행 정책

- 고정 주소 `http://127.0.0.1:8080`, 컨텍스트 8192, 동시 슬롯 1개를 사용합니다.
- 웹 UI를 끄며 외부 주소에 바인딩하지 않습니다. 화면 없이 터미널로만 동작합니다.
- 기존 서버는 health·인증·모델 alias를 확인한 뒤 재사용하며 종료하지 않습니다. 인증 없는 기존 서버는 거부합니다.
- 새로 시작한 프로세스는 성공·실패 시 모두 종료합니다. 다른 프로세스를 임의로 종료하지 않습니다.
- 모델 로딩 실패·포트 충돌·시작 시간 초과 시 원인을 안내합니다. 강제 종료된 CLI가 서버를 남기면 사용자가 해당 프로세스를 확인해야 합니다.
- 엔진 파일은 필요한 라이브러리와 함께 빌드 디렉터리에 유지하세요.

서버를 계속 유지하려면 별도 터미널에서 수동 실행할 수 있습니다. 먼저 위와 같이 `AI_API_KEY`를 설정합니다.

```bash
# macOS/Linux, 프로젝트 루트
LLAMA_API_KEY="$AI_API_KEY" ./.build/llama.cpp/bin/llama-server --model ./models/qwen2.5-coder-7b/qwen2.5-coder-7b-instruct-q4_k_m.gguf --alias qwen2.5-coder-7b-instruct --host 127.0.0.1 --port 8080 --ctx-size 8192 --parallel 1 --no-context-shift --no-webui
```

```powershell
# Windows Developer PowerShell (Visual Studio 빌드 예시)
$env:LLAMA_API_KEY = $env:AI_API_KEY
.\.build\llama.cpp\bin\Release\llama-server.exe --model .\models\qwen2.5-coder-7b\qwen2.5-coder-7b-instruct-q4_k_m.gguf --alias qwen2.5-coder-7b-instruct --host 127.0.0.1 --port 8080 --ctx-size 8192 --parallel 1 --no-context-shift --no-webui
```

수동 서버는 `Ctrl+C`로 종료합니다. `/health`는 서버 사양상 공개이며 생성 API는 키를 요구합니다. 상태 확인은 `curl --fail http://127.0.0.1:8080/health`로 수행합니다(PowerShell에서는 `curl.exe`).

### Git 분석 범위

- `git status`로 파일 목록, `git diff`로 staged·unstaged 변경을 구분하여 수집합니다.
- 루트의 `.git` 디렉터리 또는 worktree용 `.git` 파일이 필요합니다.
- **PR도 현재 작업 트리 기준**이며 브랜치 전체 이력을 비교하지 않습니다.
- 변경이 없으면 서버 시작·키 확인·생성 요청 없이 `변경 사항이 없습니다`를 출력합니다.
- untracked는 이름만 전달합니다. 내용 분석은 사용자가 `git add` 후 재실행합니다.
- 바이너리 내용은 추론하지 않으며 충돌 상태에서는 중단합니다.
- 제품은 stage·commit·push·GitHub PR 등록을 수행하지 않습니다. 설치 스크립트의 소스 clone/checkout은 제품의 변경 수집과 별개입니다.

## 출력 예시

실제 llama-server 검증에서 얻은 출력의 발췌입니다. 입력과 모델에 따라 달라집니다.

```text
--- 변경 요약 ---
- calculator.py 파일에서 0으로 나누는 경우 ValueError를 발생시킵니다.

--- Commit Message ---
feat(calculator.py): 0으로 나누는 경우 ValueError 추가

- calculator.py 파일에서 divide 함수를 수정하여, 분모가 0인 경우 ValueError를 발생시킵니다.
----------------------
```

PR 형식 예시:

```text
--- PR Title ---
feat: calculator.py에서 0으로 나누는 오류 처리 추가

--- PR Body (현재 작업 트리 기준) ---

## Why
- 0으로 나누는 입력에 명확한 오류를 제공

## What
- divide 함수에 0 검사 추가 및 ValueError 발생

## How to Test
- 분모에 0을 전달하여 ValueError 발생 여부를 확인합니다.
----------------------
```

커밋 제목은 50자 이내 권장·최대 72자, PR 제목은 최대 80자입니다(Python `len()` 기준). 제목은 한 줄이며 커밋 본문은 1~2개 핵심 불릿, PR은 Why/What/How to Test에 각각 최소 한 항목이 필요합니다. 잘못된 응답은 임의 보완·재호출하지 않고 실패 처리합니다. 테스트 절차 제안은 성공 증거가 아닙니다.

## 안전 모드와 입력 제한

- 기본 ON: 키 형태, 토큰·비밀번호 할당, 이메일 패턴을 `[REDACTED]`로 치환합니다.
- 파일 목록·diff·배경·요구사항 모두 적용합니다. 정규표현식에는 탐지 누락과 오탐이 있으므로 실행 전에 내용을 검토하세요.
- 원문 diff와 키는 로그에 남기지 않습니다. 추론은 로컬 서버에서 처리합니다.
- 최종 지침·입력은 UTF-8 64KiB 상한입니다.
- 추가로 **입력 UTF-8 바이트 수 ≤ 8192 − max-tokens − 1024**의 보수적 예산을 적용합니다. 정밀 토큰 계산이 아니므로 정상 처리 가능한 입력도 거부할 수 있습니다.
- 초과 시 일부만 보내지 않고 요청 전에 중단합니다. 안전 모드 OFF에도 크기 제한은 유지됩니다.

## 요청 횟수와 오류 대응

각 실행의 **AI 생성 POST는 최대 1회**이며 자동 재시도하지 않습니다. health·인증·모델 확인용 GET은 추론을 수행하지 않으며 생성 횟수에 포함하지 않습니다. 로그·경고는 stderr, 초안은 stdout에 출력합니다. 로그에는 파일 수·diff 줄 수·마스킹 건수·생성 요청 횟수가 포함됩니다.

로컬 실행은 외부 AI API 요금이 없지만 다운로드 트래픽·CPU·메모리·전력을 사용합니다.

| 상황 | 대응 |
| --- | --- |
| Key 누락 / 인증 실패 | `AI_API_KEY` 설정 및 기존 서버와 키 일치 확인 |
| 엔진 없음 | `uv run python scripts/setup_inference.py --build` |
| 모델 없음 / 해시 불일치 | 모델 확인 후 `--download` 재실행 |
| 기존 서버 모델 불일치 | `--model`과 기존 서버 alias 확인 |
| 포트 충돌 / 서버 종료 | 포트 8080·메모리·실행 권한·라이브러리 확인 |
| 시간 초과 / 입력 초과 | 변경 범위 축소 및 장비 부하 확인 |
| JSON·제목·섹션 오류 | 성공 초안으로 취급하지 않음. 사용자가 원인 검토 후 재실행 |

정상·변경 없음은 종료 코드 0, 입력·Git·서버·API·응답 검증 실패는 1입니다.

## 동봉된 GitHub CLI (macOS Intel)

`gh 2.103.3`이 `vendor/gh/darwin-amd64/bin/gh`에 있습니다. 원격 반영 후 clone하면 별도 gh 다운로드 없이 사용할 수 있습니다. **macOS Intel 전용**이며 Windows·ARM64용 바이너리는 포함하지 않습니다. 인증은 각 사용자가 직접 해야 합니다.

```bash
./vendor/gh/darwin-amd64/bin/gh --version
./vendor/gh/darwin-amd64/bin/gh auth login
./vendor/gh/darwin-amd64/bin/gh auth setup-git
```

Python에서는 `from github_cli import bundled_gh_path`로 현재 디렉터리와 무관한 실행 경로를 얻습니다. 본 프로그램은 gh로 원격 반영하지 않습니다. [라이선스와 상세 안내](vendor/gh/README.md)를 참고하세요.

## 테스트와 검증 기록

```bash
uv run pytest -q
```

일반 테스트는 임시 Git 저장소·모의 HTTP·모의 서버 프로세스를 사용합니다. 실제 모델 다운로드·빌드·추론은 수행하지 않습니다. 실제 연결 확인은 위 `scripts/check_local_model.py`를 사용하세요.

실제 commit/pr을 확인할 때는 작은 tracked 변경을 만들고 **커밋하기 전에 두 초안을 생성**합니다. 검증 결과와 제한은 [검증 기록](doc/verification.md)을 참고하세요. 기존 Ollama 검증은 과거 기록이며 현재 환경에서는 Ollama를 제거했습니다.
