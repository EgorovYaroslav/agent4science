"""
Модуль для работы с FTP-сервером СРГ.
Загрузка FITS-файлов по заданным временным меткам.
"""

import os
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
import requests
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)

# Паттерны для имен файлов
# ВАЖНО: 12200 МГц файлы физически лежат в SRH1224, но имя файла содержит 12960
FILE_PATTERNS = {
    3000: "srh_I_{date}T{time}_3000.fit",
    6000: "srh_{date}T{time}_6000_I.fit",
    12200: "srh_{date}T{time}_12960_I.fit",
}

BASE_URLS = {
    3000: "https://ftp.rao.istp.ac.ru/SRH/SRH0306/cleanMaps",
    6000: "https://ftp.rao.istp.ac.ru/SRH/SRH0612/cleanMaps",
    12200: "https://ftp.rao.istp.ac.ru/SRH/SRH1224/cleanMaps",
}


class FTPClient:
    """Клиент для доступа к FTP-серверу СРГ."""
    
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'SRH-CrossFrequency-Experiment/1.0'})
        
    def _format_date_3000(self, dt: datetime) -> str:
        """Форматирование даты для 3000 МГц: YYYY-MM-DD."""
        return dt.strftime("%Y-%m-%d")
    
    def _format_time_3000(self, dt: datetime) -> str:
        """Форматирование времени для 3000 МГц: HH:MM:SS."""
        return dt.strftime("%H:%M:%S")
    
    def _format_date_other(self, dt: datetime) -> str:
        """Форматирование даты для 6000/12960 МГц: YYYYMMDD."""
        return dt.strftime("%Y%m%d")
    
    def _format_time_other(self, dt: datetime) -> str:
        """Форматирование времени для 6000/12960 МГц: HHMMSS."""
        return dt.strftime("%H%M%S")
    
    def build_url(self, frequency: int, dt: datetime) -> str:
        """
        Построение URL для файла заданной частоты и времени.
        
        Args:
            frequency: 3000, 6000 или 12960 МГц
            dt: datetime объекта наблюдения
            
        Returns:
            URL файла на FTP-сервере
        """
        if frequency == 3000:
            date_str = self._format_date_3000(dt)
            time_str = self._format_time_3000(dt)
            filename = FILE_PATTERNS[3000].format(
                date=date_str, time=time_str
            )
            dir_date = dt.strftime("%Y%m%d")
            dir_url = urljoin(BASE_URLS[3000] + "/", f"{dir_date}/")
        else:
            date_str = self._format_date_other(dt)
            time_str = self._format_time_other(dt)
            filename = FILE_PATTERNS[frequency].format(
                date=date_str, time=time_str
            )
            dir_url = urljoin(BASE_URLS[frequency] + "/", f"{date_str}/")
        
        file_url = urljoin(dir_url, filename)
        
        return file_url
    
    def download_file(self, url: str, local_path: Optional[str] = None) -> Optional[str]:
        """
        Скачивание файла по URL с кэшированием.
        
        Args:
            url: URL файла на FTP
            local_path: путь для сохранения (если None, генерируется из URL)
            
        Returns:
            Путь к скачанному файлу или None при ошибке
        """
        if local_path is None:
            # Генерируем имя файла из URL
            filename = os.path.basename(url)
            local_path = os.path.join(self.cache_dir, filename)
        
        # Проверяем кэш
        if os.path.exists(local_path):
            logger.info(f"Файл уже в кэше: {local_path}")
            return local_path
        
        logger.info(f"Скачивание {url} -> {local_path}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Проверяем, что это действительно FITS-файл (не HTML-страница с ошибкой)
            if len(response.content) < 1000:  # FITS-файлы обычно >1KB
                logger.warning(f"Файл слишком маленький: {url} ({len(response.content)} байт)")
                return None
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Скачан {local_path} ({len(response.content)} байт)")
            return local_path
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при скачивании {url}: {e}")
            return None
    
    def find_closest_file(self, frequency: int, target_dt: datetime,
                         max_diff_sec: int = 180) -> Tuple[Optional[datetime], Optional[str]]:
        """
        Поиск ближайшего по времени файла на заданной частоте.
        Парсит HTML-листинг директории за соответствующий день.
        
        Args:
            frequency: частота (3000, 6000, 12960)
            target_dt: целевое время
            max_diff_sec: максимально допустимое отклонение (сек)
            
        Returns:
            (datetime фактического файла, URL) или (None, None) если не найден
        """
        date_str = target_dt.strftime("%Y%m%d")
        dir_url = urljoin(BASE_URLS[frequency] + "/", f"{date_str}/")
        
        try:
            response = self.session.get(dir_url, timeout=30)
            response.raise_for_status()
            
            from urllib.parse import unquote
            html = response.text
            files = re.findall(r'href="([^"]+\.fit)"', html)
            if not files:
                return None, None
            
            best_diff = max_diff_sec + 1
            best_file = None
            best_dt = None
            
            for file in files:
                decoded_file = unquote(file)
                dt = self._parse_datetime_from_filename(frequency, decoded_file)
                if dt is None:
                    continue
                diff = abs((dt - target_dt).total_seconds())
                if diff < best_diff:
                    best_diff = diff
                    best_file = file
                    best_dt = dt
            
            if best_diff <= max_diff_sec:
                file_url = urljoin(dir_url, best_file)
                return best_dt, file_url
            else:
                return None, None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при доступе к {dir_url}: {e}")
            return None, None
    
    def _parse_datetime_from_filename(self, frequency: int, filename: str) -> Optional[datetime]:
        """
        Парсинг даты-времени из имени файла.
        """
        try:
            if frequency == 3000:
                # srh_I_2025-01-01T00:00:00_3000.fit
                match = re.search(r'srh_I_(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})_3000\.fit', filename)
                if match:
                    year, month, day, hour, minute, second = map(int, match.groups())
                    return datetime(year, month, day, hour, minute, second)
            else:
                # srh_20250101T000000_6000_I.fit or srh_20250101T000000_12960_I.fit
                match = re.search(r'srh_(\d{8})T(\d{6})_(\d{4,5})_I\.fit', filename)
                if match:
                    date_str, time_str, freq = match.groups()
                    year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
                    hour, minute, second = int(time_str[:2]), int(time_str[2:4]), int(time_str[4:6])
                    return datetime(year, month, day, hour, minute, second)
        except (ValueError, AttributeError) as e:
            logger.debug(f"Не удалось распарсить дату из {filename}: {e}")
        
        return None

    def list_files(self, frequency: int, dt: datetime) -> List[Tuple[datetime, str]]:
        """
        Получение списка всех .fit (I-поляризация) файлов на заданную дату.
        Возвращает список (datetime, URL_encoded).
        """
        date_str = dt.strftime("%Y%m%d")
        dir_url = urljoin(BASE_URLS[frequency] + "/", f"{date_str}/")
        
        try:
            response = self.session.get(dir_url, timeout=30)
            response.raise_for_status()
            
            from urllib.parse import unquote
            html = response.text
            files = re.findall(r'href="([^"]+\.fit)"', html)
            
            result = []
            for file in files:
                decoded = unquote(file)
                dt_parsed = self._parse_datetime_from_filename(frequency, decoded)
                if dt_parsed is not None:
                    file_url = urljoin(dir_url, file)
                    result.append((dt_parsed, file_url))
            
            result.sort(key=lambda x: x[0])
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при доступе к {dir_url}: {e}")
            return []
    
    def find_triplet_by_3000_file(self, dt_3000: datetime, url_3000: str,
                                   max_diff_sec: int = 180) -> Dict[int, Tuple[datetime, str]]:
        """
        Поиск тройки по известному файлу 3000 МГц.
        Ищет 6000 и 12200 в окрестности dt_3000.
        """
        result = {3000: (dt_3000, url_3000)}
        
        for freq in [6000, 12200]:
            dt_freq, url_freq = self.find_closest_file(freq, dt_3000, max_diff_sec)
            if dt_freq is None:
                return {}
            result[freq] = (dt_freq, url_freq)
        
        times = [dt for dt, _ in result.values()]
        max_diff = max(abs((t1 - t2).total_seconds()) for t1 in times for t2 in times)
        if max_diff > max_diff_sec:
            return {}
        
        return result

    def find_triplet(self, target_dt: datetime, max_diff_sec: int = 180) -> Dict[int, Tuple[datetime, str]]:
        """
        Поиск тройки файлов (3000, 6000, 12960 МГц) для заданного времени.
        Перебирает все файлы дня на 3000 МГц и ищет совпадения.
        """
        files_3000 = self.list_files(3000, target_dt)
        if not files_3000:
            logger.warning(f"Нет файлов 3000 МГц на {target_dt.strftime('%Y%m%d')}")
            return {}
        
        best = None
        best_diff = float('inf')
        for dt_3000, url_3000 in files_3000:
            diff = abs((dt_3000 - target_dt).total_seconds())
            if diff > best_diff:
                continue
            triplet = self.find_triplet_by_3000_file(dt_3000, url_3000, max_diff_sec)
            if triplet:
                return triplet
        
        return {}