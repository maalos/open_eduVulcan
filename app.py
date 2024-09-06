import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import json

load_dotenv()

class App:
    def __init__(self, town, schoolId, keyId, signature, vDate, pupilId, alias, password):
        self.url = f"https://lekcjaplus.vulcan.net.pl/{town}/{schoolId}/api/mobile"

        self.baseParams = {
            "pupilId": pupilId,
        }

        self.globalKey = "" # hash skrzynki pocztowej

        self.baseHeaders = {
            "accept-encoding": "gzip",
            "content-type": "application/json; charset=utf-8",
            "host": "lekcjaplus.vulcan.net.pl",
            "signature": 'keyId="' + keyId + '",headers="vDate",algorithm="sha256-digest",signature=' + signature,
            "vapi": "1",
            "vdate": vDate,
            "vhint": "a tutaj podobnie jak w vcanonicalurl, tez byle co",
            "vos": "Android",  # Android lub iOS, bez roznicy
            "vversioncode": "hujlo hujlo placcie 40zl co roku za dziecko",
            "user-agent": "Dart/3.3 (dart:io)",
            "vcanonicalurl": "api%2fmobile%2fregister%2fjwt",
            "vversioncode": "617"
        }

        data = self.getUserData()
        if data and data[2] != None:
            print(f"Zalogowano jako {data[2]}")
            return

        ### ETAP 1 - bieremy tokena ze strony logowania i wysylamy razem z aliasem (emailem)

        response = requests.get("https://eduvulcan.pl/logowanie?ReturnUrl=%2fapi%2fap")
        cookieTokenValue = response.cookies.get_dict()["__RequestVerificationToken"]

        if response.ok:
            soup = BeautifulSoup(response.text, "html.parser")
            tokenElement = soup.select_one('input[name="__RequestVerificationToken"]')
            if tokenElement:
                tokenValue = tokenElement.get("value")
            else:
                print("Nie znaleziono tokenu na stronie logowania!")
                exit(1)
        else:
            print("Nie udało się załadować strony logowania!")
            exit(1)

        data = {
            "alias": alias,
            "__RequestVerificationToken": tokenValue
        }

        # tutaj jeszcze nie potrzeba zadnych dodatkowych naglowkow ani ciastek xd
        response = requests.post("https://eduvulcan.pl/Account/QueryUserInfo", data=data)
        if response.ok:
            print("QueryUserInfo OK") if response.json()["success"] else print("QueryUserInfo sie zesralo")

        ### ETAP 2 - wysylamy alias, haslo, token i jakies ciastka na serwis

        cookies = {
            "__RequestVerificationToken": cookieTokenValue
        }

        data = {
            "Alias": alias,
            "Password": password,
            "captchaUser": "",
            "__RequestVerificationToken": tokenValue # nw na huj tu sa 2 rozne tokeny
        }

        response = requests.post("https://eduvulcan.pl/logowanie?ReturnUrl=%2fapi%2fap", cookies=cookies, data=data)
        if response.ok:
            soup = BeautifulSoup(response.text, "html.parser")
            tokenElement = soup.select_one('#ap')
            if tokenElement:
                mysteriousJSON = json.loads(tokenElement.get("value"))
            else:
                print("Nie znaleziono tokenu na stronie weryfikacji!")
                exit(1)
        else:
            print("Nie udało się załadować strony weryfikacji!")
            exit(1)
        
        if not mysteriousJSON["Success"]:
            print("JSON bez sukcesow")
            exit(1)

        verificationToken = mysteriousJSON["Tokens"][0]
        #accessToken = mysteriousJSON["AccessToken"] # nieuzywane? xd

        data = {
            "AppName": "DzienniczekPlus 3.0", # to musi zostac, i nie, nie moze byc tu wpisane dupadupa123
            "Envelope": {
                "OS": "Android", # gdy wywala "Internal Server Error (GenericADOException)" to znaczy ze czegos brakuje
                "Certificate": os.getenv("Certificate"), # gdy wywala "Certyfikat o podanym odcisku palca już istnieje" to cos jest nie tak w tym dict
                "CertificateType": "UUID",
                "DeviceModel": "213769420",
                "SelfIdentifier": os.getenv("SelfIdentifier"),
                "Tokens": [
                    verificationToken
                ]
            }
        }

        response = requests.post(f"https://lekcjaplus.vulcan.net.pl/{town}/api/mobile/register/jwt", headers=self.baseHeaders, data=json.dumps(data))
        # jesli tu wywala "Użytkownik nie jest uprawniony do przeglądania żądanych danych" to cos jest nie tak w naglowkach, pewnie signaturka lub data albo czegos brakuje
        print("Logowanie i rejestracja JWT", response.json()["Status"]["Message"])

        data = self.getUserData()
        print(f"Zalogowano jako {data[2]}")

    def getUserData(self):
        response = requests.get(f"{self.url}/register/hebe?mode=2&lastSyncDate=1970-01-01%2001%3A00%3A00", headers=self.baseHeaders)
        responseEnvelope = response.json()['Envelope']

        self.globalKey = responseEnvelope[0]['MessageBox']['GlobalKey']

        grade = responseEnvelope[0]["ClassDisplay"]
        schoolName = responseEnvelope[0]["Unit"]["DisplayName"]
        fullName = f"{responseEnvelope[0]["Pupil"]["FirstName"]} {responseEnvelope[0]["Pupil"]["SecondName"]} {responseEnvelope[0]["Pupil"]["Surname"]}"
        isMale = responseEnvelope[0]["Pupil"]["Sex"]

        return [grade, schoolName, fullName, isMale]

    def getTimetable(self, dateFrom, dateTo):
        timetableParams = self.baseParams.copy()
        timetableParams["dateFrom"] = dateFrom
        timetableParams["dateTo"] = dateTo

        response = requests.get(f"{self.url}/schedule/withchanges/byPupil", headers=self.baseHeaders, params=timetableParams)

        if not response.ok:
            return response.status_code

        responseEnvelope = response.json().get("Envelope")
        if responseEnvelope is None:
            return False

        timetable = []
        for lesson in responseEnvelope:
            timetable.append([
                lesson["Date"]["DateDisplay"],
                lesson["TimeSlot"]["Start"],
                lesson["TimeSlot"]["End"],
                lesson["Room"]["Code"],
                lesson["TeacherPrimary"]["DisplayName"]
            ])

        return timetable
    
    def getLuckyNumber(self, constituentId, day): # prosze mnie nie pytac co robi constituentId ja sam nie wiem
        luckyNumberParams = self.baseParams.copy()
        luckyNumberParams["constituentId"] = constituentId
        luckyNumberParams["day"] = day

        response = requests.get(f"{self.url}/school/lucky", headers=self.baseHeaders, params=luckyNumberParams)

        if not response.ok:
            return response.status_code

        responseEnvelope = response.json().get("Envelope")
        if responseEnvelope is None:
            return False


        return responseEnvelope["Number"]

    def getMessages(self, folder, lastSyncDate):
        messagesParams = self.baseParams.copy()
        messagesParams["box"] = self.globalKey
        messagesParams["lastId"] = "-2147483648"
        messagesParams["pageSize"] = 1000
        messagesParams["lastSyncDate"] = lastSyncDate

        response = requests.get(f"{self.url}/messages/{folder}/byBox", headers=self.baseHeaders, params=messagesParams)

        if not response.ok:
            return response.status_code

        responseEnvelope = response.json().get("Envelope")
        if responseEnvelope is None:
            return False

        messageList = []
        for message in responseEnvelope:
            messageList.append([
                message["Id"],
                message["GlobalKey"],
                message["Sender"]["Name"],
                message["Subject"],
                message["Content"],
                message["DateSent"]["DateDisplay"],
                message["DateSent"]["Time"],
                message["DateRead"]["DateDisplay"] if message["DateRead"] is not None else None,
                message["DateRead"]["Time"] if message["DateRead"] is not None else None,
                message["Attachments"] if message["Attachments"] is not None else None,
            ])

        return messageList

app = App(
    town = os.getenv("town"),
    schoolId = os.getenv("schoolId"),
    keyId = os.getenv("keyId"),
    signature = os.getenv("signature"),
    vDate = os.getenv("vDate"),
    pupilId = os.getenv("pupilId"),

    alias = os.getenv("alias"),
    password = os.getenv("password"),
)

luckyNumber = app.getLuckyNumber("41", datetime.today().strftime('%Y-%m-%d'))   # nie, nie da sie znajdowac numerkow na przyszle dni.
                                                                                # generowane sa okolo 5 minut po polnocy codziennie.

if luckyNumber == False:
    print("Nie udało się pobrać danych z dziennika!")
    exit(1)

print(f"Szczęśliwy numerek: {"jeszcze nie wygenerowany" if luckyNumber == 0 else luckyNumber}")
print(f"Liczba wysłanych wiadomości: {len(app.getMessages("sent", "2024-09-04%2022%3A15%3A30"))}")
print(f"Liczba odebranych wiadomości: {len(app.getMessages("received", "2024-09-04%2022%3A15%3A30"))}")
print(f"Liczba usuniętych wiadomości: {len(app.getMessages("deleted", "2024-09-04%2022%3A15%3A30"))}")
