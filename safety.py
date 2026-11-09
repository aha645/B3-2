"""API 전송 데이터 마스킹과 입력 상한."""
import json
import re

PATTERNS = [
    re.compile(r'(?i)\b(?:sk-[a-z0-9_-]{8,}|gh[pousr]_[a-z0-9_]{10,}|github_pat_[a-z0-9_]{10,}|AKIA[A-Z0-9]{16})\b'),
    re.compile(r'''(?im)(\b(?:api[_-]?key|password|passwd|secret|token|authorization)\b["']?\s*[:=]\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;]+)'''),
    re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}'),
]
MAX_BYTES = 64 * 1024


def mask(text: str) -> tuple[str, int]:
    count = 0
    for index, pattern in enumerate(PATTERNS):
        replacement = r'\1[REDACTED]' if index == 1 else '[REDACTED]'
        text, found = pattern.subn(replacement, text)
        count += found
    return text, count


def prepare(data: dict, safe: bool) -> tuple[str, int]:
    count = 0

    def clean(value):
        nonlocal count
        if isinstance(value, str) and safe:
            value, found = mask(value)
            count += found
        elif isinstance(value, dict):
            value = {k: clean(v) for k, v in value.items()}
        elif isinstance(value, list):
            value = [clean(v) for v in value]
        return value

    text = json.dumps(clean(data), ensure_ascii=False)
    return text, count


def check_size(text: str) -> None:
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('입력 컨텍스트가 UTF-8 64 KiB를 초과합니다. 변경 범위를 줄이세요')
