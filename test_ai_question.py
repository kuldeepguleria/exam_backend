import os
import json
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
import gspread
from groq import Groq

# 1. Load environment variables from .env
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    raise ValueError("Error: .env file me GROQ_API_KEY nahi mili! Kripya .env file check karein.")

# 2. Google Sheets Configuration
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SPREADSHEET_NAME = "youth_library_questions"
SERVICE_ACCOUNT_FILE = "service_account.json"

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open(SPREADSHEET_NAME)
worksheet = sh.sheet1

# 3. Groq AI Client Initialization
client = Groq(
    api_key=groq_api_key,
    timeout=30.0,
    max_retries=2,
)

def generate_test_questions():
    exam_tag = "punjab_police"
    subject = "Punjabi Language Skills"
    count = 2

    print(f"Groq AI (openai/gpt-oss-120b) se {count} sawal banwaye ja rahe hain...")

    prompt = f"""
Create exactly {count} standard multiple choice questions for Punjab competitive exam.
Exam Tag: {exam_tag}
Subject: {subject}
Language: Punjabi / English mix
Difficulty & Standard: Strictly follow the actual difficulty level, style, and question pattern of Punjab Police Constable previous years' papers. Questions should be direct, conceptual, application-based, and tailored for 10+2 level competitive recruitment (not overly academic, but crisp, tricky, and exam-relevant).

Output MUST be a valid JSON array of objects with these exact keys and nothing else:
[
  {{
    "exam_tag": "{exam_tag}",
    "subject": "{subject}",
    "question": "question text",
    "option_a": "option A text",
    "option_b": "option B text",
    "option_c": "option C text",
    "option_d": "option D text",
    "correct_answer": "exact text of correct option",
    "explanation": "short explanation"
  }}
]
"""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional exam paper creator. Return ONLY a valid JSON array of objects without markdown formatting, code fences, or any intro text."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        raw_text = response.choices[0].message.content.strip()

        # Bracket se bracket tak ka exact JSON hissa extract karein
        start_idx = raw_text.find('[')
        end_idx = raw_text.rfind(']')

        if start_idx != -1 and end_idx != -1:
            raw_text = raw_text[start_idx : end_idx + 1]

        questions = json.loads(raw_text)

        # Existing rows count karke next auto-increment ID generate karna
        existing_rows = worksheet.get_all_values()
        next_id = len(existing_rows)

        rows_to_insert = []
        for q in questions:
            row = [
                next_id,
                q.get("exam_tag", exam_tag),
                q.get("subject", subject),
                q.get("question", ""),
                q.get("option_a", ""),
                q.get("option_b", ""),
                q.get("option_c", ""),
                q.get("option_d", ""),
                q.get("correct_answer", ""),
                q.get("explanation", "")
            ]
            rows_to_insert.append(row)
            next_id += 1

        worksheet.append_rows(rows_to_insert)
        print(f"Badhiya! {len(rows_to_insert)} questions Google Sheet me exact 10 columns me insert ho gaye.")

    except Exception as e:
        print(f"Error aayi: {e}")

if __name__ == "__main__":
    generate_test_questions()