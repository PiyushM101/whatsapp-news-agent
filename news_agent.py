import os
import requests
import json

# ── Config ────────────────────────────────────────────────
NEWSAPI_KEY     = os.environ["NEWSAPI_KEY"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]
TWILIO_SID      = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_TOKEN    = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM     = os.environ["TWILIO_WHATSAPP_FROM"]   # e.g. whatsapp:+14155238886
TWILIO_TO       = os.environ["TWILIO_WHATSAPP_TO"]     # e.g. whatsapp:+1XXXXXXXXXX

# Edit these to match your interests
TOPICS = [
    "artificial intelligence",
    "fintech",
    "startup funding",
    "product management",
    "MBA careers",
]

ABOUT_ME = """
I am an MBA student at NYU Stern. I focus on AI, fintech, and tech product management.
I worked at Revolut, OnePay, and Flipkart. I want news that is career-relevant or interesting to me.
"""

MAX_ARTICLES_PER_TOPIC = 5   # articles fetched per topic
MAX_FINAL_ARTICLES     = 7   # articles sent to WhatsApp


# ── Step 1: Fetch news ────────────────────────────────────
def fetch_news(topics):
    articles = []
    seen_urls = set()

    for topic in topics:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": topic,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": MAX_ARTICLES_PER_TOPIC,
            "apiKey": NEWSAPI_KEY,
        }
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()

        for a in data.get("articles", []):
            url_ = a.get("url", "")
            if url_ not in seen_urls and a.get("title") and a.get("description"):
                seen_urls.add(url_)
                articles.append({
                    "title":       a["title"],
                    "description": a["description"],
                    "url":         url_,
                    "source":      a.get("source", {}).get("name", "Unknown"),
                })

    return articles


# ── Step 2: Filter with Claude ────────────────────────────
def filter_with_claude(articles):
    headlines = "\n".join(
        f"{i+1}. [{a['source']}] {a['title']} — {a['description']}"
        for i, a in enumerate(articles)
    )

    prompt = f"""
You are a personal news curator.

About the user:
{ABOUT_ME.strip()}

Here are today's news articles (numbered):

{headlines}

Pick the {MAX_FINAL_ARTICLES} most relevant and interesting articles for this user.
Return ONLY a JSON array of the article numbers you picked, like: [2, 5, 8, 11]
No explanation. Just the JSON array.
"""

    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    res.raise_for_status()

    raw = res.json()["content"][0]["text"].strip()
    # Strip markdown fences if present
    raw = raw.replace("```json", "").replace("```", "").strip()
    indices = json.loads(raw)

    # indices are 1-based
    picked = []
    for i in indices:
        if 1 <= i <= len(articles):
            picked.append(articles[i - 1])
    return picked


# ── Step 3: Send to WhatsApp ──────────────────────────────
def send_whatsapp(articles):
    lines = ["🗞 *Your Daily News Brief*\n"]
    for i, a in enumerate(articles, 1):
        lines.append(f"*{i}. {a['title']}*")
        lines.append(f"_{a['source']}_")
        lines.append(a["url"])
        lines.append("")

    message = "\n".join(lines).strip()

    res = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
        auth=(TWILIO_SID, TWILIO_TOKEN),
        data={
            "From": TWILIO_FROM,
            "To":   TWILIO_TO,
            "Body": message,
        },
        timeout=15,
    )
    res.raise_for_status()
    print("✅ Message sent. SID:", res.json().get("sid"))


# ── Main ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("Fetching news...")
    articles = fetch_news(TOPICS)
    print(f"  Found {len(articles)} articles total.")

    print("Filtering with Claude...")
    picked = filter_with_claude(articles)
    print(f"  Picked {len(picked)} articles.")

    print("Sending to WhatsApp...")
    send_whatsapp(picked)