"""Exact URL allowlist, public DNS addresses and pinned TLS connections; no proxy environment."""
import http.client
import ipaddress
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit,urljoin

class FetchError(ValueError):pass

def validate_url(url,allowed):
    p=urlsplit(url)
    if url not in allowed or p.scheme!='https' or p.username or p.password or p.fragment or p.port not in (None,443) or not p.hostname:
        raise FetchError('http_url_denied')
    return p

def public_addresses(host):
    records=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    addresses=list(dict.fromkeys(r[4][0] for r in records))
    if not addresses or any(not ipaddress.ip_address(ip).is_global or ipaddress.ip_address(ip).is_multicast for ip in addresses):
        raise FetchError('http_address_denied')
    return addresses

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,address):
        super().__init__(host,timeout=8,context=ssl.create_default_context());self.address=address
    def connect(self):
        raw=socket.create_connection((self.address,443),self.timeout)
        try:self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except BaseException:raw.close();raise

def fetch(url,allowed,max_bytes=16384):
    for hop in range(4):
        p=validate_url(url,allowed);addresses=public_addresses(p.hostname)
        connection=PinnedHTTPS(p.hostname,addresses[0])
        def abort():
            if connection.sock:
                try:connection.sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
            connection.close()
        timer=threading.Timer(8,abort);timer.daemon=True;timer.start()
        try:
            connection.request('GET',p.path+('?' +p.query if p.query else '') or '/',headers={'Accept':'text/plain, application/json, text/html','Accept-Encoding':'identity','User-Agent':'AgentOps-local/0.3'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location or hop==3:raise FetchError('http_redirect_limit')
                url=urljoin(url,location);validate_url(url,allowed);continue
            if response.getheader('Content-Encoding','identity')!='identity':raise FetchError('http_content_denied')
            content_type=response.getheader('Content-Type','').split(';')[0].strip().lower()
            if not (content_type.startswith('text/') or content_type=='application/json'):raise FetchError('http_content_denied')
            body=response.read(max_bytes+1)
            if len(body)>max_bytes:raise FetchError('tool_result_limit')
            return {'url':url,'http_status':response.status,'content_type':content_type,'body':body.decode('utf8',errors='replace')}
        finally:timer.cancel();connection.close()
