import logging
import sys
import re

def sanitize_sensitive_data(msg: str) -> str:
    """
    Sanitizes log messages by masking database passwords, URIs, tokens, and sensitive strings.
    """
    if not isinstance(msg, str):
        msg = str(msg)
    # Mask database connection strings (postgresql://user:pass@host:port/db)
    msg = re.sub(r'((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|oracle)://[^:]+:)[^@]+(@)', r'\1*****\2', msg, flags=re.IGNORECASE)
    # Mask password=... or secret=... in error strings or logs
    msg = re.sub(r'((?:password|passwd|pass|secret|token)\s*[:=]\s*[\'"]?)([^\s\'";]+)([\'"]?)', r'\1*****\3', msg, flags=re.IGNORECASE)
    return msg

class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_sensitive_data(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(sanitize_sensitive_data(arg) if isinstance(arg, str) else arg for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: (sanitize_sensitive_data(v) if isinstance(v, str) else v) for k, v in record.args.items()}
        return True

def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SensitiveDataFilter())
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[handler]
    )
    logger = logging.getLogger("laundry-backend")
    logger.setLevel(logging.INFO)
    logger.addFilter(SensitiveDataFilter())
    return logger

logger = setup_logging()

