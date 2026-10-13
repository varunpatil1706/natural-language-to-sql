
import os
import streamlit as st
import mysql.connector
import sqlglot
from sqlglot import exp
from dotenv import load_dotenv
from openai import OpenAI

# Load credentials from .env
load_dotenv()

st.set_page_config(
    page_title="Natural Language to SQL Assistant",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Natural Language to SQL Assistant")
st.write("Ask questions about your student database in simple English.")

question = st.text_input(
    "Your question",
    placeholder="Show students who get less than 90 marks"
)

if st.button("Generate SQL", type="primary"):
    if not question.strip():
        st.warning("Please enter a question.")
        st.stop()

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        st.error("GROQ_API_KEY is missing from your .env file.")
        st.stop()

    connection = None
    cursor = None

    try:
        with st.spinner("AI is generating SQL..."):
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )

            response = client.responses.create(
                model="openai/gpt-oss-120b",
                instructions=(
                    "Convert the user's question into exactly one MySQL "
                    "SELECT query. Use only the students table and its "
                    "columns: id, name, course, marks. "
                    "Return only SQL, without markdown. "
                    "Never generate INSERT, UPDATE, DELETE, DROP, ALTER, "
                    "CREATE, or other data-changing statements."
                ),
                input=question
            )

        generated_sql = response.output_text.strip()

        # Validate the generated SQL before execution
        statements = sqlglot.parse(generated_sql, read="mysql")

        if len(statements) != 1 or not isinstance(statements[0], exp.Select):
            raise ValueError("Only one SELECT query is allowed.")

        tables = list(statements[0].find_all(exp.Table))

        if not tables or any(
            table.name.lower() != "students"
            or table.db
            or table.catalog
            for table in tables
        ):
            raise ValueError("Only the students table is allowed.")

        allowed_columns = {"id", "name", "course", "marks"}

        for column in statements[0].find_all(exp.Column):
            if column.name.lower() not in allowed_columns:
                raise ValueError(
                    f"Column '{column.name}' is not allowed."
                )

        safe_sql = statements[0].limit(100).sql(dialect="mysql")

        st.subheader("Generated SQL")
        st.code(safe_sql, language="sql")

        with st.spinner("Fetching results from MySQL..."):
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

        st.subheader("Query Results")

        if results:
            st.dataframe(results, use_container_width=True)
            st.success(f"{len(results)} row(s) returned.")
        else:
            st.info("No matching records found.")

    except Exception as error:
        st.error(f"Could not process your question: {error}")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
