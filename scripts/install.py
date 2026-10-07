#!/usr/bin/env python3
"""Project installer, shared by the PowerShell and Bash public entry points."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
from urllib.parse import quote
from urllib.request import Request, urlopen
import zipfile

START = '<!-- agent-kit:start -->'
END = '<!-- agent-kit:end -->'
IGNORE_START = '# agent-kit:start'
IGNORE_END = '# agent-kit:end'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def is_link(path):
    return path.is_symlink() or bool(
        getattr(path.lstat(), 'st_file_attributes', 0) & 0x400
    )


def safe_target(root, relative, directory=False):
    """Never follow links/junctions when writing project assets or backups."""
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or '\\' in relative or ':' in relative:
        raise ValueError('Unsafe target path: ' + relative)
    current = root
    for part in rel.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if is_link(current):
                raise ValueError('Refusing link/reparse point: ' + str(current))
    if current.exists() and not (current.is_dir() if directory else current.is_file()):
        raise ValueError('Unexpected target type: ' + str(current))
    return current


def checked_root(value):
    root = Path(os.path.abspath(os.path.expanduser(value)))
    for path in [root, *root.parents]:
        if (path.exists() or path.is_symlink()) and is_link(path):
            raise ValueError('Refusing link/reparse point: ' + str(path))
    if root.exists() and not root.is_dir():
        raise ValueError('Project path must be a directory')
    return root


def download(url):
    request = Request(url, headers={'User-Agent': 'nodaoli-agent-kit/1'})
    with urlopen(request, timeout=60) as response:
        return response.read()


def unpack(data, destination):
    archive = destination / 'source.zip'
    archive.write_bytes(data)
    with zipfile.ZipFile(archive) as zf:
        for item in zf.infolist():
            name = item.filename
            parts = Path(name).parts
            mode = item.external_attr >> 16
            if (name.startswith(('/', '\\')) or '\\' in name or ':' in name
                    or '..' in parts or stat.S_ISLNK(mode)):
                raise ValueError('Unsafe archive entry: ' + name)
        zf.extractall(destination / 'extracted')
    roots = list((destination / 'extracted').iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError('Expected one repository directory in archive')
    return roots[0]


def collect(folder):
    if not folder.is_dir() or is_link(folder):
        raise ValueError('Missing or linked source directory: ' + str(folder))
    result = {}
    for path in sorted(folder.rglob('*')):
        if is_link(path):
            raise ValueError('Source must contain real files, not links: ' + str(path))
        if path.is_file():
            relative = path.relative_to(folder).as_posix()
            if any(p in {'.git', '__pycache__', 'node_modules'} for p in path.relative_to(folder).parts):
                continue
            if path.name == '.env' or path.name.startswith('.env.') or path.suffix == '.pyc':
                continue
            result[relative] = path.read_bytes()
    return result


def names(value):
    chosen = [x.strip() for x in value.split(',') if x.strip()]
    if not chosen or any(not re.fullmatch(r'[a-z0-9][a-z0-9-]*', x) for x in chosen):
        raise ValueError('Use comma-separated lowercase names (letters, digits, hyphens)')
    return sorted(set(chosen))


def block(data, content, start=START, end=END):
    # Decode only for marker validation; bytes outside the managed span are preserved.
    data.decode('utf-8-sig')
    a, b = start.encode(), end.encode()
    managed = a + b'\n' + content.encode('utf-8') + b'\n' + b
    count_a, count_b = data.count(a), data.count(b)
    if count_a == count_b == 0:
        return data + (b'\n\n' if data and not data.endswith(b'\n\n') else b'') + managed + b'\n'
    if count_a != 1 or count_b != 1 or data.index(a) >= data.index(b):
        raise ValueError('Malformed or duplicate managed block markers')
    return data[:data.index(a)] + managed + data[data.index(b) + len(b):]


def install(source, root, args, previous, archive_hash):
    if source.resolve() == root.resolve():
        raise ValueError('Do not install into the source repository itself')
    rules_dir = source / 'rules'
    templates = source / 'templates'
    skills_dir = source / 'skills'
    for directory in [rules_dir, templates, skills_dir]:
        if not directory.is_dir() or is_link(directory):
            raise ValueError('Missing or linked source directory: ' + str(directory))
    if args.no_skills:
        selected = []
    elif args.skills is not None:
        selected = names(args.skills)
    elif previous:
        selected = previous['skills']
    else:
        selected = sorted(p.name for p in skills_dir.iterdir()
                          if p.is_dir() and (p / 'SKILL.md').is_file())
    agents = names(args.agents) if args.agents else previous.get('agents', ['codex', 'claude'])
    if not set(agents).issubset({'codex', 'claude'}):
        raise ValueError('Supported agents: codex,claude')
    stack = args.stack if args.stack is not None else previous.get('stack', '')
    if stack and not re.fullmatch(r'[a-z0-9][a-z0-9-]*', stack):
        raise ValueError('Invalid stack name')

    assets = {}
    rule_files = collect(rules_dir)
    rules = sorted(name for name in rule_files if name.endswith('.md'))
    if not rules:
        raise ValueError('No Markdown rules in source')
    for name in rules:
        assets['.agent/rules/' + name] = rule_files[name]
    if stack:
        path = safe_target(source, 'stacks/' + stack + '.md')
        if not path.is_file() or is_link(path):
            raise ValueError('Stack not found: ' + stack)
        assets['.agent/stack.md'] = path.read_bytes()
    for name in selected:
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', name):
            raise ValueError('Invalid skill name: ' + name)
        folder = skills_dir / name
        if not folder.is_dir() or is_link(folder) or not (folder / 'SKILL.md').is_file():
            raise ValueError('Skill not found: ' + name)
        files = collect(folder)
        # Validate required metadata without importing third-party YAML packages.
        manifest = files['SKILL.md'].decode('utf-8-sig')
        front = re.match(r'\A---\s*\n(.*?)\n---(?:\s|$)', manifest, re.S)
        if not front or any(not re.search(r'^' + field + r':\s*\S', front[1], re.M)
                            for field in ['name', 'description']):
            raise ValueError('Skill requires name/description frontmatter: ' + name)
        for agent in agents:
            base = '.agents' if agent == 'codex' else '.claude'
            for relative, data in files.items():
                assets[base + '/skills/' + name + '/' + relative] = data

    entries = {}
    for agent in agents:
        filename = 'AGENTS.md' if agent == 'codex' else 'CLAUDE.md'
        template_path = templates / (filename + '.tpl')
        if is_link(template_path):
            raise ValueError('Linked template: ' + str(template_path))
        template = template_path.read_text(encoding='utf-8-sig')
        imports = '\n'.join(('- `.agent/rules/' + name + '`') if agent == 'codex'
                            else ('@.agent/rules/' + name) for name in rules)
        stack_line = ('- `.agent/stack.md`' if agent == 'codex' else '@.agent/stack.md') if stack else ''
        content = template.replace('{{RULES}}', imports).replace('{{STACK}}', stack_line).strip()
        path = safe_target(root, filename)
        entries[filename] = block(path.read_bytes() if path.exists() else b'', content)
    ignore_path = safe_target(root, '.gitignore')
    entries['.gitignore'] = block(ignore_path.read_bytes() if ignore_path.exists() else b'',
                                 '.agent/backups/', IGNORE_START, IGNORE_END)

    initial = {}
    for name, data in collect(templates / 'memory').items():
        relative = '.memory/' + name
        if not safe_target(root, relative).exists():
            initial[relative] = data
    owned = previous.get('files', {})
    writes = dict(assets, **entries, **initial)
    # Preflight every target before creating project directories or modifying any file.
    for agent in agents:
        safe_target(root, ('.agents' if agent == 'codex' else '.claude') + '/skills', directory=True)
    for relative, data in writes.items():
        path = safe_target(root, relative)
        if not path.exists() or path.read_bytes() == data or relative in entries or relative in initial:
            continue
        if relative not in owned:
            raise ValueError('Unmanaged file collision: ' + relative)
        if digest(path.read_bytes()) != owned[relative] and not args.force:
            raise ValueError('Locally modified managed file: ' + relative + '; merge it or use --force with backup')
    stale = sorted(name for name in set(owned) - set(assets) if safe_target(root, name).exists())
    manifest = {
        'schema': 1, 'repo': args.repo, 'ref': args.ref, 'archive_sha256': archive_hash,
        'installed_at': datetime.now(timezone.utc).isoformat(),
        'agents': agents, 'skills': selected, 'stack': stack,
        'rules': rules, 'files': dict({name: owned[name] for name in stale},
                                    **{name: digest(data) for name, data in assets.items()}),
        'retained_files': stale,
    }
    manifest_path = safe_target(root, '.agent/kit.json')
    writes['.agent/kit.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    backup_rel = '.agent/backups/' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    changed = [(name, data) for name, data in writes.items()
               if not safe_target(root, name).exists() or safe_target(root, name).read_bytes() != data]
    # Back up all overwritten files, including entry files and previous installation metadata.
    for name, _ in changed:
        path = safe_target(root, name)
        if path.exists():
            backup = safe_target(root, backup_rel + '/' + name)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
    for name, data in changed:
        path = safe_target(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for agent in agents:
        (root / ('.agents' if agent == 'codex' else '.claude') / 'skills').mkdir(parents=True, exist_ok=True)
    print('Installed agent-kit in ' + str(root))
    print('Agents: ' + ', '.join(agents) + '; skills: ' + (', '.join(selected) or '(none)'))
    if stale:
        print('Old assets retained; remove manually if no longer needed: ' + ', '.join(stale))
    print('Existing memory preserved. Overwritten files backed up under .agent/backups/.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default=os.getcwd())
    parser.add_argument('--repo', default=None)
    parser.add_argument('--ref', default=None)
    parser.add_argument('--stack', default=None, help='optional stacks/<name>.md')
    parser.add_argument('--skills', default=None, help='comma-separated curated skill names')
    parser.add_argument('--no-skills', action='store_true')
    parser.add_argument('--agents', default=None, help='codex,claude (default: both)')
    parser.add_argument('--update', action='store_true', help='require an existing installation')
    parser.add_argument('--force', action='store_true', help='back up and replace locally edited managed assets')
    parser.add_argument('--source', help='local source for development; no download')
    args = parser.parse_args()
    if args.skills is not None and args.no_skills:
        parser.error('--skills and --no-skills are mutually exclusive')
    root = checked_root(args.project)
    manifest = safe_target(root, '.agent/kit.json')
    previous = json.loads(manifest.read_text(encoding='utf-8-sig')) if manifest.exists() else {}
    if not isinstance(previous, dict):
        raise ValueError('Installation manifest must be an object')
    if previous and previous.get('schema') != 1:
        raise ValueError('Unsupported installation manifest schema')
    if previous:
        for field in ['skills', 'agents']:
            if not isinstance(previous.get(field), list) or not all(isinstance(x, str) for x in previous[field]):
                raise ValueError('Invalid installation manifest: ' + field)
        if not isinstance(previous.get('files'), dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in previous['files'].items()):
            raise ValueError('Invalid installation manifest: files')
        if not all(isinstance(previous.get(key), str) for key in ['repo', 'ref', 'stack']):
            raise ValueError('Invalid installation manifest source')
    if args.update and not previous:
        raise ValueError('No installation found; run without --update first')
    args.repo = args.repo or previous.get('repo', 'nodaoli/nodaoli-agent-kit')
    args.ref = args.ref or previous.get('ref', 'main')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
        raise ValueError('Repository must be owner/name')
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', args.ref) or '..' in args.ref:
        raise ValueError('Invalid Git ref')
    if args.source:
        install(checked_root(args.source), root, args, previous, None)
    else:
        url = 'https://codeload.github.com/' + args.repo + '/zip/' + quote(args.ref, safe='')
        data = download(url)
        with tempfile.TemporaryDirectory(prefix='nodaoli-agent-kit-') as temporary:
            source = unpack(data, Path(temporary))
            # If a mutable branch changed between bootstrap and archive download, retry safely.
            if (source / 'scripts/install.py').read_bytes() != Path(__file__).read_bytes():
                raise ValueError('Installer changed during download; retry or pin a commit/tag')
            install(source, root, args, previous, digest(data))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print('agent-kit: ' + str(error), file=sys.stderr)
        sys.exit(1)
