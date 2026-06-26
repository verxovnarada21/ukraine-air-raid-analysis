import pandas as pd
from datetime import timezone

class AlertDataLoader:
    """
    Клас для завантаження та первинного очищення (Processing Layer 1) 
    сирих даних про повітряні тривоги.
    """
    
    @staticmethod
    def load_mock_data() -> pd.DataFrame:
        """
        Імітація завантаження сирих даних з API або бази даних.
        """
        data = {
            'region_id': [1, 1, 1, 2, 2],
            'start_time': [
                '2023-10-01 10:00:00', '2023-10-01 10:15:00', 
                '2023-10-01 14:00:00', '2023-10-01 08:00:00',
                '2023-10-02 23:00:00'
            ],
            'end_time': [
                '2023-10-01 11:00:00', '2023-10-01 12:00:00', 
                None,                  '2023-10-01 09:00:00',
                '2023-10-03 03:00:00'
            ]
        }
        return pd.DataFrame(data)

    def clean_and_process(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        Очищує дані, заповнює активні тривоги поточним часом та дедуплікує.
        """
        if raw_df.empty:
            return raw_df

        df = raw_df.copy()

        # 1. Жорстка типізація
        df['start_time'] = pd.to_datetime(df['start_time'], utc=True, errors='coerce')
        df['end_time'] = pd.to_datetime(df['end_time'], utc=True, errors='coerce')
        df = df.dropna(subset=['start_time'])

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

        return clean_df
