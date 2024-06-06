import os
import json
import sys
import time
import argparse
import smtplib
import ssl
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup, Comment

EMAIL = os.environ["EMAIL"]
PASSWORD = os.environ["PASSWORD"]

CONTEXT = ssl.create_default_context()


def strip_comments(soup):
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))

    for comment in comments:
        comment.extract()

    return soup


def fetch_webpage_content(url, outfile):
    response = requests.get(url)
    if response.status_code == 200:
        content = response.text
        soup = BeautifulSoup(content, "html.parser")
        strip_comments(soup)
        save_output(soup, outfile)
        return soup

    print(f"Failed to fetch {url}")
    return None


def detect_change(previous_content, current_content):
    return previous_content != current_content

def detect_tables(soup):
    tables = soup.find_all("table")
    return len(tables) > 0

def detect_race_numbers_for_sale(soup):
    bolds = [b.string.strip() for b in soup.find_all("b")]
    return len(bolds) == 0 or bolds[0] != "There are currently no race numbers for sale. Try again later."


def should_notify(previous_content, current_content, condition):
    return detect_change(previous_content, current_content) and condition(current_content)


def send_alert(contacts_path, url):
    with open(contacts_path, "r") as fh:
        contacts = [line.replace("\n", "") for line in fh.readlines()]
    if len(contacts) == 0:
        print("No contacts found. Skipping email")
        return
    message = f"Webpage at {url} has changed."
    msg = EmailMessage()
    content = f"{message}\n"
    msg.set_content(content)
    msg["Subject"] = "Change detected"
    msg["From"] = EMAIL
    msg["To"] = contacts
    print("Contacts:", contacts)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=CONTEXT) as server:
        server.login(EMAIL, PASSWORD)
        server.send_message(msg, EMAIL, contacts)
        print("Email successfully sent")


def save_output(soup, outfile):
    print(f"Saving output to {outfile}")
    with open(outfile, "w+") as fh:
        fh.write(soup.prettify())


def watch_webpage(url, interval, outfile, site, contacts, dryrun=False):
    if site == "onreg":
        condition = detect_race_numbers_for_sale
    else:
        condition = detect_tables
    previous_content = fetch_webpage_content(url, outfile)
    if previous_content is None:
        sys.exit(1)

    print("Fetched current state. Starting loop")

    while True:
        current_content = fetch_webpage_content(url, outfile)
        if current_content is None:
            time.sleep(interval)
            continue
        _outfile = str(time.time()) + outfile
        if should_notify(previous_content, current_content, condition) or dryrun:
            print(
                f"Ticket available at {url}",
                time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            )
            # Save current content for debugging
            save_output(current_content, _outfile)
            send_alert(contacts, url)
            previous_content = current_content
        elif detect_change(previous_content, current_content) or dryrun:
            print(
                f"Change detected at {url}",
                time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            )
            save_output(current_content, _outfile)
            previous_content = current_content

        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Watch a webpage for changes")
    parser.add_argument(
        "config", type=str, help="Location of config json file"
    )
    parser.add_argument("contacts", type=str, help="Location of contacts file")
    parser.add_argument(
        "--dryrun",
        action="store_true",
        help="Test what happens when there is a change to the webpage",
    )
    args = parser.parse_args()
    config_path = args.config
    print(args)
    with open(config_path, "r") as f:
        config = json.load(f)
    print(config)
    watch_webpage(
        config["url"],
        config.get("interval", 60),
        config["outfile"],
        config.get("site", "NONE"),
        args.contacts,
        dryrun=args.dryrun,
    )
