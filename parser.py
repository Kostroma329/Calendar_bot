# parser.py (БЕЗ SPACY)
from datetime import datetime, timedelta
import re
from dateutil.parser import parse as dateutil_parse
from typing import Dict, List, Optional
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

# ТОЛЬКО ваши танцы
DANCE_VARIANTS = {
    "Барыня": {"барыня", "барыню"},
    "Шумиха": {"шумиха", "шумиху"},
    "Соперницы": {"соперницы", "соперниц"},
    "Заигрыши": {"заигрыши", "заигрыш"},
    "Семеновна": {"семеновна", "семеновну"},
    "Цветная круговерть": {"цветная круговерть", "цветной круговерти"},
    "Дробушки": {"дробушки", "дробушку"},
    "Скакалки": {"скакалки", "скакалка"},
    "Победная пляска": {"победная пляска", "победной пляски"},
    "Морской": {"морской", "морскому", "яблочко"},
    "Снегири": {"снегири", "снегирей"},
    "Россияночка": {"россияночка", "россияночку"},
    "Субботея": {"субботея", "субботею"},
    "Ярмарочная круговерть": {"ярмарочная круговерть", "ярмарочной круговерти"},
    "Вальс": {"вальс", "вальсик"},
    "Белый вальс": {"белый вальс", "белого вальса"},
    "Школьный вальс": {"школьный вальс", "школьного вальса"},
    "Детинушка": {"детинушка", "детинушку"},
    "Сапожники": {"сапожники", "сапожников"},
    "Сюита": {"сюита", "сюиту"}
}

# Создаем плоский набор для быстрого поиска
KNOWN_DANCES = {variant: main_name for main_name, variants in DANCE_VARIANTS.items() for variant in variants}

# Паттерны для извлечения времени
TIME_PATTERNS = [
    (r'(?:в\s+)?(\d{1,2}:\d{2})', lambda m: re.sub(r'[^\d:]', '', m.group(1))),  # 19:00
    (r'(?:начало\s+в\s+)?(\d{1,2}:\d{2})', lambda m: re.sub(r'[^\d:]', '', m.group(1))),  # начало в 13:00
    (r'(?:в\s+)?(\d{1,2}\s*ч\s*\d{1,2}\s*мин)', lambda m: re.sub(r'[^\d:]', '', m.group(1).replace(' ', ':'))),
    # 19 ч 00 мин
    (r'(?:в\s+)?(\d{1,2}\s*ч)', lambda m: re.sub(r'\D', '', m.group(1)) + ':00'),  # 19 ч
    (r'(?:в\s+)?(\d{1,2}\s*часов?)', lambda m: re.sub(r'\D', '', m.group(1)) + ':00'),  # 19 часов
]

# Ключевые слова для относительных дат
RELATIVE_DATE_KEYWORDS = {
    'сегодня': 0,
    'завтра': 1,
    'послезавтра': 2,
    'в понедельник': 0,
    'во вторник': 1,
    'в среду': 2,
    'в четверг': 3,
    'в пятницу': 4,
    'в субботу': 5,
    'в воскресенье': 6,
}

# ТОЛЬКО ваши места
KNOWN_LOCATIONS = {
    'Троицкий': {'троицкий', 'троицком', 'троицкая', 'троицкое'},
    'Московский': {'московский', 'московском', 'московская'},
    'Максим': {'максим', 'максиме'},
    'БКЗ': {'бкз', 'бкзе'},
    'ДК Горького': {'дк горького', 'дк горьком'},
    'КДЦ Московский': {'кдц московский', 'кдц московском'},
}


def capitalize_location(location: str) -> str:
    """Приводит название места к правильному регистру"""
    if not location:
        return location

    # Если это улица, делаем первую букву заглавной
    if location.startswith('улица '):
        street_name = location[6:]  # убираем "улица "
        return f"Улица {street_name.capitalize()}"

    # Если это адрес
    if location.startswith('адрес: '):
        address = location[7:]  # убираем "адрес: "
        return f"Адрес: {address.capitalize()}"

    # Для известных локаций возвращаем каноническое название
    for canonical_name, variants in KNOWN_LOCATIONS.items():
        if location.lower() in variants:
            return canonical_name

    # Для остальных - просто первую букву заглавную
    return location.capitalize()


