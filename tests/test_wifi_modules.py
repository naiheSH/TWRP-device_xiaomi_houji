"""Exercise dependency loading without a phone or kernel module insertion."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'wifi/houji-wifi-control.sh'
LOADER = SOURCE.read_text().split('load_module() (', 1)[1].split('\nprepare()', 1)[0]
LOADER = 'load_module() (' + LOADER


class ModuleGraphTests(unittest.TestCase):
    def run_graph(self, dependencies, files, builtin=()):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            modules = root / 'modules'
            modules.mkdir()
            (modules / 'modules.dep').write_text(dependencies)
            for name in files:
                (modules / name).touch()
            sys_module = root / 'sys-module'
            sys_module.mkdir()
            for name in builtin:
                (sys_module / name).mkdir()
            # Replace only the read-only sysfs probe in this isolated fixture.
            loader = LOADER.replace('/sys/module/', str(sys_module) + '/')
            shell = '''set -eu
modules=$1
note() { echo "$*" >&2; }
insmod() { basename "$1"; }
''' + loader + '\nload_module radio.ko\n'
            return subprocess.run(['sh', '-c', shell, 'fixture', str(modules)],
                                  capture_output=True, text=True, timeout=5)

    def test_dependency_is_loaded_before_driver(self):
        r = self.run_graph('/vendor/lib/modules/radio.ko: /vendor/lib/modules/bus.ko\n'
                           '/vendor/lib/modules/bus.ko:\n', ['radio.ko', 'bus.ko'])
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(['bus.ko', 'radio.ko'], r.stdout.splitlines())

    def test_missing_dependency_fails_without_inserting_driver(self):
        r = self.run_graph('radio.ko: missing.ko\n', ['radio.ko'])
        self.assertNotEqual(0, r.returncode)
        self.assertEqual('', r.stdout)

    def test_builtin_driver_needs_no_module_file(self):
        r = self.run_graph('', [], builtin=['radio'])
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual('', r.stdout)

    def test_dependency_cycle_is_bounded(self):
        r = self.run_graph('radio.ko: bus.ko\nbus.ko: radio.ko\n', ['radio.ko', 'bus.ko'])
        self.assertNotEqual(0, r.returncode)
        self.assertIn('dependency depth exceeded', r.stderr)
