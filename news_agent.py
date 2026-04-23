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
    "LLM foundation models OpenAI Anthropic Google Meta",
    "LLM foundation models",
    "AI products apps launches",
    "Startups funding venture capital",
    "Fintech banking payments",
    "AI policy regulation",
    "AI infrastructure cloud compute chips"
    "H1B and F1 visa US"
    
]

ABOUT_ME = """
I am an MBA student at NYU Stern specializing in AI and tech product management.
I previously worked at Revolut, OnePay, and Flipkart in product and strategy roles.
I want to pursue a career in the US tech industry, ideally in AI product or strategy roles.
I care most about: LLMs and foundation models, AI product launches, AI startups getting funded,
AI applied to fintech AI infrastructure, and US AI policy and regulation.
Prioritize news that is insightful, career-relevant, or signals an important industry shift.
Skip generic hype pieces.
"""

MAX_ARTICLES_PER_TOPIC = 5   # articles fetched per topic
MAX_FINAL_ARTICLES     = 30   # articles sent to WhatsApp


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
                    "topic":       topic,
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
    
    try:
        indices = json.loads(raw)
        if not isinstance(indices, list) or not all(isinstance(i, int) for i in indices):
            raise ValueError("Invalid response: expected a list of integers")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing Claude's response: {e}. Returning empty list.")
        return []

    # indices are 1-based
    picked = []
    for i in indices:
        if 1 <= i <= len(articles):
            picked.append(articles[i - 1])
    return picked


# ── Topic display names ───────────────────────────────────
TOPIC_LABELS = {
    "LLM foundation models OpenAI Anthropic Google Meta": "🧠 LLMs & Foundation Models",
    "LLM foundation models": "🧠 LLMs & Foundation Models",
    "AI products apps launches": "📱 AI Products & Apps",
    "Startups funding venture capital": "💰 Startups & Venture Capital",
    "Fintech banking payments": "🏦 Fintech & Payments",
    "AI policy regulation": "⚖️ AI Policy & Regulation",
    "AI infrastructure cloud compute chips": "☁️ AI Infrastructure",
    "H1B and F1 visa US": "🇺🇸 US Visas (H1B & F1)",
}

# ── Step 3: Send to WhatsApp ──────────────────────────────
def send_whatsapp(articles):
    # Group articles by topic
    grouped = {}
    for a in articles:
        label = TOPIC_LABELS.get(a["topic"], a["topic"])
        grouped.setdefault(label, []).append(a)

    lines = ["🗞 *Your Daily News Brief*\n"]
    for label, items in grouped.items():
        lines.append(f"*{label}*")
        for a in items:
            lines.append(f"• {a['title']}")
            lines.append(f"  _{a['source']}_")
            lines.append(f"  {a['url']}")
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