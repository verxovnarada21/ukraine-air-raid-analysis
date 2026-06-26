import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd

# Імпорт наших власних модулів
from data_loader import AlertDataLoader
from analyzer import StatisticalAnomalyDetector

def plot_dashboard(df_daily: pd.DataFrame):
    """
    Генерує дашборд для керівництва.
    """
    if df_daily.empty:
        print("Немає даних для візуалізації.")
        return

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(16, 8))

    # Стовпчики
    ax.bar(df_daily['start_time'], df_daily['total_hours'], 
           color='#B0BEC5', alpha=0.6, label='Щоденна тривалість (год)', width=0.8)

    # Тренд
    ax.plot(df_daily['start_time'], df_daily['rolling_mean'], 
            color='#1565C0', linewidth=3, label='7-денний тренд')

    # Межа аномалії
    ax.plot(df_daily['start_time'], df_daily['threshold_upper'], 
            color='#EF5350', linestyle='--', alpha=0.5, linewidth=1.5, label='Межа критичності (+2 STD)')

    # Аномалії (Червоні точки)
    anomalies = df_daily[df_daily['is_anomaly'] == True]
    if not anomalies.empty:
        ax.scatter(anomalies['start_time'], anomalies['total_hours'], 
                   color='#D32F2F', s=150, zorder=5, edgecolor='white', 
                   linewidth=1.5, label='Аномальний сплеск')

    # Форматування
    ax.set_title('Моніторинг повітряних тривог: Виявлення аномалій', fontsize=18, fontweight='bold', pad=20)
    ax.set_ylabel('Тривалість (Години)', fontsize=12, fontweight='bold')
    ax.set_xlabel('')
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    plt.xticks(rotation=45, ha='right')
    ax.legend(loc='upper left', frameon=True, shadow=True)
    ax.grid(True, linestyle=':', alpha=0.7)
    sns.despine(left=True, bottom=False)
    plt.tight_layout()
    plt.show()

def run_pipeline():
    """
    Оркестратор ETL-пайплайну.
    """
    print("1. Ініціалізація завантажувача та отримання сирих даних...")
    loader = AlertDataLoader()
    
    # Для демонстрації генеруємо синтетичний часовий ряд на 14 днів
    dates = pd.date_range(start='2023-10-01', periods=14, freq='D')
    hours = [2, 3, 2.5, 8, 2, 1.5, 3, 2.5, 3, 14, 2, 1, 0.5, 2] # 8 та 14 - штучні аномалії
    raw_synthetic_df = pd.DataFrame({'start_time': dates, 'end_time': dates + pd.to_timedelta(hours, unit='h'), 'region_id': 1})
    
    print("2. Очищення та трансформація даних...")
    clean_df = loader.clean_and_process(raw_synthetic_df)

    print("3. Пошук статистичних аномалій...")
    detector = StatisticalAnomalyDetector(window_size_days=7, std_multiplier=2.0)
    anomaly_report = detector.analyze(clean_df)

    print("4. Генерація дашборду...")
    plot_dashboard(anomaly_report)

if __name__ == "__main__":
    run_pipeline()
