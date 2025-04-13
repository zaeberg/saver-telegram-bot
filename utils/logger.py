import logging
import uuid
from functools import wraps
from contextlib import contextmanager
from contextvars import ContextVar

# Контекстная переменная для хранения request_id
request_id_var = ContextVar('request_id', default=None)

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, 'request_id'):
            record.request_id = request_id_var.get(None) or '-'
        return True

# Создаем форматтер
formatter = logging.Formatter(
    '%(asctime)s [%(request_id)s] - %(levelname)s %(name)s: - %(message)s'
)

# Создаем handler
handler = logging.StreamHandler()
handler.setFormatter(formatter)
handler.addFilter(RequestIdFilter())

# Настраиваем корневой логгер
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(handler)

# Удаляем дефолтные хендлеры
for old_handler in root_logger.handlers[:-1]:
    root_logger.removeHandler(old_handler)

# Получаем наш логгер
logger = logging.getLogger(__name__)

# Устанавливаем уровни для внешних библиотек
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

@contextmanager
def request_context(request_id: str = None):
    # Контекстный менеджер для работы с request_id
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]

    token = request_id_var.set(request_id)
    try:
        yield request_id
    finally:
        request_id_var.reset(token)

def with_request_id(func):
    # Декоратор для автоматического создания request_id
    @wraps(func)
    async def wrapper(*args, **kwargs):
        with request_context() as request_id:
            return await func(*args, **kwargs)
    return wrapper
