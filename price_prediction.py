import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import joblib
import os
from dotenv import load_dotenv
from decimal import Decimal

# Загрузка переменных окружения
load_dotenv()

class PricePredictor:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=200, random_state=42, max_depth=10)
        self.scaler = StandardScaler()
        self.model_path = 'models/price_predictor.joblib'
        self.scaler_path = 'models/price_scaler.joblib'
        self.feature_names = None
        
        # Создаем директорию для моделей, если её нет
        os.makedirs('models', exist_ok=True)

    def get_db_connection(self):
        """Создание соединения с базой данных"""
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME", "alcohol_shop"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "123"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )

    def convert_decimal_to_float(self, df):
        """Преобразование Decimal в float"""
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    df[col] = df[col].astype(float)
                except:
                    pass
        return df

    def add_temporal_features(self, df):
        """Добавление временных признаков"""
        # Преобразуем дату в datetime, если это строка
        if isinstance(df['changed_at'].iloc[0], str):
            df['changed_at'] = pd.to_datetime(df['changed_at'])
        
        # Преобразуем все числовые колонки в float
        df = self.convert_decimal_to_float(df)
        
        # Добавляем циклические признаки для месяца и дня недели
        df['month_sin'] = np.sin(2 * np.pi * df['month'].astype(float) / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'].astype(float) / 12)
        df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'].astype(float) / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'].astype(float) / 7)
        
        # Добавляем признак квартала
        df['quarter'] = pd.to_datetime(df['changed_at']).dt.quarter
        
        # Добавляем признак выходного дня
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        
        # Добавляем признак праздничного периода (пример)
        holidays = [
            (1, 1), (1, 2), (1, 7), (2, 23), (3, 8), (5, 1), (5, 9),
            (6, 12), (11, 4), (12, 31)
        ]
        df['is_holiday'] = df.apply(
            lambda x: 1 if (x['month'], x['changed_at'].day) in holidays else 0,
            axis=1
        )
        
        return df

    def prepare_data(self):
        """Подготовка данных для обучения модели"""
        conn = self.get_db_connection()
        try:
            # Получаем историю цен
            price_history_query = """
                SELECT ph.*, p.category_id, p.brand_id, p.volume, p.strength,
                       EXTRACT(MONTH FROM ph.changed_at) as month,
                       EXTRACT(DOW FROM ph.changed_at) as day_of_week
                FROM price_history ph
                JOIN products p ON ph.product_id = p.id
                ORDER BY ph.changed_at
            """
            
            # Получаем информацию об акциях
            promotions_query = """
                SELECT p.product_id, p.discount_percent, 
                       EXTRACT(MONTH FROM p.start_date) as promo_month,
                       EXTRACT(DOW FROM p.start_date) as promo_day
                FROM promotions p
                WHERE p.product_id IS NOT NULL
                  AND p.start_date IS NOT NULL
            """
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(price_history_query)
                price_data = pd.DataFrame(cursor.fetchall())
                
                cursor.execute(promotions_query)
                promo_data = pd.DataFrame(cursor.fetchall())
            
            # Проверяем наличие данных
            if price_data.empty:
                raise ValueError("Нет данных о ценах в базе данных")
            
            print(f"Загружено записей о ценах: {len(price_data)}")
            print(f"Загружено записей об акциях: {len(promo_data)}")
            
            # Преобразуем все числовые колонки в float
            price_data = self.convert_decimal_to_float(price_data)
            
            # Добавляем временные признаки
            price_data = self.add_temporal_features(price_data)
            
            # Подготовка признаков
            base_features = ['category_id', 'brand_id', 'volume', 'strength', 
                           'month_sin', 'month_cos', 'day_sin', 'day_cos',
                           'quarter', 'is_weekend', 'is_holiday']
            
            X = price_data[base_features].copy()
            
            # Создаем колонки для акций
            promo_columns = []
            for month in range(1, 13):
                promo_columns.append(f'promo_month_{month}')
            for day in range(7):
                promo_columns.append(f'promo_day_{day}')
            
            # Инициализируем все колонки акций нулями
            for col in promo_columns:
                X[col] = 0
            
            # Добавляем информацию об акциях, если они есть
            if not promo_data.empty:
                promo_data = self.convert_decimal_to_float(promo_data)
                
                # Проверяем наличие необходимых колонок
                required_columns = ['promo_month', 'promo_day']
                if not all(col in promo_data.columns for col in required_columns):
                    print("Предупреждение: В данных об акциях отсутствуют некоторые необходимые колонки")
                else:
                    # Создаем признаки акций вручную
                    for _, row in promo_data.iterrows():
                        month = int(row['promo_month'])
                        day = int(row['promo_day'])
                        if 1 <= month <= 12:
                            X[f'promo_month_{month}'] = 1
                        if 0 <= day <= 6:
                            X[f'promo_day_{day}'] = 1
            
            # Сохраняем имена признаков
            self.feature_names = X.columns.tolist()
            
            # Целевая переменная - цена
            y = price_data['price'].astype(float)
            
            print(f"Количество признаков: {len(self.feature_names)}")
            print(f"Признаки: {', '.join(self.feature_names)}")
            
            return X, y
            
        finally:
            conn.close()

    def train(self):
        """Обучение модели"""
        X, y = self.prepare_data()
        
        # Разделение на обучающую и тестовую выборки
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Масштабирование признаков
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Обучение модели
        self.model.fit(X_train_scaled, y_train)
        
        # Оценка модели
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)
        
        print(f"R² score на обучающей выборке: {train_score:.3f}")
        print(f"R² score на тестовой выборке: {test_score:.3f}")
        
        # Вывод важности признаков
        feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\nВажность признаков:")
        print(feature_importance.head(10))
        
        # Сохранение модели и скейлера
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, self.scaler_path)
        joblib.dump(self.feature_names, 'models/feature_names.joblib')

    def load_model(self):
        """Загрузка сохраненной модели"""
        if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
            self.feature_names = joblib.load('models/feature_names.joblib')
            return True
        return False

    def predict_price(self, product_data):
        """
        Предсказание цены для нового товара
        
        Args:
            product_data (dict): Словарь с данными о товаре:
                {
                    'category_id': int,
                    'brand_id': int,
                    'volume': float,
                    'strength': float,
                    'month': int (1-12),
                    'day_of_week': int (0-6)
                }
        """
        if not hasattr(self.model, 'predict'):
            if not self.load_model():
                raise Exception("Модель не обучена. Сначала выполните train()")
        
        # Создаем DataFrame с нулевыми значениями для всех признаков
        X = pd.DataFrame(0, index=[0], columns=self.feature_names)
        
        # Добавляем временные признаки
        month = float(product_data['month'])
        day_of_week = float(product_data['day_of_week'])
        
        # Циклические признаки
        X['month_sin'] = np.sin(2 * np.pi * month / 12)
        X['month_cos'] = np.cos(2 * np.pi * month / 12)
        X['day_sin'] = np.sin(2 * np.pi * day_of_week / 7)
        X['day_cos'] = np.cos(2 * np.pi * day_of_week / 7)
        
        # Квартал
        X['quarter'] = int((month - 1) // 3 + 1)
        
        # Выходной день
        X['is_weekend'] = 1 if day_of_week in [5, 6] else 0
        
        # Праздничный день (пример)
        holidays = [
            (1, 1), (1, 2), (1, 7), (2, 23), (3, 8), (5, 1), (5, 9),
            (6, 12), (11, 4), (12, 31)
        ]
        X['is_holiday'] = 1 if (int(month), datetime.now().day) in holidays else 0
        
        # Заполняем остальные известные признаки
        for key, value in product_data.items():
            if key in X.columns:
                X[key] = float(value)
        
        # Масштабирование признаков
        X_scaled = self.scaler.transform(X)
        
        # Предсказание цены
        predicted_price = self.model.predict(X_scaled)[0]
        
        return predicted_price

    def suggest_promotion_timing(self, product_id, days_ahead=30):
        """
        Предсказание оптимального времени для проведения акции
        
        Args:
            product_id (int): ID товара
            days_ahead (int): Количество дней для анализа
        """
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Получаем информацию о товаре
                cursor.execute("""
                    SELECT category_id, brand_id, volume, strength
                    FROM products
                    WHERE id = %s
                """, (product_id,))
                product = cursor.fetchone()
                
                if not product:
                    raise Exception("Товар не найден")
                
                # Генерируем даты для анализа
                dates = [datetime.now() + timedelta(days=i) for i in range(days_ahead)]
                
                # Предсказываем цены для каждой даты
                predictions = []
                for date in dates:
                    product_data = {
                        'category_id': product['category_id'],
                        'brand_id': product['brand_id'],
                        'volume': product['volume'],
                        'strength': product['strength'],
                        'month': date.month,
                        'day_of_week': date.weekday()
                    }
                    
                    predicted_price = self.predict_price(product_data)
                    predictions.append({
                        'date': date,
                        'predicted_price': predicted_price
                    })
                
                # Находим даты с минимальными предсказанными ценами
                predictions.sort(key=lambda x: x['predicted_price'])
                best_dates = predictions[:5]  # Топ-5 лучших дат
                
                return best_dates
                
        finally:
            conn.close()

def main():
    # Создание и обучение модели
    predictor = PricePredictor()
    predictor.train()
    
    # Пример использования
    product_data = {
        'category_id': 1,  # Красное вино
        'brand_id': 3,     # Киндзмараули
        'volume': 750,
        'strength': 12.0,
        'month': datetime.now().month,
        'day_of_week': datetime.now().weekday()
    }
    
    predicted_price = predictor.predict_price(product_data)
    print(f"\nПредсказанная цена: {predicted_price:.2f} руб.")
    
    # Пример предсказания времени для акции
    best_dates = predictor.suggest_promotion_timing(1)  # Для товара с ID=1
    print("\nЛучшие даты для проведения акции:")
    for date_info in best_dates:
        print(f"Дата: {date_info['date'].strftime('%Y-%m-%d')}, "
              f"Предсказанная цена: {date_info['predicted_price']:.2f} руб.")

if __name__ == "__main__":
    main() 