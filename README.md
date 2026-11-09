# AI Git 초안 생성기

Git 작업 트리의 변경으로 한국어 커밋 메시지와 PR 초안을 만드는 Python 터미널 프로그램입니다. Ollama `qwen2.5-coder:7b`를 로컬에서 사용합니다. 생성 결과는 사용자가 검토하여 적용해야 합니다.

## 설치

Python 3.10 이상, Git, [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com/)가 필요합니다. 모델 다운로드는 약 4.7GB이며 실행 메모리는 별도로 필요합니다. Intel Mac은 CPU 추론이므로 긴 입력은 느릴 수 있습니다.

```bash
git clone https://github.com/aha645/B3-2.git
cd B3-2
uv python install 3.11
uv venv --python 3.11
uv sync --locked
ollama pull qwen2.5-coder:7b
```

서버가 실행 중이 아니면 별도 터미널에서 시작합니다. 외부에 노출하지 않습니다.

```bash
# macOS/Linux
OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

```powershell
# Windows PowerShell
$env:OLLAMA_HOST = "127.0.0.1:11434"
ollama serve
```

이번 개발 장비의 사용자 디렉터리 설치와 상세 확인 결과는 [로컬 환경 문서](doc/local-environment.md)를 참고하세요. 자동 설치 스크립트, Windows/ARM 실기기 검증은 제공하지 않습니다.

## API Key 환경변수

로컬 Ollama는 기본적으로 인증이 없어 API Key 설정이 필요하지 않습니다. 현재 버전은 외부 제공자 API와 인증 헤더를 지원하지 않습니다. 키가 필요한 API로 확장한다면 코드에 넣지 않고 다음처럼 환경변수에서만 관리해야 합니다. 아래 변수는 **현재 로컬 요청에서는 사용하지 않습니다**.

```bash
export AI_API_KEY="발급받은 키"
```

```powershell
$env:AI_API_KEY = "발급받은 키"
```

인증 API 사용 자체가 필수 제출 조건이라면 이 로컬 구현만으로 충족했다고 볼 수 없으므로 별도 확인이 필요합니다. 키를 커밋하거나 대화·로그에 붙여넣지 마세요.

## 실행

반드시 분석할 Git 저장소 루트에서 실행합니다. 이 도구가 다른 경로에 있다면 `main.py`와 Python의 전체 경로를 지정할 수 있습니다.

```bash
uv run python main.py --help
uv run python main.py commit
uv run python main.py pr
uv run python main.py commit --model qwen2.5-coder:7b --temperature 0.2 --max-tokens 1000
uv run python main.py pr --reason "변경 배경" --requirements "입력 오류를 검증"
uv run python main.py pr --safe-mode
```

| 옵션 | 기본값 / 제약 |
| --- | --- |
| `--model` | `qwen2.5-coder:7b`, 설치된 모델 이름 |
| `--temperature` | 0.2, 0~2 |
| `--max-tokens` | 1000, 1~4096, 출력 토큰 상한 |
| `--reason`, `--requirements` | 선택적 배경·요구사항 |
| `--safe-mode` / `--no-safe-mode` | 기본 ON / 마스킹 해제 |

`-model`, `-temperature`, `-max-tokens`, `-safe-mode` 표기도 지원합니다. 낮은 temperature가 사실성을 보장하지는 않습니다.

### 분석 범위

- `git status`로 파일 목록, `git diff`로 unstaged·staged 변경을 각각 수집합니다.
- **PR도 현재 작업 트리 기준**이며 브랜치 전체 이력을 비교하지 않습니다.
- 변경이 없으면 API 요청 없이 `변경 사항이 없습니다`를 출력합니다.
- untracked 파일은 목록만 전달합니다. 내용을 분석하려면 사용자가 `git add` 후 다시 실행합니다.
- 바이너리 내용은 추론하지 않으며 충돌은 해결 후 실행해야 합니다.
- `.git` 파일을 사용하는 worktree도 지원합니다.
- 프로그램은 stage, commit, push, GitHub PR 등록을 수행하지 않습니다.

## 출력 예시

실제 로컬 모델 검증에서 얻은 출력 중 발췌입니다. 모델과 입력에 따라 결과가 달라집니다.

```text
--- 변경 요약 ---
- divide 함수에 0으로 나누는 예외 처리를 추가

