"""The documented suite runs without outbound network access.

Discovery imports every test module before any test runs, so installing the
guard here applies to the whole ``python -m unittest discover -s tests`` run.
HTTP test bases install it too, for single-module runs.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import HTTPConnection
import socket
from threading import Thread
import unittest
from urllib.request import urlopen

import network_guard

network_guard.install()


class NetworkGuardTests(unittest.TestCase):
    def test_guard_is_installed_for_the_suite(self):
        self.assertTrue(network_guard.installed())

    def test_public_address_and_name_lookup_are_blocked_before_any_traffic(self):
        with socket.socket() as sock, self.assertRaises(network_guard.NetworkBlocked):
            sock.connect(('192.0.2.1',443))  # TEST-NET-1, never routed
        with socket.socket() as sock, self.assertRaises(network_guard.NetworkBlocked):
            sock.connect_ex(('192.0.2.1',443))
        with self.assertRaises(network_guard.NetworkBlocked):
            socket.getaddrinfo('sdmdataaccess.sc.egov.usda.gov',443)

    def test_loopback_port_not_served_by_this_process_is_blocked(self):
        # A loopback HTTP(S) proxy would otherwise relay requests to the internet.
        port=next(p for p in range(1,1024) if p not in network_guard._bound_ports)
        with socket.socket() as sock, self.assertRaises(network_guard.NetworkBlocked):
            sock.connect(('127.0.0.1',port))

    def test_urllib_request_is_blocked_with_or_without_proxy_settings(self):
        with self.assertRaises(network_guard.NetworkBlocked):
            urlopen('https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest',timeout=5)

    def test_this_process_loopback_server_remains_reachable(self):
        class Ok(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(204);self.end_headers()

            def log_message(self,*args):
                pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Ok)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            conn=HTTPConnection('127.0.0.1',server.server_address[1],timeout=5)
            conn.request('GET','/');self.assertEqual(conn.getresponse().status,204);conn.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':
    unittest.main()
