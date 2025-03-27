import sys
import dataclasses
import time
from urllib import parse
import requests
from typing import Optional
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
    query_params: Optional[dict] = None
    url: Optional[str] = None
    eventid: Optional[str] = None


class Scraper:
    base_url = ""
    query_params = {}

    def __init__(self, config: ScraperConfig, notifier: "Notifier"):
        self.config = config
        self.previous_content = None
        self.current_content = None
        self.notifier = notifier
        self.notifier.scraper = self
        self.tickets_available = []
        if config.query_params is not None:
            self.query_params.update(config.query_params)
        if config.url is not None:
            self.base_url = config.url

    def detect_available_tickets(self, soup: BeautifulSoup, dryrun=False):
        pass

    def should_notify(self):
        return self.detect_change()

    def fetch_webpage_content(self, url=None, query_params=None):
        url = url or self.base_url
        query_params = query_params or self.query_params

        response = requests.get(url, params=query_params, headers = {"User-Agent": ""})
        if response.status_code == 200:
            content = response.text
            soup = BeautifulSoup(content, "html.parser")
            strip_comments(soup)
            return soup, response

        print(f"Failed to fetch {response.url}")
        # print(response.json())
        print(response.request.headers)
        return None, None

    def detect_change(self):
        return self.previous_content != self.current_content

    def handle_notification(self):
        _outfile = str(time.time()) + self.config.outfile
        self.save_output(self.current_content, _outfile)
        message = """Change Detected"""
        self.notifier.notify(message=message)

    def _watch_webpage(self, dryrun=False):
        self.previous_content, _ = self.fetch_webpage_content()
        if self.previous_content is None:
            sys.exit(1)

        self.save_output(self.previous_content, self.config.outfile)

        print("Fetched current state. Starting loop")

        while True:
            # print("Checking ...")
            self.current_content, _ = self.fetch_webpage_content()
            if self.current_content is None:
                print("Response is empty")
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

class SportstimingScraper(Scraper):
    _base_url = "https://www.sportstiming.dk"
    query_params = {}

    @property
    def base_url(self):
        return self._base_url + f"/event/{self.config.eventid}/resale"

    def detect_available_tickets(self, soup: BeautifulSoup, dryrun=False):

        tickets = []
        ## There is only a tbody tag when there are tickets for sale
        table = soup.find("tbody")
        if table is None:
            self.tickets_available = []
            return []

        for row in table.find_all("tr"):
            distance = row.find("td").string.strip()
            ## TODO make distance configurable
            # if distance.lower() == "10 km": ## We have a ticket!
            ticket = row.find("a", {"class": "btn btn-primary"})
            if ticket is not None:
                tickets.append(ticket)
        if len(tickets) == 0:
            print("No tickets for desired distance available")
        self.tickets_available = tickets
        return self.tickets_available

    def should_notify(self):
        return self.detect_change() and len(self.tickets_available) > 0

    def send_alert(self):
        return self.notifier.notify()

    def save_output(self, soup: BeautifulSoup, outfile):
        print(f"Saving output to {outfile}")
        with open(outfile, "w+") as fh:
            fh.write(soup.prettify())

    def make_message(self, tickets):
        message = ""
        for ticket in tickets:
            href = ticket["href"]
            ticket_url = self._base_url + href
            message += f"Ticket available at {ticket_url}\n"

        return message

    def handle_notification(self):
        current_time = str(time.time())
        _outfile = current_time + self.config.outfile
        self.save_output(self.current_content, _outfile)
        message = self.make_message(self.tickets_available)
        self.notifier.notify(message=message)

    def _watch_webpage(self, dryrun=False):
        self.previous_content, _ = self.fetch_webpage_content()
        if self.previous_content is None:
            sys.exit(1)

        self.save_output(self.previous_content, self.config.outfile)

        print("Fetched current state. Starting loop")

        while True:
            # print("Checking ...")
            self.current_content, _ = self.fetch_webpage_content()
            if self.current_content is None:
                print("Response is empty")
                time.sleep(self.config.interval)
                continue
            self.detect_available_tickets(self.current_content, dryrun=dryrun)
            if self.should_notify() or dryrun:
                # Save current content for debugging
                self.handle_notification()
                self.previous_content = self.current_content
            time.sleep(self.config.interval)

class OnregScraper(Scraper):
    base_url = "https://secure.onreg.com/onreg2/bibexchange/"
    query_params = {"language": "us"}

    def should_notify(self):
        return self.detect_change() and len(self.tickets_available) > 0

    def detect_available_tickets(self, soup: BeautifulSoup, dryrun=False):

        bolds = [b.string.strip() for b in soup.find_all("b")]
        for _bold in bolds:
            if (
                _bold
                == "There are currently no race numbers for sale. Try again later."
            ):
                print("No tickets available")
                self.tickets_available = []
                return []
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
        ticket_url = response.history[-1].url
        return f"""Ticket available at {ticket_url}."""

    def handle_notification(self):
        current_time = str(time.time())
        _outfile = current_time + self.config.outfile
        self.save_output(self.current_content, _outfile)
        # self.notifier.notify()
        ticket = self.tickets_available[0]
        href = ticket["href"]
        params = self.parse_parameters_from_href(href)
        params.update(self.query_params)
        content, response = self.fetch_webpage_content(query_params=params)
        ticket_outfile = current_time + f".ticket." + self.config.outfile
        self.save_output(content, ticket_outfile)
        message = self.make_message(response)
        self.notifier.notify(message=message)
