import asyncio
import re
import json
import os
import hashlib
import dateutil.parser
import httpx
from telethon import TelegramClient

# ================= CONFIG =================
import os

api_id        = 34263733
api_hash      = "a82e943b286084495d9c861a4105a943"

GROQ_API_KEY  = os.getenv("GROQ_API_KEY")  # Set this environment variable with your Groq API key
NOTION_TOKEN  = os.getenv("NOTION_TOKEN")  # Set this environment variable with your Notion token
DATABASE_ID   = "20af34c645184378a9c472018328abb0"

TARGET_CHANNELS = [
    "شباب بتساعد شباب",
    "Ramzy Abdelaziz - رمزي عبدالعزيز",
]

MSG_LIMIT       = 200
SEEN_FILE       = "seen_hashes.json"
LAST_IDS_FILE   = "last_msg_ids.json"

GROQ_DELAY      = 2.5   # seconds between every Groq call
GROQ_MAX_RETRY  = 3     # retries on 429
GROQ_RETRY_WAIT = 60    # seconds to wait when rate limited
# ==========================================


# ================= PERSISTENCE =================
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def msg_hash(text):
    return hashlib.md5(text.strip().encode()).hexdigest()


# ================= KEYWORD PRE-FILTER =================
OPPORTUNITY_KW = [
    "intern", "internship", "job", "scholarship", "fellowship",
    "program", "training", "hackathon", "research", "competition",
    "grant", "تدريب", "وظيفة", "منحة", "برنامج", "مسابقة", "فرصة"
]
TECH_KW = [
    "ai", "machine learning", "deep learning", "computer vision", "nlp",
    "data science", "embedded", "fpga", "hardware", "software engineering",
    "robotics", "cloud", "devops", "cybersecurity", "computer engineering",
    "برمجة", "هندسة", "تقنية", "ذكاء اصطناعي", "بيانات"
]
DROP_KW = ["crypto", "forex", "trading", "تداول", "عملات", "ربح سريع"]

def quick_filter(text):
    if not text:
        return False
    t = text.lower()
    if any(k in t for k in DROP_KW):
        return False
    return any(k in t for k in OPPORTUNITY_KW) or any(k in t for k in TECH_KW)


# ================= GROQ AI EXTRACTION =================
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

EXTRACT_PROMPT = """You are a strict data extractor. Extract structured information from the message below.

Only mark relevant=true if the opportunity is related to:
  Tech, AI, Software, Hardware, Computer Engineering, Data Science, Robotics, Cloud, Cybersecurity, Embedded Systems, STEM Research, or general scholarships/internships.

Return ONLY valid JSON (no markdown, no explanation):
{{
  "title": "",
  "organization": "",
  "category": "",
  "deadline": "",
  "location": "",
  "link": "",
  "relevant": true
}}

Rules:
- category must be one of: Internship, Job, Scholarship, Fellowship, Hackathon, Research, Competition, Grant, Other
- Convert deadline to YYYY-MM-DD if mentioned, else leave empty string
- If not relevant set relevant=false and leave other fields empty
- Never hallucinate information not present in the text
- Keep title concise (max 10 words)

MESSAGE:
{text}
"""

async def ai_extract(text, client):
    prompt = EXTRACT_PROMPT.format(text=text[:3000])
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "max_tokens": 300,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, GROQ_MAX_RETRY + 1):
        try:
            resp = await client.post(GROQ_URL, json=payload, headers=headers, timeout=30)

            if resp.status_code == 429:
                wait = GROQ_RETRY_WAIT * attempt
                print(f"  ⏳ Groq rate limited. Waiting {wait}s (retry {attempt}/{GROQ_MAX_RETRY})...")
                await asyncio.sleep(wait)
                continue

            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)

        except httpx.HTTPStatusError as e:
            print(f"  [GROQ HTTP ERROR] {e.response.status_code} on attempt {attempt}")
            if attempt < GROQ_MAX_RETRY:
                await asyncio.sleep(GROQ_RETRY_WAIT)
        except Exception as e:
            print(f"  [GROQ ERROR] {e} on attempt {attempt}")
            if attempt < GROQ_MAX_RETRY:
                await asyncio.sleep(5)

    print("  ❌ Groq failed after all retries, skipping message.")
    return None


