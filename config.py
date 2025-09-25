# URL настройки
BASE_URL = "https://www.banki.ru/services/responses/bank/gazprombank/"

# Заголовки для HTTP запросов
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Настройки парсинга по умолчанию
DEFAULT_SETTINGS = {
    'delay_min': 1.0,
    'delay_max': 3.0,
    'jitter': 0.5,
    'timeout': 10,
    'save_every_n_pages': 5,
    'max_retries': 3
}

# Папки для сохранения
OUTPUT_DIR = "out"
LOGS_DIR = "logs"