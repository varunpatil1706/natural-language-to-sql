
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

response = client.responses.create(
    model="openai/gpt-oss-120b",
    instructions=(
        "Convert the user's question into one MySQL SELECT query. "
        "Use only the students table with columns id, name, course, marks. "
        "Return only SQL, without markdown."
    ),
    input="Show students who scored more than 80 marks."
)

print("Generated SQL:")
print(response.output_text)