--- Commit Message ---
feat(calculator.py): 0으로 나누는 예외 처리 추가

- divide 함수에 0으로 나누는 예외 처리를 추가하여 명확한 오류 메시지를 제공합니다.
----------------------
```

```text
--- PR Title ---
feat(calculator.py): 0으로 나누는 경우 ValueError 추가

--- PR Body (현재 작업 트리 기준) ---

## Why
- 0으로 나누는 입력에 명확한 오류를 제공

## What
- divide 함수에 0으로 나누는 경우 ValueError를 발생시키는 조건문 추가

## How to Test
- divide 함수를 호출하여 0으로 나누는 경우 ValueError가 발생하는지 확인
----------------------
```

제목은 한 줄이어야 합니다. 커밋은 50자 이내 권장·최대 72자, PR은 최대 80자입니다(Python `len()` 기준). 커밋 본문은 핵심 변경 1~2개, PR은 각 필수 섹션에 최소 한 항목을 요구합니다. 잘못된 응답은 재호출하거나 임의 보완하지 않고 오류로 처리합니다. 테스트 절차 제안은 테스트 성공 증거가 아닙니다.

## 안전 모드와 입력 제한

- 기본 ON: 키 형태, 토큰·비밀번호 할당, 이메일 패턴을 `[REDACTED]`로 치환합니다.
- 파일 목록, diff, 변경 배경, 요구사항 모두 마스킹합니다.
- 정규표현식은 모든 비밀을 탐지하지 못하고 오탐도 가능합니다. 실행 전 변경 내용을 검토하세요.
- 원문 diff와 키는 로그에 남기지 않습니다. 모델은 로컬 서버에서 처리합니다.
- 최종 지침·입력은 UTF-8 64 KiB 상한입니다.
- 모델 컨텍스트는 8192토큰이며 추가로 **입력 UTF-8 바이트 수 ≤ 8192 − max-tokens − 1024**라는 보수적 사전 제한을 적용합니다. 정밀 토큰 계산이 아니므로 정상 처리 가능한 입력도 거부될 수 있습니다.
- 상한 초과 시 일부만 조용히 보내지 않고 요청 전에 중단합니다. 두 제한은 안전 모드 OFF에도 유지됩니다.

## 요청 횟수·오류 대응

각 실행은 최대 1회 요청하며 자동 재시도하지 않습니다. 로그와 경고는 stderr, 최종 초안은 stdout에 출력합니다. 로그에는 파일 수, diff 줄 수, 마스킹 건수, 요청 횟수가 포함됩니다. 로컬 실행은 외부 API 호출 요금이 없지만 CPU·메모리·전력을 사용합니다.

| 상황 | 대응 |
| --- | --- |
| 연결 실패 | `ollama serve`와 포트 11434 확인 |
| HTTP 404 | `ollama pull qwen2.5-coder:7b`로 모델 확인 |
| 시간 초과 | 변경 범위 축소, 장비 부하 확인 |
| 컨텍스트 초과 | 변경을 더 작은 단위로 나누기 |
| JSON·제목·섹션 오류 | 출력을 성공으로 취급하지 않으며 원인 확인 후 사용자가 재실행 |
| Git 루트 오류 | 분석할 저장소 루트로 이동 |

정상·변경 없음은 종료 코드 0, 입력·Git·API·응답 검증 실패는 1입니다.

## 테스트

```bash
uv run pytest -q
```

일반 테스트는 임시 Git 저장소와 모의 HTTP를 사용하므로 실제 모델을 호출하지 않습니다.

로컬 연결 확인(실제 요청 1회):

```bash
uv run python scripts/check_local_model.py --temperature 0.2 --max-tokens 64
```

실제 commit/pr 확인은 임시 또는 별도 저장소에 작은 tracked 변경을 만들고, 이 프로젝트 `.venv`의 Python으로 `main.py`를 실행하세요. 두 초안은 커밋 전에 생성해야 합니다. [검증 기록](doc/verification.md)을 참고하세요.
