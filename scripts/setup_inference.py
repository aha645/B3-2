"""고정 llama.cpp 소스 빌드 및 Hugging Face 모델 준비 (생성 명령과 분리)."""
import argparse
import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
import sys

import httpx
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import HFValidationError, LocalEntryNotFoundError

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'vendor/llama.cpp'
REVISION = '7d7f0287530bc8981690f361d8c1627dbae1c99a'
MODEL_REVISION = '13fb94bfda8c8cf22497dc57b78f391a9acb426a'
MODEL_FILE = 'qwen2.5-coder-7b-instruct-q4_k_m.gguf'
MODEL_SHA256 = '509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c'


def run(*args):
    subprocess.run(list(args), cwd=ROOT, check=True)


def build(jobs: int) -> None:
    cmake = shutil.which('cmake')
    if not cmake:
        raise ValueError('CMake가 없습니다. uv sync --locked로 개발 의존성을 설치하세요')
    if not SOURCE.exists():
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        run('git', 'clone', '--filter=blob:none', '--no-checkout', 'https://github.com/ggml-org/llama.cpp.git', str(SOURCE))
    if not (SOURCE / '.git').exists():
        raise ValueError('소스 디렉터리가 Git 저장소가 아닙니다. 기존 파일을 확인하세요')
    status = subprocess.run(['git', '-C', str(SOURCE), 'status', '--porcelain'], capture_output=True, text=True, check=True)
    if status.stdout:
        raise ValueError('llama.cpp 소스에 로컬 변경이 있습니다. 자동 checkout을 중단합니다')
    run('git', '-C', str(SOURCE), 'checkout', REVISION)
    args = ['cmake', '-S', str(SOURCE), '-B', str(ROOT / '.build/llama.cpp'),
            '-DCMAKE_BUILD_TYPE=Release', '-DLLAMA_BUILD_TESTS=OFF', '-DLLAMA_BUILD_EXAMPLES=OFF']
    if platform.system() == 'Darwin' and platform.machine() == 'x86_64':
        args.append('-DGGML_METAL=OFF')
    run(*args)
    run('cmake', '--build', str(ROOT / '.build/llama.cpp'), '--config', 'Release', '--target', 'llama-server', '-j', str(jobs))


def download() -> None:
    print('Hugging Face에서 약 4.7GB 모델을 받습니다. 기존 다운로드는 재사용합니다.', flush=True)
    path = Path(hf_hub_download(
        repo_id='Qwen/Qwen2.5-Coder-7B-Instruct-GGUF', filename=MODEL_FILE,
        revision=MODEL_REVISION, local_dir=ROOT / 'models/qwen2.5-coder-7b',
    ))
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != MODEL_SHA256:
        raise ValueError('모델 SHA-256 불일치: 파일을 확인하고 다시 다운로드하세요')
    print(f'모델 SHA-256 확인 완료: {path}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if not args.build and not args.download:
        parser.error('--build 또는 --download를 지정하세요 (둘 다 지정 가능)')
    if args.jobs < 1:
        parser.error('--jobs는 양수여야 합니다')
    try:
        if args.build:
            build(args.jobs)
        if args.download:
            download()
        return 0
    except (OSError, ValueError, httpx.HTTPError, HFValidationError, LocalEntryNotFoundError, subprocess.CalledProcessError) as exc:
        # 외부 라이브러리 오류에 인증 URL 등이 포함될 수 있어 원문은 출력하지 않는다.
        print(f'[ERROR] 환경 준비 실패 ({type(exc).__name__}). 네트워크·디스크·빌드 도구·소스 상태를 확인하세요', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
