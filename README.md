# marathon-scraper

A web scraper/watcher to alert when race tickets are available for resale.

## Usage

To start the script, run the following command

```sh
marathonscraper/main.py config.json contacts.txt
```

Here is an example `config.json` file

```json
{
  "url": "https://example.com",
  "interval": 30,
  "outfile": "out.out"
}
```

The `contacts.txt` file is a newline-separated list of email addresses to send alerts to.

The script expects the following environment variables to be set:
* `EMAIL`: The email from which to send alerts.
* `PASSWORD`: The password for the email account.
