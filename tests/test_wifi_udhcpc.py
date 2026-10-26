"""Exercise DHCP callback validation without running network commands."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'wifi/houji-wifi-udhcpc-event.sh'


class UdhcpcCallbackTests(unittest.TestCase):
    def run_callback(self, address='192.0.2.2', request='s1:r1', fail_route=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / 'work'
            work.mkdir()
            (work / 'session').write_text('s1\n')
            (work / 'dhcp.request').write_text(request+'\n')
            commands = root / 'bin'
            commands.mkdir()
            mocks = {
                'getprop': 'echo running\n',
                'ifconfig': 'echo "ifconfig $*" >> "$WORK/events"\n',
                'busybox': 'echo "busybox $*" >> "$WORK/events"; [ "$FAIL_ROUTE" != 1 ]\n',
                'setprop': 'exit 0\n',
            }
            for name, content in mocks.items():
                path = commands / name
                path.write_text('#!/bin/sh\n'+content)
                path.chmod(0o755)
            script = SCRIPT.read_text().replace('PATH=/system/bin:/sbin',
                                               'PATH='+str(commands)+':/usr/bin:/bin')
            script = script.replace('work=/tmp/houji-wifi','work='+str(work))
            runner = root / 'callback.sh'
            runner.write_text(script)
            env = dict(os.environ,WORK=str(work),interface='wlan0',ip=address,
                       subnet='255.255.255.0',router='192.0.2.1',dns='192.0.2.53',
                       HOUJI_WIFI_SESSION='s1',HOUJI_WIFI_REQUEST='s1:r1',
                       FAIL_ROUTE='1' if fail_route else '0')
            result = subprocess.run(['sh',str(runner),'bound'],env=env,
                                    capture_output=True,text=True,timeout=5)
            marker = (work/'dhcp.bound').read_text() if (work/'dhcp.bound').exists() else ''
            events = (work/'events').read_text() if (work/'events').exists() else ''
            return result,marker,events

    def test_valid_options_configure_then_publish_session_marker(self):
        result,marker,events = self.run_callback()
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual('s1:r1\n',marker)
        self.assertIn('ifconfig wlan0 192.0.2.2 netmask 255.255.255.0 up',events)
        self.assertIn('busybox ip route replace default via 192.0.2.1 dev wlan0',events)

    def test_untrusted_address_cannot_become_a_command(self):
        result,marker,events = self.run_callback(address='192.0.2.2;echo injected')
        self.assertNotEqual(0,result.returncode)
        self.assertEqual('',marker)
        self.assertEqual('',events)

    def test_stale_request_does_not_touch_network(self):
        result,marker,events = self.run_callback(request='s2:r2')
        self.assertNotEqual(0,result.returncode)
        self.assertEqual('',marker)
        self.assertEqual('',events)

    def test_route_failure_cannot_publish_a_success_marker(self):
        result,marker,events = self.run_callback(fail_route=True)
        self.assertNotEqual(0,result.returncode)
        self.assertEqual('',marker)
