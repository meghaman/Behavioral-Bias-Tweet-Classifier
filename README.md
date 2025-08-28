# Behavioral Bias Tweet Classifier

A Python-based tool that scrapes tweets from financial and crypto influencers using NITTR instances, analyzes them for cognitive biases, and classifies them into various behavioral bias categories.

## Features

- **Automated Scraping**: Scrapes tweets from 20+ financial/crypto influencers
- **Bias Detection**: Identifies cognitive biases like FOMO, Overconfidence, Loss Aversion, etc.
- **NITTR Integration**: Uses multiple NITTR instances for reliable access
- **Automated Workflow**: Runs daily at 10:30 AM EST via GitHub Actions
- **Data Export**: Saves results in JSON format with timestamps

## Cognitive Bias Categories

The tool detects and classifies tweets into these bias categories:

- **FOMO (Fear of Missing Out)**: "don't miss", "all in now", "final call to buy"
- **Overconfidence**: "guaranteed", "zero risk", "can't lose", "sure thing"
- **Loss Aversion**: "paper hands", "bag holder", "holding for dear life"
- **Confirmation Bias**: "like I said", "told you", "charts don't lie"
- **Herd/Bandwagon**: "everyone's buying", "follow the herd", "mass consensus"
- **Recency Bias**: "just did", "fresh off", "latest earnings"
- **Sunk Cost Fallacy**: "averaging down", "double down", "in too deep"

## Influencers Tracked

- @LizAnnSonders - Schwab Chief Investment Strategist
- @paulkrugman - Economist
- @elerianm - Mohamed El-Erian
- @morganhousel - Author and investor
- @RayDalio - Bridgewater Associates founder
- @barronsonline - Barron's financial news
- @matt_levine - Bloomberg columnist
- @saxena_puru - Puru Saxena
- @michaelbatnick - The Irrelevant Investor
- @AswathDamodaran - NYU Professor
- @balajis - Balaji Srinivasan
- @elonmusk - Tesla CEO
- @ErikVoorhees - ShapeShift founder
- @VitalikButerin - Ethereum co-founder
- @rogerkver - Bitcoin.com founder
- @cdixon - Andreessen Horowitz partner
- @pmarca - Marc Andreessen
- @paulg - Paul Graham
- @laurashin - Laura Shin
- @CryptoWendyO - Crypto analyst

## Installation

1. Clone the repository:
```bash
git clone https://github.com/meghaman/Behavioral-Bias-Tweet-Classifier.git
cd Behavioral-Bias-Tweet-Classifier
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install fake-useragent
```

4. Install Chrome browser (required for Selenium)

## Usage

### Manual Execution

Run the scraper manually:
```bash
python main.py
```

### Environment Variables

- `HEADLESS_MODE`: Set to "true" for headless browser mode
- `OUTPUT_FILE`: Custom output file path
- `NITTER_BASE_URL`: Custom NITTR instance URL

### Output

The script generates:
- `data/tweets_with_bias_YYYY-MM-DD_HH-MM-SS.json` - Scraped tweets with bias classification
- `debug_screenshots/` - Debug screenshots for troubleshooting

## Automated Workflow

### GitHub Actions

The project includes a GitHub Actions workflow that runs automatically:

- **Schedule**: Every day at 10:30 AM EST (15:30 UTC)
- **Trigger**: Automatic daily execution + manual trigger option
- **Actions**:
  1. Sets up Python environment
  2. Installs Chrome and ChromeDriver
  3. Runs the scraper
  4. Uploads results as artifacts
  5. Commits and pushes data files to repository

### Workflow File

Located at `.github/workflows/daily-scraping.yml`

### Manual Trigger

You can manually trigger the workflow:
1. Go to Actions tab in GitHub
2. Select "Daily NITTR Scraping"
3. Click "Run workflow"

## NITTR Instances

The tool automatically tests multiple NITTR instances to find working ones:

- nitter.net
- nitter.1d4.us
- nitter.kavin.rocks
- nitter.unixfox.eu
- nitter.privacydev.net
- nitter.poast.org
- nitter.mint.lgbt
- nitter.foss.wtf
- nitter.woodland.cafe
- nitter.weiler.rocks

## Data Format

Each tweet is stored with:
```json
{
  "user": "@username",
  "text": "tweet content",
  "bias": "detected_bias_category",
  "id": "unique_tweet_id"
}
```

## Troubleshooting

### Common Issues

1. **Chrome/ChromeDriver**: Ensure Chrome browser is installed
2. **NITTR Access**: The tool automatically finds working instances
3. **Rate Limiting**: Built-in delays between requests
4. **Profile Loading**: Automatic retry with different instances

### Debug Mode

Enable debug mode to save screenshots and page sources:
```python
DEBUG_MODE = True
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Disclaimer

This tool is for educational and research purposes. Please respect Twitter's terms of service and rate limits. The bias classification is based on keyword matching and should not be considered as financial advice.
