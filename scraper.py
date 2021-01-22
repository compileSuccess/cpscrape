from googleapiclient.discovery import build
from google.oauth2 import service_account
from bs4 import BeautifulSoup
import requests
import os
import sys, getopt
import time
import datetime

# definitions you might want to customize
VALID_IMAGES = ["ExampleOS1", "ExampleOS2"]
SERVICE_ACCOUNT_FILE = 'keys.json'

# scrape info from the web
def scrape(teams):
    global VALID_IMAGES

    # obtain set of valid teams
    base_url = "http://scoreboard.uscyberpatriot.org/"
    valid_teams = set()
    response = requests.get(base_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        for tr in table.find_all('tr')[1:]:
            valid_teams.add(tr.find_all('td')[1].text)
    else:
        print('Could not reach score server.')
        sys.exit(1)
    time.sleep(3)

    # scrape from team-specific score pages
    base_url = base_url + "team.php?team="
    info = []
    for index in range(0,len(teams)):
        team = teams[index]
        if team in valid_teams:
            url = base_url + team
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
                            team_info[5 + len(VALID_IMAGES) * j + i] = details[VALID_IMAGES[i]][j]
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
    return info

def main(argv):
    global SERVICE_ACCOUNT_FILE
    input_location = ""
    output_location = ""
    sid = ""
    io_type = -1

    try:
        opts, args = getopt.getopt(argv, "hi:o:s:t:", ["help", "input=", "output=", "sid=", "type="])
        for opt, arg in opts:
            if opt in ("-h", "--help"):
                print("Usage: scraper.py -i <input> -o <output> -t <IO type> [-s <spreadsheet ID>]")
                os._exit(0)
            if opt in ("-i", "--input"):
                input_location = arg
            elif opt in ("-o", "--output"):
                output_location = arg
            elif opt in ("-s", "--sid"):
                sid = arg
            elif opt in ("-t", "--type"):
                if arg.isnumeric():
                    io_type = int(arg)
                else:
                    try:
                        io_type = int(arg.replace("f", "0").replace("s", "1"), 2)
                    except ValueError:
                        print("Invalid conversion type")
                        os._exit(1)
                if io_type not in range(0,4):
                    print("Invalid conversion type")
                    os._exit(1)
        if io_type == -1:
            print("Missing I/O type")
            os._exit(1)
        elif io_type != 0 and sid == "":
            print("Missing spreadsheet ID")
            os._exit(1)
        if not input_location or not output_location:
            print("Missing input or output location")
    except getopt.GetoptError:
        print("Invalid usage")
        sys.exit(2)
    
    print(input_location, output_location, sid, io_type)

    # spreadsheet setup
    sheet = None
    if io_type != 0:
        # obtain service credentials
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        creds = None
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        # build service
        service = build('sheets', 'v4', credentials=creds)
        # obtain list of teams to examine
        sheet = service.spreadsheets()

    # retrieve input
    teams = []
    if io_type & 2:
        # pull from spreadsheet
        result = sheet.values().get(spreadsheetId=sid,
                            range=input_location).execute()
        teams = result.get('values', [])
        if not teams:
            print('No teams found.')
            sys.exit(0)
        teams = [i[0] for i in teams]
    else:
        # pull from file
        try:
            teams = open(input_location, "r").read().replace(",", "\n").replace(";", "\n").split()
        except FileNotFoundError:
            print("File not found.")
            sys.exit(2)
        except IOError:
            print("Cannot access file.")
    print(teams)

    info = scrape(teams)

    # generate output
    if io_type & 1:
        # write to spreadsheet
        result = sheet.values().update(spreadsheetId=sid,
                                    range=output_location,
                                    valueInputOption='USER_ENTERED',
                                    body={'values':info}).execute()
    else:
        # write to file
        with open(output_location, "w") as out:
            out.writelines([",".join([x or "" for x in row]) + "\n" for row in info])

    print(f"Last updated {datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')}")

if __name__ == "__main__":
    main(sys.argv[1:])