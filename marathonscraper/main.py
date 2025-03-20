import os
import json
import sys
import argparse
from marathonscraper import (
    EmailNotifierConfig,
    EmailNotifier,
    ScraperConfig,
    OnregScraper,
    Scraper
)

EMAIL = os.environ["EMAIL"]
PASSWORD = os.environ["PASSWORD"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Watch a webpage for changes")
    parser.add_argument(
        "config", type=str, help="Location of config json file"
    )
    parser.add_argument(
        "--dryrun",
        action="store_true",
        help="Test what happens when there is a change to the webpage",
    )
    args = parser.parse_args()
    config_path = args.config
    with open(config_path, "r") as f:
        config = json.load(f)
    print(config)

    _email_config = {
        "sender_email": EMAIL,
        "sender_password": PASSWORD
    }
    _email_config.update(config["notifier"])
    email_config = EmailNotifierConfig(**_email_config)
    email_notifier = EmailNotifier(email_config)

    scraper_type = config.pop("type", None)
    if scraper_type == "onreg":
        _scraper = OnrefScraper
    else:
        _scraper = Scraper
    scaper_config = ScraperConfig(**config["scraper"])
    scraper = _scraper(scaper_config, email_notifier)

    scraper.watch_webpage(dryrun=args.dryrun)
