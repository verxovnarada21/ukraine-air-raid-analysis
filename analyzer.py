import pandas as pd

class StatisticalAnomalyDetector:
    """
    Детермінований аналізатор часових рядів на основі ліній Боллінджера.
    """
    def __init__(self, window_size_days: int = 7, std_multiplier: float = 2.0):
        self.window = window_size_days
        self.multiplier = std_multiplier

    def analyze(self, clean_df: pd.DataFrame) -> pd.DataFrame:
        """
        Агрегує дані по днях та виявляє аномалії на основі ковзного середнього.
        """
        if clean_df.empty:
            return pd.DataFrame()

        # 1. Агрегація
        daily_series = clean_df.set_index('start_time').resample('D')['duration_seconds'].sum()
        
        df_daily = daily_series.reset_index()
        df_daily.rename(columns={'duration_seconds': 'total_hours'}, inplace=True)
        df_daily['total_hours'] = df_daily['total_hours'] / 3600
        df_daily['total_hours'] = df_daily['total_hours'].fillna(0)

        # 2. Розрахунок статистичних метрик
        rolling = df_daily['total_hours'].rolling(window=self.window, min_periods=1)
        df_daily['rolling_mean'] = rolling.mean()
        df_daily['rolling_std'] = rolling.std(ddof=0)

        # 3. Маркування аномалій
        df_daily['threshold_upper'] = df_daily['rolling_mean'] + (df_daily['rolling_std'] * self.multiplier)
        df_daily['is_anomaly'] = df_daily['total_hours'] > df_daily['threshold_upper']

        return df_daily.round({'total_hours': 2, 'rolling_mean': 2, 'rolling_std': 2, 'threshold_upper': 2})
