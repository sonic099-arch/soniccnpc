"""Windows内网入口，仅Python标准库；按TCP对端IP限制全部网页与API请求。

后端仅在WSL/Windows本机127.0.0.1:8000运行。不要在本入口之前放置隐藏来源IP的端口转发。
"""
import argparse
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address, IPv4Address, IPv6Address
import json
import socket
from urllib.parse import urlsplit, urlunsplit

ALLOWED_START = '10.86.36.1'
ALLOWED_END = '10.86.36.255'
HOP_HEADERS = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
               'te', 'trailer', 'transfer-encoding', 'upgrade', 'proxy-connection'}


def client_ipv4(value):
    try:
        address = ip_address(value)
    except ValueError:
        return None
    if isinstance(address, IPv6Address):
        address = address.ipv4_mapped
    return address if isinstance(address, IPv4Address) else None


def allowed_client(value, start=ALLOWED_START, end=ALLOWED_END):
    address = client_ipv4(value)
    return address is not None and int(ip_address(start)) <= int(address) <= int(ip_address(end))


@dataclass(frozen=True)
class GatewayConfig:
    listen: str = '10.86.36.43'
    port: int = 8080
    upstream_port: int = 8000
    allowed_start: str = ALLOWED_START
    allowed_end: str = ALLOWED_END
    max_body_bytes: int = 32 * 1024 * 1024
    upstream_timeout: float = 600

    def __post_init__(self):
        values = [client_ipv4(v) for v in (self.listen, self.allowed_start, self.allowed_end)]
        if any(v is None for v in values) or int(values[1]) > int(values[2]):
            raise ValueError('监听地址和允许范围必须是有效IPv4，且范围开始不得大于结束')
        if not 0 <= self.port <= 65535 or not 1 <= self.upstream_port <= 65535:
            raise ValueError('端口不合法')


def connection_headers(headers):
    values = headers.get_all('Connection', [])
    return HOP_HEADERS | {v.strip().lower() for line in values for v in line.split(',')}


class GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'BeitianLAN/1.0'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def error(self, status, message):
        body = json.dumps({'detail': message}, ensure_ascii=False).encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)
        self.close_connection = True

    def parse_request(self):
        if not super().parse_request():
            return False
        return self.gate()

    def gate(self):
        config = self.server.config
        # 永远只信任套接字对端，不信任Forwarded/X-Forwarded-For/X-Real-IP等客户端头。
        if not allowed_client(self.client_address[0], config.allowed_start, config.allowed_end):
            self.error(403, '访问被拒绝：仅允许指定内网地址范围访问')
            return False
        host = self.headers.get_all('Host', [])
        if len(host) != 1 or host[0] != self.server.public_authority:
            self.error(403, '访问地址不正确，请使用公布的内网IP和端口')
            return False
        return True

    def handle_expect_100(self):
        if not self.gate():
            return False
        self.send_response_only(100)
        self.end_headers()
        return True

    def proxy(self):
        if not self.gate():
            return
        if not self.path.startswith('/') or self.path.startswith('//'):
            self.error(400, '请求路径无效')
            return
        if self.headers.get('Upgrade') or self.headers.get('Transfer-Encoding'):
            self.error(400, '不支持此传输方式，请使用普通HTTP请求')
            return
        lengths = self.headers.get_all('Content-Length', [])
        if len(lengths) > 1 or (lengths and not lengths[0].isascii()) or (lengths and not lengths[0].isdigit()):
            self.error(400, '请求长度无效')
            return
        if lengths and len(lengths[0]) > 10:
            self.error(413, '请求体超过允许长度')
            return
        length = int(lengths[0]) if lengths else 0
        if length > self.server.config.max_body_bytes:
            self.error(413, '请求体超过内网入口允许的32MiB上限')
            return
        config = self.server.config
        upstream = HTTPConnection('127.0.0.1', config.upstream_port, timeout=config.upstream_timeout)
        sent = False
        try:
            body = self.rfile.read(length) if length else None
            if length and len(body) != length:
                self.error(400, '请求体未完整接收')
                return
            excluded = connection_headers(self.headers) | {'host', 'expect', 'forwarded', 'x-real-ip'}
            headers = {k: v for k, v in self.headers.items() if k.lower() not in excluded and not k.lower().startswith('x-forwarded-')}
            headers['Host'] = f'127.0.0.1:{config.upstream_port}'
            headers['Connection'] = 'close'
            upstream.request(self.command, self.path, body=body, headers=headers)
            response = upstream.getresponse()
            self.send_response(response.status)
            excluded = connection_headers(response.headers) | {'server', 'date'}
            for key, value in response.getheaders():
                if key.lower() in excluded:
                    continue
                if key.lower() == 'location':
                    target = urlsplit(value)
                    if target.hostname in ('127.0.0.1', 'localhost'):
                        value = urlunsplit(('http', self.server.public_authority, target.path, target.query, target.fragment))
                self.send_header(key, value)
            # 上游chunked由http.client解码；以关闭连接标记结尾，避免传输长度歧义。
            self.send_header('Connection', 'close')
            self.end_headers()
            sent = True
            if self.command != 'HEAD':
                while chunk := response.read(64 * 1024):
                    self.wfile.write(chunk)
        except (OSError, HTTPException):
            if not sent:
                self.error(502, '无法连接本机后端，请先在Ubuntu启动 python scripts/lan.py')
        finally:
            self.close_connection = True
            upstream.close()

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = proxy

    def do_TRACE(self):
        if self.gate():
            self.error(405, '不支持此请求方法')

    do_CONNECT = do_TRACE


class GatewayServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64

    def __init__(self, config):
        self.config = config
        super().__init__((config.listen, config.port), GatewayHandler)
        self.public_authority = f'{config.listen}:{self.server_address[1]}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--listen', default='10.86.36.43')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--upstream-port', type=int, default=8000)
    args = parser.parse_args()
    try:
        config = GatewayConfig(listen=args.listen, port=args.port, upstream_port=args.upstream_port)
        with GatewayServer(config) as server:
            print(f'内网网页 http://{server.public_authority} · 接口文档 /docs', flush=True)
            print(f'只允许 {config.allowed_start}–{config.allowed_end}，按真实TCP来源检查；Ctrl+C停止', flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as exc:
        print(f'内网入口启动失败：{exc}。请确认Windows网卡地址、端口和防火墙配置。')
        raise SystemExit(1)

if __name__ == '__main__':
    main()
