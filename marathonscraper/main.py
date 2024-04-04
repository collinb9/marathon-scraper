import os
import json
import sys
import time
import argparse
import smtplib
import ssl
from email.message import EmailMessage
import requests


EMAIL = os.environ["EMAIL"]
PASSWORD = os.environ["PASSWORD"]

CONTEXT = ssl.create_default_context()


def fetch_webpage_content(url, outfile):
    response = requests.get(url)
    if response.status_code == 200:
        content = response.text
        with open(outfile, "w+") as fh:
            fh.write(content)
        return content

    print(f"Failed to fetch {url}")
    return None


def detect_change(previous_content, current_content):
    return previous_content != current_content


def send_alert(contacts_path, url):
    with open(contacts_path, "r") as fh:
        contacts = [line.replace("\n", "") for line in fh.readlines()]
    message = f"Webpage at {url} has changed."
    msg = EmailMessage()
    content = f'{message}\n'
    msg.set_content(content)
    msg['Subject'] = "Change detected"
    msg['From'] = EMAIL
    msg['To'] = contacts
    print("Contacts:", contacts)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=CONTEXT) as server:
        server.login(EMAIL, PASSWORD)
        server.send_message(msg, EMAIL, contacts)
        print("Email successfully sent")


def watch_webpage(url, interval, outfile, contacts, dryrun=False):
    previous_content = fetch_webpage_content(url, outfile)
    if previous_content is None:
        sys.exit(1)

    print("Fetched current state. Starting loop")

    while True:
        current_content = fetch_webpage_content(url, outfile)
        if current_content is None:
            time.sleep(interval)
            continue

        if detect_change(previous_content, current_content) or dryrun:
            print(
                f"Change detected for {url}",
                time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            )
            # Save current content for debugging
            with open(str(time.time()) + outfile, "w+") as fh:
                fh.write(current_content)
            send_alert(contacts, url)
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
    with open(config_path, "r") as f:
        config = json.load(f)
    watch_webpage(
        config["url"],
        config.get("interval", 60),
        config.get("outfile", "output.out"),
        config.get("contacts", "contacts.txt"),
        dryrun=args.dryrun,
    )
