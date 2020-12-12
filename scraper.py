from googleapiclient.discovery import build
from google.oauth2 import service_account
from bs4 import BeautifulSoup
import requests
import sys
import time

# definitions you will need to change every round
VALID_IMAGES = ["Server2016", "Ubuntu16", "Windows10"]
# definitions you will need to change for first-time use
SERVICE_ACCOUNT_FILE = 'keys.json'
SPREADSHEET_ID = ''
INRANGE = 'Teams!A:A'
OUTRANGE = 'out!A2'

# obtain service credentials
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = None
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# build service
service = build('sheets', 'v4', credentials=creds)

# obtain list of teams to examine
sheet = service.spreadsheets()
result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                            range=INRANGE).execute()
teams = result.get('values', [])
if not teams:
    print('No teams found.')
    sys.exit(0)
teams = [i[0] for i in teams]

# obtain set of valid teams
valid_teams = set()
response = requests.get("http://scoreboard.uscyberpatriot.org/")
if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    for tr in table.find_all('tr')[1:]:
        valid_teams.add(tr.find_all('td')[1].text)
else:
    print('Could not reach score server.')
    sys.exit(0)
time.sleep(3)

# scrape info from the web
BASE_URL = "http://scoreboard.uscyberpatriot.org/team.php?team="
info = []
for index in range(0,len(teams)):
    team = teams[index]
    if team in valid_teams:
        url = BASE_URL + team
        response = requests.get(url, timeout = 5)
        if response.status_code == 200 and response.url == url:
            soup = BeautifulSoup(response.text, 'html.parser')
            tables = soup.find_all('table')

            # scrape from general info table (ignore headers)
            summary = []
            for tr in tables[0].find_all('tr')[1:]:
                tds = tr.find_all('td')
                for i in range(0, len(tds)):
                    summary.append(tds[i].text)

            # scrape from specific info table (ignore headers)
            details = {}
            for tr in tables[1].find_all('tr')[1:]:
                tds = tr.find_all('td')
                tds = [td.text.strip() for td in tds]
                reformatted = [tds[5], "{};{};{}".format(tds[2], tds[3], tds[4]), tds[1].strip()]
                details[tds[0].split("_")[0]] = reformatted

            # parse
            team_info = [None for i in range(len(summary) + 3 * len(VALID_IMAGES))]
            for i in range(0, 5):
                # generic team information
                team_info[i] = summary[i]
            for i in range(0, len(VALID_IMAGES)):
                # specific image information - scores, then vuln details, then time
                if VALID_IMAGES[i] in details.keys():
                    for j in range(0, 3):
                        team_info[5 + 3 * j + i] = details[VALID_IMAGES[i]][j]
            for i in range(5, len(summary)):
                # team score summary
                team_info[3 * len(VALID_IMAGES) + i] = summary[i]
            info.append(team_info)
        else:
            # could not retrieve team info
            print("Error in retrieving {}".format(team))
            info.append([team])
        time.sleep(2)
    else:
        # team not found
        info.append([team])
    if len(teams) < 20 or index % int(len(teams) / 10) == 0:
        print("Progress: {}/{}".format(index, len(teams)))

# update
result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
                               range=OUTRANGE,
                               valueInputOption='USER_ENTERED',
                               body={'values':info}).execute()