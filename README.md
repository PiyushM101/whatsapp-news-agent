WhatsApp News Agent
Fetches news daily, filters it with Claude, and sends it to your WhatsApp.


Setup (one-time, ~2 hours)
1. Get your API keys
Service
Where to get it
Free tier
NewsAPI
newsapi.org → Register
100 req/day
Anthropic
console.anthropic.com → API Keys
Pay per use (~$0.01/day)
Twilio
twilio.com → Console
Free sandbox



2. Set up Twilio WhatsApp sandbox
Go to twilio.com/console
Click Messaging → Try it out → Send a WhatsApp message
Follow the steps to join the sandbox from your phone
Your TWILIO_WHATSAPP_FROM will be whatsapp:+14155238886
Your TWILIO_WHATSAPP_TO will be whatsapp:+1YOURNUMBER


3. Create a GitHub repo
git init whatsapp-news-agent

cd whatsapp-news-agent

cp /path/to/news_agent.py .

mkdir -p .github/workflows

cp /path/to/news_agent.yml .github/workflows/

git add .

git commit -m "init"

git remote add origin https://github.com/YOURUSERNAME/whatsapp-news-agent.git

git push -u origin main


4. Add secrets to GitHub
Go to your repo on GitHub
Click Settings → Secrets and variables → Actions → New repository secret
Add each of these:

NEWSAPI_KEY

ANTHROPIC_API_KEY

TWILIO_ACCOUNT_SID

TWILIO_AUTH_TOKEN

TWILIO_WHATSAPP_FROM    → whatsapp:+14155238886

TWILIO_WHATSAPP_TO      → whatsapp:+1YOURNUMBER


5. Test it
Go to Actions tab → Daily News Agent → Run workflow.

If it works, you'll get a WhatsApp message within 30 seconds.


Customize it
Open news_agent.py and edit these two sections:

TOPICS = [

    "artificial intelligence",

    "fintech",

    ...

]

ABOUT_ME = """

I am an MBA student at NYU Stern...

"""

The more specific your ABOUT_ME, the better Claude filters.


Change the schedule
Edit the cron line in .github/workflows/news_agent.yml:

- cron: "0 13 * * *"   # 8am EST daily

- cron: "0 13,20 * * *" # 8am and 3pm EST

- cron: "0 13 * * 1"   # Mondays only

Use crontab.guru to build your own schedule.

