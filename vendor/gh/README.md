# 동봉 GitHub CLI

## 파일 정보

- 위치: `darwin-amd64/bin/gh`
- 버전: 2.103.3 (2026-10-26)
- 형식: Mach-O 64-bit x86_64 (macOS Intel)
- SHA-256: `547afd9491efe0730c7f42791b53529dccecda647837155cbd18ddedf92f799f`
- 프로젝트: https://github.com/cli/cli
- 릴리스: https://github.com/cli/cli/releases/tag/v2.103.3
- 라이선스: MIT, 원본 `LICENSE`를 이 디렉터리에 포함

바이너리는 사용자가 제공한 파일이다. `file`, `gh --version`, SHA-256을 확인했다. 공식 릴리스 체크섬과의 대조는 아직 수행하지 않았다. 라이선스는 위 릴리스 태그에서 가져왔다.

Git에 이 파일이 커밋·push되면 clone 시 함께 내려받을 수 있다. 별도 gh 다운로드나 전역 설치는 필요하지 않다. 약 40MB의 바이너리가 저장소 크기에 추가된다. ARM64·Windows 지원 파일은 포함하지 않는다.

## 직접 실행

프로젝트 루트에서:

```bash
./vendor/gh/darwin-amd64/bin/gh --version
./vendor/gh/darwin-amd64/bin/gh auth login
./vendor/gh/darwin-amd64/bin/gh auth setup-git
```

인증은 각 사용자가 직접 수행한다. 로그인에는 네트워크가 필요하며 토큰·인증 파일을 저장소에 넣지 않는다. 실행 파일 동봉은 로그인이나 저장소 권한을 제공하지 않는다.

## Python 경로 접근

```python
import subprocess
from github_cli import bundled_gh_path

subprocess.run([str(bundled_gh_path()), "--version"], check=True)
```

경로는 `github_cli.py` 위치를 기준으로 계산하므로 현재 작업 디렉터리에 의존하지 않는다. 지원하지 않는 OS/CPU에서는 명확한 오류를 반환한다. 실제 배포 지원 범위는 macOS Intel에서만 검증했다.

본 초안 생성 CLI는 이 실행 파일을 자동 호출하여 push·PR 등록을 수행하지 않는다. 사용자가 검토 후 수동으로 실행하는 제출 작업용 도구다.
