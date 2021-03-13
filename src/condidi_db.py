from arango import ArangoClient
import arango
import unittest
import subprocess
import time
import bcrypt


class Event(dict):
    def __init__(self, noinit=False):
        """
        define the keys we want to have in the event document
        """
        super().__init__()
        self.allowed_keys = ["name", "type", "subject", "venue information", "address", "url", "organiser institution",
                             "contact person name", "contact person email", "submission deadline",
                             "registration deadline", "date", "organiser userid"]
        if not noinit:
            for key in self.allowed_keys:
                self[key] = None

    def load(self, eventdict):
        badkeys = list()
        for key in eventdict:
            if key in self.allowed_keys:
                self[key] = eventdict[key]
            else:
                badkeys.append(key)
        return badkeys


class Participant(dict):
    def __init__(self, noinit=False):
        """
        define the keys we want to have in the participant in the participantlist document. if a participant has
        a condidi userid, it is noted in the userid field, otherwise it is None.
        """
        super().__init__()
        self.allowed_keys = ["userid", "name", "email", "did", "payment status", "attendence status", "participation",
                             "signup date", "ticket id", "credential id"]
        if not noinit:
            for key in self.allowed_keys:
                self[key] = None

    def load(self, participantdict):
        badkeys = list()
        for key in participantdict:
            if key in self.allowed_keys:
                self[key] = participantdict[key]
            else:
                badkeys.append(key)
        return badkeys

class Credential(dict):
    def __init__(self):
        """
        a credential document
        """
        super().__init__()
        self.allowed_keys = ["previous ids", "issuing date"]
        for key in self.allowed_keys:
            self[key] = None

    def load(self, credentialdict):
        badkeys = list()
        for key in credentialdict:
            if key in self.allowed_keys:
                self[key] = credentialdict[key]
            else:
                badkeys.append(key)
        return badkeys

def create_event(db, neweventdata):
    # event data
    eventdata = Event()
    badkeys = eventdata.load(neweventdata)
    if len(badkeys) > 0:
        print("new event: bad keys found:", badkeys)
    # add event
    events = db.collection("events")
    result = events.insert(eventdata)
    # add list of participants for event as well
    participantlists = db.collection("participantlists")
    participantlists.insert({"eventid": result["_key"], "participants": []})
    return True, result

def find_events(db, matchdict):
    # match events by match dict
    # remove fields we don't support
    eventdata = Event()
    badmatch = eventdata.load(matchdict)
    for key in badmatch:
        matchdict.pop(key, None)
    # construct database query
    events = db.collection("events")
    matched = events.find(matchdict, skip=0, limit=100)
    eventslist = [item for item in matched.batch()]
    return eventslist

def get_event(db, eventid):
    # return event dociment for the id
    events = db.collection("events")
    eventdict = events.get(eventid)
    return eventdict

def create_user(db, userdata):
    # userdata = {"name": name, "email":email, "did":did, "password":password}
    users = db.collection("users")
    # see if email already exists
    result = users.find({'email': userdata['email']}, skip=0, limit=10)
    if result.count() != 0:
        return False, None
    # hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(str(userdata["password"]).encode('utf8'), salt)
    userdata["password"] = hashed.decode('utf8')
    # store user
    result = users.insert(userdata)
    return True, result


def list_participants(db, eventid):
    """
    gets the participant list for a event given by eventid
    :param db: AragnoDB db
    :param eventid: ID from the event in events
    :return: participantlist dictionary
    """
    matchdict = {"eventid": eventid}
    participantlists = db.collection("participantlists")
    participants = db.collection("participants")
    matched = participantlists.find(matchdict, skip=0, limit=10)
    participantids = [item for item in matched.batch()]
    result = [participants.get(item) for item in participantids[0]["participants"] ]
    return result

def add_participant_to_event(db, participantid, eventid=None, listid=None):
    # we can either use the id of the participant list, or look it up via eventid
    participantlists = db.collection("participantlists")
    if not listid:
        if not eventid:
            return False, "need either eventid, orlistid"
        # find by eventid
        matchdict = {"eventid": eventid}
        participantlists = db.collection("participantlists")
        result = participantlists.find(matchdict, skip=0, limit=1)
        participantsdict = [item for item in result]
        if len(participantsdict) == 0:
            return False, "Participant not found"
        else:
            participantsdict = participantsdict[0]
    else:
        participantsdict = participantlists.get(listid)
    listofparticipants = participantsdict["participants"]
    if participantid in listofparticipants:
        return True, "Participant already added"
    listofparticipants.append(participantid)
    print(listofparticipants)
    result = participantlists.replace(participantsdict)
    return True, result


