import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Загрузка переменных окружения
load_dotenv()

class RecommendationSystem:
    def __init__(self):
        self.user_item_matrix = None
        self.item_features = None
        self.user_similarity = None
        self.item_similarity = None
        self.popular_items = None
        
    def get_db_connection(self):
        """Создание соединения с базой данных"""
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME", "alcohol_shop"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "123"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )

    def prepare_data(self):
        """Подготовка данных для рекомендательной системы"""
        conn = self.get_db_connection()
        try:
            # Получаем историю заказов
            orders_query = """
                SELECT o.user_id, oi.product_id, oi.quantity, o.created_at,
                       p.category_id, p.brand_id, p.volume, p.strength,
                       p.price, p.name as product_name,
                       c.name as category_name,
                       b.name as brand_name
                FROM orders o
                JOIN order_items oi ON o.id = oi.order_id
                JOIN products p ON oi.product_id = p.id
                JOIN categories c ON p.category_id = c.id
                JOIN brands b ON p.brand_id = b.id
                WHERE o.status = 'paid'
                ORDER BY o.created_at
            """
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(orders_query)
                orders_data = pd.DataFrame(cursor.fetchall())
            
            if orders_data.empty:
                raise ValueError("Нет данных о заказах в базе данных")
            
            print(f"Загружено записей о заказах: {len(orders_data)}")
            
            # Создаем матрицу пользователь-товар
            self.user_item_matrix = orders_data.pivot_table(
                index='user_id',
                columns='product_id',
                values='quantity',
                fill_value=0
            )
            
            # Сохраняем информацию о товарах
            self.item_features = orders_data[['product_id', 'category_id', 'brand_id', 
                                            'volume', 'strength', 'price', 'product_name',
                                            'category_name', 'brand_name']].drop_duplicates()
            
            # Вычисляем популярные товары
            self.popular_items = orders_data.groupby('product_id').agg({
                'quantity': 'sum',
                'product_name': 'first',
                'category_name': 'first',
                'brand_name': 'first',
                'price': 'first'
            }).sort_values('quantity', ascending=False)
            
            return True
            
        finally:
            conn.close()

    def compute_similarities(self):
        """Вычисление матриц схожести"""
        if self.user_item_matrix is None:
            raise ValueError("Сначала выполните prepare_data()")
        
        # Вычисляем схожесть пользователей
        self.user_similarity = cosine_similarity(self.user_item_matrix)
        
        # Вычисляем схожесть товаров
        self.item_similarity = cosine_similarity(self.user_item_matrix.T)
        
        print("Матрицы схожести вычислены")

    def get_user_recommendations(self, user_id, n_recommendations=5):
        """
        Получение рекомендаций для пользователя
        
        Args:
            user_id: ID пользователя
            n_recommendations: количество рекомендаций
        """
        if self.user_similarity is None:
            self.compute_similarities()
        
        if user_id not in self.user_item_matrix.index:
            # Если пользователь новый, возвращаем популярные товары
            return self.get_popular_recommendations(n_recommendations)
        
        # Получаем индекс пользователя
        user_idx = self.user_item_matrix.index.get_loc(user_id)
        
        # Получаем похожих пользователей
        similar_users = self.user_similarity[user_idx]
        
        # Получаем товары, которые пользователь еще не покупал
        user_items = set(self.user_item_matrix.columns[self.user_item_matrix.iloc[user_idx] > 0])
        all_items = set(self.user_item_matrix.columns)
        new_items = all_items - user_items
        
        if not new_items:
            return self.get_popular_recommendations(n_recommendations)
        
        # Вычисляем предсказанные оценки для новых товаров
        predictions = []
        for item in new_items:
            item_idx = self.user_item_matrix.columns.get_loc(item)
            # Используем оценки похожих пользователей
            item_ratings = self.user_item_matrix.iloc[:, item_idx]
            pred_rating = np.sum(similar_users * item_ratings) / np.sum(np.abs(similar_users))
            predictions.append((item, pred_rating))
        
        # Сортируем по предсказанной оценке
        predictions.sort(key=lambda x: x[1], reverse=True)
        
        # Формируем рекомендации
        recommendations = []
        for item_id, _ in predictions[:n_recommendations]:
            item_info = self.item_features[self.item_features['product_id'] == item_id].iloc[0]
            recommendations.append({
                'product_id': item_id,
                'name': item_info['product_name'],
                'category': item_info['category_name'],
                'brand': item_info['brand_name'],
                'price': item_info['price']
            })
        
        return recommendations

    def get_similar_items(self, product_id, n_recommendations=5):
        """
        Получение похожих товаров
        
        Args:
            product_id: ID товара
            n_recommendations: количество рекомендаций
        """
        if self.item_similarity is None:
            self.compute_similarities()
        
        if product_id not in self.user_item_matrix.columns:
            raise ValueError("Товар не найден")
        
        # Получаем индекс товара
        item_idx = self.user_item_matrix.columns.get_loc(product_id)
        
        # Получаем схожесть с другими товарами
        item_similarities = self.item_similarity[item_idx]
        
        # Получаем индексы самых похожих товаров (исключая сам товар)
        similar_indices = np.argsort(item_similarities)[::-1][1:n_recommendations+1]
        
        # Формируем рекомендации
        recommendations = []
        for idx in similar_indices:
            item_id = self.user_item_matrix.columns[idx]
            item_info = self.item_features[self.item_features['product_id'] == item_id].iloc[0]
            recommendations.append({
                'product_id': item_id,
                'name': item_info['product_name'],
                'category': item_info['category_name'],
                'brand': item_info['brand_name'],
                'price': item_info['price'],
                'similarity': item_similarities[idx]
            })
        
        return recommendations

    def get_popular_recommendations(self, n_recommendations=5):
        """
        Получение популярных товаров
        
        Args:
            n_recommendations: количество рекомендаций
        """
        if self.popular_items is None:
            raise ValueError("Сначала выполните prepare_data()")
        
        recommendations = []
        for idx, row in self.popular_items.head(n_recommendations).iterrows():
            recommendations.append({
                'product_id': idx,
                'name': row['product_name'],
                'category': row['category_name'],
                'brand': row['brand_name'],
                'price': row['price'],
                'popularity': row['quantity']
            })
        
        return recommendations

    def get_category_recommendations(self, category_id, n_recommendations=5):
        """
        Получение рекомендаций по категории
        
        Args:
            category_id: ID категории
            n_recommendations: количество рекомендаций
        """
        if self.popular_items is None:
            raise ValueError("Сначала выполните prepare_data()")
        
        # Получаем популярные товары в категории
        category_items = self.item_features[self.item_features['category_id'] == category_id]
        category_popular = self.popular_items[self.popular_items.index.isin(category_items['product_id'])]
        
        recommendations = []
        for idx, row in category_popular.head(n_recommendations).iterrows():
            recommendations.append({
                'product_id': idx,
                'name': row['product_name'],
                'category': row['category_name'],
                'brand': row['brand_name'],
                'price': row['price'],
                'popularity': row['quantity']
            })
        
        return recommendations