# ================= NORMALIZERS =================
def normalize_deadline(date_str):
    if not date_str:
        return None
    try:
        dt = dateutil.parser.parse(date_str, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def normalize_category(cat):
    valid = {"Internship", "Job", "Scholarship", "Fellowship",
             "Hackathon", "Research", "Competition", "Grant", "Other"}
    return cat if cat in valid else "Other"

def extract_first_url(text):
    urls = re.findall(r'https?://\S+', text)
    return urls[0] if urls else None


# ================= NOTION =================
NOTION_PAGES_URL = "https://api.notion.com/v1/pages"

async def send_to_notion(data, client):
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    db_id = DATABASE_ID.replace("-", "")

    properties = {
        "Name": {
            "title": [{"text": {"content": data.get("title") or "Untitled"}}]
        },
        "Category": {
            "select": {"name": data.get("category", "Other")}
        },
        "Organization": {
            "rich_text": [{"text": {"content": data.get("organization") or ""}}]
        },
        "Location": {
            "rich_text": [{"text": {"content": data.get("location") or ""}}]
        },
        "Source": {
            "rich_text": [{"text": {"content": data.get("source") or "Telegram"}}]
        },
    }

    link = data.get("link")
    if link:
        properties["Link"] = {"url": link}

    deadline = data.get("deadline")
    if deadline:
        properties["Deadline"] = {"date": {"start": deadline}}

    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
    }

    try:
        resp = await client.post(NOTION_PAGES_URL, json=payload, headers=headers, timeout=15)

        if resp.status_code == 404:
            print("  [NOTION 404] Database not found. Check:")
            print(f"     → DATABASE_ID value: '{DATABASE_ID}'")
            print("     → Open DB in Notion → '...' → Connections → add your integration")
            return False
        if resp.status_code == 401:
            print("  [NOTION 401] Bad token. Check NOTION_TOKEN.")
            return False

        resp.raise_for_status()
        return True

    except Exception as e:
        print(f"  [NOTION ERROR] {e}")
        return False


# ================= NOTION STARTUP TEST =================
async def test_notion(client):
    print("\n🔧 Testing Notion connection...")
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
    }
    db_id = DATABASE_ID.replace("-", "")
    try:
        resp = await client.get(
            f"https://api.notion.com/v1/databases/{db_id}",
            headers=headers, timeout=10
        )
        if resp.status_code == 200:
            title = resp.json().get("title", [{}])[0].get("plain_text", "Unknown")
            print(f"  ✅ Notion OK! Database: '{title}'")
            return True
        elif resp.status_code == 404:
            print("  ❌ Notion 404 — database not found or integration not connected.")
            print("     Fix: Notion DB → '...' → Connections → add your integration")
            return False
        elif resp.status_code == 401:
            print("  ❌ Notion 401 — invalid token.")
            return False
        else:
            print(f"  ⚠️  Notion returned unexpected status {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Notion test error: {e}")
        return False


# ================= MAIN =================
async def main():
    seen_hashes = set(load_json(SEEN_FILE, []))
    last_ids    = load_json(LAST_IDS_FILE, {})
    added_count = 0

    # ✅ Fix: use "async with" instead of awaiting TelegramClient directly
    async with TelegramClient("session", api_id, api_hash) as tg_client:
        await tg_client.start()

        async with httpx.AsyncClient() as http:

            # Fail fast if Notion is misconfigured
            notion_ok = await test_notion(http)
            if not notion_ok:
                print("\n⛔ Fix Notion config before running. Exiting.")
                return  # async with handles disconnect automatically

            # Find target channels
            target_map = {}
            async for dialog in tg_client.iter_dialogs():
                if dialog.name in TARGET_CHANNELS:
                    target_map[dialog.name] = dialog.entity
                    print(f"✅ Found channel: {dialog.name}")

            for m in set(TARGET_CHANNELS) - set(target_map.keys()):
                print(f"⚠️  Channel not found: '{m}'")

            for ch_name, entity in target_map.items():
                ch_key    = str(entity.id)
                min_id    = last_ids.get(ch_key, 0)
                newest_id = min_id

                print(f"\n📡 Scanning: {ch_name}  (messages after id={min_id})")

                async for msg in tg_client.iter_messages(entity, limit=MSG_LIMIT, min_id=min_id):
                    text = msg.text
                    if not text:
                        continue

                    if msg.id > newest_id:
                        newest_id = msg.id

                    h = msg_hash(text)
                    if h in seen_hashes:
                        continue

                    if not quick_filter(text):
                        seen_hashes.add(h)
                        continue

                    print(f"  🔍 Checking msg {msg.id} …")

                    # Proactive delay to stay within Groq rate limit
                    await asyncio.sleep(GROQ_DELAY)

                    extracted = await ai_extract(text, http)
                    if not extracted or not extracted.get("relevant"):
                        seen_hashes.add(h)
                        continue

                    extracted["category"] = normalize_category(extracted.get("category", ""))
                    extracted["deadline"] = normalize_deadline(extracted.get("deadline", "")) or ""
                    extracted["source"]   = ch_name

                    if not extracted.get("link"):
                        extracted["link"] = extract_first_url(text)

                    ok = await send_to_notion(extracted, http)
                    if ok:
                        print(f"  ✅ Added: {extracted.get('title')}")
                        added_count += 1
                    else:
                        print(f"  ❌ Notion failed for: {extracted.get('title')}")

                    seen_hashes.add(h)

                if newest_id > min_id:
                    last_ids[ch_key] = newest_id

    # Save state after client closes
    save_json(SEEN_FILE, list(seen_hashes))
    save_json(LAST_IDS_FILE, last_ids)
    print(f"\n🏁 Done. {added_count} new opportunities added to Notion.")


if __name__ == "__main__":
    asyncio.run(main())