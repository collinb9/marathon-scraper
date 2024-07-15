import dataclasses
import ssl
import smtplib
from email.message import EmailMessage


@dataclasses.dataclass
class NotifierConfig:
    contacts: str


class Notifier:

    def __init__(self, config: NotifierConfig):
        self.config = config
        self.scraper = None

    def notify(self) -> None:
        pass


@dataclasses.dataclass
class EmailNotifierConfig(NotifierConfig):
    sender_email: str
    sender_password: str
    host: str = "smtp.gmail.com"
    port: int = 465


class EmailNotifier(Notifier):
    def __init__(self, config: EmailNotifierConfig):
        self.context = ssl.create_default_context()
        super().__init__(config)

    def read_contacts(self):
        with open(self.config.contacts, "r") as fh:
            contacts = [line.replace("\n", "") for line in fh.readlines()]
        return contacts

    def create_message(self, contacts, subject=None, message=None):
        msg = EmailMessage()
        message = message or f"Webpage at {self.scraper.base_url} has changed."
        content = f"{message}\n"
        msg.set_content(content)
        msg["Subject"] = subject or "Change detected"
        msg["From"] = self.config.sender_email
        msg["To"] = contacts
        return msg

    def send_email(self, subject=None, message=None):
        contacts = self.read_contacts()
        if len(contacts) == 0:
            print("No contacts found. Skipping email")
            return
        # print("Contacts:", contacts)
        msg = self.create_message(contacts, subject=subject, message=message)
        email = self.config.sender_email
        password = self.config.sender_password
        with smtplib.SMTP_SSL(
            self.config.host, self.config.port, context=self.context
        ) as server:
            server.login(email, password)
            server.send_message(msg, email, contacts)
            print("Email successfully sent")

    def notify(self, subject=None, message=None):
        self.send_email(subject=subject, message=message)
