"""
Модуль для работы с API классификации изображений СРГ.
"""

import os
import time
import json
import logging
from typing import Dict, Optional, Any
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class APIClient:
    """Клиент для API классификации СРГ."""
    
    def __init__(self, 
                 base_url: str = "https://forecasting.iszf.irk.ru/api/srh/predict",
                 timeout: int = 30,
                 max_retries: int = 3,
                 retry_delays: list = None):
        
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delays = retry_delays or [1, 2, 4]
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SRH-CrossFrequency-Experiment/1.0',
            'Accept': 'application/json'
        })
        
        # Статистика
        self.requests_count = 0
        self.success_count = 0
        self.error_count = 0
        
    def predict_from_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Отправка локального файла на классификацию.
        
        Args:
            file_path: путь к FITS/PNG/JPEG файлу
            
        Returns:
            Словарь с ответом API или None при ошибке
        """
        if not os.path.exists(file_path):
            logger.error(f"Файл не найден: {file_path}")
            return None
        
        filename = os.path.basename(file_path)
        
        # Определяем MIME-тип
        if filename.lower().endswith('.fit') or filename.lower().endswith('.fits'):
            mime_type = 'application/fits'
        elif filename.lower().endswith('.png'):
            mime_type = 'image/png'
        elif filename.lower().endswith(('.jpg', '.jpeg')):
            mime_type = 'image/jpeg'
        else:
            logger.error(f"Неподдерживаемый формат файла: {filename}")
            return None
        
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f, mime_type)}
            return self._make_request(files=files, params=None)
    
    def predict_from_url(self, file_url: str) -> Optional[Dict[str, Any]]:
        """
        Отправка URL FITS-файла на классификацию.
        
        Args:
            file_url: URL FITS-файла на FTP-сервере
            
        Returns:
            Словарь с ответом API или None при ошибке
        """
        params = {'url': file_url}
        return self._make_request(files=None, params=params)
    
    def _make_request(self, files, params) -> Optional[Dict[str, Any]]:
        """
        Выполнение POST-запроса к API с повторными попытками.
        """
        for attempt in range(self.max_retries + 1):
            self.requests_count += 1
            
            try:
                response = self.session.post(
                    self.base_url,
                    files=files,
                    params=params,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    self.success_count += 1
                    result = response.json()
                    
                    # Валидация ответа
                    if 'label' not in result or 'probability' not in result:
                        logger.error(f"Некорректный формат ответа API: {result}")
                        return None
                    
                    logger.debug(f"Успешный запрос: {result['label']} (conf={result['probability']:.3f})")
                    return result
                    
                else:
                    error_msg = f"Ошибка API: {response.status_code} - {response.text}"
                    if attempt < self.max_retries:
                        delay = self.retry_delays[min(attempt, len(self.retry_delays)-1)]
                        logger.warning(f"{error_msg}. Повтор через {delay} сек...")
                        time.sleep(delay)
                    else:
                        self.error_count += 1
                        logger.error(error_msg)
                        return None
                        
            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays)-1)]
                    logger.warning(f"Таймаут запроса. Повтор через {delay} сек...")
                    time.sleep(delay)
                else:
                    self.error_count += 1
                    logger.error("Таймаут запроса после всех попыток")
                    return None
                    
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays)-1)]
                    logger.warning(f"Ошибка сети: {e}. Повтор через {delay} сек...")
                    time.sleep(delay)
                else:
                    self.error_count += 1
                    logger.error(f"Ошибка сети после всех попыток: {e}")
                    return None
                    
            except json.JSONDecodeError as e:
                self.error_count += 1
                logger.error(f"Ошибка парсинга JSON ответа: {e}")
                return None
        
        return None
    
    def get_stats(self) -> Dict[str, int]:
        """Возвращает статистику запросов."""
        return {
            'requests': self.requests_count,
            'success': self.success_count,
            'errors': self.error_count,
            'success_rate': self.success_count / max(self.requests_count, 1)
        }
    
    def reset_stats(self):
        """Сброс статистики."""
        self.requests_count = 0
        self.success_count = 0
        self.error_count = 0