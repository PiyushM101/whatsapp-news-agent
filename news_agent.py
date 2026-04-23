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

FETCH_PER_TOPIC = 15
TOP_PER_TOPIC   = 5

TOPIC_LABELS = {
    "LLM foundation models OpenAI Anthropic Google Meta": "🧠 LLMs & Foundation Models",
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

Rules:
1. If multiple articles cover the same story, pick only the best one. Skip the rest.
2. Pick up to {TOP_PER_TOPIC} articles that cover DIFFERENT stories.
3. Rank them by relevance and importance to the user. Most important first.
4. Skip generic hype, press releases, and repetitive coverage.

Return ONLY a JSON array of article numbers in ranked order, like: [3, 7, 1, 9, 5]
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
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    indices = json.loads(raw[start:end])

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
        send_whatsapp_message(message)
        time.sleep(60)  # small delay between messages


# ── Main ──────────────────────────────────────────────────
if __name__ == "__main__":
    # TOPIC_INDEX tells us which single topic to run (0-based)
    # If not set, run all topics at once
    topic_index = os.environ.get("TOPIC_INDEX")

    if topic_index is not None:
        selected = [TOPICS[int(topic_index)]]
    else:
        selected = TOPICS

    print("Fetching news by topic...")
    by_topic = fetch_news_by_topic(selected)
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