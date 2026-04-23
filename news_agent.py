import os
import time
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

FETCH_PER_TOPIC = 10  # fetch more so Claude has options
TOP_PER_TOPIC   = 5   # top N to send per topic

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


# ── Step 1: Fetch news per topic ──────────────────────────
def fetch_news_by_topic(topics):
    by_topic = {}
    seen_urls = set()

    for topic in topics:
        params = {
            "q": topic,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": FETCH_PER_TOPIC,
            "apiKey": NEWSAPI_KEY,
        }
        res = requests.get("https://newsapi.org/v2/everything", params=params, timeout=10)
        res.raise_for_status()

        articles = []
        for a in res.json().get("articles", []):
            url_ = a.get("url", "")
            if url_ not in seen_urls and a.get("title") and a.get("description"):
                seen_urls.add(url_)
                articles.append({
                    "title":       a["title"],
                    "description": a["description"],
                    "url":         url_,
                    "source":      a.get("source", {}).get("name", "Unknown"),
                })
        by_topic[topic] = articles

    return by_topic


# ── Step 2: Filter top 5 per topic with Claude ────────────
def filter_topic(topic, articles):
    headlines = "\n".join(
        f"{i+1}. [{a['source']}] {a['title']} — {a['description']}"
        for i, a in enumerate(articles)
    )

    prompt = f"""
You are a personal news curator.

About the user:
{ABOUT_ME.strip()}

Topic: {TOPIC_LABELS.get(topic, topic)}

Here are today's articles for this topic (numbered):

{headlines}

Pick the top {TOP_PER_TOPIC} most relevant and interesting articles for this user.
Return ONLY a JSON array of article numbers, like: [2, 4, 5, 7, 9]
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
            "max_tokens": 100,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    res.raise_for_status()

    raw = res.json()["content"][0]["text"].strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    if start == -1 or end == 0 or end <= start:
        print("Error parsing Claude's response: no JSON array found. Returning empty list.")
        return []

    try:
        indices = json.loads(raw[start:end])
        if not isinstance(indices, list) or not all(isinstance(i, int) for i in indices):
            raise ValueError("Expected a list of integers")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing Claude's response: {e}. Returning empty list.")
        return []

    picked = []
    for i in indices:
        if 1 <= i <= len(articles):
            picked.append(articles[i - 1])
    return picked


# ── Step 3: Send one WhatsApp message per topic ───────────
def send_whatsapp_message(body):
    res = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
        auth=(TWILIO_SID, TWILIO_TOKEN),
        data={"From": TWILIO_FROM, "To": TWILIO_TO, "Body": body},
        timeout=15,
    )
    if not res.ok:
        print("❌ Twilio error:", res.status_code, res.text)
    res.raise_for_status()
    print("✅ Sent. SID:", res.json().get("sid"))


def send_topic_messages(filtered_by_topic):
    for topic, articles in filtered_by_topic.items():
        if not articles:
            continue

        label = TOPIC_LABELS.get(topic, topic)
        lines = [f"🗞 *{label}*\n"]
        for i, a in enumerate(articles, 1):
            lines.append(f"*{i}. {a['title']}*")
            lines.append(f"_{a['source']}_")
            lines.append(a["url"])
            lines.append("")

        message = "\n".join(lines).strip()

        chunks = []
        current = ""
        for line in message.split("\n"):
            if len(current) + len(line) + 1 > 1500:
                chunks.append(current.strip())
                current = line + "\n"
            else:
                current += line + "\n"
        if current.strip():
            chunks.append(current.strip())

        for i, chunk in enumerate(chunks, start=1):
            body = chunk
            if len(chunks) > 1:
                body += f"\n\n({i}/{len(chunks)})"
            send_whatsapp_message(body)
            time.sleep(1)  # small delay between messages


# ── Main ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("Fetching news by topic...")
    by_topic = fetch_news_by_topic(TOPICS)
    for t, arts in by_topic.items():
        print(f"  {TOPIC_LABELS.get(t, t)}: {len(arts)} articles")

    print("\nFiltering top 5 per topic with Claude...")
    filtered = {}
    for topic, articles in by_topic.items():
        if articles:
            picked = filter_topic(topic, articles)
            label = TOPIC_LABELS.get(topic, topic)
            filtered[topic] = picked
            print(f"  {label}: picked {len(picked)}")

    print("\nSending to WhatsApp...")
    send_topic_messages(filtered)
    print("Done!")