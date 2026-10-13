import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

connection = None

try:
    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE")
    )

    print("MySQL connection successful!")

    cursor = connection.cursor()
    cursor.execute("SELECT id, name, course, marks FROM students LIMIT 5")

    for row in cursor.fetchall():
        print(row)

    cursor.close()

except mysql.connector.Error as error:
    print("Connection error:", error)

finally:
    if connection is not None and connection.is_connected():
        connection.close()