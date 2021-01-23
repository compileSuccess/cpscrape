from googleapiclient.discovery import build
from google.oauth2 import service_account
from bs4 import BeautifulSoup
import requests
import os
import sys, getopt
import time
import datetime

# definitions you might want to customize


class Scraper:
    def __init__(self, key, images):
        self.key_file = key
        self.valid_images = images
        self.sheet = self.build_sheet()

    def build_sheet(self):
        # obtain service credentials
        sc = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = None
        creds = service_account.Credentials.from_service_account_file(
            self.key_file, scopes=sc)
        # build service
        service = build('sheets', 'v4', credentials=creds)
        return service.spreadsheets()

    def scrape(self, teams):
        """Given some teams, scrape their info from the website"""

        # obtain set of valid teams on the scoreboard
        base_url = "http://scoreboard.uscyberpatriot.org/"
        valid_teams = set()
        response = requests.get(base_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table')
            for tr in table.find_all('tr')[1:]:
                valid_teams.add(tr.find_all('td')[1].text)
        else:
            print("Could not reach score server.")
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
                    team_info = [None for i in range(len(summary) + 3 * len(self.valid_images))]
                    for i in range(0, 5):
                        # generic team information
                        team_info[i] = summary[i]
                    for i in range(0, len(self.valid_images)):
                        # specific image information - scores, then vuln details, then time
                        if self.valid_images[i] in details.keys():
                            for j in range(0, 3):
                                team_info[5 + len(self.valid_images) * j + i] = details[self.valid_images[i]][j]
                    for i in range(5, len(summary)):
                        # team score summary
                        team_info[3 * len(self.valid_images) + i] = summary[i]
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

    def pull_sheet(self, location, sid):
        result = self.sheet.values().get(spreadsheetId=sid, range=location).execute()
        teams = result.get('values', [])
        if not teams:
            print("No teams found.")
            sys.exit(0)
        return [i[0] for i in teams]

    def pull_file(self, location):
        try:
            teams = open(location, "r").read().replace(",", "\n").replace(";", "\n").split()
        except FileNotFoundError:
            print("File not found.")
            sys.exit(2)
        except IOError:
            print("Cannot access file.")
        return teams

    def write_sheet(self, info, location, sid):
        result = self.sheet.values().update(spreadsheetId=sid,
                                            range=location,
                                            valueInputOption='USER_ENTERED',
                                            body={'values':info}).execute()

    def write_file(self, info, location):
        with open(location, "w") as out:
                out.writelines([",".join([x or "" for x in row]) + "\n" for row in info])

    def scrape_points(self, teams):
        plot = []
        for team in teams:
            base_url = "http://scoreboard.uscyberpatriot.org/" + "team.php?team=" + team
            response = requests.get(base_url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                script = soup.find_all('script')[1]
                data = str(script).split("arrayToDataTable([\n")[1].split("]);")[0].replace("'","").replace("null","")
                data = [x[1:-2].split(", ") for x in data.split("\r\n")[:-1]]
                data = [[team]] + data
            # pad to 80 rows
            data = data + [[]] * (80 - len(data))
            plot.extend(data)
        return plot

    def generate_charts(self, teams, points, sid, gid):
        """Requires team #, points over time data, spreadsheet ID, AND data sheet ID (gid)"""
        # clear current points data
        delreq = {"requests": [{"updateCells": {"range": {"sheetId": gid}, "fields": "userEnteredValue"}}]}
        result = self.sheet.batchUpdate(spreadsheetId=sid,body=delreq).execute()
        # add data
        result = self.sheet.values().update(spreadsheetId=sid,
                                            range="Graph Data",
                                            valueInputOption='USER_ENTERED',
                                            body={'values':points}).execute()
        # generate charts
        chreq = []
        for i, t in enumerate(teams):
            chreq.append(
                {"addChart": {"chart": {
                    "spec": {
                        "title": t + " scores",
                        "basicChart": {
                            "chartType": "LINE",
                            "legendPosition": "BOTTOM_LEGEND",
                            "axis": [{"position": "BOTTOM_AXIS", "title": "Time"}, {"position": "LEFT_AXIS", "title": "Points"}],
                            "domains": [{"domain": {"sourceRange": {"sources": [{"sheetId": gid, "startRowIndex": 80*i, "endRowIndex": 80*i + 80, "startColumnIndex": 0, "endColumnIndex": 1}]}}}],
                            "series": [{"series":{"sourceRange":{"sources":[{"sheetId": gid, "startRowIndex": 80*i, "endRowIndex": 80*i + 80, "startColumnIndex": x + 1, "endColumnIndex": x + 2}]}}, "targetAxis": "LEFT_AXIS"} for x in range(len(self.valid_images))],
                            "headerCount": 1
                        }
                    },
                    "position": {
                        "newSheet": True
                    }
                }}}
            )
        result = self.sheet.batchUpdate(spreadsheetId=sid,body={"requests": chreq}).execute()

    def main(self, i, o, io_type, sid):
        if io_type & 2:
            teams = self.pull_sheet(i, sid)
        else:
            teams = self.pull_file(i)
        
        info = self.scrape(teams)

        if io_type & 1:
            self.write_sheet(info, o, sid)
        else:
            self.write_file(info, o)
        
        print(f"Last updated {datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')}")

if __name__ == "__main__":
    sid = ""
    # parse from command line
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:o:s:t:", ["help", "input=", "output=", "sid=", "type="])
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
    s = Scraper("keys.json", ["Debian9", "Server2019", "Ubuntu18", "Windows10"])
    s.main(input_location, output_location, io_type, sid)

    # generate chart for top team(s)
    num_top = 1
    response = requests.get("http://scoreboard.uscyberpatriot.org/")
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        top = [row.find_all('td')[1].text for row in table.find_all('tr')[1:1+num_top]]
        s.generate_charts(top, s.scrape_points(top), sid, 123456789)