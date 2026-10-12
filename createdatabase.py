
import sqlite3

conn = sqlite3.connect("products.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    barcode TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price INTEGER,
    location TEXT
)
""")

products = [
    (
        "8934673503358",
        "Sua vimamilk socola",
        9000,
        "Ke A1"
    ),
    (
        "8934673502351",
        "Sua vinamilk dau",
        9000,
        "Ke A2"
    )
]

cursor.executemany("""
INSERT OR REPLACE INTO products
(barcode, name, price, location)
VALUES (?, ?, ?, ?)
""", products)

conn.commit()

print("DA TAO DATABASE")
print("---------------------------")

cursor.execute("SELECT * FROM products")

for product in cursor.fetchall():
    print(product)

conn.close()