def create_participant(db, participantdict):
    """
    creates an participant to the database
    :param db: arangodb connection
    :param participantdict: dict for participant
    :return: arango insert result, i.e. the dict with the _key, _id and _rev
    """
    newparticipant = Participant()
    newparticipant.load(participantdict)
    participants = db.collection("participants")
    result = participants.insert(newparticipant)
    return result

def remove_participant_from_event(db, participantid, eventid=None, listid=None):
    participantlists = db.collection("participantlists")
    if not listid:
        if not eventid:
            return False, "need either eventid, orlistid"
        # find by eventid
        matchdict = {"eventid": eventid}
        participantlists = db.collection("participantlists")
        result = participantlists.find(matchdict, skip=0, limit=1)
        participantsdict = [item for item in result]
        if len(participantsdict) == 0:
            return False, "Participant not found"
        else:
            participantsdict = participantsdict[0]
    else:
        participantsdict = participantlists.get(listid)
    listofparticipants = participantsdict["participants"]
    if participantid not in listofparticipants:
        return True, "Participant already removed"
    listofparticipants.remove(participantid)
    print(listofparticipants)
    result = participantlists.replace(participantsdict)
    return True, result


def delete_participant(db, participantid, eventid=None, listid=None):
    # we can either use the id of the participant list, or look it up via eventid
    participantlists = db.collection("participantlists")
    if not listid:
        if not eventid:
            return False, "need either eventid, orlistid"
        matchdict = {"eventid": eventid}
        participantlists = db.collection("participantlists")
        listid = [item for item in participantlists.find(matchdict, skip=0, limit=1)][0]
    participants = db.collection("participants")
    try:
        participants.delete(participantid)
    except arango.execptions.DocumentDeleteError:
        return False, "participant not found"
    return True


def create_collections(db):
    """creates all collections needed for ConDIDI, i.e. the user collection and the event collection
       db: database connection"""
    # we use automatically created keys that are int and increment automatically.
    # maybe later add schema validation
    # check if the collections already exist:
    if not db.has_collection('users'):
        users = db.create_collection("users", key_generator="autoincrement")
        # we will mostly search for emails, so lets make an index for it.
        # ArangoDB is supposed to automatically use the index for faster search if it exists.
        users.add_hash_index(fields=["email"], unique=True)
    if not db.has_collection('events'):
        # noinspection PyUnusedLocal
        events = db.create_collection("events", key_generator="autoincrement")
    if not db.has_collection('participantlists'):
        # noinspection PyUnusedLocal
        participantlists = db.create_collection("participantlists", key_generator="autoincrement")
        participantlists.add_hash_index(fields=["eventid"], unique=True)
    if not db.has_collection('participants'):
        # noinspection PyUnusedLocal
        participantlists = db.create_collection("participants", key_generator="autoincrement")
        participantlists.add_hash_index(fields=["email"], unique=False)
        participantlists.add_hash_index(fields=["userid"], unique=False)  # if the participant has no condidi userid, it
        # will be None
    if not db.has_collection('credentials'):
        # noinspection PyUnusedLocal
        participantlists = db.create_collection("credentials")
        # we will use the hash as key

    # ArangoDB uses _id and _key for every document as unique identifiers. _id  = collection_name/_key. So
    # _key is our user_id and event_id for later use
    return True


def create_database(sys_db, dbname="condidi"):
    """creates the database for condidi"""
    # Create a new database named "test".
    if not sys_db.has_database(dbname):
        sys_db.create_database(dbname)
    # TODO: also use specific user for access
    return True


def check_pass(db, password, user_email=None, userid=None):
    """checks the password of the user given by mail or internal id, returns True if password correct, false if not"""
    users = db.collection("users")
    if user_email:
        result = users.find({'email': user_email}, skip=0, limit=10)
    elif userid:
        # result = users.find({'_key': userid}, skip=0, limit=10)
        result = users.get(userid)
    else:
        # neither email nor id given
        return False, None
    if result.count() == 0:
        # user not found
        return False, None
    user_hash = result.batch()[0]["password"]
    if bcrypt.checkpw(password.encode('utf8'), user_hash.encode('utf8')):
        # password correct
        return True, result.batch()[0]["_key"]
    else:
        return False, None


