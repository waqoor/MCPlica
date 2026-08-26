import re

_DNS_NAME = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def normalize_dns_hostname(value: str) -> str:
    normalized = value.strip().strip(".").casefold()
    if not _DNS_NAME.fullmatch(normalized):
        raise ValueError("value must be a DNS hostname")
    return normalized
