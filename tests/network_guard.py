"""Process-wide guard: the test suite opens no outbound network connections.

``install()`` patches ``socket.socket.connect``/``connect_ex`` and
``socket.getaddrinfo``. Loopback connections are allowed only to ports bound by
this process (the tests' own local HTTP servers), so a loopback HTTP(S) proxy
cannot relay a request to the internet either. Unix-domain sockets are unaffected.

``NetworkBlocked`` deliberately derives from ``BaseException``: application code
that turns ``except Exception`` into "source unavailable" cannot hide an
attempted connection, so the test reports an error instead of passing quietly.
Child processes (e.g. Node UI checks) are not covered by this in-process guard.
"""
import ipaddress
import socket
from threading import Lock

_lock=Lock()
_original={}
_bound_ports=set()


class NetworkBlocked(BaseException):
    """An attempted non-local connection or name lookup during tests."""


def _local(host,*,allow_unspecified=False):
    if host in (None,'','localhost'):
        return True
    try:
        address=ipaddress.ip_address(str(host).split('%')[0])
    except ValueError:
        return False
    return address.is_loopback or (allow_unspecified and address.is_unspecified)


def _check(sock,address):
    if sock.family not in (socket.AF_INET,socket.AF_INET6):
        return
    host,port=address[0],address[1]
    if _local(host) and port in _bound_ports:
        return
    raise NetworkBlocked(f'Tests may not connect to {host}:{port}; inject a stub source instead')


def _bind(sock,address):
    _original['bind'](sock,address)
    if sock.family in (socket.AF_INET,socket.AF_INET6):
        host,port=sock.getsockname()[:2]
        if _local(host,allow_unspecified=True):
            _bound_ports.add(port)


def _connect(sock,address):
    _check(sock,address)
    return _original['connect'](sock,address)


def _connect_ex(sock,address):
    _check(sock,address)
    return _original['connect_ex'](sock,address)


def _getaddrinfo(host,*args,**kwargs):
    name=host.decode() if isinstance(host,bytes) else host
    if not _local(name,allow_unspecified=True):
        raise NetworkBlocked(f'Tests may not resolve {name!r}; inject a stub source instead')
    return _original['getaddrinfo'](host,*args,**kwargs)


def install():
    """Idempotently block non-local networking for the rest of this process."""
    with _lock:
        if _original:
            return
        _original.update(bind=socket.socket.bind,connect=socket.socket.connect,
                         connect_ex=socket.socket.connect_ex,getaddrinfo=socket.getaddrinfo)
        socket.socket.bind=_bind
        socket.socket.connect=_connect
        socket.socket.connect_ex=_connect_ex
        socket.getaddrinfo=_getaddrinfo


def installed():
    return bool(_original) and socket.socket.connect is _connect


def offline_opener(request,timeout=None):
    """Injected public-source opener: every source is unavailable, with no attempt."""
    url=getattr(request,'full_url',request)
    raise OSError(f'Public sources are offline in tests: {url}')
