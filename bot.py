import tweepy
import requests
import xml.etree.ElementTree as ET
import time
import os
import random
import re
from html import unescape
from io import BytesIO

# ================================
# X (Twitter) API KEYS
# ================================
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")

# ================================
# API v2 Client (for tweeting)
# ================================
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# ================================
# API v1.1 (for media upload)
# ================================
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api_v1 = tweepy.API(auth)

# ================================
# TRENDING TOPICS (100% FREE – Google News RSS)
# ================================
def fetch_trending_topics():
    """
    Fetch trending news from Google News RSS (FREE, unlimited).
    Returns list of dicts: {title, description}
    """
    try:
        url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
        r = requests.get(url)
        r.raise_for_status()

        root = ET.fromstring(r.content)

        items = []
        for item in root.findall("./channel/item"):
            title = item.find("title").text
            desc = item.find("description").text

            if title and desc:
                items.append({
                    "title": title,
                    "description": desc
                })

        return items[:10] if items else []

    except Exception as e:
        print("⚠️ RSS fetch error:", e)
        return []

# ================================
# GENERATE TWEET CONTENT
# (Simple + clean summary)
# ================================
def clean_html(raw_html):
    clean = re.sub(r"<.*?>", "", raw_html)
    return unescape(clean)

previous_titles = set()

def search_image_bing(query):
    """
    Free Bing image scraper (no API key needed).
    Returns direct image URL.
    """
    try:
        q = query.replace(" ", "+")
        url = f"https://www.bing.com/images/search?q={q}&form=HDRSC2"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers)
        html = r.text

        # Extract direct image URLs
        matches = re.findall(r"murl&quot;:&quot;(.*?)&quot;", html)
        if matches:
            return matches[0]  # best match
        return None

    except Exception as e:
        print("⚠️ Image scrape failed:", e)
        return None

def download_image_memory(url):
    """
    Downloads image into memory (NO file saved).
    Returns BytesIO object or None.
    """
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return BytesIO(r.content)  # in-memory object
    except Exception:
        pass
    return None

def upload_image_memory(image_bytes):
    """
    Upload in-memory image to X API using v1.1.
    """
    try:
        media = api_v1.media_upload(filename="image.jpg", file=image_bytes)
        return media.media_id_string
    except Exception as e:
        print("❌ Image upload error:", e)
        return None

def create_tweet_text(topic):
    title = clean_html(topic["title"])
    description = clean_html(topic["description"])

    # Avoid repetition if description starts like title
    if description.lower().startswith(title.lower()[:20]):
        description = ""

    # avoid duplicate titles in same run
    if title in previous_titles:
        return None
    previous_titles.add(title)

    intros = [
        "🔥 Breaking Khabar!",
        "📰 Aaj Ki Taaza Update!",
        "📢 Trending News Alert!",
        "⚡ Fact Check This!",
        "🚨 Big Update!"
    ]

    hashtags = [
        "#Trending", "#IndiaNews", "#Breaking",
        "#LatestUpdate", "#TopStory", "#InShorts"
    ]

    intro = random.choice(intros)
    tag_string = " ".join(random.sample(hashtags, 3))

    tweet = (
        f"{intro}\n\n"
        f"👉 {title}\n\n"
        f"{description}\n\n"
        f"{tag_string}"
    )

    # Always unique due to timestamp (helps avoid duplicate rejection)
    tweet += f"\n\n⏳ {int(time.time())}"

    # keep last 275 chars so hashtags & timestamp survive
    return tweet[-275:]

# ================================
# MAIN BOT LOOP
# ================================
def run_bot(interval=3600):
    """
    Runs bot forever with:
    - auto rate limit detection
    - random posting time
    - anti-ban safety mode
    - self-adjust scheduling
    """
    print("🚀 Bot started with Safety Mode ON.")

    while True:
        topics = fetch_trending_topics()

        if not topics:
            print("⚠️ No topics returned. Sleeping for 2 minutes...")
            time.sleep(120)
            continue

        topic = random.choice(topics)
        tweet_text = create_tweet_text(topic)

        if tweet_text is None or tweet_text.strip() == "":
            print("⚠️ Skipping empty or duplicate tweet.")
            time.sleep(60)
            continue

        try:
            # Get related image
            image_url = search_image_bing(topic["title"])
            media_id = None

            if image_url:
                img_bytes = download_image_memory(image_url)
                if img_bytes:
                    media_id = upload_image_memory(img_bytes)

            # Tweet final message (with or without image)
            if media_id:
                client.create_tweet(text=tweet_text, media_ids=[media_id])
            else:
                client.create_tweet(text=tweet_text)

            print("✅ Tweet posted successfully!")
            print("Tweet:", tweet_text)

            # ANTI-BAN: Sleep random time (75–150 minutes)
            sleep_time = random.randint(4500, 9000)
            print(f"⏳ Sleeping safely for {sleep_time//60} minutes...")
            time.sleep(sleep_time)

        except Exception as e:
            print("❌ Tweet error:", e)

            # AUTO RATE-LIMIT DETECTION (429)
            if "429" in str(e):
                print("⚠️ Rate limit hit! Sleeping 2 hours for safety...")
                time.sleep(7200)
                continue

            # FORBIDDEN (403) — often caused by duplicates or permission
            if "403" in str(e):
                print("⚠️ Forbidden error — skipping this topic.")
                time.sleep(300)
                continue

            # RANDOM fallback sleep (Avoid being detected as bot)
            fallback_sleep = random.randint(1800, 3600)
            print(f"😴 Safety cooldown: Sleeping {fallback_sleep//60} minutes...")
            time.sleep(fallback_sleep)

# ================================
# START BOT
# ================================
if __name__ == "__main__":
    run_bot(interval=3600)   # base interval, but actual sleep is randomized
