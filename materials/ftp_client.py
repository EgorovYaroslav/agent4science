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

# Паттерны для имен файлов (из конфига)
# Временные константы (используем 12200 вместо 12960 для 2025 года)
FILE_PATTERNS = {
    3000: "srh_I_{date}T{time}_{frequency}.fit",
    6000: "srh_{date}T{time}_{frequency}_I.fit",
    12200: "srh_{date}T{time}_{frequency}_I.fit"  # временно вместо 12960
}

BASE_URLS = {
    3000: "https://ftp.rao.istp.ac.ru/SRH/SRH0306/cleanMaps",
    6000: "https://ftp.rao.istp.ac.ru/SRH/SRH0612/cleanMaps",
    12200: "https://ftp.rao.istp.ac.ru/SRH/SRH1224/cleanMaps"  # временно вместо 12960
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
                date=date_str, time=time_str, frequency=frequency
            )
            # Директория: BASE_URL/YYYYMMDD/ (да, для 3000 тоже YYYYMMDD в пути!)
            dir_date = dt.strftime("%Y%m%d")
            dir_url = urljoin(BASE_URLS[3000] + "/", f"{dir_date}/")
        else:
            date_str = self._format_date_other(dt)
            time_str = self._format_time_other(dt)
            filename = FILE_PATTERNS[frequency].format(
                date=date_str, time=time_str, frequency=frequency
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
        
        Args:
            frequency: частота (3000, 6000, 12960)
            target_dt: целевое время
            max_diff_sec: максимально допустимое отклонение (сек)
            
        Returns:
            (datetime фактического файла, URL) или (None, None) если не найден
        """
        # Пробуем несколько стратегий
        
        # Стратегия 1: Прямой URL по шаблону (если файл существует точно в это время)
        direct_url = self.build_url(frequency, target_dt)
        if self._check_file_exists(direct_url):
            return target_dt, direct_url
        
        # Стратегия 2: Поиск в окрестности +/- max_diff_sec секунд
        # Генерируем временные метки с шагом 2 минуты (типичный кадр СРГ)
        step = 120  # 2 минуты в секундах
        for offset in range(0, max_diff_sec + step, step):
            # Пробуем +offset и -offset
            for sign in [1, -1]:
                if offset == 0 and sign == -1:
                    continue  # уже проверили
                    
                dt_candidate = target_dt + timedelta(seconds=sign * offset)
                candidate_url = self.build_url(frequency, dt_candidate)
                
                if self._check_file_exists(candidate_url):
                    diff = abs((dt_candidate - target_dt).total_seconds())
                    if diff <= max_diff_sec:
                        return dt_candidate, candidate_url
        
        # Стратегия 3: Парсинг HTML директории (fallback)
        return self._find_closest_file_fallback(frequency, target_dt, max_diff_sec)
    
    def _check_file_exists(self, url: str) -> bool:
        """Проверка существования файла по URL (HEAD-запрос)."""
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def _find_closest_file_fallback(self, frequency: int, target_dt: datetime, 
                                   max_diff_sec: int) -> Tuple[Optional[datetime], Optional[str]]:
        """
        Fallback-стратегия: парсинг HTML директории.
        """
        date_str = target_dt.strftime("%Y%m%d")
        dir_url = urljoin(BASE_URLS[frequency] + "/", f"{date_str}/")
        
        try:
            response = self.session.get(dir_url, timeout=30)
            response.raise_for_status()
            
            # Декодируем HTML-сущности
            from urllib.parse import unquote
            html = response.text
            
            # Ищем все .fit файлы (учитываем кодирование %3A)
            files = re.findall(r'href="([^"]+\.fit)"', html)
            if not files:
                return None, None
            
            best_diff = max_diff_sec + 1
            best_file = None
            best_dt = None
            
            for file in files:
                # Декодируем URL
                decoded_file = unquote(file)
                dt = self._parse_datetime_from_filename(frequency, decoded_file)
                if dt is None:
                    continue
                
                diff = abs((dt - target_dt).total_seconds())
                if diff < best_diff:
                    best_diff = diff
                    best_file = file  # оригинальный (кодированный) URL
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
                # srh_20250101T000000_6000_I.fit
                match = re.search(r'srh_(\d{8})T(\d{6})_(\d{4})_I\.fit', filename)
                if match:
                    date_str, time_str, freq = match.groups()
                    year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
                    hour, minute, second = int(time_str[:2]), int(time_str[2:4]), int(time_str[4:6])
                    return datetime(year, month, day, hour, minute, second)
        except (ValueError, AttributeError) as e:
            logger.debug(f"Не удалось распарсить дату из {filename}: {e}")
        
        return None
    
    def find_triplet(self, target_dt: datetime, max_diff_sec: int = 180) -> Dict[int, Tuple[datetime, str]]:
        """
        Поиск тройки файлов (3000, 6000, 12960 МГц) для заданного времени.
        
        Args:
            target_dt: целевое время (обычно для 3000 МГц)
            max_diff_sec: максимальное отклонение для каждого файла
            
        Returns:
            Словарь {частота: (datetime, URL)} или пустой словарь если не все найдены
        """
        result = {}
        
        # Сначала ищем файл на 3000 МГц (целевой канал)
        dt_3000, url_3000 = self.find_closest_file(3000, target_dt, max_diff_sec)
        if dt_3000 is None:
            logger.warning(f"Не найден файл 3000 МГц для {target_dt}")
            return {}
        result[3000] = (dt_3000, url_3000)
        
        # Для 6000 и 12200 ищем ближайшие к dt_3000 (не к target_dt!)
        for freq in [6000, 12200]:
            dt_freq, url_freq = self.find_closest_file(freq, dt_3000, max_diff_sec)
            if dt_freq is None:
                logger.warning(f"Не найден файл {freq} МГц для времени {dt_3000}")
                return {}
            result[freq] = (dt_freq, url_freq)
        
        # Проверяем, что все три файла находятся в пределах max_diff_sec друг от друга
        times = [dt for dt, _ in result.values()]
        max_actual_diff = max(abs((t1 - t2).total_seconds()) for t1 in times for t2 in times)
        if max_actual_diff > max_diff_sec:
            logger.warning(f"Тройка найдена, но max_diff={max_actual_diff} сек > {max_diff_sec}")
            return {}
        
        logger.info(f"Найдена тройка: 3000={dt_3000}, 6000={result[6000][0]}, 12960={result[12960][0]}")
        return result