class DateTimeExtractor:
    @staticmethod
    def extract_russian_date(text: str) -> Optional[datetime]:
        """Извлекает даты в русском формате: '20 ноября', '5 декабря' и т.д."""
        # Словарь месяцев
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
        }

        # Паттерн для дат: "20 ноября", "5 декабря" и т.д.
        pattern = r'(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)'
        match = re.search(pattern, text.lower())

        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            month = months[month_name]

            now = datetime.now()
            year = now.year

            # Если месяц уже прошел в этом году, берем следующий год
            if month < now.month or (month == now.month and day < now.day):
                year += 1

            try:
                # Создаем дату без времени
                return datetime(year, month, day)
            except ValueError:
                return None

        return None

    @staticmethod
    def extract_relative_date(text: str) -> Optional[datetime]:
        """Извлекает относительные даты типа 'завтра', 'в субботу'"""
        text_lower = text.lower()
        now = datetime.now()

        for keyword, days_offset in RELATIVE_DATE_KEYWORDS.items():
            if keyword in text_lower:
                if keyword in ['сегодня', 'завтра', 'послезавтра']:
                    return now + timedelta(days=days_offset)
                else:
                    return DateTimeExtractor._get_next_weekday(keyword, now)
        return None

    @staticmethod
    def _get_next_weekday(weekday_keyword: str, from_date: datetime) -> datetime:
        """Получает дату следующего указанного дня недели"""
        weekday_map = {
            'в понедельник': 0, 'во вторник': 1, 'в среду': 2,
            'в четверг': 3, 'в пятницу': 4, 'в субботу': 5, 'в воскресенье': 6
        }
        target_weekday = weekday_map[weekday_keyword]
        current_weekday = from_date.weekday()

        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:
            days_ahead += 7

        return from_date + timedelta(days=days_ahead)

    @staticmethod
    def extract_time(text: str) -> Optional[datetime]:
        """Извлекает время из текста"""
        for pattern, time_processor in TIME_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    time_str = time_processor(match)
                    if ':' not in time_str:
                        time_str += ':00'

                    time_obj = datetime.strptime(time_str, "%H:%M").time()
                    return datetime.combine(datetime.now().date(), time_obj)
                except ValueError as e:
                    logger.debug(f"Ошибка парсинга времени '{time_str}': {e}")
                    continue
        return None

    @staticmethod
    def combine_date_time(date_part: Optional[datetime], time_part: Optional[datetime]) -> Optional[datetime]:
        """Объединяет дату и время"""
        if not date_part and not time_part:
            return None

        if date_part and time_part:
            return datetime.combine(date_part.date(), time_part.time())
        elif date_part:
            # Если есть только дата, добавляем время по умолчанию (13:00 или текущее +1 час)
            if date_part.hour == 0 and date_part.minute == 0:
                # Если время не указано, используем 13:00 как время по умолчанию
                return date_part.replace(hour=13, minute=0, second=0, microsecond=0)
            else:
                return date_part
        else:
            # Если есть только время, используем сегодня/завтра
            now = datetime.now()
            if time_part.time() > now.time():
                return datetime.combine(now.date(), time_part.time())
            else:
                return datetime.combine(now.date() + timedelta(days=1), time_part.time())


def extract_datetime(text: str) -> Optional[datetime]:
    """Основная функция извлечения даты и времени"""
    try:
        extractor = DateTimeExtractor()

        # 1. Пробуем извлечь русскую дату (новый метод)
        date_part = extractor.extract_russian_date(text)

        # 2. Если не нашли русскую дату, пробуем относительные даты
        if not date_part:
            date_part = extractor.extract_relative_date(text)

        # 3. Извлекаем время
        time_part = extractor.extract_time(text)

        # 4. Комбинируем дату и время
        result = extractor.combine_date_time(date_part, time_part)

        # 5. Fallback: используем dateutil для сложных случаев
        if not result:
            try:
                result = dateutil_parse(text, fuzzy=True, dayfirst=True)
                if result and result <= datetime.now():
                    result += timedelta(days=1)
            except Exception:
                pass

        return result if result and result > datetime.now() else None

    except Exception as e:
        logger.error(f"Error extracting datetime from '{text}': {e}")
        return None