def main():
    # Создание и инициализация системы рекомендаций
    recommender = RecommendationSystem()
    recommender.prepare_data()
    
    # Пример получения рекомендаций для пользователя
    user_id = 1  # Замените на реальный ID пользователя
    print("\nРекомендации для пользователя:")
    user_recommendations = recommender.get_user_recommendations(user_id)
    for rec in user_recommendations:
        print(f"{rec['name']} ({rec['category']}, {rec['brand']}) - {rec['price']} руб.")
    
    # Пример получения похожих товаров
    product_id = 1  # Замените на реальный ID товара
    print("\nПохожие товары:")
    similar_items = recommender.get_similar_items(product_id)
    for item in similar_items:
        print(f"{item['name']} ({item['category']}, {item['brand']}) - {item['price']} руб.")
    
    # Пример получения популярных товаров
    print("\nПопулярные товары:")
    popular_items = recommender.get_popular_recommendations()
    for item in popular_items:
        print(f"{item['name']} ({item['category']}, {item['brand']}) - {item['price']} руб.")
    
    # Пример получения рекомендаций по категории
    category_id = 1  # Замените на реальный ID категории
    print("\nРекомендации по категории:")
    category_recommendations = recommender.get_category_recommendations(category_id)
    for rec in category_recommendations:
        print(f"{rec['name']} ({rec['category']}, {rec['brand']}) - {rec['price']} руб.")

if __name__ == "__main__":
    main() 