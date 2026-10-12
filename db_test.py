
import mysql.connector

connection = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="2004",
    database="student_db"
)

print("MySQL connected successfully!")

cursor = connection.cursor()
cursor.execute("SELECT name, marks FROM students")

for row in cursor.fetchall():
    print(row)

cursor.close()
connection.close()
