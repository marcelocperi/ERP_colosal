import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

config = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", "3307")),
    "user": os.environ.get("DB_USER", "admin_colosal"),
    "password": os.environ.get("DB_PASSWORD", "Marce#2026"),
    "database": os.environ.get("DB_NAME", "multi_mcp_db"),
    "connect_timeout": 5
}

try:
    print(f"Connecting to {config['host']}:{config['port']}...")
    conn = pymysql.connect(**config)
    print("Connection successful!")
    with conn.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"MariaDB/MySQL Version: {version[0]}")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
