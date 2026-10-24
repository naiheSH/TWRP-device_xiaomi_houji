#!/usr/bin/env python3
"""Check HAL declarations at Android recovery's actual system VINTF paths.

This presence check complements cloud assemble_vintf parsing; it is not a full
VINTF compatibility, HAL registration, or device decryption test.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SYSTEM_BASE = 'system/etc/vintf/manifest.xml'
SYSTEM_FRAGMENTS = 'system/etc/vintf/manifest/'
# format, package, version, interface/instance. Omitted AIDL versions default to 1.
REQUIRED = {
    ('aidl', 'android.hardware.security.keymint', '3', 'IKeyMintDevice/default'),
    ('aidl', 'android.hardware.security.keymint', '3', 'IRemotelyProvisionedComponent/default'),
    ('aidl', 'android.hardware.security.keymint', '3', 'IKeyMintDevice/strongbox'),
    ('aidl', 'android.hardware.security.keymint', '3', 'IRemotelyProvisionedComponent/strongbox'),
    ('aidl', 'android.hardware.security.secureclock', '1', 'ISecureClock/default'),
    ('aidl', 'android.hardware.security.sharedsecret', '1', 'ISharedSecret/default'),
    ('aidl', 'android.hardware.security.sharedsecret', '1', 'ISharedSecret/strongbox'),
    ('aidl', 'android.hardware.gatekeeper', '1', 'IGatekeeper/default'),
    ('aidl', 'android.hardware.weaver', '2', 'IWeaver/default'),
    ('aidl', 'android.hardware.secure_element', '1', 'ISecureElement/eSE1'),
    ('aidl', 'android.hardware.boot', '1', 'IBootControl/default'),
    ('aidl', 'android.hardware.health', '2', 'IHealth/default'),
    ('aidl', 'android.hardware.vibrator', '1', 'IVibrator/vibratorfeature'),
    ('aidl', 'android.se.omapi', '1', 'ISecureElementService/default'),
    ('aidl', 'android.system.keystore2', '1', 'IKeystoreService/default'),
    ('hidl', 'android.hidl.manager', '1.2', 'IServiceManager/default'),
    ('hidl', 'android.hardware.health', '2.1', 'IHealth/default'),
}


def check_files(files, required=REQUIRED):
    """Accept ramdisk-relative paths mapped to bytes; vendor paths never count."""
    found = set()
    errors = []
    paths = sorted(p for p in files if p == SYSTEM_BASE or
                   (p.startswith(SYSTEM_FRAGMENTS) and p.endswith('.xml')))
    for path in paths:
        try:
            root = ET.fromstring(files[path])
            if root.tag != 'manifest' or root.get('type') != 'framework':
                raise ValueError('system VINTF must also support the ordinary framework loader')
            for hal in root.findall('hal'):
                fmt, name = hal.get('format', 'hidl'), hal.findtext('name')
                if fmt not in ('aidl', 'hidl'):
                    continue
                versions = [v.text for v in hal.findall('version')] or ['1']
                for fq in hal.findall('fqname'):
                    value = fq.text or ''
                    if fmt == 'hidl':
                        match = re.fullmatch(r'@([0-9]+\.[0-9]+)::(.+/.+)', value)
                        if not match:
                            raise ValueError('invalid HIDL fqname: ' + value)
                        found.add((fmt, name, match[1], match[2]))
                    else:
                        for version in versions:
                            found.add((fmt, name, version, value))
                for interface in hal.findall('interface'):
                    for instance in interface.findall('instance'):
                        for version in versions:
                            found.add((fmt, name, version,
                                       interface.findtext('name') + '/' + instance.text))
        except (ET.ParseError, ValueError, TypeError) as error:
            errors.append({'path': path, 'error': str(error)})
    missing = sorted(required - found)
    return {'paths': paths, 'missing': missing, 'errors': errors,
            'scope': 'System recovery VINTF declaration presence only; HAL registration is unverified.'}


def check_source(root):
    ramdisk = Path(root) / 'recovery/root'
    files = {str(p.relative_to(ramdisk)): p.read_bytes()
             for p in (ramdisk / 'system/etc/vintf').rglob('*.xml')}
    # se_omapi installs its system fragment from the upstream module at build time.
    source_required = REQUIRED - {('aidl', 'android.se.omapi', '1', 'ISecureElementService/default')}
    report = check_files(files, source_required)
    # Keep vendor originals and system copies in sync without duplicating OMAPI.
    for vendor in (ramdisk / 'vendor/etc/vintf/manifest').glob('*.xml'):
        if vendor.name == 'se_omapi.xml':
            continue
        system = ramdisk / SYSTEM_FRAGMENTS / vendor.name
        expected = vendor.read_bytes().replace(b'type="device"', b'type="framework"')
        if not system.exists() or system.read_bytes() != expected:
            report['errors'].append({'path': str(system), 'error': 'system copy differs from vendor declaration'})
    return report
