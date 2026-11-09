"""AI 출력 계약 검증과 Markdown 렌더링."""
import json


def validate(text: str, mode: str) -> tuple[dict, list[str]]:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError('생성 결과가 유효한 JSON이 아닙니다') from exc
    if not isinstance(data, dict):
        raise ValueError('생성 결과는 JSON 객체여야 합니다')
    title = data.get('title')
    if not isinstance(title, str) or not title.strip() or any(c in title for c in '\r\n\u2028\u2029'):
        raise ValueError('제목은 비어 있지 않은 한 줄이어야 합니다')
    title = ' '.join(title.split())
    limit = 72 if mode == 'commit' else 80
    if len(title) > limit:
        raise ValueError(f'제목은 최대 {limit}자입니다')
    data['title'] = title
    fields = ['summary', 'body'] if mode == 'commit' else ['summary', 'why', 'what', 'how_to_test']
    for field in fields:
        items = data.get(field)
        if not isinstance(items, list) or not items or any(not isinstance(x, str) or not x.strip() or '\n' in x or '\r' in x for x in items):
            raise ValueError(f'{field}: 비어 있지 않은 한 줄 문자열 배열이 필요합니다')
        data[field] = [x.strip() for x in items]
    if mode == 'commit' and len(data['body']) > 2:
        raise ValueError('커밋 본문은 핵심 변경 1~2개가 필요합니다')
    warnings = ['커밋 제목이 권장 길이 50자를 초과합니다'] if mode == 'commit' and len(title) > 50 else []
    return data, warnings


def bullets(items: list[str]) -> str:
    return '\n'.join('- ' + x for x in items)


def render(data: dict, mode: str) -> str:
    sections = ['--- 변경 요약 ---', bullets(data['summary'])]
    if mode == 'commit':
        sections += ['\n--- Commit Message ---', data['title'], '', bullets(data['body'])]
    else:
        sections += ['\n--- PR Title ---', data['title'], '\n--- PR Body (현재 작업 트리 기준) ---']
        for heading, key in [('Why', 'why'), ('What', 'what'), ('How to Test', 'how_to_test')]:
            sections += [f'\n## {heading}', bullets(data[key])]
    return '\n'.join(sections) + '\n----------------------'
