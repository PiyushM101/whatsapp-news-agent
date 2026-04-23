import os
import requests
import json

# ── Config ────────────────────────────────────────────────
NEWSAPI_KEY     = os.environ["NEWSAPI_KEY"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]
TWILIO_SID      = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_TOKEN    = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM     = os.environ["TWILIO_WHATSAPP_FROM"]
TWILIO_TO       = os.environ["TWILIO_WHATSAPP_TO"]

TOPICS = [
    "LLM foundation models OpenAI Anthropic Google Meta",
    "LLM foundation models",
    "AI products apps launches",
    "Startups funding venture capital",
    "Fintech banking payments",
    "AI policy regulation",
    "AI infrastructure cloud compute chips",
    "H1B and F1 visa US",
]

ABOUT_ME = """
I am an MBA student at NYU Stern specializing in AI and tech product management.
I previously worked at Revolut, OnePay, and Flipkart in product and strategy roles.
I want to pursue a career in the US tech industry, ideally in AI product or strategy roles.
I care most about: LLMs and foundation models, AI product launches, AI startups getting funded,
AI applied to fintech, AI infrastructure, and US AI policy and regulation.
Prioritize news that is insightful, career-relevant, or signals an important industry shift.
Skip generic hype pieces.
"""

MAX_ARTICLES_PER_TOPIC = 5
MAX_FINAL_ARTICLES     = 30


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
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    res.raise_for_status()

    raw = res.json()["content"][0]["text"].strip()
    # Extract just the JSON array, ignoring any surrounding text
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    indices = json.loads(raw[start:end])

    picked = []
    for i in indices:
        if 1 <= i <= len(articles):
            picked.append(articles[i - 1])
    return picked


TOPIC_LABELS = {
    "LLM foundation models OpenAI Anthropic Google Meta": "🧠 LLMs & Foundation Models",
    "LLM foundation models":                              "🧠 LLMs & Foundation Models",
    "AI products apps launches":                         "📱 AI Products & Apps",
    "Startups funding venture capital":                  "💰 Startups & Venture Capital",
    "Fintech banking payments":                          "🏦 Fintech & Payments",
    "AI policy regulation":                              "⚖️ AI Policy & Regulation",
    "AI infrastructure cloud compute chips":             "☁️ AI Infrastructure",
    "H1B and F1 visa US":                                "🇺🇸 US Visas (H1B & F1)",
}


def send_whatsapp(articles):
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

    full_message = "\n".join(lines).strip()

    # Split into chunks of 1500 chars max
    chunks = []
    current = ""
    for line in full_message.split("\n"):
        if len(current) + len(line) + 1 > 1500:
            chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.strip())

    for i, chunk in enumerate(chunks):
        res = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            data={"From": TWILIO_FROM, "To": TWILIO_TO, "Body": chunk},
            timeout=15,
        )
        if not res.ok:
            print(f"❌ Twilio error on chunk {i+1}:", res.status_code, res.text)
        res.raise_for_status()
        print(f"✅ Chunk {i+1}/{len(chunks)} sent. SID:", res.json().get("sid"))


if __name__ == "__main__":
    print("Fetching news...")
    articles = fetch_news(TOPICS)
    print(f"  Found {len(articles)} articles total.")

    print("Filtering with Claude...")
    picked = filter_with_claude(articles)
    print(f"  Picked {len(picked)} articles.")

    print("Sending to WhatsApp...")
    send_whatsapp(picked)