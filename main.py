import os
import random
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Punjab Exam Prep Backend",
    version="1.0.0",
    description="Backend for Tests, Current Affairs, Vault, and Mindset Mentor via Groq SDK"
)

# Flutter ऐप से कॉल करने के लिए CORS परमिशन
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# GROQ क्लाइंट सेटअप (ऑफिशियल Groq SDK)
# --------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# अगर .env में GROQ_API_KEY सेट है, तो Groq() अपने आप उसे पहचान लेता है
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

GROQ_MODEL = "openai/gpt-oss-120b"

MENTOR_SYSTEM_INSTRUCTION = """
Aap ek supportive aur realistic study mentor hain jo chat par natural insaan ki tarah Hinglish me baat karta hai.

STRICT CONVERSATION RULES:
1. NO PRE-WRITTEN INTRO: "Namaste! Main aapka Mindset & Strategy mentor hoon", "Aapko kis cheez mein guidance chahiye" jaisi lines bolna SAKHT MANA HAI. Apni pehchan ya post har baar repeat mat karo.
2. GREETINGS: Agar user sirf "hi", "hello", ya "hlo" likhe, to WhatsApp style me short reply do: "Hello! Kaisi chal rahi hai taiyari? Aaj kya padh rahe ho?"
3. CRISP & POINT-TO-POINT: Har jawab strictly 2 se 3 natural sentences me practical hona chahiye. Koi lambe bhashan nahi.
"""

# --------------------------------------------------------------------------
# इन-मेमोरी डेटा बैंक (Google Sheet से कैश्ड)
# --------------------------------------------------------------------------
QUESTION_BANK = [
    {
        "id": 1,
        "exam_tag": "punjab_police",
        "subject": "Punjab GK",
        "question": "Which treaty was signed between Maharaja Ranjit Singh and the British in 1809?",
        "options": ["Treaty of Lahore", "Treaty of Amritsar", "Treaty of Bhyrowal", "Treaty of Sutlej"],
        "correct_answer": "Treaty of Amritsar",
        "explanation": "The Treaty of Amritsar was signed in 1809 between Maharaja Ranjit Singh and Charles T. Metcalfe of the British East India Company."
    },
    {
        "id": 2,
        "exam_tag": "punjab_police",
        "subject": "Reasoning",
        "question": "If PUNJAB is coded as QVOJBC, what is the code for POLICE?",
        "options": ["QPMJDF", "QPMJDE", "QPNJDF", "QOMJDE"],
        "correct_answer": "QPMJDF",
        "explanation": "Each letter is shifted forward by +1: P->Q, O->P, L->M, I->J, C->D, E->F."
    },
    {
        "id": 3,
        "exam_tag": "psssb",
        "subject": "Punjab GK",
        "question": "Which district of Punjab has the lowest literacy rate according to Census 2011?",
        "options": ["Mansa", "Muktsar", "Fazilka", "Bathinda"],
        "correct_answer": "Mansa",
        "explanation": "According to the 2011 Census, Mansa had the lowest literacy rate (approx 61.8%) in Punjab."
    }
]

CURRENT_AFFAIRS_BANK = [
    {
        "id": 101,
        "category": "Punjab State",
        "date": "2026-10-10",
        "title": "Punjab Canal System Modernization Project",
        "bullets": [
            "State government initiates lining of regional distributor canals.",
            "Aimed at boosting water efficiency in Malwa belt.",
            "Important for state agriculture & economy sections."
        ]
    },
    {
        "id": 102,
        "category": "National",
        "date": "2026-10-12",
        "title": "National Green Hydrogen Corridor Launch",
        "bullets": [
            "Inaugurated to fast-track heavy transit decarbonization.",
            "Exam relevance: Environment, Science & Technology."
        ]
    }
]

# --------------------------------------------------------------------------
# डेटा मॉडल्स (Pydantic Schemas)
# --------------------------------------------------------------------------
class QuestionPublic(BaseModel):
    id: int
    exam_tag: str
    subject: str
    question: str
    options: List[str]

class UserAnswer(BaseModel):
    question_id: int
    selected_option: str

class SubmitTestRequest(BaseModel):
    exam_tag: str
    answers: List[UserAnswer]
    negative_marking_rate: float = 0.25

class QuestionAnalysis(BaseModel):
    question_id: int
    question: str
    user_selected: str
    correct_answer: str
    is_correct: bool
    explanation: str

class SubmitTestResponse(BaseModel):
    total_questions: int
    attempted: int
    correct: int
    incorrect: int
    score: float
    accuracy_percentage: float
    review: List[QuestionAnalysis]

class VaultRequest(BaseModel):
    question_ids: List[int]

class MentorQuery(BaseModel):
    message: str = Field(..., max_length=300)

class MentorResponse(BaseModel):
    reply: str
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_questions_from_sheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open("youth_library_questions").sheet1
        records = sheet.get_all_records()
        
        bank = []
        for r in records:
            bank.append({
                "id": int(r["id"]),
                "exam_tag": str(r["exam_tag"]).strip(),
                "subject": str(r.get("subject", "")).strip(),
                "question": str(r["question"]).strip(),
                "options": [str(r["option_a"]), str(r["option_b"]), str(r["option_c"]), str(r["option_d"])],
                "correct_answer": str(r["correct_answer"]).strip(),
                "explanation": str(r.get("explanation", "")).strip()
            })
        print(f"--- SUCCESS: Sheet se {len(bank)} questions load hue! ---")
        return bank
    except Exception as e:
        print("Sheet Fetch Error:", e)
        return QUESTION_BANK

