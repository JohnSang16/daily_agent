import logging
import re
import uuid
from collections.abc import Iterable

BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")


class RedactionFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str] = ()):
        super().__init__()
        self.secrets = [s for s in secrets if s]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = BEARER.sub(r"\1[REDACTED]", record.getMessage())
        for s in self.secrets:
            msg = msg.replace(s, "[REDACTED]")
        record.msg, record.args = msg, None
        return True


def setup_logging(secrets: Iterable[str] = ()) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter('{"t":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}')
    )
    handler.addFilter(RedactionFilter(secrets))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # these log full URLs including query strings, which can carry private text
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def new_request_id() -> str:
    return uuid.uuid4().hex
