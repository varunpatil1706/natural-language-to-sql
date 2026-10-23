
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Student Analytics Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Student Performance Analytics")
st.caption("AI-Powered Data Analytics | Python • MySQL • Streamlit")

@st.cache_data(ttl=60)
def load_student_data():
    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "student_db"),
        connection_timeout=10
    )

    try:
        query = """
            SELECT id, name, course, marks
            FROM students
            LIMIT 5000
        """
        return pd.read_sql(query, connection)
    finally:
        connection.close()


try:
    df = load_student_data()

    if df.empty:
        st.warning("No student records found in the database.")
        st.stop()

    df["marks"] = pd.to_numeric(df["marks"], errors="coerce")
    df = df.dropna(subset=["marks"])

    if df.empty:
        st.warning("No valid marks found.")
        st.stop()

    # Dashboard filters
    st.sidebar.header("Dashboard Filters")

    courses = sorted(df["course"].dropna().unique().tolist())
    selected_courses = st.sidebar.multiselect(
        "Select courses",
        options=courses,
        default=courses
    )

    filtered_df = df[df["course"].isin(selected_courses)]

    st.sidebar.caption("Dashboard refresh interval: 60 seconds")

    if filtered_df.empty:
        st.info("Select at least one course to view analytics.")
        st.stop()

    # KPI cards
    total_students = len(filtered_df)
    average_marks = filtered_df["marks"].mean()
    highest_marks = filtered_df["marks"].max()
    students_below_40 = (filtered_df["marks"] < 40).sum()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Students", f"{total_students:,}")
    col2.metric("Average Marks", f"{average_marks:.2f}")
    col3.metric("Highest Marks", f"{highest_marks:g}")
    col4.metric("Below 40 Marks", f"{students_below_40:,}")

    st.divider()

    # Charts
    left, right = st.columns(2)

    with left:
        st.subheader("Average Marks by Course")

        course_avg = (
            filtered_df.groupby("course", as_index=False)["marks"]
            .mean()
            .sort_values("marks", ascending=False)
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
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Marks Distribution")

        fig = px.histogram(
            filtered_df,
            x="marks",
            nbins=10,
            labels={"marks": "Marks"},
            color_discrete_sequence=["#4C78A8"]
        )
        st.plotly_chart(fig, use_container_width=True)

    # Student records
    st.subheader("Student Records")

    search = st.text_input("Search student by name")

    display_df = filtered_df.copy()

    if search.strip():
        display_df = display_df[
            display_df["name"].astype(str).str.contains(
                search.strip(),
                case=False,
                na=False
            )
        ]

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # CSV export
    csv_data = display_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="⬇️ Download CSV",
        data=csv_data,
        file_name="student_analytics.csv",
        mime="text/csv"
    )

    st.caption(
        "Analytics are calculated from the records loaded into this dashboard. "
        "Maximum records loaded: 5,000."
    )

except Exception as error:
    st.error(
        "Database connection or dashboard error. "
        "Check your .env settings and MySQL service."
    )
    st.code(str(error))