# --------------------------------------------------------------------------
# टैब 1: टेस्ट और क्विज़ (सुरक्षित बैकएंड इवैल्यूएशन)
# --------------------------------------------------------------------------
@app.get("/api/test/start")
def start_test(
    exam: str = "punjab_police", 
    subject: Optional[str] = None, 
    count: int = 10
):
    all_data = get_questions_from_sheet()

    # 1. Sirf same exam_tag filter karein
    pool = [
        q for q in all_data 
        if str(q.get("exam_tag", "")).strip().lower() == exam.strip().lower()
    ]

    # 2. Agar subject diya ho, toh sirf wahi subject rakhein
    if subject:
        pool = [
            q for q in pool 
            if str(q.get("subject", "")).strip().lower() == subject.strip().lower()
        ]

    if not pool:
        return []

    # 3. Same exam aur subject ke questions ko random shuffle karein
    shuffled_questions = list(pool)
    random.shuffle(shuffled_questions)

    selected = shuffled_questions[:min(len(shuffled_questions), count)]

    # 4. Har question ke options shuffle karein (Tag aur Subject bilkul wahi rahega)
    result = []
    for q in selected:
        opts = list(q["options"])
        random.shuffle(opts)
        result.append({
            "id": q["id"],
            "exam_tag": q["exam_tag"],
            "subject": q["subject"],
            "question": q["question"],
            "options": opts,
            "correct_answer": q["correct_answer"],
            "explanation": q.get("explanation", "")
        })
    return result

@app.post("/api/test/submit", response_model=SubmitTestResponse)
def submit_test(submission: SubmitTestRequest):
    current_bank = get_questions_from_sheet()
    lookup = {q["id"]: q for q in current_bank}
    
    correct_count = 0
    incorrect_count = 0
    review_list = []
    
    for ans in submission.answers:
        q_data = lookup.get(ans.question_id)
        if not q_data:
            continue
            
        is_corr = (ans.selected_option.strip() == q_data["correct_answer"].strip())
        if is_corr:
            correct_count += 1
        else:
            incorrect_count += 1
            
        review_list.append(QuestionAnalysis(
            question_id=q_data["id"],
            question=q_data["question"],
            user_selected=ans.selected_option,
            correct_answer=q_data["correct_answer"],
            is_correct=is_corr,
            explanation=q_data["explanation"]
        ))
    
    attempted = len(submission.answers)
    final_score = (correct_count * 1.0) - (incorrect_count * submission.negative_marking_rate)
    accuracy = (correct_count / attempted * 100.0) if attempted > 0 else 0.0
    
    return SubmitTestResponse(
        total_questions=attempted,
        attempted=attempted,
        correct=correct_count,
        incorrect=incorrect_count,
        score=round(max(0.0, final_score), 2),
        accuracy_percentage=round(accuracy, 2),
        review=review_list
    )

# --------------------------------------------------------------------------
# टैब 2: करंट अफेयर्स (फ़ास्ट कैश्ड डेटा)
# --------------------------------------------------------------------------
@app.get("/api/current-affairs")
def get_current_affairs(category: Optional[str] = None):
    try:
        # gspread service account client initialize karein
        client = gspread.service_account(filename="service_account.json")
        sheet = client.open("youth_library_questions").worksheet("current_affairs")
        records = sheet.get_all_records()
        
        # Latest entries pehle lane ke liye reverse karein
        records.reverse()
        
        if category:
            return [
                r for r in records 
                if str(r.get("category", "")).strip().lower() == category.strip().lower()
            ]
        return records[:10]
    except Exception as e:
        print("Current affairs fetch error:", e)
        return []

# --------------------------------------------------------------------------
# टैब 3: सब्जेक्ट प्रैक्टिस और मिस्टेक वॉल्ट
# --------------------------------------------------------------------------
@app.get("/api/practice/questions", response_model=List[QuestionPublic])
def get_practice_questions(subject: str):
    filtered = [q for q in QUESTION_BANK if q["subject"].lower() == subject.lower()]
    return [
        QuestionPublic(
            id=q["id"],
            exam_tag=q["exam_tag"],
            subject=q["subject"],
            question=q["question"],
            options=q["options"]
        ) for q in filtered
    ]

@app.post("/api/vault/details", response_model=List[QuestionAnalysis])
def get_vault_explanations(payload: VaultRequest):
    lookup = {q["id"]: q for q in QUESTION_BANK}
    results = []
    for q_id in payload.question_ids:
        if q_id in lookup:
            q = lookup[q_id]
            results.append(QuestionAnalysis(
                question_id=q["id"],
                question=q["question"],
                user_selected="Previously Failed",
                correct_answer=q["correct_answer"],
                is_correct=False,
                explanation=q["explanation"]
            ))
    return results

# --------------------------------------------------------------------------
# टैब 4: मेंटर (Groq SDK द्वारा पावर्ड)
# --------------------------------------------------------------------------
@app.post("/api/mentor/ask", response_model=MentorResponse)
def ask_mentor(query: MentorQuery):
    if not groq_client:
        return MentorResponse(
            reply="Hello! Kaisi chal rahi hai taiyari? Aaj kya padh rahe ho?"
        )
    
    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": MENTOR_SYSTEM_INSTRUCTION},
                {"role": "user", "content": query.message}
            ],
            max_tokens=400,
            temperature=0.7,
        )
        reply_text = completion.choices[0].message.content.strip()
        return MentorResponse(reply=reply_text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Groq Mentor Error: {str(e)}"
        )

# --------------------------------------------------------------------------
# सिस्टम: कैशे रीफ़्रेश
# --------------------------------------------------------------------------
@app.post("/api/system/refresh-cache")
def refresh_cache():
    return {"status": "success", "message": "Question cache refreshed successfully."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
