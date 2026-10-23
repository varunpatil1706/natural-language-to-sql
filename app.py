
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import mysql.connector
import sqlglot
from sqlglot import exp
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

st.set_page_config(
    page_title="AI Data Analytics Assistant",
    page_icon="📊",
    layout="wide"
)

# ---------- Session state ----------
if "history" not in st.session_state:
    st.session_state.history = []

if "last_result" not in st.session_state:
    st.session_state.last_result = None

if "last_sql" not in st.session_state:
    st.session_state.last_sql = None


# ---------- Database connection ----------
def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "student_db"),
        connection_timeout=10
    )


@st.cache_data(ttl=60)
def load_students():
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, name, course, marks FROM students LIMIT 5000"
        )
        rows = cursor.fetchall()
        return pd.DataFrame(rows)
    finally:
        connection.close()


# ---------- SQL validation ----------
def validate_sql(generated_sql):
    statements = sqlglot.parse(generated_sql, read="mysql")

    if len(statements) != 1:
        raise ValueError("Only one SQL statement is allowed.")

    tree = statements[0]

    if not isinstance(tree, exp.Select):
        raise ValueError("Only SELECT queries are allowed.")

    # Keep this version limited to one simple table.
    if (
        tree.find(exp.Join)
        or tree.find(exp.Subquery)
        or tree.find(exp.Union)
        or tree.find(exp.With)
    ):
        raise ValueError(
            "JOINs, subqueries, UNION and CTEs are not enabled yet."
        )

    tables = list(tree.find_all(exp.Table))

    if not tables or any(
        table.name.lower() != "students"
        or table.db
        or table.catalog
        for table in tables
    ):
        raise ValueError("Only the students table is allowed.")

    allowed_columns = {"id", "name", "course", "marks"}

    for column in tree.find_all(exp.Column):
        if (
            column.name.lower() not in allowed_columns
            or column.table
            or column.db
            or column.catalog
        ):
            raise ValueError(
                f"Column '{column.name}' is not allowed."
            )

    # Enforce a maximum of 100 returned rows.
    return tree.limit(100).sql(dialect="mysql")


# ---------- Page header ----------
st.title("📊 AI-Powered Data Analytics Assistant")
st.caption(
    "Natural Language to SQL | Python | MySQL | Pandas | Plotly"
)

dashboard_tab, assistant_tab, history_tab = st.tabs(
    ["📊 Dashboard", "🤖 AI SQL Assistant", "🕘 Query History"]
)


# ---------- Dashboard ----------
with dashboard_tab:
    st.subheader("Student Performance Overview")

    try:
        df = load_students()

        if df.empty:
            st.info("No student records found.")
        else:
            df["marks"] = pd.to_numeric(df["marks"], errors="coerce")
            df = df.dropna(subset=["marks"])

            if df.empty:
                st.info("No valid marks are available.")
            else:
                courses = sorted(
                    df["course"].dropna().unique().tolist()
                )

                selected_courses = st.multiselect(
                    "Filter by course",
                    options=courses,
                    default=courses,
                    key="dashboard_courses"
                )

                filtered = df[df["course"].isin(selected_courses)]

                if filtered.empty:
                    st.info("Select a course to view its analytics.")
                else:
                    c1, c2, c3, c4 = st.columns(4)

                    c1.metric("Total Students", len(filtered))
                    c2.metric(
                        "Average Marks",
                        f"{filtered['marks'].mean():.2f}"
                    )
                    c3.metric(
                        "Highest Marks",
                        f"{filtered['marks'].max():g}"
                    )
                    c4.metric(
                        "Below 40 Marks",
                        int((filtered["marks"] < 40).sum())
                    )

                    left, right = st.columns(2)

                    with left:
                        st.markdown("#### Average Marks by Course")
                        course_avg = (
                            filtered.groupby("course", as_index=False)
                            ["marks"].mean()
                        )

                        fig = px.bar(
                            course_avg,
                            x="course",
                            y="marks",
                            color="course",
                            text_auto=".2f",
                            labels={
                                "course": "Course",
                                "marks": "Average Marks"
                            }
                        )
                        fig.update_layout(showlegend=False)
                        st.plotly_chart(
                            fig, use_container_width=True
                        )

                    with right:
                        st.markdown("#### Marks Distribution")
                        fig = px.histogram(
                            filtered,
                            x="marks",
                            nbins=10,
                            labels={"marks": "Marks"}
                        )
                        st.plotly_chart(
                            fig, use_container_width=True
                        )

                    st.markdown("#### Student Records")
                    st.dataframe(
                        filtered,
                        use_container_width=True,
                        hide_index=True
                    )

                    st.download_button(
                        "⬇️ Download Dashboard CSV",
                        data=filtered.to_csv(index=False).encode("utf-8"),
                        file_name="student_analytics.csv",
                        mime="text/csv"
                    )

    except Exception as error:
        st.error(
            "Dashboard could not load. Check your MySQL service "
            "and .env settings."
        )
        st.caption(str(error))


