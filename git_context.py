"""읽기 전용 Git status/diff 수집."""
from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass
class GitContext:
    files: list[dict[str, str]]
    staged: str
    unstaged: str


def run_git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ['git', *args], cwd=root, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError('Git 실행 실패 또는 시간 초과') from exc
    if result.returncode:
        raise ValueError('Git 명령 실패: 유효한 저장소와 Git 설정을 확인하세요')
    return result.stdout


def parse_status(raw: bytes) -> list[dict[str, str]]:
    entries = raw.split(b'\0')
    files = []
    i = 0
    while i < len(entries) and entries[i]:
        entry = entries[i]
        status = entry[:2].decode('ascii')
        path = entry[3:].decode('utf-8', errors='replace')
        if status in {'DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU'}:
            raise ValueError('충돌 상태입니다. 충돌을 해결한 후 다시 실행하세요')
        item = {'status': status, 'path': path}
        if 'R' in status or 'C' in status:
            i += 1
            if i >= len(entries) or not entries[i]:
                raise ValueError('잘못된 Git rename 상태 출력')
            item['original_path'] = entries[i].decode('utf-8', errors='replace')
        files.append(item)
        i += 1
    return files


def collect(root: Path) -> GitContext:
    root = root.resolve()
    if not (root / '.git').exists():
        raise ValueError('Git 프로젝트 루트에서 실행하세요 (.git 디렉터리 또는 파일 필요)')
    files = parse_status(run_git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all'))
    if not files:
        return GitContext([], '', '')
    options = ('--no-ext-diff', '--no-textconv', '--no-color', '--no-renames')
    unstaged = run_git(root, 'diff', *options).decode('utf-8', errors='replace')
    staged = run_git(root, 'diff', '--cached', *options).decode('utf-8', errors='replace')
    return GitContext(files, staged, unstaged)
