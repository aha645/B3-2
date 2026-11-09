# 1차 기능 검증 기록

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
