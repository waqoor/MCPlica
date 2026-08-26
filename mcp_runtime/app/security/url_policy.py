from urllib.parse import urljoin, urlparse


class UpstreamUrlPolicy:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Upstream base URL must be absolute http(s)")
        self.scheme = parsed.scheme
        self.hostname = parsed.hostname.lower()
        self.port = parsed.port

    def resolve(self, path: str) -> str:
        target = urljoin(self.base_url, path.lstrip("/"))
        parsed = urlparse(target)
        if parsed.scheme != self.scheme or (parsed.hostname or "").lower() != self.hostname or parsed.port != self.port:
            raise ValueError("Resolved upstream URL escaped manifest server origin")
        if parsed.username or parsed.password:
            raise ValueError("Credentials in upstream URL are forbidden")
        return target
