
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY is missing in .env")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1"
)

user_question = input("Ask your question: ")

response = client.responses.create(
    model="openai/gpt-oss-120b",
    instructions=(
        "Convert the user's question into one MySQL SELECT query. "
        "Use only the students table with columns id, name, course, marks. "
        "Return only SQL, without markdown."
    ),
    input=user_question
)


print("Generated SQL:")

generated_sql = response.output_text.strip()
print(generated_sql)

import mysql.connector

connection = None
cursor = None

try:
    # Only execute a validated SELECT query
    import sqlglot
    from sqlglot import exp

    statements = sqlglot.parse(generated_sql, read="mysql")

    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("Only one SELECT query is allowed.")

    tables = list(statements[0].find_all(exp.Table))

    if not tables or any(
        table.name.lower() != "students" for table in tables
    ):
        raise ValueError("Only the students table is allowed.")

    # Restrict output to 100 rows
    safe_sql = statements[0].limit(100).sql(dialect="mysql")

    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "student_db"),
        connection_timeout=10
    )

    cursor = connection.cursor(dictionary=True)
    cursor.execute(safe_sql)
    results = cursor.fetchmany(100)

    print("\nQuery Results:")

    if results:
        for row in results:
            print(row)
    else:
        print("No matching records found.")

except Exception as error:
    print("\nError:", error)

finally:
    if cursor is not None:
        cursor.close()

    if connection is not None and connection.is_connected():
        connection.close()

