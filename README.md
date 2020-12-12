# cpscrape
A *CyberPatriot-unofficial-scoreboard*-to-*Google-spreadsheet* scraper/parser.

It takes a column of teams from a Google spreadsheet file and outputs to the same file in a nice table! All you need is python and a Google service account.

## Installation
First, ensure you have the necessary packages.
```bash
pip install -r requirements.txt
```

## Setup
This program requires you to make a [Google service account](https://support.google.com/a/answer/7378726?hl=en).

To quickly summarize: create a project in the Google developer console, set up the service account, create the JSON key and save it, then add the account as an editor to your spreadsheet.

Additionally, you will need to change several variables in `scraper.py`.

### Definitions you'll need to change

- `VALID_IMAGES`
    - A list of all images tested in the current round. You can select a team to see the image names - what you want is the part before the first underscore.
- `SERVICE_ACCOUNT_FILE`
    - The relative path to your service key, which should be a JSON file.
- `SPREADSHEET_ID`
    - The unique ID of your Google spreadsheet. You can find it in the URL, and it will be the part after "/d/" but before "/edit"
- `INRANGE`
    - Located in your spreadsheet, this should be the one column of team numbers that you want the program to scrape.
- `OUTRANGE`
    - Also located in your spreadsheet, this should be the upper-left corner cell of the desired output location.