import redis
import unittest
import subprocess
import time
import secrets

# we will have a key - json-document session storag
# key is the session token
# document is a json dict with
# "userid": ConDIDI userid
# "DID": User DID (can be empty)
# "email": User email
# "sessionstatus": "valid" if logged in, "waiting" if a wallet session waits for wallet confirmation
#

# start a password login session
def start_session(db, user_data):
    # create session key
    session_key = secrets.token_urlsafe(32)
    db.set(session_key, user_data)
    return session_key


# close/delete a session
def close_session(db, session_token):
    return True

# start a wallet login session
def start_wallet_session(db, session_token):
    return True

# check status of session
def check_session(db, session_token, userid):
    session = db.get(session_token)
    if not session:
        # token not in session database
        return False, None
    if userid == session["userid"].lower():
        return True,

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
        token = start_session(db, user_data=user)
        self.assertTrue(token)
        print("check close session")
        self.assertTrue(close_session(db, session_token=token))

if __name__ == '__main__':
    # do tests
    unittest.main()

