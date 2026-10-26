"""Run the DHCP coordinator against mock init/network commands on the host."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'wifi/houji-wifi-dhcp.sh'


class DhcpLifecycleTests(unittest.TestCase):
    def run_attempt(self, outcome, initial_worker='stopped'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / 'work'
            work.mkdir()
            (work / 'session').write_text('session1\n')
            (work / 'wpa-state').write_text('running\n')
            (work / 'worker-state').write_text(initial_worker+'\n')
            commands = root / 'bin'
            commands.mkdir()
            sources = {
                'getprop': '''case "$1" in
init.svc.wpa_supplicant) cat "$WORK/wpa-state";;
init.svc.houji.wifi-dhcp) cat "$WORK/worker-state";;
esac
''',
                'stop': 'echo stop >> "$WORK/events"\n',
                'start': '''echo start >> "$WORK/events"
case "$OUTCOME" in
success) cp "$WORK/dhcp.request" "$WORK/dhcp.ok";;
disabled) cp "$WORK/dhcp.request" "$WORK/dhcp.ok"; echo stopped > "$WORK/wpa-state";;
failed) cp "$WORK/dhcp.request" "$WORK/dhcp.failed";;
esac
''',
                'busybox': 'tool=$1; shift; exec "$tool" "$@"\n',
                'ip': 'echo "ip $*" >> "$WORK/events"\n',
                'setprop': 'exit 0\n',
                'sleep': 'exit 0\n',
                'control': 'echo "cleanup $*" >> "$WORK/events"\n',
            }
            for name, source in sources.items():
                p = commands / name
                p.write_text('#!/bin/sh\n'+source)
                p.chmod(0o755)
            source = SCRIPT.read_text().replace('#!/system/bin/sh','#!/bin/sh')
            source = source.replace('PATH=/system/bin:/sbin', 'PATH='+str(commands)+':/usr/bin:/bin')
            source = source.replace('work=/tmp/houji-wifi', 'work='+str(work))
            source = source.replace('/system/bin/houji-wifi-control', str(commands/'control'))
            runner = root / 'runner.sh'
            runner.write_text(source)
            import os
            env = dict(os.environ,WORK=str(work),OUTCOME=outcome)
            result = subprocess.run(['sh',str(runner),'wlan0'],env=env,
                                    capture_output=True,text=True,timeout=5)
            events = (work/'events').read_text() if (work/'events').exists() else ''
            return result, events

    def test_success_requires_current_running_session(self):
        result, events = self.run_attempt('success')
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual('HOUJI_WIFI_DHCP_OK\n',result.stdout)
        self.assertNotIn('cleanup',events)

    def test_stale_success_after_disable_is_rejected_and_cleaned(self):
        result, events = self.run_attempt('disabled')
        self.assertNotEqual(0,result.returncode)
        self.assertNotIn('HOUJI_WIFI_DHCP_OK',result.stdout)
        self.assertIn('cleanup dhcp-failed session1:',events)

    def test_failed_transaction_runs_cleanup(self):
        result, events = self.run_attempt('failed')
        self.assertNotEqual(0,result.returncode)
        self.assertIn('cleanup dhcp-failed session1:',events)

    def test_stopping_worker_is_not_reused(self):
        result, events = self.run_attempt('success',initial_worker='stopping')
        self.assertNotEqual(0,result.returncode)
        self.assertNotIn('start\n',events)
        self.assertNotIn('ip ',events)
