"""Regression for the observed vendor-only VINTF packaging failure."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import vintfcheck

KEYMINT = ('aidl', 'android.hardware.security.keymint', '3', 'IKeyMintDevice/default')
FRAGMENT = b'''<manifest version="7.0" type="framework"><hal format="aidl">
<name>android.hardware.security.keymint</name><version>3</version>
<fqname>IKeyMintDevice/default</fqname></hal></manifest>'''


class RecoveryVintfTests(unittest.TestCase):
    def test_vendor_only_keymint_is_not_recovery_visible(self):
        report = vintfcheck.check_files({'vendor/etc/vintf/manifest/keymint.xml': FRAGMENT}, {KEYMINT})
        self.assertIn(KEYMINT, report['missing'])

    def test_framework_fragment_is_recovery_visible(self):
        report = vintfcheck.check_files({vintfcheck.SYSTEM_FRAGMENTS + 'keymint.xml': FRAGMENT}, {KEYMINT})
        self.assertEqual([], report['missing'])
        self.assertEqual([], report['errors'])

    def test_wrong_version_cannot_satisfy_required_keymint(self):
        report = vintfcheck.check_files({vintfcheck.SYSTEM_FRAGMENTS + 'keymint.xml':
                                         FRAGMENT.replace(b'<version>3', b'<version>2')}, {KEYMINT})
        self.assertIn(KEYMINT, report['missing'])

    def test_device_fragment_in_system_rejects_framework_loader_conflict(self):
        report = vintfcheck.check_files({vintfcheck.SYSTEM_FRAGMENTS + 'keymint.xml':
                                         FRAGMENT.replace(b'type="framework"', b'type="device"')}, {KEYMINT})
        self.assertTrue(report['errors'])
        self.assertIn(KEYMINT, report['missing'])
