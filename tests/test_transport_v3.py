import hashlib
import errno
import http.client
import io
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit
from datetime import datetime, timezone
from email.message import Message
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from contextlib import ExitStack, contextmanager
from unittest.mock import MagicMock, call, patch

from codex_science.connector_contract import QueryRequest, classify_drift, execute_connector, sha256_json
from codex_science.connectors import PubMedConnector
from codex_science.source_operations_v3 import (
    ChEMBLMoleculeSearchV3,
    EuropePMCSearchV3,
    PDBSearchV3,
    PubMedSearchV3,
)
from codex_science.transport_v3 import (
    PageRequest,
    SafeRedirectHandler,
    TransportError,
    TransportPolicy,
    TransportResponse,
    UrllibTransport,
    execute_paginated,
    replay_snapshot_directory,
)


@contextmanager
def local_chunked_response(body=b'{"resultList":{"result":[]}}', *, trailers=60, status=200,
                           phase="trailers"):
    """Drip HTTP bytes locally so each operation beats an inactivity timeout."""
    rx, tx = socket.socketpair()
    stopped = threading.Event()
    call_timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
    rx.settimeout(call_timeout)
    if phase == "body":
        tx.sendall(f"HTTP/1.1 {status} Test\r\nContent-Length: {trailers}\r\n\r\n".encode())
        piece, ending = b"x", b""
    else:
        tx.sendall(f"HTTP/1.1 {status} Test\r\nTransfer-Encoding: chunked\r\n\r\n".encode())
        if body:
            tx.sendall(f"{len(body):x}\r\n".encode() + body + b"\r\n")
        tx.sendall(b"0;" if phase == "framing" else b"0\r\n")
        piece, ending = (b"x", b"\r\n\r\n") if phase == "framing" else (b"X-T: 1\r\n", b"\r\n")

    def send_trailers():
        try:
            for _ in range(trailers):
                if stopped.wait(0.01):
                    return
                tx.sendall(piece)
            tx.sendall(ending)
        except OSError:
            pass

    sender = threading.Thread(target=send_trailers)
    response = http.client.HTTPResponse(rx, url="https://example.org")
    try:
        response.begin()
        response.url = "https://example.org"
        sender.start()
        yield response
    finally:
        stopped.set()
        response.close()
        rx.close()
        tx.close()
        if sender.ident is not None:
            sender.join(call_timeout)
            if sender.is_alive():
                raise AssertionError("local trailer sender leaked")


@contextmanager
def local_redirect_server(*, trailers=60, body=b"{}", malformed=False, slow_headers=None, header_chunks=60,
                          single_header=False):
    stopped = threading.Event()
    seen = []
    errors = []
    call_timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_GET(self):
            seen.append(self.path)
            try:
                if slow_headers == "status":
                    self.wfile.write(b"HTTP/1.1 200 ")
                    self.wfile.flush()
                    for _ in range(header_chunks):
                        if stopped.wait(0.01):
                            return
                        self.wfile.write(b"X")
                        self.wfile.flush()
                    self.wfile.write(b"\r\nContent-Length: " + str(len(body)).encode()
                                     + b"\r\nConnection: close\r\n\r\n" + body)
                    return
                redirect = self.path != "/target" and slow_headers != "initial"
                self.send_response(302 if redirect else 200)
                if slow_headers == "initial" or slow_headers == ("redirect" if redirect else "target"):
                    self.flush_headers()
                    # An incomplete line avoids the parser's header-count cap during a long drip.
                    prefix, piece, ending = ((b"X-H: ", b"1", b"\r\n") if single_header
                                             else (b"", b"X-H: 1\r\n", b""))
                    self.wfile.write(prefix)
                    self.wfile.flush()
                    for _ in range(header_chunks):
                        if stopped.wait(0.01):
                            return
                        self.wfile.write(piece)
                        self.wfile.flush()
                    self.wfile.write(ending)
                if not redirect:
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_header("Location", "/target")
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Connection", "close")
                self.end_headers()
                if malformed:
                    self.wfile.write(b"invalid\r\n")
                    return
                if body:
                    self.wfile.write(f"{len(body):x}\r\n".encode() + body + b"\r\n")
                self.wfile.write(b"0\r\n")
                self.wfile.flush()
                for _ in range(trailers):
                    if stopped.wait(0.01):
                        return
                    self.wfile.write(b"X-T: 1\r\n")
                    self.wfile.flush()
                self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                # Deadline shutdown intentionally disconnects the streaming client.
                pass
            except OSError as error:
                errors.append(error)

    class Server(HTTPServer):
        def finish_request(self, request, client_address):
            if slow_headers == "tls":
                seen.append("tls")
                try:
                    request.recv(1)
                    stopped.wait(call_timeout)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except OSError as error:
                    errors.append(error)
            else:
                super().finish_request(request, client_address)

    server = Server(("127.0.0.1", 0), Handler)
    server.socket.settimeout(call_timeout)
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01))
    original_builder = urllib.request.build_opener

    def connect(_host, **kwargs):
        connection_class = http.client.HTTPSConnection if slow_headers == "tls" else http.client.HTTPConnection
        return connection_class(*server.server_address, **kwargs)

    class LoopbackHTTPSHandler(urllib.request.HTTPSHandler):
        def https_open(self, request):
            # Keep Europe PMC URL validation and redirects; route only the connection.
            return self.do_open(connect, request, **({"context": self._context} if slow_headers == "tls" else {}))

    def build_opener(*handlers):
        local_handlers = [handler for handler in handlers if isinstance(handler, urllib.request.HTTPSHandler)]
        if local_handlers:
            for handler in local_handlers:
                handler.https_open = lambda request, handler=handler: handler.do_open(
                    connect, request, **({"context": handler._context} if slow_headers == "tls" else {}))
            return original_builder(urllib.request.ProxyHandler({}), *handlers)
        return original_builder(urllib.request.ProxyHandler({}), LoopbackHTTPSHandler(), *handlers)

    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", seen, build_opener
    finally:
        stopped.set()
        server.shutdown()
        server.server_close()
        worker.join(call_timeout)
        if worker.is_alive():
            raise AssertionError("local redirect server leaked")
        if errors:
            raise AssertionError("local redirect server socket operation failed") from errors[0]


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def send(self, request: PageRequest) -> TransportResponse:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if len(response) == 3 and isinstance(response[0], int):
            status_code, body, headers = response
        else:
            payload, headers = response
            status_code = 200
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return TransportResponse(
            status_code,
            request.url,
            headers,
            body,
            "application/json",
            "2026-07-20T00:00:00Z",
            1,
        )


