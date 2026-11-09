import platform
import subprocess

import pytest

from github_cli import bundled_gh_path


def test_path_independent_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(platform, 'machine', lambda: 'x86_64')
    path = bundled_gh_path()
    assert path.is_absolute() and path.is_file()
    assert path.parts[-5:] == ('vendor', 'gh', 'darwin-amd64', 'bin', 'gh')


@pytest.mark.parametrize('system,machine', [('Darwin', 'arm64'), ('Windows', 'AMD64'), ('Linux', 'x86_64')])
def test_unsupported_platform(system, machine, monkeypatch):
    monkeypatch.setattr(platform, 'system', lambda: system)
    monkeypatch.setattr(platform, 'machine', lambda: machine)
    with pytest.raises(ValueError, match='전용'):
        bundled_gh_path()


@pytest.mark.skipif(platform.system() != 'Darwin' or platform.machine() != 'x86_64', reason='동봉 macOS Intel 바이너리 실행 검사')
def test_bundled_version(tmp_path):
    result = subprocess.run([str(bundled_gh_path()), '--version'], cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert 'gh version 2.103.3' in result.stdout
