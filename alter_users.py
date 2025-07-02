import sqlite3

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Додаємо поле, якщо воно ще не існує
try:
    cursor.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
    print("✅ Стовпець 'is_verified' успішно додано.")
except Exception as e:
    print("⚠️ Можливо, поле вже існує:", e)

conn.commit()
conn.close()
