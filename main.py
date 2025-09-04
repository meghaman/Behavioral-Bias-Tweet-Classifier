import os
import time
import random
import json
import re
import traceback
from datetime import datetime, timedelta, timezone

import requests
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

# ----------------------------
# Configuration
# ----------------------------
CREATOR_HANDLES = [
    "@Ashcryptoreal", "@StockSavvyShay", "@RiskReversal", "@CarterBWorth", "@jonnajarian",
    "@GRDecter", "@NorthmanTrader", "@biancoresearch", "@KeithMcCullough",
    "@Beth_Kindig", "@RedDogT3", "@NYSEguru", "@leadlagreport"
]

# Multiple Nitter instances as fallbacks
NITTR_INSTANCES = [
    "https://nitter.net",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.unixfox.eu",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.mint.lgbt",
    "https://nitter.foss.wtf",
    "https://nitter.woodland.cafe",
    "https://nitter.weiler.rocks",
]

HEADLESS_MODE = True
DEBUG_MODE = True
SCREENSHOT_DIR = "debug_screenshots"
MAX_SCROLL_ATTEMPTS = 30
SCROLL_PAUSE_TIME = 2.5
REQUEST_DELAY = random.uniform(2, 5)  # Random delay between requests
BASE_URL = os.getenv("NITTER_BASE_URL", "https://nitter.net")

# ----------------------------
# Finance-Only Topic Filter
# ----------------------------
FINANCE_WHITELIST_TERMS = set(map(str.lower, [
    # assets / instruments
    "stock","stocks","equity","equities","etf","etfs","index","indices","option","options","calls","puts",
    "gamma","delta","theta","vega","future","futures","swap","swaps","bond","bonds","treasury","yield",
    "dividend","earnings","guidance","buyback","split","ipo","spinoff","merger","m&a","acquisition","spac",
    # markets / macro / data
    "market","markets","risk-on","risk off","vol","volatility","vix","inflation","deflation","cpi","ppi",
    "jobs","payrolls","ism","pmi","gdp","housing","credit","liquidity","fed","ecb","boj","boe","rate hike",
    # crypto
    "bitcoin","btc","ethereum","eth","altcoin","crypto","on-chain","onchain",
    # trading & analysis
    "rally","selloff","breakout","support","resistance","trend","setup","portfolio","alpha","beta","hedge",
    "long","short","leverage","positioning","orderflow","order flow","execution","flow","liquidity",
    # corp/tech finance
    "revenue","eps","cash flow","free cash flow","fcf","gross margin","operating margin","profit","loss",
    "valuation","multiple","pe","p/e","ebitda","ev/ebitda","price target","upgrade","downgrade"
]))
FINANCE_WHITELIST_TERMS |= set(
    t.strip().lower()
    for t in os.getenv("FINANCE_WHITELIST_APPEND", "").split(",")
    if t.strip()
)

POLITICS_BLACKLIST_TERMS = set(map(str.lower, [
    "election","elections","president","prime minister","senate","house","congress","parliament","campaign",
    "vote","voting","ballot","democrat","republican","liberal","conservative","labour","tory",
    "biden","trump","kamala","harris","obama","hillary","clinton","putin","zelenskyy","netanyahu","xi jinping"
]))
POLITICS_BLACKLIST_TERMS |= set(
    t.strip().lower()
    for t in os.getenv("POLITICS_BLACKLIST_APPEND", "").split(",")
    if t.strip()
)

OFFTOPIC_BLACKLIST_TERMS = set(map(str.lower, [
    "nba","nfl","mlb","nhl","soccer","premier league","uefa","fifa","concert","movie","actor","actress",
    "celebrity","gossip","gaming","streamer","music video","award show"
]))

# $TSLA or TSLA (1–5 caps), very permissive; adjust if you get false positives
TICKER_REGEX = re.compile(r'(?<![A-Za-z0-9])(?:\$?[A-Z]{1,5})(?![A-Za-z])')
CRYPTO_TICKER_REGEX = re.compile(r'(?<![A-Za-z0-9])(?:BTC|ETH|SOL|ADA|DOGE|SHIB)(?![A-Za-z])', re.IGNORECASE)

STRICT_FINANCE_ONLY = os.getenv("STRICT_FINANCE_ONLY", "true").lower() in ("1","true","t")

