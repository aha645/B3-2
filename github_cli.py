"""동봉된 GitHub CLI 경로 확인. 원격 작업이나 인증을 자동 실행하지 않는다."""
from pathlib import Path
import os
import platform


def bundled_gh_path() -> Path:
    """프로젝트 기준 경로를 반환하고 지원 OS/CPU와 실행 권한을 확인한다."""
    system = platform.system()
    machine = platform.machine().lower()
    if system != 'Darwin' or machine not in {'x86_64', 'amd64'}:
        raise ValueError('동봉된 gh는 macOS Intel(x86_64) 전용입니다. ARM64·Windows용 바이너리는 포함되어 있지 않습니다')
    executable = Path(__file__).resolve().parent / 'vendor' / 'gh' / 'darwin-amd64' / 'bin' / 'gh'
    if not executable.is_file():
        raise ValueError('동봉된 gh 실행 파일이 없습니다')
    if not os.access(executable, os.X_OK):
        raise ValueError('gh 실행 권한이 없습니다. chmod +x vendor/gh/darwin-amd64/bin/gh를 실행하세요')
    return executable
