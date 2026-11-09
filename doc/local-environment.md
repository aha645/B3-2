# 로컬 실행 환경 및 API 옵션 검토

## 현재 구성

- Python 요구 버전: 3.10 이상. 개발 인터프리터: uv 관리 Python 3.11.18.
- `.venv/` 가상환경을 사용하고 `uv run`으로 실행한다.
- `httpx`와 개발용 `pytest`는 `uv.lock`으로 고정한다.
- 로컬 모델: Ollama의 `qwen2.5-coder:7b` (다운로드 약 4.7 GB).
- 검증 장비: Intel x86_64 Mac, RAM 32 GiB, macOS 15.7.4. Intel에서는 CPU 추론을 사용한다.
- 웹 화면 없이 터미널과 loopback HTTP API만 사용한다.

## Python 환경 재현

```bash
uv python install 3.11
uv venv --python 3.11
uv sync --locked
uv run python --version
```

직접 활성화해야 할 경우:

```bash
source .venv/bin/activate
python --version
```

## Ollama 설치 및 실행

이번 환경은 Homebrew 설치 경로에 쓰기 권한이 없어 `brew install ollama`가 실패했다. 시스템 경로 권한은 변경하지 않았다. 대신 공식 v0.40.15 macOS 배포본을 사용자 디렉터리에 설치했다.

- 실행 파일과 라이브러리: `~/.local/share/ollama/`
- 실행 링크: `~/.local/bin/ollama`
- 모델: 기본 Ollama 모델 저장 위치 `~/.ollama/models/`
- 현재 서버 로그: `~/.local/share/ollama/server.log`

새 터미널에서 실행 파일을 찾지 못하면 전체 경로를 사용한다. 서버가 실행 중이면 중복 실행하지 않는다.

```bash
OLLAMA_HOST=127.0.0.1:11434 ~/.local/bin/ollama serve
```

다른 터미널에서:

```bash
~/.local/bin/ollama pull qwen2.5-coder:7b
uv run python scripts/check_local_model.py --temperature 0.2 --max-tokens 64
```

서버를 로그인 시 자동 시작하는 시스템 서비스는 등록하지 않았다. 재부팅 후 필요하면 다시 실행한다. 모델 다운로드는 외부 네트워크를 사용하지만, 위 확인 요청은 로컬 API에만 연결한다.

## 옵션 매핑

네이티브 `POST /api/generate`를 사용한다.

| CLI 옵션 | Ollama 필드 | 기본값 계획 |
| --- | --- | --- |
| `--model` | `model` | `qwen2.5-coder:7b` |
| `--temperature` | `options.temperature` | 0.2 |
| `--max-tokens` | `options.num_predict` | 실제 CLI 1000, 환경 확인 스크립트 64 |

`num_predict`는 출력 토큰 상한이며 입력 크기나 전체 컨텍스트 상한이 아니다. `num_ctx`는 별도로 관리한다. 환경 확인 스크립트는 2048을 사용하며, 실제 diff 생성용 컨텍스트 크기는 별도 검증해야 한다. 출력 한도에 도달하면 완성된 초안으로 처리하지 않는다.

`stream: false`로 전체 응답을 받고 `format: "json"`으로 JSON 출력을 요청한다. 응답 구조와 내용 검증은 별도로 필요하다.

## API Key 제약의 해석

로컬 Ollama API는 기본적으로 인증을 요구하지 않는다. 가짜 Key를 코드에 넣거나 의미 없이 필수화하지 않는다. 추후 인증이 필요한 API에 연결하는 경우 키는 환경변수에서만 읽고 로그에 남기지 않는다. 과제에서 인증된 API 사용 자체를 필수로 평가한다면 로컬 무인증 방식의 허용 여부를 확인해야 한다.

## Git 및 기능 범위

- 실제 CLI의 Git 수집 명령은 `git status`, `git diff`로 제한한다. 루트 확인에 `git rev-parse`를 사용하지 않는다.
- 루트의 `.git` 디렉터리 또는 worktree용 `.git` 파일을 확인하고 Git 실행 결과로 유효성을 검사한다.
- 프로그램은 초안만 출력하며 stage, commit, push, PR 원격 생성 기능을 구현하지 않는다.
- 개발·제출 과정의 수동 GitHub CLI 사용은 제품 기능과 분리한다.
- 안전 모드는 기본 활성화하고 모든 사용자 전송 데이터에 마스킹을 적용한다.

## 실행 확인 결과

`uv sync --locked`와 가상환경 내 Python 3.11.18 및 의존성 import를 확인했다.

아래 명령은 로컬 생성 API를 실제 1회 호출했다.

```bash
uv run python scripts/check_local_model.py --temperature 0.2 --max-tokens 64
```

관측 결과: `{"message": "로컬 모델 연결 확인"}`, 출력 11토큰, 약 10.0초. 이 결과는 짧은 연결 확인용이며 실제 diff 요약 품질이나 긴 입력의 속도를 보장하지 않는다. 이후 commit/pr CLI를 구현하고 실제 생성과 모의 테스트를 수행했다. 최신 결과는 `doc/verification.md`를 참고한다.

## 공식 참고 문서

- https://docs.ollama.com/api/generate
- https://docs.ollama.com/modelfile
- https://docs.ollama.com/macos
- https://github.com/ollama/ollama/releases/tag/v0.40.15