def looks_like_finance(text: str) -> bool:
    """Return True if text is finance/markets-related and not political/off-topic."""
    t = (text or "").lower()

    if any(term in t for term in POLITICS_BLACKLIST_TERMS):
        return False
    if any(term in t for term in OFFTOPIC_BLACKLIST_TERMS):
        return False

    whitelist_hit = any(term in t for term in FINANCE_WHITELIST_TERMS)
    ticker_hit = bool(TICKER_REGEX.search(text or "")) or bool(CRYPTO_TICKER_REGEX.search(text or ""))
    return whitelist_hit or ticker_hit

# ----------------------------
# Bias Keyword Classifiers (existing behavior)
# ----------------------------
CLASSIFIERS = {
    # (truncated in this snippet for brevity—you can keep your full dictionary as-is)
    "moon": "FOMO",
    "breakout": "FOMO",
    "parabolic": "Euphoria / Greed",
    "bear market": "Panic / Capitulation",
    "dividend": "Contrarian",
    "VIX": "Panic / Capitulation",
    "hodl": "Loss Aversion",
    "bullish": "Euphoria / Greed",
    "bearish": "Panic / Capitulation",
    # ...
}

# ----------------------------
# Driver / Nitter helpers
# ----------------------------
def test_nitter_instances() -> str:
    """Pick a working Nitter instance."""
    for base in [os.getenv("NITTER_BASE_URL", "")] + NITTR_INSTANCES:
        base = base or ""
        if not base:
            continue
        try:
            r = requests.get(base, timeout=8)
            if r.ok:
                return base
        except Exception:
            continue
    return "https://nitter.net"

def setup_driver():
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    ua = UserAgent()
    options = Options()
    if HEADLESS_MODE:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,1600")
    options.add_argument(f"--user-agent={ua.random}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
        "TE": "Trailers",
    }})
    return driver

# ----------------------------
# Time window & parsing helpers
# ----------------------------
def calculate_time_threshold():
    """Include tweets from the past 48 hours (adjust to taste)."""
    return datetime.now(timezone.utc) - timedelta(hours=48)

def detect_bias(tweet_text: str):
    """Detect the most likely cognitive bias based on classifier keywords."""
    t = (tweet_text or "").lower()
    for keyword, bias in CLASSIFIERS.items():
        if keyword.lower() in t:
            return bias
    return None

def parse_timestamp(timestamp_str: str):
    """Parse various timestamp formats from Nitter HTML."""
    try:
        if 'h' in timestamp_str:
            hours = int(timestamp_str.replace('h', ''))
            return datetime.now(timezone.utc) - timedelta(hours=hours)
        elif '·' in timestamp_str:
            # Example: "Jun 13, 2025 · 7:57 PM UTC"
            dt_str = timestamp_str.split('·')[0].strip()
            return datetime.strptime(dt_str, "%b %d, %Y").replace(tzinfo=timezone.utc)
        else:
            # Absolute date string: "Jun 13, 2025"
            return datetime.strptime(timestamp_str, "%b %d, %Y").replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

def extract_metrics(tweet_element):
    """Extract engagement metrics from tweet element."""
    metrics = {'replies': 0, 'retweets': 0, 'quotes': 0, 'likes': 0, 'views': 0}
    try:
        stats_div = tweet_element.find_element(By.CLASS_NAME, 'tweet-stats')
        stats = stats_div.find_elements(By.CLASS_NAME, 'tweet-stat')
        for stat in stats:
            text = stat.text.strip()
            if not text:
                continue
            value = 0
            numbers = re.findall(r'[\d,]+', text)
            if numbers:
                value = int(numbers[0].replace(',', ''))
            inner = stat.get_attribute('innerHTML')
            if 'icon-comment' in inner:
                metrics['replies'] = value
            elif 'icon-retweet' in inner:
                metrics['retweets'] = value
            elif 'icon-quote' in inner:
                metrics['quotes'] = value
            elif 'icon-heart' in inner:
                metrics['likes'] = value
            elif 'icon-play' in inner:
                metrics['views'] = value
    except Exception:
        pass
    return metrics