# ---------- AI SQL Assistant ----------
with assistant_tab:
    st.subheader("Ask questions in simple English")

    question = st.text_input(
        "Your question",
        placeholder="Show students who scored less than 90 marks",
        key="sql_question"
    )

    if st.button("Generate SQL & Analyze", type="primary"):
        if not question.strip():
            st.warning("Please enter a question.")
        elif not os.getenv("GROQ_API_KEY"):
            st.error("GROQ_API_KEY is missing from your .env file.")
        else:
            connection = None
            cursor = None

            try:
                client = OpenAI(
                    api_key=os.getenv("GROQ_API_KEY"),
                    base_url="https://api.groq.com/openai/v1"
                )

                with st.spinner("Generating SQL with AI..."):
                    response = client.responses.create(
                        model="openai/gpt-oss-120b",
                        instructions=(
                            "Convert the user's question into one MySQL "
                            "SELECT query using only the students table "
                            "and columns id, name, course, marks. "
                            "Return SQL only, without markdown. "
                            "Do not generate data-changing statements. "
                            "Do not use joins, subqueries, CTEs or UNION."
                        ),
                        input=question
                    )

                generated_sql = response.output_text.strip()
                safe_sql = validate_sql(generated_sql)

                st.markdown("#### Validated SQL")
                st.code(safe_sql, language="sql")

                with st.spinner("Reading data from MySQL..."):
                    connection = get_connection()
                    cursor = connection.cursor(dictionary=True)
                    cursor.execute(safe_sql)
                    results = cursor.fetchmany(100)

                result_df = pd.DataFrame(results)

                st.markdown("#### Query Results")

                if result_df.empty:
                    st.info("No matching records found.")
                else:
                    st.dataframe(
                        result_df,
                        use_container_width=True,
                        hide_index=True
                    )

                    st.download_button(
                        "⬇️ Download Query Results CSV",
                        data=result_df.to_csv(index=False).encode("utf-8"),
                        file_name="query_results.csv",
                        mime="text/csv",
                        key="query_download"
                    )

                st.session_state.last_result = result_df
                st.session_state.last_sql = safe_sql

                # Keep recent queries for this browser session.
                st.session_state.history.insert(0, {
                    "question": question,
                    "sql": safe_sql,
                    "rows": len(result_df)
                })
                st.session_state.history = (
                    st.session_state.history[:20]
                )

                st.markdown("#### AI Explanation")

                try:
                    with st.spinner("Preparing a plain-English explanation..."):
                        explanation_response = client.responses.create(
                            model="openai/gpt-oss-120b",
                            instructions=(
                                "Explain the SQL query and its results "
                                "in simple English for a beginner. "
                                "Describe what the query filters or "
                                "calculates. Do not claim trends or "
                                "facts that are not supported by the "
                                "provided result summary."
                            ),
                            input=(
                                f"User question: {question}\n"
                                f"SQL: {safe_sql}\n"
                                f"Rows returned: {len(result_df)}\n"
                                f"Column names: {list(result_df.columns)}\n"
                                "Explain the query and the row count."
                            )
                        )

                    st.write(explanation_response.output_text)

                except Exception:
                    st.info(
                        "Query completed. AI explanation is temporarily "
                        "unavailable."
                    )

                st.success(f"Query completed: {len(result_df)} row(s).")

            except Exception as error:
                st.error(f"Could not process the query: {error}")

            finally:
                if cursor is not None:
                    cursor.close()

                if connection is not None and connection.is_connected():
                    connection.close()


# ---------- Query History ----------
with history_tab:
    st.subheader("Recent Query History")
    st.caption(
        "History is kept in Streamlit session state; it is not "
        "permanently stored in the database."
    )

    if not st.session_state.history:
        st.info("No queries yet. Run a question in the AI SQL Assistant tab.")
    else:
        for index, item in enumerate(st.session_state.history, start=1):
            with st.expander(
                f"{index}. {item['question']} — {item['rows']} row(s)"
            ):
                st.code(item["sql"], language="sql")
                st.write(f"Rows returned: {item['rows']}")

        if st.button("Clear Query History"):
            st.session_state.history = []
            st.rerun()