def extract_dances_simple(text: str) -> List[str]:
    """Извлекает танцы из текста без spacy"""
    dances_found = set()
    text_lower = text.lower()

    # Простой поиск по словам
    words = re.findall(r'\b\w+\b', text_lower)

    # Поиск отдельных слов
    for word in words:
        if word in KNOWN_DANCES:
            dances_found.add(KNOWN_DANCES[word])

    # Поиск по 2-3 словам
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i + 1]}"
        if bigram in KNOWN_DANCES:
            dances_found.add(KNOWN_DANCES[bigram])

    for i in range(len(words) - 2):
        trigram = f"{words[i]} {words[i + 1]} {words[i + 2]}"
        if trigram in KNOWN_DANCES:
            dances_found.add(KNOWN_DANCES[trigram])

    return list(dances_found)


def extract_location_improved(text: str) -> Optional[str]:
    """Улучшенная логика определения места"""
    text_lower = text.lower()
    found_locations = []

    # 1. Ищем известные локации
    for canonical_name, variants in KNOWN_LOCATIONS.items():
        for variant in variants:
            if variant in text_lower:
                found_locations.append(canonical_name)
                break

    # 2. Ищем улицы
    street_patterns = [
        r'улица\s+([^\s,\.!?]+)',  # "улица Попова"
        r'ул\.\s*([^\s,\.!?]+)',  # "ул. Попова"
        r'ул\s+([^\s,\.!?]+)',  # "ул Попова"
    ]

    for pattern in street_patterns:
        match = re.search(pattern, text_lower)
        if match:
            street_name = match.group(1)
            found_locations.append(f"улица {street_name}")
            break

    # 3. Ищем адреса
    address_patterns = [
        r'адрес:\s*([^\.!?\n]+)',  # "адрес: Попова 25"
        r'адрес\s*([^\.!?\n]+)',  # "адрес Попова 25"
    ]

    for pattern in address_patterns:
        match = re.search(pattern, text_lower)
        if match:
            address = match.group(1).strip()
            found_locations.append(f"адрес: {address}")
            break

    # 4. Ищем локации после предлогов (только если не нашли другие)
    if not found_locations:
        location_prepositions = {'в', 'на', 'у'}
        words = text_lower.split()

        for i, word in enumerate(words):
            word_clean = re.sub(r'[^\w]', '', word)

            if word_clean in location_prepositions and i + 1 < len(words):
                # Берем 1-2 следующих слова
                location_words = []
                for j in range(1, 3):
                    if i + j < len(words):
                        next_word = words[i + j]
                        # Останавливаемся если встретили время или другой предлог
                        if (re.match(r'\d{1,2}[:ч]', next_word) or
                                re.sub(r'[^\w]', '', next_word) in location_prepositions):
                            break
                        location_words.append(next_word)
                    else:
                        break

                if location_words:
                    location = ' '.join(location_words)
                    location = re.sub(r'[.,!?;:]+$', '', location)
                    if len(location) > 2:  # Отсекаем слишком короткие
                        found_locations.append(location)

    # Приводим к правильному регистру и выбираем наиболее специфичную
    if found_locations:
        capitalized_locations = [capitalize_location(loc) for loc in found_locations]
        capitalized_locations.sort(key=len, reverse=True)
        return capitalized_locations[0]

    return None


def extract_with_spacy(text: str) -> Dict[str, Optional[str]]:
    """
    Извлекает информацию о мероприятии из текста (теперь без spacy)
    """
    if not text or not text.strip():
        return {"datetime": None, "location": None, "dances": []}

    try:
        # Извлекаем локации
        location = extract_location_improved(text)

        # Извлекаем танцы (простая версия без spacy)
        dances = extract_dances_simple(text)

        # Извлекаем дату и время
        dt = extract_datetime(text)

        return {
            "datetime": dt,
            "location": location,
            "dances": dances
        }

    except Exception as e:
        logger.error(f"Error in extract_with_spacy for text '{text}': {e}")
        return {"datetime": None, "location": None, "dances": []}
