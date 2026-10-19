import os
import json
import gspread
import feedparser
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# 1. Setup Clients
groq_client = Groq(api_key="")
sheet_client = gspread.service_account(filename="service_account.json")
worksheet = sheet_client.open("youth_library_questions").worksheet("current_affairs")

# 2. Fetch Live RSS Headlines (The Tribune / PIB)
# 2. Reliable Google News RSS Feeds (Ye kabhi block nahi hoti)
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=Punjab+government+scheme+OR+cabinet+decision&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=India+national+policy+economy+MoU&hl=en-IN&gl=IN&ceid=IN:en"
]

def fetch_live_headlines():
    headlines = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                summary_text = entry.get('summary', '') or entry.get('description', '')
                headlines.append(f"Title: {entry.title} - Details: {summary_text}")
        except Exception as e:
            print(f"Feed error {url}: {e}")
    return "\n".join(headlines[:8])

# 3. AI Summarizer for Exam Format
def generate_and_update_affairs():
    raw_news = fetch_live_headlines()
    
    # AGAR NEWS NAHI MILI TOH AI CALL HI NAHI HOGA (Fake News Stop)
    if not raw_news.strip():
        print("ERROR: No real news fetched from RSS. Aborting to prevent fake news.")
        return

    prompt = f"""
Strict Instruction:
1. Summarize ONLY actual government policy, schemes, appointments, or national/state events.
2. DO NOT include test series, cut-off marks, answer keys, results, or coaching institute names (like Adda247, Testbook, etc.).
3. Write completely neutral text without mentioning any third-party website or coaching platform.

Raw News Data:
{raw_news}

Format Guidelines:
• Category: Either 'Punjab' or 'National'
• Title: Crisp news headline under 12 words
• Desc: 1-2 lines summarizing the event and its importance for exams
• Tag: Relevant topic like Polity, Agriculture, Governance, Economy

Return ONLY a valid JSON array matching this exact schema:
[
  {{
    "category": "Punjab",
    "title": "Headline",
    "desc": "Description text",
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