# ----------------------------
# Scraper
# ----------------------------
def scrape_creator_tweets(driver, handle, cutoff_time):
    print(f"\nStarting scrape for {handle}")
    clean_handle = handle.lstrip('@')
    url = f"{BASE_URL}/{clean_handle}"
    print(f"Navigating to: {url}")

    # initial page load attempts
    for attempt in range(3):
        try:
            time.sleep(random.uniform(1, 3))
            driver.get(url)
            time.sleep(5)
            if DEBUG_MODE:
                driver.save_screenshot(f"{SCREENSHOT_DIR}/01_{clean_handle}_creator.png")
                print(f"Screenshot: 01_{clean_handle}_creator.png saved")
            break
        except Exception as e:
            print(f"Navigation error ({attempt+1}/3): {e}")
            if attempt == 2:
                raise

    seen_tweet_ids = set()
    all_tweets = []
    start_time = time.time()
    scroll_attempts = 0
    consecutive_no_recent_tweets = 0
    consecutive_old_tweets = 0
    scroll_count = 0

    while scroll_attempts < MAX_SCROLL_ATTEMPTS and consecutive_no_recent_tweets < 3:
        scroll_count += 1
        print(f"Scroll #{scroll_count} - Attempt {scroll_attempts+1}/{MAX_SCROLL_ATTEMPTS}")

        last_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        pause_time = SCROLL_PAUSE_TIME + random.uniform(0.3, 1.0)
        print(f"Waiting {pause_time:.1f} seconds after scroll.")
        time.sleep(pause_time)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            scroll_attempts += 1
            print("Scroll detected as ineffective (no new height)")
        else:
            scroll_attempts = 0
            print(f"Scroll effective (new height: {new_height}px)")

        try:
            print("Locating tweet elements.")
            WebDriverWait(driver, 20).until(
                EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "div[class*='timeline-item']"))
            )
            tweet_elements = driver.find_elements(By.CSS_SELECTOR, "div[class*='timeline-item']")
            print(f"Found {len(tweet_elements)} tweet elements")
        except Exception as e:
            print(f"Error locating tweets: {e}")
            if DEBUG_MODE:
                driver.save_screenshot(f"{SCREENSHOT_DIR}/04_{clean_handle}_scroll_error_{scroll_count}.png")
                print(f"Screenshot: 04_{clean_handle}_scroll_error_{scroll_count}.png saved")
            break

        if DEBUG_MODE and scroll_count % 10 == 0:
            driver.save_screenshot(f"{SCREENSHOT_DIR}/04_{clean_handle}_scroll_{scroll_count}.png")
            print(f"Screenshot: 04_{clean_handle}_scroll_{scroll_count}.png saved")

        current_batch = []
        found_recent_tweet = False
        print(f"Processing {len(tweet_elements)} tweets.")

        for idx, tweet in enumerate(tweet_elements):
            try:
                # Robust tweet id extraction
                try:
                    tweet_link = tweet.find_element(By.CLASS_NAME, 'tweet-link')
                    href = tweet_link.get_attribute('href')
                    tweet_id = href.split('/')[-1].split('#')[0]
                except Exception:
                    try:
                        content_div = tweet.find_element(By.CLASS_NAME, 'tweet-content')
                        text_snippet = content_div.text[:50].replace('\n', '')
                        tweet_id = f"temp_{scroll_count}_{idx}_{hash(text_snippet)}"
                    except Exception:
                        tweet_id = f"unknown_{scroll_count}_{idx}"

                if tweet_id in seen_tweet_ids:
                    continue
                seen_tweet_ids.add(tweet_id)

                # Timestamp
                try:
                    date_elem = tweet.find_element(By.CLASS_NAME, 'tweet-date')
                    title = date_elem.find_element(By.TAG_NAME, 'a').get_attribute('title')
                    timestamp = parse_timestamp(title)
                except Exception:
                    timestamp = datetime.now(timezone.utc)

                if timestamp < cutoff_time:
                    consecutive_old_tweets += 1
                    print(f"Skipping old tweet (timestamp: {timestamp})")
                    continue

                found_recent_tweet = True

                # Handle & text
                try:
                    username_elem = tweet.find_element(By.CLASS_NAME, 'username')
                    user_handle = username_elem.get_attribute('title')
                except Exception:
                    user_handle = handle

                try:
                    content_div = tweet.find_element(By.CLASS_NAME, 'tweet-content')
                    tweet_text = content_div.text
                except Exception:
                    tweet_text = ""

                # ------------- FINANCE-ONLY GATE -------------
                if STRICT_FINANCE_ONLY and not looks_like_finance(tweet_text):
                    # Drop political / off-topic / non-finance tweets
                    continue
                # ---------------------------------------------

                bias = detect_bias(tweet_text)
                metrics = extract_metrics(tweet)

                has_media = False
                try:
                    tweet.find_element(By.CLASS_NAME, 'attachments')
                    has_media = True
                except Exception:
                    pass

                tweet_data = {
                    "user": user_handle,
                    "text": tweet_text,
                    "bias": bias,
                    "timestamp": timestamp.isoformat(),
                    "id": tweet_id,
                    "metrics": metrics,
                    "has_media": has_media,
                }

                current_batch.append(tweet_data)
                consecutive_old_tweets = 0

            except (StaleElementReferenceException, NoSuchElementException):
                continue
            except Exception as e:
                print(f"Error processing tweet: {e}")
                if DEBUG_MODE:
                    driver.save_screenshot(
                        f"{SCREENSHOT_DIR}/05_{clean_handle}_tweet_error_{scroll_count}_{idx}.png"
                    )
                    print(f"Screenshot: 05_{clean_handle}_tweet_error_{scroll_count}_{idx}.png saved")
                continue

        if not found_recent_tweet:
            consecutive_no_recent_tweets += 1
            print(f"No recent tweets found in this scroll (consecutive: {consecutive_no_recent_tweets}/3)")
        else:
            consecutive_no_recent_tweets = 0

        all_tweets.extend(current_batch)
        print(f"Added {len(current_batch)} new tweets (total: {len(all_tweets)})")

        if consecutive_old_tweets > 30:
            print("30+ consecutive old tweets, stopping collection")
            break
        if consecutive_no_recent_tweets >= 3:
            print("3 consecutive scrolls with no recent tweets, stopping collection")
            break
        if len(all_tweets) > 1000:
            print("Reached 1000 tweet limit, stopping collection")
            break
        if time.time() - start_time > 600:
            print("10 minute timeout reached, stopping collection")
            break
        if scroll_attempts > MAX_SCROLL_ATTEMPTS / 2:
            print("Multiple ineffective scrolls, attempting recovery.")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)

    print(f"Finished scrape for {handle} - {len(all_tweets)} tweets collected")
    print(f"Scraped {len(all_tweets)} tweets in {time.time() - start_time:.1f} seconds")
    return all_tweets

