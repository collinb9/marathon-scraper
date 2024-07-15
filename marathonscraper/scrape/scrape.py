import sys
import dataclasses
import time
from urllib import parse
import requests
from bs4 import BeautifulSoup, Comment


def strip_comments(soup: BeautifulSoup):
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))

    for comment in comments:
        comment.extract()

    return soup


def detect_tables(soup: BeautifulSoup):
    tables = soup.find_all("table")
    return len(tables) > 0


@dataclasses.dataclass
class ScraperConfig:
    interval: int
    outfile: str
    query_params: dict


class Scraper:
    base_url = ""
    query_params = {}

    def __init__(self, config: ScraperConfig, notifier: "Notifier"):
        self.config = config
        self.previous_content = None
        self.current_content = None
        self.notifier = notifier
        self.notifier.scraper = self
        self.query_params.update(config.query_params)
        self.tickets_available = []

    def detect_available_tickets(self, soup: BeautifulSoup, dryrun=False):
        pass

    def should_notify(self):
        return self.detect_change() and len(self.tickets_available) > 0

    def fetch_webpage_content(self, url=None, query_params=None):
        url = url or self.base_url
        query_params = query_params or self.query_params
        response = requests.get(url, params=query_params)
        if response.status_code == 200:
            content = response.text
            soup = BeautifulSoup(content, "html.parser")
            strip_comments(soup)
            return soup, response

        print(f"Failed to fetch {response.url}")
        return None, None

    def detect_change(self):
        return self.previous_content != self.current_content

    def send_alert(self):
        return self.notifier.notify()

    def save_output(self, soup: BeautifulSoup, outfile):
        print(f"Saving output to {outfile}")
        with open(outfile, "w+") as fh:
            fh.write(soup.prettify())

    def handle_notification(self):
        _outfile = str(time.time()) + self.config.outfile
        self.save_output(self.current_content, _outfile)
        self.notifier.notify()

    def _watch_webpage(self, dryrun=False):
        self.previous_content, _ = self.fetch_webpage_content()
        if self.previous_content is None:
            sys.exit(1)

        self.save_output(self.previous_content, self.config.outfile)

        print("Fetched current state. Starting loop")

        while True:
            self.current_content, _ = self.fetch_webpage_content()
            if self.current_content is None:
                time.sleep(self.config.interval)
                continue
            self.detect_available_tickets(self.current_content, dryrun=dryrun)
            if self.should_notify() or dryrun:
                # Save current content for debugging
                self.handle_notification()
                self.previous_content = self.current_content
            time.sleep(self.config.interval)

    def watch_webpage(self, dryrun=False):
        self._watch_webpage(dryrun=dryrun)


class OnregScraper(Scraper):
    base_url = "https://secure.onreg.com/onreg2/bibexchange/"
    query_params = {"language": "us"}

    def detect_available_tickets(self, soup: BeautifulSoup, dryrun=False):

        bolds = [b.string.strip() for b in soup.find_all("b")]
        for _bold in bolds:
            if (
                _bold
                == "There are currently no race numbers for sale. Try again later."
            ):
                print("No tickets available")
                return False
        btns = soup.find_all("a", {"class": "btn button_cphhalf"})
        if len(btns) == 0:
            print("All tickets are in the process of being purchased")
        self.tickets_available = btns
        return self.tickets_available

    def parse_parameters_from_href(self, href):
        parse.urlparse(href)
        parsed_url = parse.urlparse(href)
        params = {
            key: value[0]
            for key, value in parse.parse_qs(parsed_url.query).items()
        }
        return params

    def make_message(self, response):
        return f"""Ticket available at {response.url}.
        Use cookies {response.cookies} to purchase ticket."""

    def handle_notification(self):
        ticket = self.tickets_available[0]
        href = ticket["href"]
        params = self.parse_parameters_from_href(href)
        params.update(self.query_params)
        current_time = str(time.time())
        _outfile = current_time + self.config.outfile
        self.save_output(self.current_content, _outfile)
        content, response = self.fetch_webpage_content(query_params=params)
        ticket_outfile = current_time + ".ticket." + self.config.outfile
        self.save_output(content, ticket_outfile)
        subject = "Ticket available"
        message = self.make_message(response)
        self.notifier.notify(subject=subject, message=message)
