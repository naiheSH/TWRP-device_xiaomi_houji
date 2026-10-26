"""Evaluate optional product copy paths without inherited DEVICE_PATH state."""
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WifiProductPathsTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('make'), 'GNU Make is required')
    def test_copy_sources_expand_inside_the_houji_tree(self):
        # Android product inheritance does not promise parent-local variables.
        # Evaluate the actual child Makefile with an isolated inheritance stub,
        # exercising Make expansion rather than searching its text for a token.
        makefile = ('inherit-product =\n'
                    'include twrp_houji_wifi.mk\n'
                    '$(info COPIES=$(PRODUCT_COPY_FILES))\n'
                    '.PHONY: dump\ndump:\n\t@:\n')
        environment = dict(os.environ)
        for name in ('DEVICE_PATH', 'HOUJI_WIFI_PATH', 'PRODUCT_COPY_FILES',
                     'MAKEFLAGS', 'MAKEOVERRIDES', 'GNUMAKEFLAGS', 'MAKEFILES'):
            environment.pop(name, None)
        result = subprocess.run(['make', '--no-print-directory', '-f', '-', 'dump'],
                                input=makefile, text=True, capture_output=True,
                                cwd=ROOT, env=environment, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        copies = next(line.removeprefix('COPIES=') for line in result.stdout.splitlines()
                      if line.startswith('COPIES=')).split()
        self.assertTrue(copies)
        for entry in copies:
            source, destination = entry.split(':', 1)
            path = PurePosixPath(source)
            self.assertFalse(path.is_absolute(), source)
            self.assertNotIn('..', path.parts, source)
            self.assertTrue(source.startswith('device/xiaomi/houji/'), source)
            self.assertTrue((ROOT / source.removeprefix('device/xiaomi/houji/')).is_file(), source)
            self.assertTrue(destination.startswith('recovery/root/'), destination)
