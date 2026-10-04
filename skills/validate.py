"""Validate project skill packages without importing backend or contacting services."""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

MAPPING = {
    'classrooms': 'classroom-search',
    'dishes': 'food-recommendation',
    'courses': 'course-auditing',
    'secondhand': 'secondhand-guidance',
}
PRIMARY_TOOLS = {
    'classrooms': 'query_classrooms', 'dishes': 'recommend_dishes',
    'courses': 'query_courses', 'secondhand': 'query_secondhand',
}
ALLOWED_TOOLS = {*PRIMARY_TOOLS.values(), 'search_knowledge'}
MAX_CHARACTERS = 6000


class ValidationError(ValueError):
    """A skill artifact violates the current backend contract."""


def confined_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValidationError('File path must be a nonempty string')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValidationError(f'Unsafe relative path: {relative}')
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValidationError(f'Path escapes root: {relative}')
    if not resolved.is_file():
        raise ValidationError(f'Missing file: {relative}')
    return resolved


def read_metadata(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0] != '---':
        raise ValidationError('Missing frontmatter opening delimiter')
    try:
        end = lines.index('---', 1)
    except ValueError as exc:
        raise ValidationError('Missing frontmatter closing delimiter') from exc
    metadata = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(':')
        if not separator or key not in {'name', 'description'} or key in metadata:
            raise ValidationError('Frontmatter needs exactly one name and description')
        try:
            parsed = json.loads(value.strip())
        except json.JSONDecodeError as exc:
            raise ValidationError('Frontmatter values must be JSON quoted strings') from exc
        if not isinstance(parsed, str) or not parsed.strip():
            raise ValidationError('Empty or non-string frontmatter value')
        metadata[key] = parsed
    if set(metadata) != {'name', 'description'}:
        raise ValidationError('Missing frontmatter field')
    body = '\n'.join(lines[end + 1:])
    if not body.strip():
        raise ValidationError('Skill body must not be empty')
    return metadata, body


def literal_assignment(file: Path, name: str):
    for node in ast.parse(file.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValidationError(f'Backend assignment missing: {name}')


def validate(root: Path, backend_root: Path | None = None) -> dict:
    root = root.resolve()
    catalog = json.loads(confined_file(root, 'catalog.json').read_text(encoding='utf-8'))
    if not isinstance(catalog, dict) or catalog.get('format_version') != 1:
        raise ValidationError('Unsupported catalog version')
    if catalog.get('max_characters_per_skill') != MAX_CHARACTERS:
        raise ValidationError('Catalog length cap must match backend 6000 characters')
    if catalog.get('automatic_reference_loading') is not False:
        raise ValidationError('Current backend does not automatically load references')
    entries = catalog.get('skills')
    if not isinstance(entries, list) or len(entries) != len(MAPPING):
        raise ValidationError('Catalog must contain the four current business skills')
    seen = set()
    reports = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValidationError('Catalog entry must be an object')
        kind = entry.get('kind')
        if not isinstance(kind, str) or kind not in MAPPING or kind in seen:
            raise ValidationError('Unknown or duplicate kind')
        seen.add(kind)
        slug = MAPPING[kind]
        if entry.get('name') != slug or entry.get('file') != f'{slug}/SKILL.md':
            raise ValidationError(f'Incorrect registry mapping: {kind}')
        tools = entry.get('tools')
        if not isinstance(tools, list) or tools != [PRIMARY_TOOLS[kind], 'search_knowledge']:
            raise ValidationError(f'Tool contract mismatch: {slug}')
        if not set(tools) <= ALLOWED_TOOLS:
            raise ValidationError(f'Tool outside whitelist: {slug}')
        file = confined_file(root, entry['file'])
        text = file.read_text(encoding='utf-8')
        metadata, body = read_metadata(text)
        if metadata['name'] != slug:
            raise ValidationError(f'Frontmatter name mismatch: {slug}')
        if len(text) > MAX_CHARACTERS:
            raise ValidationError(f'{slug}: {len(text)} characters would be truncated at 6000')
        for tool in tools:
            if f'`{tool}`' not in body:
                raise ValidationError(f'Missing declared tool instruction: {slug}/{tool}')
        references = entry.get('references')
        if (not isinstance(references, list) or not references
                or not all(isinstance(ref, str) for ref in references)
                or len(set(references)) != len(references)):
            raise ValidationError(f'Missing or duplicate references: {slug}')
        linked = re.findall(r'\[[^\]]+\]\(([^)]+)\)', body)
        expected_links = []
        for reference in references:
            if not isinstance(reference, str) or not reference.startswith(f'{slug}/references/'):
                raise ValidationError(f'Reference must belong to skill: {slug}')
            ref_file = confined_file(root, reference)
            if not ref_file.read_text(encoding='utf-8').strip():
                raise ValidationError(f'Empty reference: {reference}')
            expected_links.append(reference.removeprefix(slug + '/'))
        if sorted(linked) != sorted(expected_links):
            raise ValidationError(f'Reference links differ from catalog: {slug}')
        reports.append({'kind': kind, 'name': slug, 'characters': len(text),
                        'utf8_bytes': len(text.encode('utf-8')), 'references': len(references)})
    actual = {p.parent.name for p in root.glob('*/SKILL.md')}
    if actual != set(MAPPING.values()):
        raise ValidationError('Unregistered skill package found or expected package missing')
    if backend_root is not None:
        folder = backend_root.resolve() / 'app' / 'skills'
        if literal_assignment(folder / 'registry.py', 'SKILLS') != MAPPING:
            raise ValidationError('Backend registry differs from catalog contract')
        if literal_assignment(folder / 'policies.py', 'ALLOWED_TOOLS') != ALLOWED_TOOLS:
            raise ValidationError('Backend tool whitelist differs from catalog contract')
    return {'ok': True, 'skills': reports, 'max_characters_per_skill': MAX_CHARACTERS,
            'combined_characters': sum(r['characters'] for r in reports) + len(reports) - 1,
            'automatic_reference_loading': False, 'backend_contract_checked': backend_root is not None}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--backend-root', type=Path)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = validate(args.root, args.backend_root)
    except (ValueError, OSError, TypeError, SyntaxError) as exc:
        print(f'Skill validation failed: {exc}', file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for skill in result['skills']:
            print(f"{skill['name']}: {skill['characters']}/6000 characters; {skill['references']} reference(s)")
        print(f"PASS: {len(result['skills'])} skills; combined {result['combined_characters']} characters")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
