import os
import json
import gspread
import feedparser
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# 1. Setup Clients
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
sheet_client = gspread.service_account(filename="service_account.json")
worksheet = sheet_client.open("youth_library_questions").worksheet("current_affairs")

# 2. Fetch Live RSS Headlines (The Tribune / PIB)
RSS_FEEDS = [
    "https://www.tribuneindia.com/rss/punjab.xml", # Punjab regional updates
    "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1" # National policy & schemes
]

def fetch_live_headlines():
    headlines = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]: # Top 5 headlines per source
                headlines.append(f"Title: {entry.title} - Summary: {entry.get('summary', '')}")
        except Exception as e:
            print(f"Feed error {url}: {e}")
    return "\n".join(headlines[:8])

# 3. AI Summarizer for Exam Format
def generate_and_update_affairs():
    raw_news = fetch_live_headlines()
    
    prompt = f"""
Convert these raw news headlines into exactly 4 high-yield, exam-relevant Current Affairs cards for Punjab competitive exams (Punjab Police, Patwari).

Raw News Data:
{raw_news}

Format Guidelines:
• Category: Either 'Punjab' or 'National'
• Title: Crisp, professional news headline (under 12 words)
• Desc: 1-2 lines summarizing the event + exam importance (e.g., historical linkage, ministry, act, scheme)
• Tag: Relevant topic (e.g., 'Polity', 'Agriculture', 'Governance', 'Economy')

Return ONLY a valid JSON array matching this exact schema:
[
  {{
    "category": "Punjab",
    "title": "Headline text here",
    "desc": "Exam-relevant summary with policy or static fact",
    "tag": "Governance"
  }}
]
"""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "You are an expert exam content editor. Return ONLY a valid JSON array."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    raw_text = response.choices[0].message.content.strip()
    start_idx = raw_text.find('[')
    end_idx = raw_text.rfind(']')
    data = json.loads(raw_text[start_idx : end_idx + 1])

    # 4. Insert into Google Sheet (current_affairs tab)
    rows_to_insert = []
    for item in data:
        rows_to_insert.append([
            item.get("category", "Punjab"),
            item.get("title", ""),
            item.get("desc", ""),
            item.get("tag", "General")
        ])

    worksheet.append_rows(rows_to_insert)
    print(f"--- SUCCESS: {len(rows_to_insert)} live exam current affairs added! ---")

if __name__ == "__main__":
    generate_and_update_affairs()