# tests
class TestDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # start docker databases
        print("start docker")
        # subprocess.run(["docker-compose", "-f", "docker-compose-development.yml", "up", "-d"], cwd="..", timeout=20,
        #               check=True)
        subprocess.run(["docker", "run", "-e", "ARANGO_ROOT_PASSWORD=justfortest", "-p", "8529:8529", "-d",
                        "--rm", "--name", "arangotest", "arangodb"],
                       timeout=20, check=True)
        # give ArangoDB some time to start up
        time.sleep(10)

    @classmethod
    def tearDownClass(cls):
        # stop docker databases
        print("stop docker")
        # subprocess.run(["docker-compose", "-f", "docker-compose-development.yml", "down"], cwd="..")
        subprocess.run(["docker", "stop", "arangotest"])

    def test_manage_user_database(self):
        client = ArangoClient(hosts="http://localhost:8529")
        sys_db = client.db("_system", username="root", password="justfortest")
        # first try to delete the test database
        sys_db.delete_database('test', ignore_missing=True)
        print("create DB")
        self.assertTrue(create_database(sys_db, dbname='test'))
        db = client.db("test", username="root", password="justfortest")
        # test collection creation
        print("create collections")
        self.assertTrue(create_collections(db))
        # test create user
        print("create user")
        userdata = {"name": "Testuser", "email": "test@condidi.tib.eu", "password": "test123"}
        print(create_user(db, userdata))
        print("check existing user detection")
        self.assertFalse(create_user(db, userdata)[0])
        print("check correct password")
        self.assertTrue(check_pass(db, password="test123", user_email="test@condidi.tib.eu")[0])
        print("check wrong password")
        self.assertFalse(check_pass(db, password="false", user_email="test@condidi.tib.eu")[0])
        print("check wrong password call")
        self.assertFalse(check_pass(db, password="false")[0])
        print("delete test database")
        self.assertTrue(sys_db.delete_database('test'))
        # close sessions
        client.close()

    def test_manage_event_database(self):
        client = ArangoClient(hosts="http://localhost:8529")
        sys_db = client.db("_system", username="root", password="justfortest")
        # first try to delete the test database
        sys_db.delete_database('test', ignore_missing=True)
        print("create DB")
        self.assertTrue(create_database(sys_db, dbname='test'))
        db = client.db("test", username="root", password="justfortest")
        # test collection creation
        print("create collections")
        self.assertTrue(create_collections(db))
        # test create event
        print("event dict")
        myevent = Event()
        eventdict = {"name": "test event", "url": "http://nada", "error": "False", "organiser userid": 0}
        badkeys = myevent.load(eventdict)
        self.assertEqual(badkeys, ["error"])
        self.assertEqual(len(myevent.keys()), len(myevent.allowed_keys))
        print("add event")
        result = create_event(db, myevent)
        print(result)
        myevent["name"] = "test event 1"
        result = create_event(db, myevent)
        print(result)
        eventid = result[1]["_key"]
        print("retrieve 1 event")
        result = get_event(db, eventid)
        print(result)
        print("find events")
        result = find_events(db, {"organiser userid": 0})
        print(result)
        print("delete test database")
        self.assertTrue(sys_db.delete_database('test'))
        # close sessions
        client.close()

    def test_manage_participants_database(self):
        client = ArangoClient(hosts="http://localhost:8529")
        sys_db = client.db("_system", username="root", password="justfortest")
        # first try to delete the test database
        sys_db.delete_database('test', ignore_missing=True)
        print("create DB")
        self.assertTrue(create_database(sys_db, dbname='test'))
        db = client.db("test", username="root", password="justfortest")
        # test collection creation
        print("create collections")
        self.assertTrue(create_collections(db))
        # test create event
        #print("event dict")
        myevent = Event()
        eventdict = {"name": "test event1", "url": "http://nada", "error": "False", "organiser userid": 0}
        #badkeys = myevent.load(eventdict)
        #self.assertEqual(badkeys, ["error"])
        #self.assertEqual(len(myevent.keys()), len(myevent.allowed_keys))
        print("add event")
        result = create_event(db, myevent)
        eventid = result[1]["_key"]
        # list participants, should be empty
        print("get participants")
        result = list_participants(db, eventid)
        print(result)
        print("add participant")
        par = Participant()
        par.load({"name": "Testparticipant"})
        print("create a participant")
        result = create_participant(db, par)
        parid=result["_key"]
        print(result)
        print("list participants")
        result = list_participants(db, eventid)
        print(result)
        print("add to event")
        result = add_participant_to_event(db, parid, eventid=eventid)
        print(result)
        listid = result[1]["_key"]
        result = add_participant_to_event(db, parid, listid=listid)
        print(result)
        print("remove participant")
        result = remove_participant_from_event(db, parid, eventid = eventid)
        print(result)
        result = remove_participant_from_event(db, parid, listid = listid)
        print(result)
        result = list_participants(db, eventid)
        print(result)

        print("delete test database")
        self.assertTrue(sys_db.delete_database('test'))
        # close sessions
        client.close()



if __name__ == '__main__':
    # do tests
    unittest.main()
