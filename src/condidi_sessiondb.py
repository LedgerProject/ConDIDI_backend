import redis
import unittest
import subprocess
import time
import secrets
import json

# we will have a key - json-document session storag
# key is the session token
# document is a json dict with
# "userid": ConDIDI userid
# "DID": User DID (can be empty)
# "email": User email
# "sessionstatus": "valid" if logged in, "waiting" if a wallet session waits for wallet confirmation
#

# start a password login session
def start_session(db, userid):
    """
    creates a session token and starts a new session in the session database
    :param db: redisconnection
    :param userid: userid for the session.
    :return: session token as string
    """
    # create session key
    session_key = secrets.token_urlsafe(36)
    session_data=dict(lastaccess=time.time(), login="full")
    db.set(session_key, json.dumps(session_data))
    return session_key


# close/delete a session
def close_session(db, session_token):
    result = db.delete(session_token)
    if result == 1:
        return True, result
    return False, result

# start a wallet login session
def start_wallet_session(db, ssi_token):
    session_key = ssi_token
    session_data=dict(lastaccess=time.time(), login="pending")
    db.set(session_key, json.dumps(session_data))
    return ssi_token

# check status of session
def check_session(db, session_token):
    data = db.get(session_token)
    if not data:
        # token not in session database
        return False, None
    sessiondict = json.loads(data)
    if sessiondict["login"] == "full":
        # update last access
        sessiondict["lastaccess"] = time.time()
        db.set(session_token, json.dumps(sessiondict))
        # good session, return true and "full"
        return True, None
    elif sessiondict["login"] == "pending":
        # still waiting for wallet confirmation
        return False, "Waiting for wallet confirmation"
    # token in session database, but not a matching user
    return False, None



class TestDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # start docker databases
        print("start docker")
        subprocess.run(["docker", "run", "-p", "6379:6379", "-d",
                        "--rm", "--name", "redistest", "redis"],
                       timeout=20, check=True)
        # give Redis some time to start up
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        # stop docker databases
        print("stop docker")
        subprocess.run(["docker", "stop", "redistest"])

    def test_manage_database(self):
        db = redis.Redis(host="127.0.0.1", port=6379)
        print("check redis runnin")
        self.assertTrue(db.ping())
        # should return True
        print("check start session")
        user = {"name":"test user", "email":"test@test.invalid", "did":"1234abcd:4245:3224", "_key": "jdsal"}
        token = start_session(db, userid=0)
        self.assertIsNotNone(token)
        print("check session status")
        result = check_session(db, token)
        self.assertTrue(result[0])
        self.assertIsNone(result[1])
        print("check fake session")
        result = check_session(db, secrets.token_urlsafe(36))
        self.assertFalse(result[0])
        self.assertIsNone(result[1])
        print("check delete session")
        result = close_session(db, token)
        self.assertTrue(result[0])
        result = close_session(db, token)
        self.assertTrue(result[0])
        result = check_session(db, token)
        self.assertFalse(result[0])
        self.assertIsNone(result[1])
        print("check wallet pending session")
        ssitoken = "12345"
        token = start_wallet_session(db, ssitoken)
        self.assertIs(token, ssitoken)
        result = check_session(db, token)
        self.assertFalse(result[0])
        self.assertIsNotNone(result[1])
        print("message: ", result[1])
        print("check delete wallet session")
        result = close_session(db, token)
        self.assertTrue(result[0])
        result = close_session(db, token)
        self.assertTrue(result[0])
        result = check_session(db, token)
        self.assertFalse(result[0])
        self.assertIsNone(result[1])


if __name__ == '__main__':
    # do tests
    unittest.main()

