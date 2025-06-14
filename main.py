# main.py
import os
import time
import random
import json
from datetime import datetime, timedelta, timezone
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import traceback
from fake_useragent import UserAgent
import re
from classifiers import CLASSIFIERS  # Import CLASSIFIERS from classifiers.py

# Configuration
CREATOR_HANDLES = ["Ashcryptoreal"]

HEADLESS_MODE = True
DEBUG_MODE = True
SCREENSHOT_DIR = "debug_screenshots"
MAX_SCROLL_ATTEMPTS = 30
SCROLL_PAUSE_TIME = 2.5
REQUEST_DELAY = random.uniform(2, 5)  # Random delay between requests
BASE_URL = "https://nitter.net"

if DEBUG_MODE and not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

def setup_driver():
    chrome_options = Options()
    
    # Generate random user agent
    ua = UserAgent()
    user_agent = ua.random
    chrome_options.add_argument(f"user-agent={user_agent}")
    
    # Stealth options to avoid detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--dns-prefetch-disable")
    chrome_options.add_argument("--disable-geolocation")
    chrome_options.add_argument("--disable-notifications")
    
    # Proxy settings (if available)
    if os.getenv("PROXY_SERVER"):
        chrome_options.add_argument(f"--proxy-server={os.getenv('PROXY_SERVER')}")
    
    if HEADLESS_MODE:
        chrome_options.add_argument("--headless=new")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    # Execute CDP commands to mask automation
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
            Object.defineProperty(navigator, 'doNotTrack', { get: () => '1' });
            window.chrome = { runtime: {}, app: {} };
        '''
    })
    
    # Set common headers
    driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
        'headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'TE': 'Trailers'
        }
    })
    
    return driver

def calculate_time_threshold():
    return datetime.now(timezone.utc) - timedelta(hours=24)

def detect_bias(tweet_text):
    """Detect the most likely cognitive bias based on classifier keywords."""
    tweet_text = tweet_text.lower()
    for keyword, bias in CLASSIFIERS.items():
        if keyword.lower() in tweet_text:
            return bias
    return None  # No bias detected

def parse_timestamp(timestamp_str):
    """Parse various timestamp formats from the HTML"""
    try:
        # Handle relative time formats (e.g., "1h", "2h", "Jun 12")
        if 'h' in timestamp_str:
            hours = int(timestamp_str.replace('h', ''))
            return datetime.now(timezone.utc) - timedelta(hours=hours)
        elif '·' in timestamp_str:
            # Format: "Jun 13, 2025 · 7:57 PM UTC"
            dt_str = timestamp_str.split('·')[0].strip()
            return datetime.strptime(dt_str, "%b %d, %Y").replace(tzinfo=timezone.utc)
        else:
            # Absolute date format
            return datetime.strptime(timestamp_str, "%b %d, %Y").replace(tzinfo=timezone.utc)
    except:
        return datetime.now(timezone.utc)

def extract_metrics(tweet_element):
    """Extract engagement metrics from tweet element"""
    metrics = {
        'replies': 0,
        'retweets': 0,
        'quotes': 0,
        'likes': 0,
        'views': 0
    }
    
    try:
        stats_div = tweet_element.find_element(By.CLASS_NAME, 'tweet-stats')
        stats = stats_div.find_elements(By.CLASS_NAME, 'tweet-stat')
        
        for stat in stats:
            text = stat.text.strip()
            if not text:
                continue
            
            # Extract numeric value
            value = 0
            numbers = re.findall(r'[\d,]+', text)
            if numbers:
                value = int(numbers[0].replace(',', ''))
            
            # Determine metric type
            if 'icon-comment' in stat.get_attribute('innerHTML'):
                metrics['replies'] = value
            elif 'icon-retweet' in stat.get_attribute('innerHTML'):
                metrics['retweets'] = value
            elif 'icon-quote' in stat.get_attribute('innerHTML'):
                metrics['quotes'] = value
            elif 'icon-heart' in stat.get_attribute('innerHTML'):
                metrics['likes'] = value
            elif 'icon-play' in stat.get_attribute('innerHTML'):
                metrics['views'] = value
    except:
        pass
    
    return metrics

def calculate_time_threshold():
    """Set time threshold to include tweets from the past 2 days (48 hours)."""
    return datetime.now(timezone.utc) - timedelta(hours=48)

def scrape_creator_tweets(driver, handle, cutoff_time):
    print(f"\nStarting scrape for @{handle}")
    url = f"{BASE_URL}/{handle}"
    print(f"Navigating to: {url}")
    
    for attempt in range(3):
        try:
            time.sleep(random.uniform(1, 3))
            driver.get(url)
            time.sleep(5)
            
            if DEBUG_MODE:
                driver.save_screenshot(f"{SCREENSHOT_DIR}/01_{handle}_creator.png")
                print(f"Screenshot: 01_{handle}_creator.png saved")
            
            print("Waiting for timeline to load...")
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'timeline'))
            )
            print("Timeline detected, waiting additional time for content...")
            time.sleep(3)
            if DEBUG_MODE:
                driver.save_screenshot(f"{SCREENSHOT_DIR}/02_{handle}_timeline_loaded.png")
                print(f"Screenshot: 02_{handle}_timeline_loaded.png saved")
            break
        except Exception as e:
            print(f"Error loading timeline for @{handle} (attempt {attempt+1}/3): {str(e)}")
            if DEBUG_MODE:
                driver.save_screenshot(f"{SCREENSHOT_DIR}/03_{handle}_timeline_error_{attempt+1}.png")
                print(f"Screenshot: 03_{handle}_timeline_error_{attempt+1}.png saved")
            if attempt == 2:
                return []
    
    all_tweets = []
    seen_tweet_ids = set()
    scroll_attempts = 0
    consecutive_old_tweets = 0
    consecutive_no_recent_tweets = 0
    start_time = time.time()
    scroll_count = 0
    
    print(f"Beginning scroll collection for @{handle}...")
    
    while scroll_attempts < MAX_SCROLL_ATTEMPTS and consecutive_no_recent_tweets < 3:
        scroll_count += 1
        print(f"Scroll #{scroll_count} - Attempt {scroll_attempts+1}/{MAX_SCROLL_ATTEMPTS}")
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        pause_time = SCROLL_PAUSE_TIME + random.uniform(0.3, 1.0)
        print(f"Waiting {pause_time:.1f} seconds after scroll...")
        time.sleep(pause_time)
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            scroll_attempts += 1
            print(f"Scroll detected as ineffective (no new height)")
        else:
            scroll_attempts = 0
            print(f"Scroll effective (new height: {new_height}px)")
        
        try:
            print("Locating tweet elements...")
            timeline = driver.find_element(By.CLASS_NAME, 'timeline')
            tweet_elements = WebDriverWait(driver, 10).until(
                EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "div[class*='timeline-item']"))
            )
            print(f"Found {len(tweet_elements)} tweet elements")
        except Exception as e:
            print(f"Error locating tweets: {str(e)}")
            if DEBUG_MODE:
                driver.save_screenshot(f"{SCREENSHOT_DIR}/04_{handle}_scroll_error_{scroll_count}.png")
                print(f"Screenshot: 04_{handle}_scroll_error_{scroll_count}.png saved")
            break
        
        if DEBUG_MODE and scroll_count % 10 == 0:
            driver.save_screenshot(f"{SCREENSHOT_DIR}/04_{handle}_scroll_{scroll_count}.png")
            print(f"Screenshot: 04_{handle}_scroll_{scroll_count}.png saved")
        
        current_batch = []
        found_recent_tweet = False
        print(f"Processing {len(tweet_elements)} tweets...")
        
        for idx, tweet in enumerate(tweet_elements):
            try:
                try:
                    tweet_link = tweet.find_element(By.CLASS_NAME, 'tweet-link')
                    href = tweet_link.get_attribute('href')
                    tweet_id = href.split('/')[-1].split('#')[0]
                except:
                    try:
                        content_div = tweet.find_element(By.CLASS_NAME, 'tweet-content')
                        text_snippet = content_div.text[:50].replace('\n', '')
                        tweet_id = f"temp_{scroll_count}_{idx}_{hash(text_snippet)}"
                    except:
                        tweet_id = f"unknown_{scroll_count}_{idx}"
                
                if tweet_id in seen_tweet_ids:
                    continue
                seen_tweet_ids.add(tweet_id)
                
                try:
                    date_elem = tweet.find_element(By.CLASS_NAME, 'tweet-date')
                    title = date_elem.find_element(By.TAG_NAME, 'a').get_attribute('title')
                    timestamp = parse_timestamp(title)
                except:
                    timestamp = datetime.now(timezone.utc)
                
                if timestamp < cutoff_time:
                    consecutive_old_tweets += 1
                    print(f"Skipping old tweet (timestamp: {timestamp})")
                    continue
                
                found_recent_tweet = True
                
                try:
                    username_elem = tweet.find_element(By.CLASS_NAME, 'username')
                    user_handle = username_elem.get_attribute('title')
                except:
                    user_handle = f"@{handle}"
                
                try:
                    content_div = tweet.find_element(By.CLASS_NAME, 'tweet-content')
                    tweet_text = content_div.text
                except:
                    tweet_text = ""
                
                bias = detect_bias(tweet_text)
                metrics = extract_metrics(tweet)
                
                has_media = False
                try:
                    tweet.find_element(By.CLASS_NAME, 'attachments')
                    has_media = True
                except:
                    pass
                
                tweet_data = {
                    'user': user_handle,
                    'text': tweet_text,
                    'bias': bias,
                    'timestamp': timestamp.isoformat(),
                    'id': tweet_id,
                    'metrics': metrics,
                    'has_media': has_media
                }
                
                current_batch.append(tweet_data)
                consecutive_old_tweets = 0
                
            except (StaleElementReferenceException, NoSuchElementException):
                continue
            except Exception as e:
                print(f"Error processing tweet: {str(e)}")
                if DEBUG_MODE:
                    driver.save_screenshot(f"{SCREENSHOT_DIR}/05_{handle}_tweet_error_{scroll_count}_{idx}.png")
                    print(f"Screenshot: 05_{handle}_tweet_error_{scroll_count}_{idx}.png saved")
                continue
        
        if not found_recent_tweet:
            consecutive_no_recent_tweets += 1
            print(f"No recent tweets found in this scroll (consecutive: {consecutive_no_recent_tweets}/3)")
        else:
            consecutive_no_recent_tweets = 0
        
        all_tweets.extend(current_batch)
        print(f"Added {len(current_batch)} new tweets (total: {len(all_tweets)}")
        
        if consecutive_old_tweets > 30:
            print(f"30+ consecutive old tweets, stopping collection")
            break
        if consecutive_no_recent_tweets >= 3:
            print(f"3 consecutive scrolls with no recent tweets, stopping collection")
            break
        if len(all_tweets) > 1000:
            print(f"Reached 1000 tweet limit, stopping collection")
            break
        if time.time() - start_time > 600:
            print(f"10 minute timeout reached, stopping collection")
            break
        if scroll_attempts > MAX_SCROLL_ATTEMPTS/2:
            print(f"Multiple ineffective scrolls, attempting recovery...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)
    
    print(f"Finished scrape for @{handle} - {len(all_tweets)} tweets collected")
    print(f"Scraped {len(all_tweets)} tweets in {time.time() - start_time:.1f} seconds")
    return all_tweets

def save_tweets_to_json(tweets, filename="tweets_with_bias.json"):
    """Save tweets to JSON file in the requested format."""
    output_dir = os.path.dirname(filename)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    simplified_tweets = [
        {
            "user": tweet["user"],
            "text": tweet["text"],
            "bias": tweet["bias"] if tweet["bias"] else "None"
        }
        for tweet in tweets
    ]
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(simplified_tweets, f, indent=2, ensure_ascii=False)
    print(f"Tweets saved to {filename}")
    
def main():
    print("Starting Twitter scraper with bias detection...")
    
    # Get output filename from environment variable or use default
    output_file = os.getenv("OUTPUT_FILE", "data/tweets_with_bias.json")
    print(f"Using output file: {output_file}")
    
    # Set headless mode based on environment variable
    global HEADLESS_MODE
    if os.getenv("HEADLESS_MODE", "False").lower() in ("true", "1", "t"):
        HEADLESS_MODE = True
        print("Running in headless mode")
    
    driver = setup_driver()
    print("Driver initialized with stealth settings")
    
    time_threshold = calculate_time_threshold()
    print(f"Scraping tweets since: {time_threshold.strftime('%Y-%m-%d %H:%M UTC')}")
    
    all_tweets = []
    for handle in CREATOR_HANDLES:
        try:
            print(f"\nScraping @{handle}...")
            start_time = time.time()
            tweets = scrape_creator_tweets(driver, handle, time_threshold)
            duration = time.time() - start_time
            print(f"Scraped {len(tweets)} tweets in {duration:.1f} seconds")
            all_tweets.extend(tweets)
        except Exception as e:
            print(f"Error scraping @{handle}: {str(e)}")
            if DEBUG_MODE:
                traceback.print_exc()
    
    # Save tweets to JSON file
    save_tweets_to_json(all_tweets, output_file)
    print(f"Total tweets collected: {len(all_tweets)}")
    
    driver.quit()
    print(f"\nScraping completed. Tweets saved to {output_file}")
    print(f"Time range covered: {time_threshold.strftime('%Y-%m-%d %H:%M')} to {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")

if __name__ == "__main__":
    main()
