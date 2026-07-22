import os

class Config:
    # Llave secreta para proteger las sesiones de Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'smarttech_super_secret_key_2026'
    
    # URL entregada automáticamente por Render en producción
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # Configuración local de respaldo
    DB_CONFIG_LOCAL = {
        'dbname': 'smartech_db',  
        'user': 'postgres',        
        'password': '123456',  
        'host': 'localhost',
        'port': '5432'
    }