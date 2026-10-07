#!/usr/bin/env python3
"""Behavior tests using only generated fixtures, never installed personal skills."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('kit_installer', REPO / 'scripts/install.py')
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


class InstallerTest(unittest.TestCase):
    def setUp(self):
        temporary = REPO / '.tmp'
        temporary.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='installer-test-', dir=temporary)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'fixture source'
        self.source.mkdir()
        for name in ['rules', 'templates']:
            shutil.copytree(REPO / name, self.source / name)
        (self.source / 'skills').mkdir()
        (self.source / 'skills/README.md').write_text('# Empty curated skills\n', encoding='utf-8')
        (self.source / 'stacks').mkdir()
        (self.source / 'scripts').mkdir()
        shutil.copyfile(REPO / 'scripts/install.py', self.source / 'scripts/install.py')
        (self.source / 'stacks/demo.md').write_text('# Demo stack\n', encoding='utf-8')
        self.project = self.base / 'project 中文 space'

    def run_install(self, *options, project=None, success=True):
        cmd = [sys.executable, str(REPO / 'scripts/install.py'), '--source', str(self.source),
               '--project', str(project or self.project), *options]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                                env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def skill(self, name='demo-skill'):
        folder = self.source / 'skills' / name
        (folder / 'references').mkdir(parents=True)
        (folder / 'SKILL.md').write_text(
            '---\nname: ' + name + '\ndescription: Synthetic installer test.\n---\n# Demo\n',
            encoding='utf-8')
        (folder / 'references/info.txt').write_text('supporting resource\n', encoding='utf-8')

    def manifest(self):
        return json.loads((self.project / '.agent/kit.json').read_text(encoding='utf-8'))

    def snapshot(self):
        return {p.relative_to(self.project).as_posix(): p.read_bytes()
                for p in self.project.rglob('*') if p.is_file()}

    def test_empty_install_and_repeated_install_preserve_project_and_memory(self):
        self.project.mkdir()
        custom = b'\xef\xbb\xbf# Project instructions\r\nKeep this exact content.\r\n'
        (self.project / 'AGENTS.md').write_bytes(custom)
        (self.project / '.gitignore').write_bytes(b'node_modules/\r\n')
        self.run_install()
        self.assertEqual(self.manifest()['skills'], [])
        self.assertTrue((self.project / '.agents/skills').is_dir())
        self.assertTrue((self.project / '.claude/skills').is_dir())
        entry = self.project / 'AGENTS.md'
        self.assertTrue(entry.read_bytes().startswith(custom))
        entry.write_bytes(entry.read_bytes() + b'\r\n# User suffix\r\n')
        before = entry.read_bytes()
        memory = self.project / '.memory/TODO.md'
        memory.write_bytes(b'# Actual user TODO\n')
        self.run_install('--update')
        self.assertEqual(entry.read_bytes(), before)
        self.assertEqual(entry.read_bytes().count(kit.START.encode()), 1)
        self.assertEqual(memory.read_bytes(), b'# Actual user TODO\n')
        self.assertTrue((self.project / '.gitignore').read_bytes().startswith(b'node_modules/\r\n'))

    def test_skills_are_complete_and_updates_keep_selection(self):
        self.skill()
        self.run_install('--stack', 'demo')
        for base in ['.agents', '.claude']:
            self.assertEqual((self.project / base / 'skills/demo-skill/references/info.txt').read_text(),
                             'supporting resource\n')
        self.skill('new-skill')
        self.run_install('--update')
        self.assertEqual(self.manifest()['skills'], ['demo-skill'])
        self.assertEqual(self.manifest()['stack'], 'demo')
        self.assertFalse((self.project / '.agents/skills/new-skill').exists())
        self.run_install('--update', '--skills', 'new-skill', '--stack', '')
        self.assertTrue((self.project / '.agents/skills/demo-skill/SKILL.md').exists())
        self.assertNotIn('stack.md', (self.project / 'AGENTS.md').read_text(encoding='utf-8'))
        self.assertIn('.agent/stack.md', self.manifest()['retained_files'])
        # Re-selecting retained managed assets remains safe on subsequent updates.
        self.run_install('--update', '--skills', 'demo-skill', '--stack', 'demo')

    def test_no_skills_and_codex_only(self):
        self.skill()
        self.run_install('--no-skills', '--agents', 'codex')
        self.assertEqual(self.manifest()['skills'], [])
        self.assertFalse((self.project / 'CLAUDE.md').exists())
        self.assertFalse((self.project / '.claude').exists())

    def test_unmanaged_assets_are_preserved(self):
        self.project.mkdir()
        target = self.project / '.agent/rules/general.md'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'# My own rules\n')
        self.run_install(success=False)
        self.assertEqual(target.read_bytes(), b'# My own rules\n')
        self.assertFalse((self.project / 'AGENTS.md').exists())

    def test_unrelated_skill_and_rules_survive(self):
        self.run_install()
        files = ['.agent/project.md', '.agent/rules/custom.md', '.agents/skills/custom/SKILL.md']
        for relative in files:
            path = self.project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'User owned\n')
        self.run_install('--update')
        for relative in files:
            self.assertEqual((self.project / relative).read_bytes(), b'User owned\n')

    def test_local_edits_stop_before_writes_and_force_backs_up(self):
        self.run_install()
        target = self.project / '.agent/rules/general.md'
        edited = b'# Locally edited rule\n'
        target.write_bytes(edited)
        before = self.snapshot()
        self.run_install('--update', success=False)
        self.assertEqual(self.snapshot(), before)
        self.run_install('--update', '--force')
        self.assertNotEqual(target.read_bytes(), edited)
        backups = list((self.project / '.agent/backups').glob('*/.agent/rules/general.md'))
        self.assertTrue(any(p.read_bytes() == edited for p in backups))

    def test_source_change_updates_rules_and_backs_up_entry(self):
        self.run_install()
        old = (self.project / '.agent/rules/general.md').read_bytes()
        (self.source / 'rules/general.md').write_bytes(b'# New shared rules\n')
        (self.source / 'rules/new-rule.md').write_bytes(b'# Additional rule\n')
        self.run_install('--update')
        self.assertEqual((self.project / '.agent/rules/general.md').read_bytes(), b'# New shared rules\n')
        self.assertIn('new-rule.md', (self.project / 'CLAUDE.md').read_text(encoding='utf-8'))
        backups = list((self.project / '.agent/backups').glob('*/.agent/rules/general.md'))
        self.assertTrue(any(p.read_bytes() == old for p in backups))

    def test_missing_skill_and_broken_markers_do_not_write(self):
        self.run_install('--skills', 'missing', success=False)
        self.assertFalse(self.project.exists())
        self.project.mkdir()
        entry = self.project / 'CLAUDE.md'
        entry.write_text(kit.START + '\n# Broken\n', encoding='utf-8')
        before = self.snapshot()
        self.run_install(success=False)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_paths_missing_update_and_self_install(self):
        self.run_install('--stack', '../outside', success=False)
        self.run_install('--update', success=False)
        self.run_install(project=self.source, success=False)
        self.run_install('--no-skills', '--skills', 'demo', success=False)
        self.assertFalse(self.project.exists())

    def test_target_link_rejected_even_with_empty_skills(self):
        outside = self.base / 'outside'
        outside.mkdir()
        self.project.mkdir()
        try:
            (self.project / '.agents').symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest('Host cannot create symlinks: ' + str(error))
        self.run_install(success=False)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.project / 'AGENTS.md').exists())

    def test_archive_rejects_traversal_and_links(self):
        for name, mode in [('../escaped', 0), ('/absolute', 0), ('root/link', 0o120777 << 16)]:
            with self.subTest(name=name):
                data = io.BytesIO()
                with zipfile.ZipFile(data, 'w') as zf:
                    item = zipfile.ZipInfo(name)
                    item.external_attr = mode
                    zf.writestr(item, 'bad')
                folder = self.base / ('archive-' + str(mode))
                folder.mkdir(exist_ok=True)
                with self.assertRaises(ValueError):
                    kit.unpack(data.getvalue(), folder)

    def test_public_archive_flow_without_clone(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as zf:
            for path in self.source.rglob('*'):
                if path.is_file():
                    zf.write(path, 'repository-main/' + path.relative_to(self.source).as_posix())
        data = archive.getvalue()
        args = ['install.py', '--project', str(self.project), '--repo', 'example/kit', '--ref', 'v1']
        with patch.object(sys, 'argv', args), patch.object(kit, 'urlopen', return_value=io.BytesIO(data)) as request:
            with contextlib.redirect_stdout(io.StringIO()):
                kit.main()
        self.assertEqual(request.call_args.args[0].full_url, 'https://codeload.github.com/example/kit/zip/v1')
        self.assertEqual(self.manifest()['archive_sha256'], kit.digest(data))
        self.assertFalse((self.project / '.git').exists())

    def test_download_failure_leaves_project_untouched(self):
        args = ['install.py', '--project', str(self.project)]
        with patch.object(sys, 'argv', args), patch.object(kit, 'urlopen', side_effect=OSError('offline')):
            with self.assertRaises(OSError):
                kit.main()
        self.assertFalse(self.project.exists())

    def test_powershell_local_and_iex_entry(self):
        pwsh = shutil.which('pwsh') or shutil.which('powershell')
        if not pwsh:
            self.skipTest('PowerShell unavailable')
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        command = [pwsh, '-NoProfile', '-File', str(REPO / 'scripts/install.ps1'),
                   '-SourcePath', str(self.source), '-ProjectPath', str(self.project), '-NoSkills']
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        # A downloaded script has no PSScriptRoot; emulate irm | iex with raw script text.
        command_text = (
            "$ErrorActionPreference='Stop'; "
            "& ([scriptblock]::Create((Get-Content -LiteralPath $env:KIT_SCRIPT -Raw))) "
            "-SourcePath $env:KIT_SOURCE -ProjectPath $env:KIT_PROJECT -Update -Stack ''"
        )
        env.update(KIT_SCRIPT=str(REPO / 'scripts/install.ps1'),
                   KIT_SOURCE=str(self.source), KIT_PROJECT=str(self.project))
        result = subprocess.run([pwsh, '-NoProfile', '-Command', command_text],
                                capture_output=True, text=True, encoding='utf-8', env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.manifest()['stack'], '')

    def test_bash_pipe_entry(self):
        bash = shutil.which('bash')
        if os.name == 'nt':
            git = shutil.which('git')
            candidate = Path(git).parent.parent / 'bin/bash.exe' if git else None
            if candidate and candidate.is_file():
                bash = str(candidate)
        if not bash:
            self.skipTest('Bash unavailable')
        script = (REPO / 'scripts/install.sh').read_text(encoding='utf-8')
        # Use forward-slash Windows paths so Git Bash and Python receive the same absolute paths.
        command = [bash, '-s', '--', '--source', self.source.as_posix(),
                   '--project', self.project.as_posix(), '--no-skills']
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        # Bundled Python uses the same stdlib on both platforms, with no pip dependencies.
        env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
        result = subprocess.run(command, input=script, capture_output=True, text=True,
                                encoding='utf-8', env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.manifest()['skills'], [])

    def test_powershell_public_pipeline_with_mock_download(self):
        pwsh = shutil.which('pwsh') or shutil.which('powershell')
        if not pwsh:
            self.skipTest('PowerShell unavailable')
        # Mock only transport; the downloaded runner delegates to the actual installer
        # with a generated source fixture. The real remote ZIP flow is tested separately.
        runner = self.base / 'downloaded-runner.py'
        runner.write_text(
            "import os, runpy, sys\n"
            "sys.argv.extend(['--source', os.environ['KIT_SOURCE']])\n"
            "runpy.run_path(os.environ['KIT_CORE'], run_name='__main__')\n", encoding='utf-8')
        requests = self.base / 'requests.txt'
        env = dict(os.environ, PYTHONIOENCODING='utf-8', KIT_SOURCE=str(self.source),
                   KIT_CORE=str(REPO / 'scripts/install.py'), KIT_SCRIPT=str(REPO / 'scripts/install.ps1'),
                   KIT_REMOTE_STUB=str(runner), KIT_REQUEST_LOG=str(requests), KIT_PROJECT=str(self.project))
        command = (
            "$ErrorActionPreference='Stop'; "
            "function Invoke-RestMethod { param($Uri) Get-Content -LiteralPath $env:KIT_SCRIPT -Raw }; "
            "function Invoke-WebRequest { param($Uri,$OutFile,[switch]$UseBasicParsing,$TimeoutSec) "
            "Copy-Item -LiteralPath $env:KIT_REMOTE_STUB -Destination $OutFile; "
            "[IO.File]::WriteAllText($env:KIT_REQUEST_LOG, $Uri) }; "
            "New-Item -ItemType Directory -Path $env:KIT_PROJECT | Out-Null; "
            "Set-Location -LiteralPath $env:KIT_PROJECT; "
            "irm 'https://raw.githubusercontent.com/nodaoli/nodaoli-agent-kit/main/scripts/install.ps1' | iex"
        )
        result = subprocess.run([pwsh, '-NoProfile', '-Command', command],
                                capture_output=True, text=True, encoding='utf-8', env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / 'AGENTS.md').is_file())
        self.assertEqual(requests.read_text(),
                         'https://raw.githubusercontent.com/nodaoli/nodaoli-agent-kit/main/scripts/install.py')


if __name__ == '__main__':
    unittest.main(verbosity=2)
