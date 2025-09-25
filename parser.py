import requests
from bs4 import BeautifulSoup
import json
import time
import random
import re
from datetime import datetime
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BankiRuParser:
    def __init__(self):
        self.base_url = "https://www.banki.ru/services/responses/bank/gazprombank/"
        self.api_base = "https://www.banki.ru"
        self.session = requests.Session()
        
        # Список User-Agent для ротации (различные браузеры и устройства)
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        self.current_ua_index = 0
        self.update_headers()
    
    def clean_review_text(self, text):
        """
        Очистка текста отзыва от нежелательных элементов: 
        футеров сайта, исследовательских дисклеймеров и прочего мусора
        """
        if not text or not isinstance(text, str):
            return text
        
        # Паттерны для удаления
        footer_patterns = [
            # Основной футер с QR-кодом и копирайтом
            r'\n\n?Наведите камеру своего телефона на QR-код и перейдите по ссылке\n\n?ООО ИА «Банки\.ру».*?Свидетельство на товарный знак № \d+ от \d+\.\d+\.\d+г\.',
            
            # Футер только с копирайтом (если QR-код отсутствует)
            r'\n\n?ООО ИА «Банки\.ру»\n использует файлы cookie.*?Свидетельство на товарный знак № \d+ от \d+\.\d+\.\d+г\.',
            
            # Исследовательский дисклеймер
            r'\* На основе исследований OMI \(Online Market Intelligence\) в \d{4} г\., ООО «Тибурон» и АО «ИОМ Анкетолог» в \d{4} г\.\s*',
            
            # Дополнительные варианты футера
            r'© \d{4}—\d{4} ООО ИА «Банки\.ру»\..*?обязательна\.',
            
            # Информация о cookies отдельно
            r'использует файлы cookie для повышения удобства пользователей.*?настройки браузера\.',
            
            # Условия использования
            r'Условия использованиясмотрите здесь\.',
            
            # QR-код отдельно
            r'Наведите камеру своего телефона на QR-код и перейдите по ссылке',
            
            # Свидетельство о товарном знаке
            r'Свидетельство на товарный знак № \d+ от \d+\.\d+\.\d+г\.'
        ]
        
        # Применяем паттерны для удаления
        cleaned_text = text
        for pattern in footer_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.DOTALL | re.IGNORECASE)
        
        # Удаляем лишние переносы строк и пробелы
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)  # Максимум 2 перевода строки подряд
        cleaned_text = re.sub(r'^\s+', '', cleaned_text)  # Пробелы в начале
        cleaned_text = re.sub(r'\s+$', '', cleaned_text)  # Пробелы в конце
        cleaned_text = re.sub(r'\t+', ' ', cleaned_text)  # Табы заменяем на пробелы
        
        return cleaned_text
    
    def update_headers(self):
        """Обновить заголовки с новым User-Agent"""
        self.session.headers.update({
            'User-Agent': self.user_agents[self.current_ua_index],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Sec-GPC': '1'
        })
        
        # Ротация User-Agent
        self.current_ua_index = (self.current_ua_index + 1) % len(self.user_agents)
    
    def get_page_advanced(self, page_number, antiban_mode=False):
        """Получить страницу с расширенным анализом и антибан мерами"""
        url = f"{self.base_url}?page={page_number}"
        
        try:
            # Обновляем заголовки перед каждым запросом
            self.update_headers()
            
            # Добавляем реферер для имитации естественного перехода
            if page_number > 1:
                self.session.headers['Referer'] = f"{self.base_url}?page={page_number-1}"
            else:
                self.session.headers['Referer'] = "https://www.banki.ru/services/responses/bank/gazprombank/"
            
            logger.info(f"Загружаем страницу: {url} (UA: {self.session.headers['User-Agent'][:50]}...)")
            
            # Антибан режим - дополнительная задержка
            if antiban_mode:
                extra_delay = random.uniform(2.0, 5.0)
                logger.info(f"Антибан режим: дополнительная задержка {extra_delay:.2f} сек")
                time.sleep(extra_delay)
            
            response = self.session.get(url, timeout=20)
            
            # Проверяем статус ответа
            if response.status_code == 403:
                logger.warning(f"403 Forbidden для страницы {page_number}. Возможна блокировка.")
                return None, None
            elif response.status_code == 429:
                logger.warning(f"429 Too Many Requests для страницы {page_number}. Увеличиваем задержку.")
                time.sleep(random.uniform(10.0, 20.0))
                return None, None
            
            response.raise_for_status()
            
            html = response.text
            logger.info(f"Получена страница размером {len(html)} символов")
            
            return html, None
            
        except requests.RequestException as e:
            logger.error(f"Ошибка при запросе страницы {page_number}: {e}")
            
            # Если получили блокировку, рекомендуем увеличить задержки
            if "403" in str(e) or "Forbidden" in str(e):
                logger.warning("⚠️ Обнаружена блокировка! Рекомендуется:")
                logger.warning("  1. Увеличить задержки до 10-30 секунд")
                logger.warning("  2. Включить антибан режим")
                logger.warning("  3. Попробовать позже")
            
            return None, None
    
    def parse_reviews_from_page(self, html, get_full_text=True, antiban_mode=False):
        """Улучшенный парсинг HTML для извлечения настоящих отзывов"""
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        reviews = []
        
        # Ищем настоящие отзывы по специфичным селекторам банки.ру
        review_containers = []
        
        # Используем точный селектор для контейнеров отзывов banki.ru
        specific_selectors = [
            'div.la8a5ef73',  # Основной контейнер отзыва
            'div[class*="la8a5ef73"]',  # Вариации основного контейнера
        ]
        
        for selector in specific_selectors:
            try:
                containers = soup.select(selector)
                if containers:
                    logger.info(f"Найдено {len(containers)} элементов по селектору: {selector}")
                    review_containers.extend(containers)
                    break  # Если нашли по основному селектору, не ищем дальше
            except Exception as e:
                logger.debug(f"Ошибка с селектором {selector}: {e}")
        
        # Если не нашли специфичные селекторы, ищем по ссылкам на отзывы
        if not review_containers:
            logger.info("Основные селекторы не работают, ищем отзывы по ссылкам...")
            review_containers = self.find_reviews_by_links(soup)
        else:
            logger.info(f"Используем основной селектор, найдено {len(review_containers)} контейнеров")
        
        # Обрабатываем найденные контейнеры
        processed_ids = set()  # Избегаем дубликатов по ID
        processed_urls = set()  # Избегаем дубликатов по URL
        processed_signatures = set()  # Избегаем дубликатов по подписи (дата+заголовок)
        
        for i, container in enumerate(review_containers):
            try:
                if get_full_text:
                    logger.info(f"Извлекаем отзыв {i+1}/{len(review_containers)} с полным текстом...")
                
                review = self.extract_review_data_enhanced(container, get_full_text=get_full_text, antiban_mode=antiban_mode)
                if review and self.is_valid_review(review):
                    # Многоуровневая проверка на дубликаты
                    review_id = review.get('review_id')
                    review_url = review.get('url')
                    review_signature = f"{review.get('date', '')}_{review.get('title', '')[:50]}"
                    
                    is_duplicate = False
                    
                    # Проверка по ID
                    if review_id and review_id in processed_ids:
                        logger.debug(f"Пропускаем дубликат по ID: {review_id}")
                        is_duplicate = True
                    
                    # Проверка по URL
                    if review_url and review_url in processed_urls:
                        logger.debug(f"Пропускаем дубликат по URL: {review_url}")
                        is_duplicate = True
                    
                    # Проверка по подписи (дата + заголовок)
                    if review_signature in processed_signatures:
                        logger.debug(f"Пропускаем дубликат по подписи: {review_signature}")
                        is_duplicate = True
                    
                    if not is_duplicate:
                        reviews.append(review)
                        if review_id:
                            processed_ids.add(review_id)
                        if review_url:
                            processed_urls.add(review_url)
                        processed_signatures.add(review_signature)
                    
            except Exception as e:
                logger.warning(f"Ошибка при парсинге отзыва {i+1}: {e}")
                continue
        
        logger.info(f"Извлечено {len(reviews)} уникальных отзывов")
        return reviews
    
    def find_reviews_by_links(self, soup):
        """Поиск отзывов по ссылкам на отзывы"""
        containers = []
        
        # Ищем все ссылки, которые ведут к отзывам
        review_links = soup.find_all('a', href=re.compile(r'/response/\d+'))
        
        for link in review_links:
            # Находим родительский контейнер отзыва
            container = link.find_parent(['div', 'article', 'section'])
            if container and container not in containers:
                # Проверяем, что контейнер содержит достаточно данных
                text_length = len(container.get_text(strip=True))
                if 50 < text_length < 5000:  # Разумный размер для отзыва
                    containers.append(container)
        
        logger.info(f"Найдено {len(containers)} контейнеров по ссылкам на отзывы")
        return containers[:25]  # Ограничиваем до 25 (стандартное количество на странице)
    
    def is_valid_review(self, review):
        """Проверяет, является ли найденный элемент настоящим отзывом"""
        if not review:
            return False
        
        # Должен быть заголовок или текст
        if not (review.get('title') or review.get('text')):
            return False
        
        # Текст должен быть разумного размера
        text = review.get('text', '')
        if len(text) < 10 or len(text) > 10000:
            return False
        
        # Не должен содержать слишком много навигационных элементов
        navigation_keywords = [
            'калькулятор', 'все продукты', 'банки россии', 'курс', 
            'кредитные карты', 'вклады', 'страхование', 'рко',
            'дебетовые карты', 'ипотека', 'инвестиции'
        ]
        
        title_lower = (review.get('title') or '').lower()
        text_lower = text.lower()
        
        # Если заголовок содержит навигационные слова, это не отзыв
        if any(keyword in title_lower for keyword in navigation_keywords):
            return False
        
        # Если текст состоит в основном из навигационных элементов
        nav_count = sum(1 for keyword in navigation_keywords if keyword in text_lower)
        if nav_count > 5:  # Слишком много навигационных слов
            return False
        
        return True
    
    def get_full_review_text(self, review_url, antiban_mode=False):
        """Получить полный текст отзыва со страницы отзыва с антибан защитой"""
        if not review_url:
            return None
        
        try:
            # В антибан режиме делаем дополнительную задержку
            if antiban_mode:
                extra_delay = random.uniform(1.0, 3.0)
                time.sleep(extra_delay)
            
            # Обновляем заголовки перед запросом
            self.update_headers()
            
            logger.debug(f"Загружаем полный отзыв: {review_url}")
            
            # Добавляем реферер
            headers = self.session.headers.copy()
            headers['Referer'] = self.base_url
            
            response = self.session.get(review_url, timeout=15, headers=headers)
            
            # Проверяем на блокировку
            if response.status_code == 403:
                logger.warning(f"403 при получении полного текста: {review_url}")
                return None
            elif response.status_code == 429:
                logger.warning(f"429 при получении полного текста: {review_url}")
                time.sleep(random.uniform(5.0, 10.0))
                return None
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем полный текст отзыва на странице отзыва по специфичным селекторам banki.ru
            text_selectors = [
                # Основной контейнер с текстом отзыва на странице отзыва
                'div[class*="response-text"]',
                'div[class*="review-text"]', 
                'div[class*="content-text"]',
                'div.text-content',
                '.response-body',
                '.review-body',
                # Параграфы с текстом
                'div.response-content p',
                'div.review-content p',
                # Более общие селекторы
                'p:not([class*="nav"]):not([class*="menu"]):not([class*="footer"])',
            ]
            
            full_text_parts = []
            
            for selector in text_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(strip=True)
                    # Проверяем, что это содержательный текст
                    if 30 < len(text) < 5000 and not self.is_navigation_text(text):
                        # Исключаем дубликаты и короткие фразы
                        if text not in full_text_parts and not any(text in existing for existing in full_text_parts):
                            # Убираем фразы "Помогите другим пользователям выбрать лучший банк"
                            if not self.is_promotional_text(text):
                                full_text_parts.append(text)
            
            # Если не нашли по селекторам, ищем все параграфы с длинным текстом
            if not full_text_parts:
                paragraphs = soup.find_all('p')
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 50 and not self.is_navigation_text(text) and not self.is_promotional_text(text):
                        if text not in full_text_parts:
                            full_text_parts.append(text)
            
            if full_text_parts:
                full_text = '\n\n'.join(full_text_parts[:5])  # Берем первые 5 частей
                # Убираем остатки обрезанного текста
                full_text = full_text.replace('...Читать полностью', '').replace('...', '').strip()
                # Очищаем от футеров и нежелательного контента
                full_text = self.clean_review_text(full_text)
                return full_text
            
            return None
            
        except Exception as e:
            logger.warning(f"Не удалось получить полный текст отзыва {review_url}: {e}")
            return None

    def is_promotional_text(self, text):
        """Проверяет, является ли текст рекламным/промо"""
        promo_phrases = [
            'помогите другим пользователям выбрать лучший банк',
            'читать полностью',
            'все продукты банка',
            'рекламный контент'
        ]
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in promo_phrases)

    def extract_review_data_enhanced(self, container, get_full_text=True, antiban_mode=False):
        """Улучшенное извлечение данных отзыва с точными селекторами banki.ru"""
        review = {
            'date': None,
            'title': None,
            'text': None,
            'url': None,
            'review_id': None,
            'rating': None
        }
        
        # Извлекаем заголовок по точному селектору banki.ru
        title_element = container.select_one('h3.text-weight-medium a.link-simple')
        if not title_element:
            title_element = container.select_one('h3 a[href*="/response/"]')
        if not title_element:
            title_element = container.select_one('a[href*="/response/"]')
        
        if title_element:
            title_text = title_element.get_text(strip=True)
            if title_text and len(title_text) < 200 and not self.is_system_title(title_text):
                review['title'] = title_text
        
        # Извлекаем URL и ID сначала
        link = container.find('a', href=re.compile(r'/response/\d+'))
        if link:
            href = link['href']
            if not href.startswith('http'):
                href = 'https://www.banki.ru' + href
            review['url'] = href
            review['review_id'] = self.extract_review_id_from_url(href)
        
        # Извлекаем дату по точному селектору
        date_element = container.select_one('span.l0caf3d5f')
        if date_element:
            date_text = date_element.get_text(strip=True)
            if date_text and len(date_text) < 50:
                review['date'] = self.parse_date(date_text)
        
        # Извлекаем рейтинг по точному селектору
        rating_element = container.select_one('div.lb3db10af')
        if rating_element:
            rating_text = rating_element.get_text(strip=True)
            try:
                rating = int(rating_text)
                if 1 <= rating <= 5:
                    review['rating'] = rating
            except (ValueError, TypeError):
                pass
        
        # Извлекаем текст отзыва
        if get_full_text and review['url']:
            # Получаем полный текст со страницы отзыва
            full_text = self.get_full_review_text(review['url'], antiban_mode=antiban_mode)
            if full_text:
                review['text'] = full_text
            else:
                # Если не удалось получить полный текст, используем превью
                text_element = container.select_one('div.l22dd3882 a')
                if not text_element:
                    text_element = container.select_one('div.l22dd3882')
                if text_element:
                    preview_text = text_element.get_text(strip=True)
                    if preview_text and len(preview_text) > 20:
                        review['text'] = self.clean_review_text(preview_text)
            
            # Добавляем небольшую задержку между запросами к страницам отзывов
            if antiban_mode:
                # В антибан режиме увеличиваем задержку
                delay = random.uniform(1.0, 3.0)
            else:
                delay = random.uniform(0.5, 1.5)
            time.sleep(delay)
        else:
            # Используем только превью текст (быстрый режим)
            text_element = container.select_one('div.l22dd3882 a')
            if not text_element:
                text_element = container.select_one('div.l22dd3882')
            if text_element:
                preview_text = text_element.get_text(strip=True)
                if preview_text and len(preview_text) > 20:
                    review['text'] = self.clean_review_text(preview_text)
        
        return review
    
    def is_system_title(self, title):
        """Проверяет, является ли заголовок системным"""
        system_titles = [
            'отзывы о газпромбанке', 'народный рейтинг', 'все продукты',
            'калькуляторы', 'почему нам доверяют', 'предложения компании'
        ]
        return title.lower() in system_titles
    
    def is_navigation_text(self, text):
        """Проверяет, является ли текст навигационным"""
        # Если текст содержит много ссылочных слов, это навигация
        nav_patterns = [
            r'калькулятор\s+\w+',
            r'вклады\s+в\s+\w+',
            r'кредитные\s+карты',
            r'ипотека\s+в\s+\w+',
            r'рко\s+в\s+\w+',
            r'страхование\s+\w+'
        ]
        
        nav_matches = sum(1 for pattern in nav_patterns if re.search(pattern, text.lower()))
        return nav_matches > 2 or len(text.split('\n')) > 20
    
    def extract_review_id_from_url(self, review_url):
        """Извлечь ID отзыва из URL"""
        if not review_url:
            return None
        match = re.search(r'/response/(\d+)', review_url)
        return match.group(1) if match else None
    
    def parse_date(self, date_str):
        """Парсинг даты из строки"""
        try:
            date_str = str(date_str).strip().lower()
            
            months = {
                'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
                'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
                'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
            }
            
            for month_name, month_num in months.items():
                if month_name in date_str:
                    parts = date_str.replace(month_name, month_num).split()
                    if len(parts) >= 3:
                        day = parts[0].zfill(2)
                        month = month_num
                        year = parts[2]
                        return f"{day}.{month}.{year}"
            
            date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', date_str)
            if date_match:
                day, month, year = date_match.groups()
                return f"{day.zfill(2)}.{month.zfill(2)}.{year}"
            
            # ISO format
            iso_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
            if iso_match:
                year, month, day = iso_match.groups()
                return f"{day}.{month}.{year}"
            
            return date_str
        except Exception as e:
            logger.warning(f"Не удалось распарсить дату '{date_str}': {e}")
            return str(date_str)
    
    def parse_rating(self, rating_element):
        """Извлечь оценку из элемента"""
        try:
            if not rating_element:
                return None
            
            # Ищем data-rating
            rating = rating_element.get('data-rating')
            if rating:
                return int(rating)
            
            # Ищем по классам со звездами
            stars = rating_element.find_all(class_=re.compile(r'star|rating'))
            if stars:
                filled_stars = len([s for s in stars if any(cls in ' '.join(s.get('class', [])) for cls in ['filled', 'active', 'selected'])])
                if filled_stars > 0:
                    return filled_stars
            
            # Ищем числовую оценку в тексте
            rating_text = rating_element.get_text(strip=True)
            rating_match = re.search(r'(\d+)', rating_text)
            if rating_match:
                rating_val = int(rating_match.group(1))
                if 1 <= rating_val <= 5:
                    return rating_val
            
            return None
        except Exception as e:
            logger.warning(f"Не удалось извлечь оценку: {e}")
            return None
    
    def is_date_in_range(self, review_date, start_date, end_date):
        """Проверить, попадает ли дата отзыва в заданный диапазон"""
        if not review_date or not start_date or not end_date:
            return True
        
        try:
            review_dt = datetime.strptime(review_date, '%d.%m.%Y')
            start_dt = datetime.strptime(start_date, '%d.%m.%Y')
            end_dt = datetime.strptime(end_date, '%d.%m.%Y')
            
            return start_dt <= review_dt <= end_dt
        except ValueError as e:
            logger.warning(f"Ошибка при сравнении дат: {e}")
            return True
    
    def save_reviews_to_file(self, reviews, filename):
        """Сохранить отзывы в JSON файл"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(reviews, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранено {len(reviews)} отзывов в {filename}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении файла {filename}: {e}")
    
    def parse_reviews(self, start_page=1, end_page=10, delay_min=1, delay_max=3, 
                     jitter=0.5, start_date=None, end_date=None, save_every_n_pages=5,
                     get_full_text=True, save_all_reviews=True, antiban_mode=False):
        """
        Основной метод парсинга отзывов с поддержкой антибан режима
        
        Args:
            start_page: начальная страница
            end_page: конечная страница
            delay_min: минимальная задержка между запросами (сек)
            delay_max: максимальная задержка между запросами (сек)
            jitter: джиттер (случайное отклонение)
            start_date: начальная дата фильтра (DD.MM.YYYY)
            end_date: конечная дата фильтра (DD.MM.YYYY)
            save_every_n_pages: сохранять каждые N страниц
            get_full_text: получать полный текст отзывов (медленнее, но полнее)
            save_all_reviews: сохранять общий файл со всеми отзывами
            antiban_mode: антибан режим с увеличенными задержками
        """
        all_reviews = []
        current_batch = []
        
        for page in range(start_page, end_page + 1):
            logger.info(f"Парсинг страницы {page}...")
            
            # Антибан задержка между страницами
            if page > start_page:
                base_delay = random.uniform(delay_min, delay_max)
                if antiban_mode:
                    # В антибан режиме увеличиваем задержку в 2-3 раза
                    base_delay *= random.uniform(2.0, 3.0)
                    logger.info(f"🛡️ Антибан режим: увеличенная задержка {base_delay:.2f} сек")
                
                jitter_value = random.uniform(-jitter, jitter)
                total_delay = max(1, base_delay + jitter_value)
                
                logger.info(f"Ожидание {total_delay:.2f} секунд...")
                time.sleep(total_delay)
            
            html, api_data = self.get_page_advanced(page, antiban_mode)
            
            if not html:
                logger.error(f"Не удалось получить страницу {page}")
                # Если это 403 ошибка, рекомендуем прекратить
                if "403" in str(html):
                    logger.warning("🚫 Обнаружена блокировка. Рекомендуется прекратить парсинг.")
                    break
                continue
            
            reviews = self.parse_reviews_from_page(html, get_full_text=get_full_text, antiban_mode=antiban_mode)
            
            # Фильтрация по датам
            if start_date and end_date:
                filtered_reviews = []
                for review in reviews:
                    if self.is_date_in_range(review['date'], start_date, end_date):
                        filtered_reviews.append(review)
                reviews = filtered_reviews
                logger.info(f"После фильтрации по датам осталось {len(reviews)} отзывов")
            
            current_batch.extend(reviews)
            all_reviews.extend(reviews)
            
            logger.info(f"Найдено {len(reviews)} отзывов на странице {page}")
            
            # Сохранение каждые N страниц
            if (page - start_page + 1) % save_every_n_pages == 0:
                filename = f"out/pages_{page - save_every_n_pages + 1:03d}_{page:03d}.json"
                self.save_reviews_to_file(current_batch, filename)
                current_batch = []
            
            # Задержка между запросами
            if page < end_page:
                delay = random.uniform(delay_min, delay_max)
                jitter_amount = random.uniform(-jitter, jitter)
                total_delay = max(0.5, delay + jitter_amount)
                
                logger.info(f"Ожидание {total_delay:.2f} секунд...")
                time.sleep(total_delay)
        
        # Сохранение оставшихся отзывов
        if current_batch:
            # Простая логика: если это остатки, используем диапазон от последней сохраненной страницы до конечной
            last_saved_page = ((page - 1) // save_every_n_pages) * save_every_n_pages + 1
            filename = f"out/pages_{last_saved_page:03d}_{end_page:03d}.json"
            self.save_reviews_to_file(current_batch, filename)
        
        # Сохранение всех отзывов в один файл (опционально)
        if save_all_reviews:
            all_filename = f"out/all_reviews_{start_page:03d}_{end_page:03d}.json"
            self.save_reviews_to_file(all_reviews, all_filename)
            logger.info(f"Сохранен общий файл: {all_filename}")
        
        logger.info(f"Парсинг завершен. Всего найдено {len(all_reviews)} отзывов")
        return all_reviews

if __name__ == "__main__":
    parser = BankiRuParser()
    
    try:
        # Тестируем с получением полных текстов (медленнее, но полнее)
        print("Запускаем парсер с получением полных текстов отзывов...")
        print("Это займет больше времени, так как нужно загружать каждую страницу отзыва.")
        print("Задержки: 0.5-1.5 сек между отзывами + основные задержки между страницами.")
        
        reviews = parser.parse_reviews(
            start_page=1,
            end_page=1,  # Тестируем только первую страницу
            delay_min=5,  # Увеличенные задержки
            delay_max=8,
            jitter=2.0,
            save_every_n_pages=1,
            get_full_text=True  # Получаем полные тексты
        )
        
        print(f"Парсинг завершен. Найдено {len(reviews)} отзывов.")
        
        if reviews:
            print("\nПример первого отзыва с полным текстом:")
            first_review = reviews[0]
            print(f"Заголовок: {first_review['title']}")
            print(f"Дата: {first_review['date']}")
            print(f"Рейтинг: {first_review['rating']}")
            print(f"ID: {first_review['review_id']}")
            print(f"URL: {first_review['url']}")
            print(f"Текст ({len(first_review.get('text', ''))} символов):")
            print(f"{first_review.get('text', 'Текст не найден')[:300]}...")
            
            # Проверяем, есть ли ещё обрезанные тексты
            truncated_count = sum(1 for r in reviews if '...Читать полностью' in r.get('text', ''))
            if truncated_count > 0:
                print(f"\n⚠️ Внимание: {truncated_count} отзывов всё ещё содержат обрезанный текст")
            else:
                print(f"\n✅ Все {len(reviews)} отзывов содержат полный текст!")
        else:
            print("Отзывы не найдены. Возможно, структура сайта изменилась.")
            
    except Exception as e:
        print(f"Ошибка: {e}")