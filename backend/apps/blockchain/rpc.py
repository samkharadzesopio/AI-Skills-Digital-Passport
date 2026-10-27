"""Bounded RPC transport and a shared budget for one verification operation."""
from contextlib import contextmanager
from contextvars import ContextVar
import time

import requests
from web3 import HTTPProvider


class RPCUnavailable(Exception):
    pass


class RPCDeadlineExceeded(RPCUnavailable):
    pass


_deadline = ContextVar('passport_rpc_deadline', default=None)
_sessions = ContextVar('passport_rpc_sessions', default=None)
VERIFICATION_SECONDS = 6
WORKER_SECONDS = 25


def _close_session(session):
    try:
        session.close()
    except Exception:
        # Cleanup must not mask evidence/errors or retain a request's deadline.
        pass


@contextmanager
def rpc_budget(seconds):
    current = _deadline.get()
    deadline = time.monotonic() + seconds
    token = _deadline.set(min(current, deadline) if current is not None else deadline)
    session_token = _sessions.set([]) if _sessions.get() is None else None
    try:
        yield
    finally:
        if session_token is not None:
            for session in _sessions.get():
                _close_session(session)
            _sessions.reset(session_token)
        _deadline.reset(token)


class BoundedHTTPProvider(HTTPProvider):
    """No redirects/retries; bounded body and streaming reads between deadline checks."""
    MAX_RESPONSE_BYTES = 8 * 1024 * 1024

    def __init__(self, endpoint_uri):
        super().__init__(endpoint_uri, exception_retry_configuration=None)
        self._session = requests.Session()

    def _make_request(self, method, request_data):
        deadline = min(_deadline.get() or float('inf'), time.monotonic() + 5)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RPCDeadlineExceeded()
        sessions = _sessions.get()
        if sessions is not None and self._session not in sessions:
            sessions.append(self._session)
        # read1 returns available bytes, rather than waiting to fill a large
        # chunk while a server trickles a body. Inspect the deadline every read.
        try:
            with self._session.post(
                self.endpoint_uri, data=request_data, headers=self.get_request_headers(),
                timeout=(min(1, remaining / 2), min(1, remaining / 2)),
                allow_redirects=False, stream=True,
            ) as response:
                if response.status_code != 200:
                    raise RPCUnavailable()
                body = bytearray()
                while True:
                    if time.monotonic() >= deadline:
                        raise RPCDeadlineExceeded()
                    chunk = response.raw.read1(65536, decode_content=True)
                    if time.monotonic() >= deadline:
                        raise RPCDeadlineExceeded()
                    if not chunk:
                        return bytes(body)
                    body.extend(chunk)
                    if len(body) > self.MAX_RESPONSE_BYTES:
                        raise RPCUnavailable()
        except requests.exceptions.Timeout:
            raise RPCDeadlineExceeded() from None
        except RPCUnavailable:
            raise
        except Exception:
            raise RPCUnavailable() from None
        finally:
            if sessions is None:
                _close_session(self._session)
