import os
import json
import gspread
import feedparser
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# 1. Setup Clients
groq_client = Groq(api_key="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")
sheet_client = gspread.service_account(filename="service_account.json")
worksheet = sheet_client.open("youth_library_questions").worksheet("current_affairs")

# 2. Fetch Live RSS Headlines (The Tribune / PIB)
# 2. Reliable Google News RSS Feeds (Ye kabhi block nahi hoti)
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=Punjab+government+exam&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=India+national+news+economy+policy&hl=en-IN&gl=IN&ceid=IN:en"
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
Strict Instruction: Summarize ONLY the actual facts present in the Raw News Data below.
DO NOT fabricate, guess, or invent any news, percentages, or government acts.

Raw News Data:
{raw_news}
"""

Format Guidelines:
- Category: Either 'Punjab' or 'National'
- Title: Crisp, professional news headline (under 12 words)
- Desc: 1-2 lines summarizing the event + exam importance (e.g., historical linkage, ministry, act, scheme)
- Tag: Relevant topic (e.g., 'Polity', 'Agriculture', 'Governance', 'Economy')

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
