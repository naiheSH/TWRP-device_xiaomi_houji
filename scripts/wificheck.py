"""Fail closed when an experimental Wi-Fi image omits its runtime."""
import elfcheck

REQUIRED = (
    'system/bin/wpa_supplicant', 'system/bin/wpa_cli', 'system/bin/dhcpdbg',
    'system/bin/houji-wifi-control', 'system/bin/houji-wifi-dhcp',
    'system/etc/init/houji-wifi.rc', 'system/etc/wifi/houji.conf',
    'vendor/etc/wifi/kiwi_v2/WCNSS_qcom_cfg.ini',
)
EXECUTABLES = REQUIRED[:5]


def check(entries):
    missing = [name for name in REQUIRED if name not in entries]
    errors = []
    for name in EXECUTABLES:
        if name in entries and not entries[name].mode & 0o111:
            errors.append(name + ' is not executable')
    config = entries.get('system/etc/wifi/houji.conf')
    if config and b'update_config=0' not in config.data:
        errors.append('supplicant must not persist recovery credentials')
    containers = [entries.get(p) for p in ('system/bin/recovery', 'system/lib64/libgui2.so')]
    if not any(e and b'houji-wifi-dhcp ' in e.data for e in containers):
        errors.append('GUI2 does not invoke the controlled DHCP helper')
    binaries = ('system/bin/wpa_supplicant', 'system/bin/wpa_cli', 'system/bin/dhcpdbg')
    checks = elfcheck.check_entries(entries, binaries)
    failures = {name: value for name, value in checks.items()
                if value['error'] or value['missing_libraries'] or value['missing_strong_symbols']}
    return {'missing': missing, 'errors': errors, 'elf_failures': failures,
            'scope': 'Packaging only; Wi-Fi driver, association, DHCP and DNS need device validation.'}
