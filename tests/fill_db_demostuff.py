import requests
import json
#APIURL = "http://localhost:8080/api/"
APIURL = "https://labs.tib.eu/condidi/api/"

# create demo organiser
print("create demo user")
userdict = {"name": "testuser", "email": "test@condidi.invalid", "password": "12345"}
r = requests.post(APIURL+'create_user', json=userdict)
result = r.json()
print(result)
print("login")
r = requests.post(APIURL+'login_password', json=userdict)
print(r.text)
result = r.json()
print(result)
token = result["token"]
# add some events
print("add some events")
eventdict = {"name": "TEST 5. VIVO-Workshop 2021", "type":"Workshop", "subject":"VIVO","presenter":"VIVODE21",
             "venue information":"online", "address":"online", "url": "https://events.tib.eu/vivo-workshop-2021",
             "organiser institution":"TIB",
            "contact person name":"TEST", "contact person email":"TEST@TEST.INVALID", "submission deadline":"2021-02-15 ",
            "registration deadline":"", "date":"2021-03-23"}
calldict = {"token": token, "eventdict": eventdict}
r = requests.post(APIURL+'add_event', json=calldict)
result = r.json()
eventid = result["eventdict"]["eventid"]
print(result)
print("list events")
calldict = {"token": token}
r = requests.post(APIURL+'list_my_events', json=calldict)
result = r.json()
print(result)
# add some participants
print("add participants")
participantdict = {"name": "Testuser", "email": "testuser@test.invalid", "did": "12345:1234:1234", "payment status": "paid",
                   "attendence status": "registered", "participation": "speaker",
                   "signup date": "2021-01-01", "ticket id": None, "credential id": None}
calldict = {"token": token, "eventid": eventid, "participantdict": participantdict}
r = requests.post(APIURL+'add_participant', json=calldict)
result = r.json()
print(result)
participantdict = {"name": "Testuser2", "email": "testuser2@test.invalid", "did": "12345:466787:1234", "payment status": "",
                   "attendence status": "registered", "participation": "attendent",
                   "signup date": "2021-02-02", "ticket id": None, "credential id": None}
calldict = {"token": token, "eventid": eventid, "participantdict": participantdict}
r = requests.post(APIURL+'add_participant', json=calldict)
result = r.json()
# list participants
calldict = {"token": token, "eventid": eventid}
r = requests.post(APIURL+'list_participants', json=calldict)
result = r.json()
print(result)
print("log out")