class TransportV3Tests(unittest.TestCase):
    def test_slow_header_drip_stays_within_parser_limits(self):
        call_timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
        for single_header, chunks in ((False, 0), (False, 2), (True, 0),
                                      (True, http.client._MAXHEADERS), (True, http.client._MAXHEADERS + 1)):
            body = b"{}" if chunks else b""
            with self.subTest(single_header=single_header, chunks=chunks), local_redirect_server(
                trailers=0, body=body, slow_headers="target", header_chunks=chunks, single_header=single_header,
            ) as (url, seen, build_opener):
                with build_opener().open(url + "/target", timeout=call_timeout) as response:
                    self.assertEqual(body, response.read())
                    self.assertEqual(["1" * chunks] if single_header else ["1"] * chunks,
                                     response.headers.get_all("X-H", []))
                self.assertEqual(["/target"], seen)

    def test_slow_trailers_obey_attempt_deadline(self):
        timers = []
        duplicates = []
        timer_factory = threading.Timer
        duplicate_socket = socket.socket.dup

        def tracked_timer(*args, **kwargs):
            timer = timer_factory(*args, **kwargs)
            timers.append(timer)
            return timer

        def tracked_duplicate(connection):
            duplicate = duplicate_socket(connection)
            duplicates.append(duplicate)
            return duplicate

        duplicate_patch = patch.object(socket.socket, "dup", tracked_duplicate)
        duplicate_patch.start()
        self.addCleanup(lambda: self.assertTrue(all(connection.fileno() == -1 for connection in duplicates)))
        self.addCleanup(duplicate_patch.stop)
        self.addCleanup(lambda: self.assertTrue(all(not timer.is_alive() for timer in timers)))
        timer_patch = patch("threading.Timer", side_effect=tracked_timer)
        timer_patch.start()
        self.addCleanup(timer_patch.stop)
        for phase, trailers in (("trailers", 10), ("trailers", 30), ("trailers", 60),
                                ("framing", 60), ("body", 60)):
            with self.subTest(phase=phase, trailers=trailers), local_chunked_response(
                trailers=trailers, phase=phase,
            ) as response:
                opener = MagicMock()
                opener.open.return_value = response
                with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener):
                    started = time.monotonic()
                    with self.assertRaises(TransportError) as raised:
                        UrllibTransport(TransportPolicy(timeout_seconds=0.05, max_attempts=1)).send(
                            PageRequest("GET", "https://example.org", {}))
                    elapsed = time.monotonic() - started
                self.assertTrue(raised.exception.retryable)
                self.assertIn("deadline", str(raised.exception))
                self.assertLess(elapsed, 0.3)
                self.assertTrue(response.isclosed())
                self.assertTrue(all(not timer.is_alive() for timer in timers))

        # A quick or empty response at the byte limit keeps its exact body.
        for body in (b"", b"{}"):
            with self.subTest(body=body), local_chunked_response(body, trailers=0) as response:
                opener = MagicMock()
                opener.open.return_value = response
                with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener):
                    result = UrllibTransport(TransportPolicy(max_response_bytes=max(1, len(body)))).send(
                        PageRequest("GET", "https://example.org", {}))
                self.assertEqual(body, result.body)
                self.assertTrue(response.isclosed())
                self.assertTrue(all(not timer.is_alive() for timer in timers))

        # The remaining deadline includes time already spent opening the response.
        with local_chunked_response() as response:
            opener = MagicMock()
            opener.open.return_value = response
            with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener), patch(
                "codex_science.transport_v3.time.monotonic", side_effect=[0, 0.05],
            ), self.assertRaisesRegex(TransportError, "deadline"):
                UrllibTransport(TransportPolicy(timeout_seconds=0.05, max_attempts=1)).send(
                    PageRequest("GET", "https://example.org", {}))
            self.assertTrue(response.isclosed())

        with local_redirect_server() as (url, seen, build_opener), patch(
            "codex_science.transport_v3.urllib.request.build_opener", side_effect=build_opener,
        ):
            started = time.monotonic()
            with self.assertRaisesRegex(TransportError, "deadline") as raised:
                UrllibTransport(TransportPolicy(timeout_seconds=0.05, max_attempts=1)).send(
                    PageRequest("GET", url + "/redirect", {}))
            elapsed = time.monotonic() - started
            self.assertTrue(raised.exception.retryable)
            self.assertLess(elapsed, 0.3)
            self.assertEqual(["/redirect"], seen)
            self.assertTrue(all(not timer.is_alive() for timer in timers))

        for body in (b"", b"{}"):
            with self.subTest(redirect_body=body), local_redirect_server(trailers=0, body=body) as (
                url, seen, build_opener,
            ), patch("codex_science.transport_v3.urllib.request.build_opener", side_effect=build_opener):
                result = UrllibTransport(TransportPolicy(max_attempts=1)).send(
                    PageRequest("GET", url + "/redirect", {}))
                self.assertEqual(body, result.body)
                self.assertEqual(["/redirect", "/target"], seen)
                self.assertTrue(all(not timer.is_alive() for timer in timers))

        with local_redirect_server(malformed=True) as (url, seen, build_opener), patch(
            "codex_science.transport_v3.urllib.request.build_opener", side_effect=build_opener,
        ), self.assertRaises(TransportError):
            UrllibTransport(TransportPolicy(max_attempts=1)).send(PageRequest("GET", url + "/redirect", {}))
        self.assertEqual(["/redirect"], seen)

        baseline = sum(thread.name == "codex-science-http-deadline" for thread in threading.enumerate())
        for hop in ("initial", "redirect", "target", "status", "tls"):
            with self.subTest(slow_headers=hop), local_redirect_server(trailers=0, slow_headers=hop) as (
                url, seen, build_opener,
            ), patch("codex_science.transport_v3.urllib.request.build_opener", side_effect=build_opener):
                started = time.monotonic()
                with self.assertRaisesRegex(TransportError, "deadline") as raised:
                    UrllibTransport(TransportPolicy(timeout_seconds=0.05, max_attempts=1)).send(
                        PageRequest("GET", (url.replace("http:", "https:") if hop == "tls" else url)
                                    + "/redirect", {}))
                self.assertLess(time.monotonic() - started, 0.3)
                self.assertTrue(raised.exception.retryable)
                self.assertEqual(["/redirect", "/target"] if hop == "target"
                                 else (["tls"] if hop == "tls" else ["/redirect"]), seen)
                self.assertEqual(baseline, sum(thread.name == "codex-science-http-deadline"
                                               for thread in threading.enumerate()))

        with local_redirect_server(trailers=0) as (url, _seen, build_opener), patch(
            "codex_science.transport_v3.urllib.request.build_opener", side_effect=build_opener,
        ):
            port = int(url.rsplit(":", 1)[1])
            addresses = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", candidate))
                         for candidate in (0, port)]
            with patch("codex_science.transport_v3.socket.getaddrinfo", return_value=addresses):
                result = UrllibTransport(TransportPolicy(max_attempts=1)).send(PageRequest("GET", url + "/target", {}))
                self.assertEqual(b"{}", result.body)
            socket_class = socket.socket
            families = []

            class FamilySocket(socket_class):
                def __init__(self, family=-1, type=-1, proto=-1, fileno=None):
                    if fileno is None:
                        families.append(family)
                        if family == socket.AF_INET6:
                            raise OSError(errno.EAFNOSUPPORT, "unsupported address family")
                    super().__init__(family, type, proto, fileno)

            unsupported = (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("::1", port, 0, 0))
            with patch("codex_science.transport_v3.socket.getaddrinfo", return_value=[unsupported, addresses[1]]), \
                    patch("codex_science.transport_v3.socket.socket", FamilySocket):
                with socket.create_connection(("127.0.0.1", port),
                                              timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))):
                    pass
                self.assertEqual([socket.AF_INET6, socket.AF_INET], families)
                families.clear()
                result = UrllibTransport(TransportPolicy(max_attempts=1)).send(PageRequest("GET", url + "/target", {}))
                self.assertEqual(b"{}", result.body)
                self.assertEqual([socket.AF_INET6, socket.AF_INET], families)
                families.clear()
                with patch("codex_science.transport_v3.socket.getaddrinfo", return_value=[unsupported]), \
                        self.assertRaisesRegex(TransportError, "unsupported address family"):
                    UrllibTransport(TransportPolicy(max_attempts=1)).send(PageRequest("GET", url + "/target", {}))
                self.assertEqual([socket.AF_INET6], families)
            for answers in ([], addresses[:1]):
                with self.subTest(addresses=answers), patch(
                    "codex_science.transport_v3.socket.getaddrinfo", return_value=answers,
                ), self.assertRaises(TransportError):
                    UrllibTransport(TransportPolicy(max_attempts=1)).send(PageRequest("GET", url + "/target", {}))
            with patch("codex_science.transport_v3.socket.getaddrinfo", side_effect=socket.gaierror("bad address")), \
                    self.assertRaisesRegex(TransportError, "bad address"):
                UrllibTransport(TransportPolicy(max_attempts=1)).send(PageRequest("GET", url + "/target", {}))
            self.assertEqual(baseline, sum(thread.name == "codex-science-http-deadline"
                                           for thread in threading.enumerate()))
            self.assertTrue(all(not timer.is_alive() for timer in timers))

            from codex_science.transport_v3 import _DeadlineHTTPHandler
            call_timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
            attempts = []
            failed_sockets = []
            exhaust_budget = True

            class SlowSocket(socket_class):
                def connect(self, _endpoint):
                    attempts.append(self.gettimeout())
                    failed_sockets.append(self)
                    threading.Event().wait(self.gettimeout() if exhaust_budget else 0.001)
                    raise TimeoutError(f"slow address {len(attempts)}")

            with patch("codex_science.transport_v3.socket.getaddrinfo", return_value=[addresses[0]] * 3), \
                    patch("codex_science.transport_v3.socket.socket", SlowSocket):
                started = time.monotonic()
                with ExitStack() as stack, self.assertRaises(TimeoutError):
                    _DeadlineHTTPHandler(started + 0.04)._connect(("127.0.0.1", port), 1, None, stack)
                elapsed = time.monotonic() - started
                self.assertEqual(1, len(attempts))
                self.assertLess(elapsed, 0.1)
                self.assertTrue(all(connection.fileno() == -1 for connection in failed_sockets))
                attempts.clear()
                failed_sockets.clear()
                exhaust_budget = False
                with ExitStack() as stack, self.assertRaisesRegex(TimeoutError, "slow address 3"):
                    _DeadlineHTTPHandler(time.monotonic() + call_timeout)._connect(
                        ("127.0.0.1", port), call_timeout, None, stack)
                self.assertEqual(3, len(attempts))
                self.assertTrue(all(connection.fileno() == -1 for connection in failed_sockets))
            with ExitStack() as stack:
                connection = _DeadlineHTTPHandler(time.monotonic() + call_timeout)._connect(
                    ("127.0.0.1", port), call_timeout, ("127.0.0.1", 0), stack)
                try:
                    self.assertEqual("127.0.0.1", connection.getsockname()[0])
                finally:
                    connection.close()
            for deadline in (0, -1):
                with self.subTest(deadline=deadline), ExitStack() as stack, patch(
                    "codex_science.transport_v3.socket.getaddrinfo", return_value=addresses,
                ), patch("codex_science.transport_v3.time.monotonic", return_value=0), \
                        self.assertRaisesRegex(TimeoutError, "deadline"):
                    _DeadlineHTTPHandler(deadline)._connect(("127.0.0.1", port), 1, None, stack)

        # Preserve unrelated read errors and retire the watchdog on that path too.
        with local_chunked_response(trailers=0) as response:
            opener = MagicMock()
            opener.open.return_value = response
            with patch.object(response, "read", side_effect=OSError("broken read")), patch(
                "codex_science.transport_v3.urllib.request.build_opener", return_value=opener,
            ), self.assertRaisesRegex(TransportError, "broken read"):
                UrllibTransport(TransportPolicy(max_attempts=1)).send(PageRequest("GET", "https://example.org", {}))
            self.assertTrue(response.isclosed())

    def test_short_http_bodies_are_transport_failures(self):
        payload = b'{"esearchresult":{"count":"1","idlist":["1"]}}'

        class Socket:
            def makefile(self, *_args):
                return io.BytesIO(wire)

        request = QueryRequest("pubmed", "search", {"query": "x"}, source_contract_version="3")
        for declared in (len(payload) + 1, 1000):
            wire = b"HTTP/1.1 200 OK\r\nContent-Length: " + str(declared).encode() + b"\r\n\r\n" + payload
            response = http.client.HTTPResponse(Socket(), url="https://example.org")
            response.begin()
            response.url = "https://example.org"
            opener = MagicMock()
            opener.open.return_value = response
            with self.subTest(declared=declared), patch(
                "codex_science.transport_v3.urllib.request.build_opener", return_value=opener
            ):
                result = execute_paginated(PubMedSearchV3(), request,
                    transport=UrllibTransport(TransportPolicy(max_attempts=1)))
            self.assertEqual("source-unavailable", result.receipt.status)
            self.assertEqual(0, result.receipt.fetched_pages)
            self.assertIn("incomplete", result.receipt.warnings[0])
        for body, declared in ((b"", "0"), (payload, str(len(payload))),
                               (payload, " " + str(len(payload)) + " ")):
            opener, _ = self._retry_opener(None)
            opener.open.side_effect = None
            response = opener.open.return_value
            response.read.return_value = body
            response.headers["Content-Length"] = declared
            with self.subTest(body=body, declared=declared), patch(
                "codex_science.transport_v3.urllib.request.build_opener", return_value=opener
            ):
                result = UrllibTransport(TransportPolicy(max_response_bytes=max(1, len(body)))).send(
                    PageRequest("GET", "https://example.org", {}))
                self.assertEqual(body, result.body)
        for declared in ("", "invalid", "-1", "1.5", "9" * 5000):
            opener, _ = self._retry_opener(None)
            opener.open.side_effect = None
            opener.open.return_value.headers["Content-Length"] = declared
            with self.subTest(declared=declared), patch(
                "codex_science.transport_v3.urllib.request.build_opener", return_value=opener
            ), self.assertRaisesRegex(TransportError, "invalid Content-Length"):
                UrllibTransport().send(PageRequest("GET", "https://example.org", {}))
        for method, status, extra in (("HEAD", 200, {}), ("GET", 204, {}), ("GET", 304, {}),
                                      ("GET", 200, {"Transfer-Encoding": "chunked"})):
            opener, _ = self._retry_opener(None)
            opener.open.side_effect = None
            response = opener.open.return_value
            response.status = status
            response.read.return_value = b""
            response.headers.update({"Content-Length": "1000", **extra})
            with self.subTest(method=method, status=status, extra=extra), patch(
                "codex_science.transport_v3.urllib.request.build_opener", return_value=opener
            ):
                self.assertEqual(b"", UrllibTransport().send(PageRequest(method, "https://example.org", {})).body)

    def test_chunked_transfer_codings_ignore_content_length(self):
        for value in ("chunked", "gzip, chunked", "gzip, CHUNKED", " chunked , gzip "):
            opener, _ = self._retry_opener(None)
            opener.open.side_effect = None
            opener.open.return_value.headers.update({"Content-Length": "1000", "Transfer-Encoding": value})
            with self.subTest(value=value), patch(
                "codex_science.transport_v3.urllib.request.build_opener", return_value=opener
            ):
                result = UrllibTransport(TransportPolicy(max_attempts=1)).send(
                    PageRequest("GET", "https://example.org", {}))
                self.assertEqual(b"{}", result.body)
        for value in ("", "identity", "gzip", "gzip; chunked"):
            opener, _ = self._retry_opener(None)
            opener.open.side_effect = None
            opener.open.return_value.headers.update({"Content-Length": "1000", "Transfer-Encoding": value})
            with self.subTest(value=value), patch(
                "codex_science.transport_v3.urllib.request.build_opener", return_value=opener
            ), self.assertRaises(TransportError):
                UrllibTransport(TransportPolicy(max_attempts=1)).send(PageRequest("GET", "https://example.org", {}))

    def test_incomplete_read_uses_transport_failure_path(self):
        opener, _ = self._retry_opener(None)
        opener.open.side_effect = None
        opener.open.return_value.read.side_effect = http.client.IncompleteRead(b"{", 10)
        with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener):
            with self.assertRaises(TransportError):
                UrllibTransport(TransportPolicy(max_attempts=1)).send(PageRequest("GET", "https://example.org", {}))
        opener.open.return_value.read.side_effect = [http.client.IncompleteRead(b"{", 10), b"{}"]
        with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener):
            result = UrllibTransport(TransportPolicy(max_attempts=2, backoff_seconds=(0, 0))).send(
                PageRequest("GET", "https://example.org", {}))
        self.assertEqual(2, result.attempts)
        self.assertEqual(b"{}", result.body)

    def test_snapshot_reuse_is_refused_before_transport_or_writes(self):
        request = QueryRequest("pubmed", "search", {"query": "x"}, page_size=1,
                               max_pages=3, source_contract_version="3")
        pages = [({"esearchresult": {"count": "2", "retstart": str(i), "idlist": [str(i)]}}, {})
                 for i in range(2)]
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            execute_paginated(PubMedSearchV3(), request, transport=FakeTransport(pages), snapshot_dir=root)
            before = {p.name: p.read_bytes() for p in (root / request.query_id).iterdir()}
            transport = FakeTransport([({"esearchresult": {"count": "1", "idlist": ["new"]}}, {})])
            with self.assertRaisesRegex(ValueError, "snapshot already exists"):
                execute_paginated(PubMedSearchV3(), request, transport=transport, snapshot_dir=root)
            self.assertEqual([], transport.requests)
            self.assertEqual(before, {p.name: p.read_bytes() for p in (root / request.query_id).iterdir()})
            self.assertEqual(2, len(replay_snapshot_directory(root, request.query_id)))
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            failed = execute_paginated(PubMedSearchV3(), request,
                transport=FakeTransport([TransportError("temporary outage")]), snapshot_dir=root)
            self.assertEqual("source-unavailable", failed.receipt.status)
            self.assertEqual(0, failed.receipt.fetched_pages)
            self.assertFalse((root / request.query_id).exists())
            retried = execute_paginated(PubMedSearchV3(), request, transport=FakeTransport(pages), snapshot_dir=root)
            self.assertEqual("complete", retried.receipt.status)
            with self.assertRaisesRegex(ValueError, "remove.*directory.*new snapshot"):
                execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([]), snapshot_dir=root)
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            failed = execute_paginated(PubMedSearchV3(), request,
                transport=FakeTransport([pages[0], TransportError("later outage")]), snapshot_dir=root)
            self.assertEqual(1, failed.receipt.fetched_pages)
            with self.assertRaisesRegex(ValueError, "snapshot already exists"):
                execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([]), snapshot_dir=root)
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)

            class ResidueTransport:
                def send(self, page_request):
                    (root / request.query_id / "page-0000.body").write_bytes(b"unpublished")
                    raise TransportError("outage after another writer left a file")

            failed = execute_paginated(PubMedSearchV3(), request, transport=ResidueTransport(), snapshot_dir=root)
            self.assertEqual("source-unavailable", failed.receipt.status)
            self.assertEqual(b"unpublished", (root / request.query_id / "page-0000.body").read_bytes())
            with self.assertRaisesRegex(ValueError, "snapshot already exists"):
                execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([]), snapshot_dir=root)
        for residue in (None, b"unpublished"):
            with self.subTest(residue=residue), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                reserved = root / request.query_id
                reserved.mkdir()
                if residue is not None:
                    (reserved / "page-0000.body").write_bytes(residue)
                with self.assertRaisesRegex(ValueError, "snapshot already exists"):
                    execute_paginated(PubMedSearchV3(), request, transport=FakeTransport(pages), snapshot_dir=root)
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            outer = self

            class CompetingTransport(FakeTransport):
                def send(self, page_request):
                    with outer.assertRaisesRegex(ValueError, "snapshot already exists"):
                        execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([]), snapshot_dir=root)
                    return super().send(page_request)

            execute_paginated(PubMedSearchV3(), request, transport=CompetingTransport(pages), snapshot_dir=root)
            self.assertEqual(2, len(replay_snapshot_directory(root, request.query_id)))
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with patch.object(Path, "write_text", side_effect=OSError("interrupted metadata write")):
                with self.assertRaisesRegex(OSError, "interrupted"):
                    execute_paginated(PubMedSearchV3(), request, transport=FakeTransport(pages), snapshot_dir=root)
            self.assertTrue((root / request.query_id / "page-0000.body").is_file())
            self.assertFalse((root / request.query_id / "page-0000.json").exists())
            with self.assertRaisesRegex(ValueError, "snapshot already exists"):
                execute_paginated(PubMedSearchV3(), request, transport=FakeTransport(pages), snapshot_dir=root)
            with self.assertRaisesRegex(ValueError, "no snapshot pages"):
                replay_snapshot_directory(root, request.query_id)

    def test_pubmed_duplicate_ids_within_page_are_schema_drift(self):
        request = QueryRequest("pubmed", "search", {"query": "x"}, page_size=10,
                               max_pages=1, source_contract_version="3")
        for ids in (["1", "1"], ["1", "1", "2"], ["1", "2", "1"]):
            payload = {"esearchresult": {"count": str(len(ids)), "idlist": ids}}
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, "schema-drift:.*duplicate PMIDs"):
                execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([(payload, {})]))
        for ids in ([], ["1"], [str(i) for i in range(10)]):
            payload = {"esearchresult": {"count": str(len(ids)), "idlist": ids}}
            result = execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([(payload, {})]))
            self.assertEqual("complete" if ids else "negative", result.receipt.status)
            self.assertEqual(tuple(ids), result.receipt.returned_record_ids)

    def test_overlapping_page_identities_are_schema_drift(self):
        for operation, pages in (
            (PubMedSearchV3(), [
                {"esearchresult": {"count": "2", "retstart": "0", "idlist": ["1"]}},
                {"esearchresult": {"count": "2", "retstart": "1", "idlist": ["1"]}},
            ]),
            (PDBSearchV3(), [
                {"total_count": 2, "result_set": [{"identifier": "1ABC"}]},
                {"total_count": 2, "result_set": [{"identifier": "1ABC"}]},
            ]),
            (ChEMBLMoleculeSearchV3(), [
                {"molecules": [{"molecule_chembl_id": "CHEMBL1"}], "page_meta": {"next": "?offset=1"}},
                {"molecules": [{"molecule_chembl_id": "CHEMBL1"}], "page_meta": {"next": None}},
            ]),
        ):
            request = QueryRequest(operation.source, "search", {"query": "x"}, page_size=1,
                                   max_pages=3, source_contract_version="3")
            with self.subTest(source=operation.source), self.assertRaisesRegex(ValueError, "schema-drift:.*overlapping record"):
                execute_paginated(operation, request, transport=FakeTransport([(p, {}) for p in pages]))

    def test_stable_page_identities_allow_empty_and_distinct_records(self):
        cases = (
            (PDBSearchV3(), lambda ids: {"total_count": len(ids), "result_set": [{"identifier": i} for i in ids]}),
            (ChEMBLMoleculeSearchV3(), lambda ids: {
                "molecules": [{"molecule_chembl_id": i} for i in ids], "page_meta": {"next": None}}),
        )
        for operation, payload in cases:
            request = QueryRequest(operation.source, "search", {"query": "x"}, page_size=2,
                                   source_contract_version="3")
            for ids in ([], ["0"], ["0", "1"]):
                with self.subTest(source=operation.source, ids=ids):
                    result = execute_paginated(operation, request, transport=FakeTransport([(payload(ids), {})]))
                    self.assertEqual("complete" if ids else "negative", result.receipt.status)
                    self.assertEqual(tuple(ids), result.receipt.returned_record_ids)
            with self.subTest(source=operation.source), self.assertRaisesRegex(ValueError, "schema-drift:.*overlapping record"):
                execute_paginated(operation, request, transport=FakeTransport([(payload(["0", "0"]), {})]))

        pages = [
            {"hitCount": 2, "nextCursorMark": "next", "resultList": {"result": [{"id": "1", "source": "MED"}]}},
            {"hitCount": 2, "nextCursorMark": "next", "resultList": {"result": [{"id": "1", "source": "PMC"}]}},
        ]
        request = QueryRequest("europepmc", "search", {"query": "x"}, page_size=1,
                               max_pages=2, source_contract_version="3")
        result = execute_paginated(EuropePMCSearchV3(), request, transport=FakeTransport([(p, {}) for p in pages]))
        self.assertEqual("complete", result.receipt.status)
        self.assertEqual(["MED", "PMC"], [r["source"] for r in result.records])

    def test_europepmc_duplicate_pages_remain_available_to_callers(self):
        for source in ("", "MED"):
            for titles in (("one", "one"), ("one", "two")):
                records = [{"id": "0", "source": source, "title": title} for title in titles]
                for pages in (
                    [{"hitCount": 2, "resultList": {"result": records}}],
                    [{"hitCount": 2, "nextCursorMark": "next", "resultList": {"result": [r]}} for r in records],
                ):
                    request = QueryRequest("europepmc", "search", {"query": "x"}, page_size=2,
                                           max_pages=2, source_contract_version="3")
                    with self.subTest(source=source, titles=titles, pages=len(pages)):
                        result = execute_paginated(EuropePMCSearchV3(), request,
                            transport=FakeTransport([(p, {}) for p in pages]))
                        self.assertEqual("complete", result.receipt.status)
                        self.assertEqual(("0", "0"), result.receipt.returned_record_ids)
                        self.assertEqual(list(titles), [r["title"] for r in result.records])

    def test_unenforced_cutoffs_warn_and_never_claim_completion(self):
        cases = (
            (PDBSearchV3(), {"total_count": 1, "result_set": [{"identifier": "1ABC"}]}),
            (ChEMBLMoleculeSearchV3(), {"molecules": [{"molecule_chembl_id": "CHEMBL1"}], "page_meta": {"next": None}}),
            (PDBSearchV3(), {"total_count": 0, "result_set": []}),
            (ChEMBLMoleculeSearchV3(), {"molecules": [], "page_meta": {"next": None}}),
        )
        for operation, payload in cases:
            for cutoff in (None, "2026-01-01"):
                with self.subTest(source=operation.source, payload=payload, cutoff=cutoff):
                    request = QueryRequest(operation.source, "search", {"query": "x"},
                        evidence_cutoff=cutoff, source_contract_version="3")
                    fake = FakeTransport([(payload, {})])
                    result = execute_paginated(operation, request, transport=fake)
                    self.assertEqual(1, len(fake.requests))
                    if cutoff:
                        self.assertEqual("bounded-by-user", result.receipt.status)
                        self.assertEqual("bounded-by-user", result.receipt.completeness)
                        self.assertEqual("partial", result.receipt.missingness)
                        self.assertEqual((f"evidence cutoff was not enforced by source: {operation.source}",), result.receipt.warnings)
                    else:
                        self.assertIn(result.receipt.status, ("complete", "negative"))
                        self.assertEqual((), result.receipt.warnings)

    def test_unenforced_cutoffs_preserve_page_bounds_and_transport_failures(self):
        request = QueryRequest("pdb", "search", {"query": "x"}, evidence_cutoff="2026-01-01",
                               page_size=1, source_contract_version="3")
        for response, expected in (
            (({"total_count": 2, "result_set": [{"identifier": "1ABC"}]}, {}), "bounded-by-user"),
            ((204, b"", {}), "bounded-by-user"),
            (TransportError("offline"), "source-unavailable"),
            (TransportError("HTTP 429", status_code=429), "partial-rate-limit"),
        ):
            with self.subTest(expected=expected):
                result = execute_paginated(PDBSearchV3(), request, transport=FakeTransport([response]))
                self.assertEqual(expected, result.receipt.status)
                self.assertIn("evidence cutoff was not enforced", result.receipt.warnings[0])

        for operation, payload in (
            (PubMedSearchV3(), {"esearchresult": {"count": "1", "idlist": ["1"]}}),
            (EuropePMCSearchV3(), {"hitCount": 1, "resultList": {"result": [{"id": "1", "source": "MED"}]}}),
        ):
            request = QueryRequest(operation.source, "search", {"query": "x"},
                evidence_cutoff="2026-01-01", source_contract_version="3")
            fake = FakeTransport([(payload, {})])
            result = execute_paginated(operation, request, transport=fake)
            self.assertEqual("complete", result.receipt.status)
            self.assertEqual((), result.receipt.warnings)
            params = parse_qs(urlsplit(fake.requests[0].url).query)
            if operation.source == "pubmed":
                self.assertEqual(["2026/01/01"], params["maxdate"])
                self.assertEqual(["1000/01/01"], params["mindate"])
                self.assertEqual(["pdat"], params["datetype"])
            else:
                self.assertEqual(["(x) AND FIRST_PDATE:[* TO 2026-01-01]"], params["query"])

    def test_pubmed_cutoff_conflicts_are_refused_before_io(self):
        for key, values in (
            ("maxdate", ("2027/01/01", "invalid", "2026/02/30", "2025/01-01", "2025-01/01", "0000", 0)),
            ("mindate", ("2026/01/02", "invalid", "2026/13", "2025/01-01", "2025-01/01", "0000", 0)),
            ("datetype", ("edat", "invalid", 0)),
        ):
            for value in values:
                request = QueryRequest("pubmed", "search", {"query": "x", key: value},
                    evidence_cutoff="2026-01-01", source_contract_version="3")
                fake = FakeTransport([({"esearchresult": {"count": "0", "idlist": []}}, {})])
                with self.subTest(key=key, value=value):
                    with self.assertRaisesRegex(ValueError, rf"evidence-cutoff-conflict:.*parameters\.{key}"):
                        execute_paginated(PubMedSearchV3(), request, transport=fake)
                    self.assertEqual([], fake.requests)

        for extra, expected_mindate in (
            ({}, None), ({"maxdate": "2026/01/01"}, None), ({"maxdate": "2026-01-01"}, None),
            ({"maxdate": "2026/1/1"}, None), ({"mindate": "2025-1-1"}, "2025/01/01"),
            ({"mindate": "2025/01/01"}, "2025/01/01"), ({"mindate": "2026/01/01"}, "2026/01/01"),
            ({"datetype": "pdat"}, None), ({"mindate": "2025"}, "2025/01/01"),
            ({"mindate": "2026/01"}, "2026/01/01"),
            ({"mindate": None, "maxdate": "", "datetype": ""}, None),
        ):
            request = QueryRequest("pubmed", "search", {"query": "x", **extra},
                evidence_cutoff="2026-01-01", source_contract_version="3")
            with self.subTest(extra=extra):
                params = parse_qs(urlsplit(PubMedSearchV3().first_request(request).url).query)
                self.assertEqual(["2026/01/01"], params["maxdate"])
                self.assertEqual(["pdat"], params["datetype"])
                self.assertEqual([expected_mindate or "1000/01/01"], params["mindate"])
        for cutoff, extra in (
            ("2026", {"mindate": "2026/12/31", "maxdate": "2026/12/31"}),
            ("2026/02", {"mindate": "2026/02/28", "maxdate": "2026/02/28"}),
            (None, {"maxdate": "2027/01/01", "datetype": "edat"}),
        ):
            request = QueryRequest("pubmed", "search", {"query": "x", **extra},
                evidence_cutoff=cutoff, source_contract_version="3")
            with self.subTest(cutoff=cutoff, extra=extra):
                params = parse_qs(urlsplit(PubMedSearchV3().first_request(request).url).query)
                self.assertEqual([extra["maxdate"]], params["maxdate"])
                self.assertEqual([extra.get("datetype", "pdat")], params["datetype"])

    def test_pubmed_narrower_maxdates_remain_normalized_within_cutoff(self):
        for value, expected in (
            ("2025/1/1", "2025/01/01"), ("2025-01-01", "2025/01/01"),
            ("2025", "2025/12/31"), ("0001/1/1", "0001/01/01"),
            ("2026/1/1", "2026/01/01"),
        ):
            request = QueryRequest("pubmed", "search", {"query": "x", "maxdate": value},
                evidence_cutoff="2026-01-01", source_contract_version="3")
            fake = FakeTransport([({"esearchresult": {"count": "1", "idlist": ["1"]}}, {})])
            with self.subTest(value=value):
                result = execute_paginated(PubMedSearchV3(), request, transport=fake)
                self.assertEqual("complete", result.receipt.status)
                self.assertEqual((), result.receipt.warnings)
                params = parse_qs(urlsplit(fake.requests[0].url).query)
                self.assertEqual([expected], params["maxdate"])
                self.assertEqual(["1000/01/01"], params["mindate"])
                self.assertEqual(["pdat"], params["datetype"])

    def test_pubmed_cutoff_date_pair_survives_pagination(self):
        for cutoff, extra, expected_mindate in (
            ("2026-01-01", {}, "1000/01/01"),
            ("2026-01-01", {"mindate": None}, "1000/01/01"),
            ("2026-01-01", {"mindate": ""}, "1000/01/01"),
            ("2026-01-01", {"mindate": "2025/1/1"}, "2025/01/01"),
            (None, {}, None),
        ):
            request = QueryRequest("pubmed", "search", {"query": "x", **extra},
                evidence_cutoff=cutoff, page_size=1, max_pages=2, source_contract_version="3")
            fake = FakeTransport([
                ({"esearchresult": {"count": "2", "idlist": ["1"]}}, {}),
                ({"esearchresult": {"count": "2", "retstart": "1", "idlist": ["2"]}}, {}),
            ])
            with self.subTest(cutoff=cutoff, extra=extra):
                result = execute_paginated(PubMedSearchV3(), request, transport=fake)
                self.assertEqual("complete", result.receipt.status)
                self.assertEqual(2, len(fake.requests))
                for page, sent in enumerate(fake.requests):
                    params = parse_qs(urlsplit(sent.url).query)
                    self.assertEqual([str(page)], params["retstart"])
                    if expected_mindate is not None:
                        self.assertEqual([expected_mindate], params["mindate"])
                        self.assertEqual(["2026/01/01"], params["maxdate"])
                        self.assertEqual(["pdat"], params["datetype"])
                    else:
                        self.assertNotIn("mindate", params)
                        self.assertNotIn("maxdate", params)

    def test_native_cutoff_dates_are_canonical_before_transport(self):
        for cutoff, canonical, lower in (
            ("2026-01-01", "2026/01/01", "2026/01/01"), ("2026/1/1", "2026/01/01", "2026/01/01"),
            ("2026", "2026/12/31", "2026/01/01"), ("2026/02", "2026/02/28", "2026/02/01"),
            ("2024-2-29", "2024/02/29", "2024/02/29"), ("0001-01-01", "0001/01/01", "0001/01/01"),
            ("9999-12-31", "9999/12/31", "9999/12/31"),
        ):
            for extra in ({}, {"maxdate": cutoff}, {"mindate": cutoff}):
                request = QueryRequest("pubmed", "search", {"query": "x", **extra},
                    evidence_cutoff=cutoff, source_contract_version="3")
                fake = FakeTransport([({"esearchresult": {"count": "0", "idlist": []}}, {})])
                with self.subTest(cutoff=cutoff, extra=extra):
                    result = execute_paginated(PubMedSearchV3(), request, transport=fake)
                    self.assertEqual("negative", result.receipt.status)
                    params = parse_qs(urlsplit(fake.requests[0].url).query)
                    self.assertEqual([canonical], params["maxdate"])
                    self.assertEqual([lower if "mindate" in extra else "1000/01/01"], params["mindate"])
            request = QueryRequest("europepmc", "search", {"query": "x"}, evidence_cutoff=cutoff,
                                   source_contract_version="3")
            with self.subTest(source="europepmc", cutoff=cutoff):
                params = parse_qs(urlsplit(EuropePMCSearchV3().first_request(request).url).query)
                self.assertEqual([f"(x) AND FIRST_PDATE:[* TO {canonical.replace('/', '-')}]"], params["query"])

    def test_invalid_cutoffs_are_labelled_before_io_or_snapshot_writes(self):
        for operation in (PubMedSearchV3(), EuropePMCSearchV3(), ChEMBLMoleculeSearchV3(), PDBSearchV3()):
            for cutoff in ("", 0, False, [], "invalid", "2026-02-30", "0000", "2026/13", "2026/0/1",
                           "2026/1/0", "2026/1/32", "10000/01/01", "２０２６-01-01", "2026-01-01\n",
                           "2026/01-01", "2026-01/01"):
                for extra in ({}, {"mindate": "2025/01/01"}, {"maxdate": "2026/01/01"}, {"datetype": "edat"}):
                    request = QueryRequest(operation.source, "search", {"query": "x", **extra},
                        evidence_cutoff=cutoff, source_contract_version="3")
                    fake = FakeTransport([])
                    with self.subTest(source=operation.source, cutoff=cutoff, extra=extra), tempfile.TemporaryDirectory() as temp:
                        snapshot = Path(temp) / "snapshots"
                        with self.assertRaisesRegex(ValueError, "^invalid evidence_cutoff:"):
                            execute_paginated(operation, request, transport=fake, snapshot_dir=snapshot)
                        self.assertEqual([], fake.requests)
                        self.assertFalse(snapshot.exists())
                        if getattr(operation, "enforces_evidence_cutoff", False):
                            with self.assertRaisesRegex(ValueError, "^invalid evidence_cutoff:"):
                                operation.first_request(request)

    def test_inconsistent_counts_and_stalled_cursors_are_not_complete(self):
        cases = [
            (PubMedSearchV3(), [{"esearchresult": {"count": "1", "idlist": []}}]),
            (PubMedSearchV3(), [{"esearchresult": {"count": "1", "retstart": "1", "idlist": []}}]),
            (PDBSearchV3(), [{"total_count": 1, "result_set": []}]),
            (EuropePMCSearchV3(), [{"hitCount": 1, "nextCursorMark": "*", "resultList": {"result": []}}]),
            (EuropePMCSearchV3(), [{"hitCount": 2, "nextCursorMark": "*", "resultList": {"result": [{"id": "1"}]}}]),
            (EuropePMCSearchV3(), [{"hitCount": 2, "nextCursorMark": "", "resultList": {"result": [{"id": "1"}]}}]),
            (PubMedSearchV3(), [
                {"esearchresult": {"count": "2", "idlist": ["1"]}},
                {"esearchresult": {"count": "2", "retstart": "1", "idlist": []}},
            ]),
            (PDBSearchV3(), [{"total_count": 2, "result_set": [{"identifier": "1"}]},
                             {"total_count": 2, "result_set": []}]),
            (EuropePMCSearchV3(), [
                {"hitCount": 3, "nextCursorMark": "next", "resultList": {"result": [{"id": "1"}]}},
                {"hitCount": 3, "nextCursorMark": "next", "resultList": {"result": [{"id": "2"}]}},
            ]),
        ]
        for operation, pages in cases:
            with self.subTest(source=operation.source, pages=pages):
                request = QueryRequest(operation.source, "search", {"query": "fixture"},
                                       page_size=2, max_pages=3, source_contract_version="3")
                with self.assertRaisesRegex(ValueError, "schema-drift"):
                    execute_paginated(operation, request, transport=FakeTransport([(page, {}) for page in pages]))
        operation = EuropePMCSearchV3()
        request = QueryRequest("europepmc", "search", {"query": "fixture"},
                               page_size=2, max_pages=2, source_contract_version="3")
        first = {"hitCount": 2, "nextCursorMark": "next", "resultList": {"result": [{"id": "1"}]}}
        second = {"hitCount": 2, "nextCursorMark": "next", "resultList": {"result": [{"id": "2"}]}}
        result = execute_paginated(operation, request, transport=FakeTransport([(first, {}), (second, {})]))
        self.assertEqual("complete", result.receipt.status)
        bounded = QueryRequest("europepmc", "search", {"query": "fixture"},
                               page_size=2, max_pages=1, source_contract_version="3")
        result = execute_paginated(operation, bounded, transport=FakeTransport([(first, {})]))
        self.assertEqual("bounded-by-user", result.receipt.status)

    def test_source_identifiers_refuse_booleans_and_non_scalar_types(self):
        cases = (
            (PubMedSearchV3(), lambda value: {"esearchresult": {"idlist": [value]}}),
            (EuropePMCSearchV3(), lambda value: {"resultList": {"result": [{"id": value}]}}),
            (ChEMBLMoleculeSearchV3(), lambda value: {"molecules": [{"molecule_chembl_id": value}]}),
            (PDBSearchV3(), lambda value: {"result_set": [{"identifier": value}]}),
        )
        for operation, payload in cases:
            for value in (True, False, None, 1.5, [], {}, ["1"]):
                with self.subTest(source=operation.source, value=value), self.assertRaises(ValueError):
                    operation.normalize(payload(value))
            for value in (0, 123, "123"):
                with self.subTest(source=operation.source, value=value):
                    self.assertEqual([str(value)], [row["id"] for row in operation.normalize(payload(value))])
            with self.subTest(source=operation.source, value=""):
                self.assertEqual([], operation.normalize(payload("")))

    def test_chembl_pagination_stays_on_initial_api_origin(self):
        operation = ChEMBLMoleculeSearchV3()
        request = QueryRequest("chembl", "search", {"query": "fixture"}, max_pages=2,
                               source_contract_version="3")
        for next_url in (
            "https://example.org/collect?offset=1", "//example.org/collect?offset=1",
            "http://www.ebi.ac.uk/chembl/api/data/molecule.json?offset=1",
            "https://www.ebi.ac.uk:444/chembl/api/data/molecule.json?offset=1",
            "https://www.ebi.ac.uk.example/collect?offset=1", "https://[bad",
            "https://www.ebi.ac.uk:bad/path", "file:///tmp/next", True, 0, {},
            "https://reader@www.ebi.ac.uk/chembl/api/data/molecule.json?offset=1",
        ):
            with self.subTest(next_url=next_url):
                payload = {"molecules": [], "page_meta": {"next": next_url}}
                transport = FakeTransport([(payload, {}), ({"molecules": [], "page_meta": {"next": None}}, {})])
                with self.assertRaisesRegex(ValueError, "schema-drift: chembl pagination"):
                    execute_paginated(operation, request, transport=transport)
                self.assertEqual(1, len(transport.requests))
        for next_url in ("/chembl/api/data/molecule.json?offset=1", "?offset=1", "next.json?offset=1",
                         "https://www.ebi.ac.uk:443/chembl/api/data/molecule.json?offset=1"):
            with self.subTest(next_url=next_url):
                first = {"molecules": [{"molecule_chembl_id": "CHEMBL1"}], "page_meta": {"next": next_url}}
                last = {"molecules": [], "page_meta": {"next": None}}
                transport = FakeTransport([(first, {}), (last, {})])
                result = execute_paginated(operation, request, transport=transport)
                self.assertEqual("complete", result.receipt.status)
                self.assertTrue(transport.requests[1].url.startswith(("https://www.ebi.ac.uk/", "https://www.ebi.ac.uk:443/")))
        for next_url in (None, ""):
            self.assertIsNone(operation.next_request(request, operation.first_request(request),
                {"page_meta": {"next": next_url}}, 0))

    def _retry_opener(self, value, status=503):
        headers = Message()
        if value is not None:
            headers["retry-after"] = value
        error = urllib.error.HTTPError("https://example.org/search", status, "Unavailable", headers, None)
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.headers = {"Content-Type": "application/json"}
        response.geturl.return_value = "https://example.org/search"
        response.read.return_value = b"{}"
        opener = MagicMock()
        opener.open.return_value = response
        opener.open.side_effect = [error, response]
        return opener, error

    def _send_retry(self, opener, policy=None):
        with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener), \
                patch("codex_science.transport_v3.time.sleep") as sleep:
            result = UrllibTransport(policy).send(PageRequest("GET", "https://example.org/search", {}))
        self.assertEqual(2, result.attempts)
        self.assertEqual(2, opener.open.call_count)
        self.assertEqual(b"{}", result.body)
        return sleep

    def test_retry_after_delta_seconds(self):
        for status in (429, 500, 503, 599):
            with self.subTest(status=status):
                opener, _ = self._retry_opener("2", status)
                self._send_retry(opener).assert_called_once_with(2)

    def test_retry_after_cap(self):
        for value in ("10", "999", "9" * 400):
            with self.subTest(value=value):
                opener, _ = self._retry_opener(value)
                self._send_retry(opener).assert_called_once_with(10)

    def test_retry_after_http_date(self):
        now = datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp()
        for value, expected in (("Thu, 29 Oct 2026 00:00:02 GMT", 2),
                                ("Thursday, 29-Oct-26 00:00:02 GMT", 2),
                                ("Thu Oct 29 00:00:02 2026", 2),
                                ("Thu, 29 Oct 2026 00:00:00 GMT", 0.5),
                                ("Thu, 29 Oct 2026 00:01:00 GMT", 10)):
            with self.subTest(value=value), patch("codex_science.transport_v3.time.time", return_value=now):
                opener, _ = self._retry_opener(value)
                self._send_retry(opener).assert_called_once_with(expected)

    def test_retry_after_invalid_or_past_falls_back_to_backoff(self):
        now = datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp()
        policy = TransportPolicy(max_retry_after_seconds=10)
        for value in (None, "", " ", "-1", "+2", "1.5", "NaN", "inf", "invalid", "٢",
                      "Thu, 29 Oct 2026 00:00:99 GMT", "Wed, 28 Oct 2026 23:59:59 GMT"):
            with self.subTest(value=value), patch("codex_science.transport_v3.time.time", return_value=now):
                opener, _ = self._retry_opener(value)
                self._send_retry(opener, policy).assert_called_once_with(0.5)

    def test_retry_after_backoff_floor_and_cap(self):
        for value, backoff, expected in (("0", 3, 3), ("1", 3, 3), ("2", 20, 20),
                                         ("999", 20, 20), ("2", 10, 10)):
            with self.subTest(value=value, backoff=backoff):
                opener, _ = self._retry_opener(value)
                policy = TransportPolicy(backoff_seconds=(0, backoff, backoff), max_retry_after_seconds=10)
                self._send_retry(opener, policy).assert_called_once_with(expected)

    def test_retry_after_policy_limit_validation(self):
        self.assertEqual(10, TransportPolicy().max_retry_after_seconds)
        for value in (True, False, -1, float("nan"), float("inf"), "invalid", None, []):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "max_retry_after_seconds"):
                UrllibTransport(TransportPolicy(max_retry_after_seconds=value))

    def test_retry_after_zero_and_configured_caps(self):
        for cap, expected in ((0, 0.5), (0.25, 0.5), (0.5, 0.5), (1.25, 1.25), (2, 2)):
            with self.subTest(cap=cap):
                opener, _ = self._retry_opener("2")
                self._send_retry(opener, TransportPolicy(max_retry_after_seconds=cap)).assert_called_once_with(expected)

    def test_retry_after_final_attempt_does_not_sleep(self):
        for attempts, expected in ((1, []), (3, [call(2), call(2)])):
            with self.subTest(attempts=attempts):
                opener, error = self._retry_opener("2")
                opener.open.side_effect = error
                policy = TransportPolicy(max_attempts=attempts)
                with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener), \
                        patch("codex_science.transport_v3.time.sleep") as sleep:
                    with self.assertRaises(TransportError) as caught:
                        UrllibTransport(policy).send(PageRequest("GET", "https://example.org/search", {}))
                self.assertEqual(503, caught.exception.status_code)
                self.assertTrue(caught.exception.retryable)
                self.assertEqual(attempts, opener.open.call_count)
                self.assertEqual(expected, sleep.call_args_list)

    def test_retry_after_applies_only_to_the_next_attempt(self):
        opener, error = self._retry_opener("2")
        opener.open.side_effect = [error, urllib.error.URLError("offline"), opener.open.return_value]
        with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener), \
                patch("codex_science.transport_v3.time.sleep") as sleep:
            result = UrllibTransport().send(PageRequest("GET", "https://example.org/search", {}))
        self.assertEqual(3, result.attempts)
        self.assertEqual(3, opener.open.call_count)
        self.assertEqual([call(2), call(1.5)], sleep.call_args_list)

    def test_retry_after_does_not_retry_other_http_errors(self):
        opener, _ = self._retry_opener("2", status=404)
        policy = TransportPolicy(max_retry_after_seconds=10)
        with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener), \
                patch("codex_science.transport_v3.time.sleep") as sleep:
            with self.assertRaises(TransportError) as caught:
                UrllibTransport(policy).send(PageRequest("GET", "https://example.org/search", {}))
        self.assertEqual(404, caught.exception.status_code)
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(1, opener.open.call_count)
        sleep.assert_not_called()

    def test_pdb_204_empty_body_is_negative_with_receipt(self) -> None:
        request = QueryRequest("pdb", "search", {"query": "no results"}, source_contract_version="3")
        result = execute_paginated(PDBSearchV3(), request, transport=FakeTransport([(204, b"", {})]))

        self.assertEqual("negative", result.receipt.status)
        self.assertEqual(1, result.receipt.fetched_pages)
        page = result.receipt.pages[0]
        self.assertEqual(204, page.status_code)
        self.assertEqual(0, page.normalized_record_count)
        self.assertEqual(0, page.response_bytes)
        self.assertEqual(hashlib.sha256(b"").hexdigest(), page.response_sha256)

    def test_pdb_204_nonempty_body_remains_schema_drift(self) -> None:
        request = QueryRequest("pdb", "search", {"query": "fixture"}, source_contract_version="3")
        with self.assertRaisesRegex(ValueError, "schema-drift: source returned invalid JSON"):
            execute_paginated(PDBSearchV3(), request, transport=FakeTransport([(204, b"not empty", {})]))

    def test_pubmed_204_empty_body_remains_schema_drift(self) -> None:
        request = QueryRequest("pubmed", "search", {"query": "fixture"}, source_contract_version="3")
        with self.assertRaisesRegex(ValueError, "schema-drift: source returned invalid JSON"):
            execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([(204, b"", {})]))

    def test_pubmed_page_fixtures_replay_stably(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures" / "pubmed_v3"
        pages = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(fixture_dir.glob("page-*.json"))]
        self.assertEqual(2, len(pages))
        request = QueryRequest(
            "pubmed", "search", {"query": "fixture query"},
            page_size=2, max_pages=3, source_contract_version="3",
        )

        results = []
        replayed = None
        for run_index in range(2):
            transport = FakeTransport([(payload, {}) for payload in pages])
            with tempfile.TemporaryDirectory() as tempdir:
                result = execute_paginated(
                    PubMedSearchV3(), request, transport=transport, snapshot_dir=Path(tempdir)
                )
                if run_index == 0:
                    replayed = replay_snapshot_directory(Path(tempdir), request.query_id)
                results.append(result)
        first, second = results
        self.assertEqual("complete", first.receipt.completeness)
        self.assertEqual(2, first.receipt.fetched_pages)
        self.assertEqual(["101", "102", "103"], [record["id"] for record in first.records])
        self.assertEqual(2, len(replayed))
        self.assertEqual(pages, [page["payload"] for page in replayed])
        self.assertEqual(first.receipt.normalized_records_sha256, second.receipt.normalized_records_sha256)
        self.assertEqual(
            [page.response_sha256 for page in first.receipt.pages],
            [page.response_sha256 for page in second.receipt.pages],
        )

    def test_pdb_empty_204_snapshot_replays_as_negative(self) -> None:
        request = QueryRequest("pdb", "search", {"query": "no results"}, source_contract_version="3")
        with tempfile.TemporaryDirectory() as tempdir:
            result = execute_paginated(
                PDBSearchV3(), request, transport=FakeTransport([(204, b"", {})]),
                snapshot_dir=Path(tempdir),
            )
            replayed = replay_snapshot_directory(Path(tempdir), request.query_id)

        self.assertEqual("negative", result.receipt.status)
        self.assertEqual(0, result.receipt.records_returned)
        self.assertEqual(1, len(replayed))
        self.assertEqual(204, replayed[0]["metadata"]["response"]["status_code"])
        self.assertIsNone(replayed[0]["payload"])

    def test_pdb_empty_204_on_later_page_remains_schema_drift(self) -> None:
        request = QueryRequest(
            "pdb", "search", {"query": "fixture"}, max_pages=2, source_contract_version="3"
        )
        first_page = {"result_set": [{"identifier": "1"}], "total_count": 2}
        with self.assertRaisesRegex(ValueError, "schema-drift: source returned invalid JSON"):
            execute_paginated(
                PDBSearchV3(), request,
                transport=FakeTransport([(first_page, {}), (204, b"", {})]),
            )

    def test_v2_classifier_reports_rehashed_normalized_record_change(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures" / "pubmed_v3"
        first_page = json.loads((fixture_dir / "page-0000.json").read_text(encoding="utf-8"))
        legacy_request = QueryRequest("pubmed", "search", {"query": "fixture query"})
        baseline = execute_connector(
            PubMedConnector(fetch_json=lambda _url: first_page),
            legacy_request,
            include_snapshot=True,
            retrieved_at="2026-07-20T00:00:00Z",
        ).snapshot()
        # This mutates a v2 normalized snapshot; source-side v3 drift is tested separately.
        drifted = json.loads(json.dumps(baseline))
        drifted["records"][0].pop("title")
        drifted["receipt"]["normalized_records_sha256"] = sha256_json(drifted["records"])
        self.assertIn("semantic-drift", classify_drift(baseline, drifted)["drift_types"])

    def test_pubmed_renamed_idlist_field_raises_named_normalization_error(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures" / "pubmed_v3"
        payload = json.loads((fixture_dir / "drift-idlist.json").read_text(encoding="utf-8"))
        request = QueryRequest(
            "pubmed", "search", {"query": "fixture query"},
            page_size=2, max_pages=3, source_contract_version="3",
        )

        with self.assertRaisesRegex(ValueError, "normalization-failed.*idlist"):
            execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([(payload, {})]))

    def test_pubmed_present_empty_idlist_remains_negative(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures" / "pubmed_v3"
        payload = json.loads((fixture_dir / "empty-result.json").read_text(encoding="utf-8"))
        request = QueryRequest("pubmed", "search", {"query": "no results"}, source_contract_version="3")

        result = execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([(payload, {})]))
        self.assertEqual("negative", result.receipt.status)
        self.assertEqual("negative", result.receipt.missingness)

    def test_europepmc_empty_page_without_cursor_remains_negative(self) -> None:
        request = QueryRequest(
            "europepmc", "search", {"query": "no results"}, source_contract_version="3"
        )
        result = execute_paginated(
            EuropePMCSearchV3(),
            request,
            transport=FakeTransport([({"hitCount": 0, "resultList": {"result": []}}, {})]),
        )
        self.assertEqual("negative", result.receipt.status)
        self.assertEqual("negative", result.receipt.missingness)

    def test_europepmc_normalize_keeps_only_valid_pmcid(self) -> None:
        base = {"id": "25203112", "source": "MED", "title": "T", "doi": "10.1/x", "firstPublicationDate": "2014-09-01"}
        records = EuropePMCSearchV3().normalize({"resultList": {"result": [
            {**base, "pmcid": "pmc4159349"},
            {**base, "id": "2", "pmcid": "4159349"},
            {**base, "id": "3"},
        ]}})
        self.assertEqual("PMC4159349", records[0]["pmcid"])
        self.assertNotIn("pmcid", records[1])
        self.assertNotIn("pmcid", records[2])
        self.assertEqual(
            {"id": "3", "title": "T", "source": "MED", "doi": "10.1/x", "publication_date": "2014-09-01",
             "url": "https://europepmc.org/article/MED/3"},
            records[2],
        )

    def test_europepmc_terminal_page_without_cursor_is_complete(self) -> None:
        request = QueryRequest(
            "europepmc", "search", {"query": "DOI:10.1038/nm.3444"},
            page_size=20, source_contract_version="3",
        )
        transport = FakeTransport([
            ({"hitCount": 1, "resultList": {"result": [{"id": "1", "source": "MED"}]}}, {}),
        ])

        result = execute_paginated(EuropePMCSearchV3(), request, transport=transport)

        self.assertEqual("complete", result.receipt.status)
        self.assertEqual(["1"], [record["id"] for record in result.records])
        self.assertEqual(1, len(result.receipt.pages))
        self.assertEqual(1, len(transport.requests))

    def test_europepmc_missing_cursor_with_unaccounted_hits_is_schema_drift(self) -> None:
        request = QueryRequest(
            "europepmc", "search", {"query": "broad query"},
            page_size=2, source_contract_version="3",
        )
        payload = {
            "hitCount": 3,
            "resultList": {"result": [{"id": "1", "source": "MED"}, {"id": "2", "source": "MED"}]},
        }

        short_request = QueryRequest(
            "europepmc", "search", {"query": "narrow query"},
            page_size=20, source_contract_version="3",
        )
        short_payload = {"hitCount": 2, "resultList": {"result": [{"id": "1", "source": "MED"}]}}
        for paged_request, page in ((request, payload), (short_request, short_payload)):
            with self.subTest(hit_count=page["hitCount"]), self.assertRaisesRegex(
                ValueError, r"^schema-drift: europepmc pagination missing nextCursorMark$"
            ):
                execute_paginated(EuropePMCSearchV3(), paged_request, transport=FakeTransport([(page, {})]))

    def test_v3_pagination_missing_keys_have_schema_drift_labels(self) -> None:
        operation = PubMedSearchV3()
        request = QueryRequest("pubmed", "search", {"query": "fixture"}, source_contract_version="3")
        first_request = operation.first_request(request)
        pubmed_cases = (
            ({}, "missing esearchresult"),
            (None, "invalid response object while reading esearchresult"),
            ({"esearchresult": None}, "invalid esearchresult: expected object"),
            ({"esearchresult": {"count": "0"}}, "missing idlist"),
            ({"esearchresult": {"count": "0", "idlist": "1"}}, "invalid idlist: expected list"),
            ({"esearchresult": {"ERROR": "Empty term"}}, "invalid response: NCBI ESearch error: Empty term"),
            ({"ERROR": "backend failure"}, "invalid response: NCBI ESearch error: backend failure"),
            ({"error": "backend failure"}, "invalid response: NCBI ESearch error: backend failure"),
        )
        for payload, detail in pubmed_cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError) as caught:
                    operation.next_request(request, first_request, payload, 0)
                self.assertEqual(f"schema-drift: pubmed pagination {detail}", str(caught.exception))

        cases = (
            (
                PubMedSearchV3(),
                QueryRequest("pubmed", "search", {"query": "fixture"}, source_contract_version="3"),
                {"esearchresult": {"idlist": []}},
                "count",
            ),
            (
                EuropePMCSearchV3(),
                QueryRequest("europepmc", "search", {"query": "fixture"}, source_contract_version="3"),
                {"resultList": {"result": [{"id": "PMC1", "source": "MED"}]}},
                "nextCursorMark",
            ),
            (
                ChEMBLMoleculeSearchV3(),
                QueryRequest("chembl", "search", {"query": "fixture"}, source_contract_version="3"),
                {"molecules": [], "page_meta": {}},
                "next",
            ),
            (
                PDBSearchV3(),
                QueryRequest("pdb", "search", {"query": "fixture"}, source_contract_version="3"),
                {"result_set": []},
                "total_count",
            ),
        )
        for operation, request, payload, missing_key in cases:
            with self.subTest(source=operation.source, key=missing_key):
                message = rf"^schema-drift: {operation.source} pagination missing {missing_key}$"
                with self.assertRaisesRegex(ValueError, message):
                    execute_paginated(operation, request, transport=FakeTransport([(payload, {})]))

    def test_missing_record_identifiers_are_skipped_and_pdb_ids_are_stringified(self) -> None:
        europepmc = EuropePMCSearchV3().normalize({
            "resultList": {"result": [{"title": "no id"}, {"id": "PMC1", "source": "MED"}]}
        })
        chembl = ChEMBLMoleculeSearchV3().normalize({
            "molecules": [{"pref_name": "no id"}, {"molecule_chembl_id": "CHEMBL1"}]
        })
        pdb = PDBSearchV3().normalize({"result_set": [{}, {"identifier": 1234}]})

        self.assertEqual(["PMC1"], [record["id"] for record in europepmc])
        self.assertEqual(["CHEMBL1"], [record["id"] for record in chembl])
        self.assertEqual(["1234"], [record["id"] for record in pdb])

    def test_redirect_handler_enforces_scheme_downgrade_and_sensitive_origin_policy(self) -> None:
        handler = SafeRedirectHandler()

        def redirect(url: str, headers: dict[str, str] | None = None):
            request = urllib.request.Request("https://example.org/start", headers=headers or {})
            return handler.redirect_request(request, None, 302, "Found", {}, url)

        self.assertIsNotNone(redirect("https://example.org/next"))
        self.assertIsNotNone(redirect("https://example.org:443/next"))
        self.assertIsNone(redirect("http://example.org/next"))
        self.assertIsNone(redirect("file:///tmp/data"))
        self.assertIsNone(redirect("ftp://example.org/data"))
        self.assertIsNone(redirect("https://other.example/next", {"X-API-Key": "secret-value"}))
        self.assertIsNone(redirect("https://example.org:444/next", {"Authorization": "secret-value"}))
        self.assertIsNotNone(redirect("https://other.example/next"))

    def test_send_maps_refused_redirect_to_non_retryable_redacted_transport_error(self) -> None:
        request = PageRequest(
            "GET", "https://example.org/start?token=query-secret",
            {"X-API-Key": "header-secret"},
        )
        handler = SafeRedirectHandler()

        class RefusingOpener:
            def open(self, req, timeout):
                redirected = handler.redirect_request(
                    req, None, 302, "Found", {}, "https://other.example/next"
                )
                if redirected is None:
                    raise urllib.error.HTTPError(
                        "https://other.example/next", 302, "Found", {}, None
                    )
                raise AssertionError("cross-origin redirect was allowed")

        with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=RefusingOpener()):
            with self.assertRaises(TransportError) as caught:
                UrllibTransport().send(request)

        self.assertFalse(caught.exception.retryable)
        self.assertNotIn("header-secret", str(caught.exception))
        self.assertNotIn("query-secret", str(caught.exception))

    def test_pubmed_fetches_all_pages_and_replays_raw_bodies(self) -> None:
        request = QueryRequest(
            "pubmed", "search", {"query": "protein folding"},
            page_size=2, max_pages=3, source_contract_version="3",
        )
        transport = FakeTransport(
            [
                ({"esearchresult": {"count": "3", "retstart": "0", "idlist": ["1", "2"]}}, {"etag": '"one"', "last-modified": "date"}),
                ({"esearchresult": {"count": "3", "retstart": "2", "idlist": ["3"]}}, {"etag": '"two"'}),
            ]
        )
        with tempfile.TemporaryDirectory() as tempdir:
            snapshot_dir = Path(tempdir)
            result = execute_paginated(PubMedSearchV3(), request, transport=transport, snapshot_dir=snapshot_dir)
            self.assertEqual("complete", result.receipt.status)
            self.assertEqual(["1", "2", "3"], [item["id"] for item in result.records])
            self.assertEqual('"one"', result.receipt.pages[0].etag)
            self.assertEqual(2, len(replay_snapshot_directory(snapshot_dir, request.query_id)))

    def test_user_page_bound_is_not_source_completion(self) -> None:
        request = QueryRequest(
            "europepmc", "search", {"query": "BRCA1"},
            page_size=1, max_pages=1, source_contract_version="3",
        )
        transport = FakeTransport(
            [({"nextCursorMark": "cursor-2", "resultList": {"result": [{"id": "1", "source": "MED"}]}}, {})]
        )
        result = execute_paginated(EuropePMCSearchV3(), request, transport=transport)
        self.assertEqual("bounded-by-user", result.receipt.status)
        self.assertEqual("partial", result.receipt.missingness)

    def test_error_statuses_remain_distinct(self) -> None:
        request = QueryRequest(
            "pubmed", "search", {"query": "x"}, source_contract_version="3"
        )
        result = execute_paginated(
            PubMedSearchV3(), request,
            transport=FakeTransport([TransportError("rate", status_code=429, retryable=True)]),
        )
        self.assertEqual("partial-rate-limit", result.receipt.status)
        self.assertEqual("partial", result.receipt.missingness)
        self.assertEqual(0, result.receipt.fetched_pages)

    def test_pubmed_search_v3_raises_on_ncbi_error_payload(self) -> None:
        request = QueryRequest("pubmed", "search", {"query": "x"}, source_contract_version="3")
        with self.assertRaisesRegex(ValueError, "NCBI ESearch error"):
            execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([({"esearchresult": {"ERROR": "Empty term"}}, {})]))

    def test_pubmed_search_v3_raises_on_missing_esearchresult(self) -> None:
        request = QueryRequest("pubmed", "search", {"query": "x"}, source_contract_version="3")
        with self.assertRaisesRegex(ValueError, "missing esearchresult"):
            execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([({"count": "0"}, {})]))

    def test_pubmed_search_v3_zero_hit_returns_empty(self) -> None:
        request = QueryRequest("pubmed", "search", {"query": "no results"}, source_contract_version="3")
        result = execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([({"esearchresult": {"count": "0", "retstart": "0", "idlist": []}}, {})]))
        self.assertEqual("negative", result.receipt.status)
        self.assertEqual(0, len(result.records))

    def test_pubmed_search_v3_ignores_errorlist_with_ids(self) -> None:
        request = QueryRequest("pubmed", "search", {"query": "x"}, source_contract_version="3")
        result = execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([({"esearchresult": {"count": "3", "retstart": "0", "idlist": ["1", "2", "3"], "errorlist": {"phrasesnotfound": ["unknown"]}}}, {})]))
        self.assertEqual(["1", "2", "3"], [record["id"] for record in result.records])


if __name__ == "__main__":
    unittest.main()
