import pandas as pd
import logging
import time
import requests
from datetime import timezone

# ==========================================
# Налаштування логування (Глобальний рівень)
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("DataLoader")

class AlertDataLoader:
    """
    Клас для завантаження та первинного очищення (Processing Layer 1) 
    сирих даних про повітряні тривоги. 
    Включає стійкість до мережевих збоїв (Resiliency) через механізм Retry.
    """
    
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.max_retries = 3
        self.retry_delay_seconds = 5
        self.timeout_seconds = 10

    def fetch_raw_data(self) -> pd.DataFrame:
        """
        Завантажує дані з API. Імплементує патерн Retry з паузами 
        для захисту від тимчасових мережевих збоїв (502, 503, 504).
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Спроба підключення до API ({attempt}/{self.max_retries}) | URL: {self.api_url}")
                
                # Виконуємо HTTP-запит із жорстким таймаутом
                response = requests.get(self.api_url, timeout=self.timeout_seconds)
                
                # Генеруємо HTTPError, якщо статус-код 4xx або 5xx
                response.raise_for_status() 
                
                data = response.json()
                logger.info("Дані успішно завантажено з API.")
                return pd.DataFrame(data)

            except requests.exceptions.RequestException as e:
                logger.error(f"Мережева помилка на спробі {attempt}: {e}")
                
                if attempt < self.max_retries:
                    logger.info(f"Очікування {self.retry_delay_seconds} секунд перед наступною спробою...")
                    time.sleep(self.retry_delay_seconds)
                else:
                    logger.critical("Всі спроби підключення вичерпано. Критичний збій завантаження даних.")
                    # Вкидаємо фатальну помилку, щоб зупинити пайплайн або перехопити її в main.py
                    raise SystemError("Критичний збій Ingestion Layer. Неможливо отримати дані від API.") from e

    def clean_and_process(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        Очищує дані, заповнює активні тривоги поточним часом та дедуплікує.
        """
        if raw_df.empty:
            logger.warning("Отримано порожній DataFrame для очищення. Переривання процесу.")
            return raw_df

        logger.info("Початок очищення та трансформації даних...")
        df = raw_df.copy()

        try:
            # 1. Жорстка типізація
            df['start_time'] = pd.to_datetime(df['start_time'], utc=True, errors='coerce')
            df['end_time'] = pd.to_datetime(df['end_time'], utc=True, errors='coerce')
            
            initial_rows = len(df)
            df = df.dropna(subset=['start_time'])
            if len(df) < initial_rows:
                logger.warning(f"Відкинуто {initial_rows - len(df)} битих записів без start_time.")

            # 2. Маркування активних тривог та ін'єкція поточного часу
            df['is_active'] = df['end_time'].isna()
            current_utc_time = pd.Timestamp.now(tz=timezone.utc)
            df['end_time'] = df['end_time'].fillna(current_utc_time)

            # 3. Дедуплікація та сортування
            df = df.drop_duplicates(subset=['region_id', 'start_time', 'end_time'])
            df = df.sort_values(by=['region_id', 'start_time'])

            # 4. Злиття накладань (Overlaps)
            merged_records = []
            for region, group in df.groupby('region_id'):
                current_start, current_end, current_is_active = None, None, False

                for _, row in group.iterrows():
                    if current_start is None:
                        current_start, current_end, current_is_active = row['start_time'], row['end_time'], row['is_active']
                        continue

                    if row['start_time'] <= current_end:
                        current_end = max(current_end, row['end_time'])
                        current_is_active = current_is_active or row['is_active']
                    else:
                        merged_records.append({
                            'region_id': region, 'start_time': current_start,
                            'end_time': current_end, 'is_active': current_is_active
                        })
                        current_start, current_end, current_is_active = row['start_time'], row['end_time'], row['is_active']

                if current_start is not None:
                    merged_records.append({
                        'region_id': region, 'start_time': current_start,
                        'end_time': current_end, 'is_active': current_is_active
                    })

            clean_df = pd.DataFrame(merged_records)
            
            # 5. Розрахунок тривалості
            if not clean_df.empty:
                clean_df['duration_seconds'] = (clean_df['end_time'] - clean_df['start_time']).dt.total_seconds()

            logger.info(f"Очищення успішно завершено. Результуючих записів: {len(clean_df)}")
            return clean_df

        except Exception as e:
            logger.error(f"Непередбачувана помилка під час очищення даних: {e}")
            raise
