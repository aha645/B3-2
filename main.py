"""Git 작업 트리 기반 커밋·PR 초안 CLI."""
import argparse
from dataclasses import asdict
from pathlib import Path
import sys

import ai_client
from git_context import collect
from prompts import build
from safety import check_size, prepare
from validation import render, validate


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f'입력 오류: {message}\n')


def parser() -> argparse.ArgumentParser:
    root = Parser(description=__doc__)
    commands = root.add_subparsers(dest='command', required=True)
    for name in ('commit', 'pr'):
        command = commands.add_parser(name)
        command.add_argument('--model', '-model', default='qwen2.5-coder:7b')
        command.add_argument('--temperature', '-temperature', type=float, default=0.2)
        command.add_argument('--max-tokens', '-max-tokens', type=int, default=1000)
        command.add_argument('--reason', default='')
        command.add_argument('--requirements', default='')
        command.add_argument('--safe-mode', '-safe-mode', dest='safe', action='store_true', default=True)
        command.add_argument('--no-safe-mode', dest='safe', action='store_false')
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    calls = 0
    try:
        if not 0 <= args.temperature <= 2:
            raise ValueError('temperature는 0~2 사이여야 합니다')
        if not 1 <= args.max_tokens <= 4096:
            raise ValueError('max-tokens는 1~4096 사이여야 합니다')
        if not args.model.strip():
            raise ValueError('모델 이름이 비어 있습니다')
        context = collect(Path.cwd())
        if not context.files:
            print('변경 사항이 없습니다')
            return 0
        print(f'[INFO] 변경 파일: {len(context.files)}개, diff: {len(context.staged.splitlines()) + len(context.unstaged.splitlines())}줄', file=sys.stderr)
        if any(x['status'] == '??' for x in context.files):
            print('[WARN] untracked 파일은 이름만 분석합니다. 내용 분석은 git add 후 재실행하세요', file=sys.stderr)
        if not args.safe:
            print('[WARN] 안전 모드 OFF: 민감정보가 모델에 전달될 수 있습니다', file=sys.stderr)
        data = asdict(context) | {'reason': args.reason, 'requirements': args.requirements}
        prepared, count = prepare(data, args.safe)
        system, prompt = build(args.command, prepared)
        check_size(system + prompt)
        ai_client.check_input(system, prompt, args.max_tokens)
        print(f'[INFO] 안전 모드: {"ON" if args.safe else "OFF"}, 마스킹: {count}건', file=sys.stderr)
        calls += 1
        text = ai_client.generate(system, prompt, args.model, args.temperature, args.max_tokens)
        result, warnings = validate(text, args.command)
        for warning in warnings:
            print('[WARN] ' + warning, file=sys.stderr)
        print(render(result, args.command))
        return 0
    except ValueError as exc:
        print(f'[ERROR] {exc}', file=sys.stderr)
        return 1
    finally:
        print(f'[INFO] AI API 요청 횟수: {calls}', file=sys.stderr)


if __name__ == '__main__':
    raise SystemExit(main())