# ----------------------------
# Output
# ----------------------------
def save_tweets_to_json(tweets, filename="tweets_with_bias.json"):
    """Save tweets to JSON file in the requested format, including tweet ID."""
    output_dir = os.path.dirname(filename)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    simplified_tweets = [
        {
            "user": tweet["user"],
            "text": tweet["text"],
            "bias": tweet["bias"] if tweet["bias"] else "None",
            "id": tweet["id"],
        }
        for tweet in tweets
    ]

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(simplified_tweets, f, indent=2, ensure_ascii=False)
    print(f"Tweets saved to {filename}")

# ----------------------------
# Main
# ----------------------------
def main():
    print("Starting Twitter scraper with bias detection + finance-only filter.")

    # Output filename
    output_file = os.getenv("OUTPUT_FILE", "data/tweets_with_bias.json")
    print(f"Using output file: {output_file}")

    # Headless toggle
    global HEADLESS_MODE
    if os.getenv("HEADLESS_MODE", "False").lower() in ("true", "1", "t"):
        HEADLESS_MODE = True
        print("Running in headless mode")

    # Choose Nitter base
    global BASE_URL
    BASE_URL = test_nitter_instances()
    print(f"Using Nitter instance: {BASE_URL}")

    driver = setup_driver()
    print("Driver initialized with stealth settings")

    time_threshold = calculate_time_threshold()
    print(f"Scraping tweets since: {time_threshold.strftime('%Y-%m-%d %H:%M UTC')}")

    all_tweets = []
    for handle in CREATOR_HANDLES:
        try:
            print(f"\nScraping {handle}.")
            t0 = time.time()
            tweets = scrape_creator_tweets(driver, handle, time_threshold)
            print(f"Scraped {len(tweets)} tweets in {time.time() - t0:.1f} seconds")
            all_tweets.extend(tweets)
            delay = random.uniform(5, 15)
            print(f"Waiting {delay:.1f} seconds before next account.")
            time.sleep(delay)
        except Exception as e:
            print(f"Error scraping {handle}: {type(e).__name__}: {e}")
            if DEBUG_MODE:
                traceback.print_exc()

    save_tweets_to_json(all_tweets, output_file)
    print(f"Total tweets collected: {len(all_tweets)}")

    driver.quit()
    print(f"\nScraping completed. Tweets saved to {output_file}")
    print(f"Time range covered: {time_threshold.strftime('%Y-%m-%d %H:%M')} to {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")

if __name__ == "__main__":
    main()
