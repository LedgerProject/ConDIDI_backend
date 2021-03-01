from arango import ArangoClient
import unittest
import subprocess
import time
import bcrypt


def create_user(db, userdata):
    # userdata = {"name": name, "email":email, "did":did, "password":password}
    users = db.collection("users")
    # see if email already exists
    result = users.find({'email': userdata['email']}, skip=0, limit=10)
    if result.count() != 0:
        return False
    # hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(str(userdata["password"]).encode('utf8'), salt)
    userdata["password"] = hashed.decode('utf8')
    # store user
    result = users.insert(userdata)
    return result


def create_collections(db):
    """creates all collections needed for ConDIDI, i.e. the user collection and the event collection
       db: database connection"""
    # we use automatically created keys that are int and increment automatically.
    # maybe later add schema validation
    users = db.create_collection("users", key_generator="autoincrement")
    # we will mostly search for emails, so lets make an index for it.
    # ArangoDB is supposed to automatically use the index for faster search if it exists.
    users.add_hash_index(fields=["email"], unique=True)
    # noinspection PyUnusedLocal
    events = db.create_collection("events", key_generator="autoincrement")
    # ArangoDB uses _id and _key for every document as unique identifiers. _id  = collection_name/_key. So
    # _key is our user_id and event_id for later use
    return True


def create_database(sys_db, dbname="condidi"):
    """creates the database for condidi"""
    # Create a new database named "test".
    sys_db.create_database(dbname)
    # TODO: also use specific user for access
    return True


def check_pass(db, password, user_email=None, userid=None):
    """checks the password of the user given by mail or internal id, returns True if password correct, false if not"""
    users = db.collection("users")
    if user_email:
        result = users.find({'email': user_email}, skip=0, limit=10)
    elif userid:
        result = users.find({'_key': userid}, skip=0, limit=10)
    else:
        # neither email nor id given
        return False
    if result.count() == 0:
        # user not found
        return False
    user_hash = result.batch()[0]["password"]
    if bcrypt.checkpw(password.encode('utf8'), user_hash.encode('utf8')):
        # password correct
        return True
    else:
        return False


class TestDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # start docker databases
        print("start docker")
        #subprocess.run(["docker-compose", "-f", "docker-compose-development.yml", "up", "-d"], cwd="..", timeout=20,
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
        #subprocess.run(["docker-compose", "-f", "docker-compose-development.yml", "down"], cwd="..")
        subprocess.run(["docker", "stop", "arangotest"])

    def test_manage_database(self):
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
        self.assertFalse(create_user(db, userdata))
        print("check correct password")
        self.assertTrue(check_pass(db, password="test123", user_email="test@condidi.tib.eu"))
        print("check wrong password")
        self.assertFalse(check_pass(db, password="false", user_email="test@condidi.tib.eu"))
        print("check wrong password call")
        self.assertFalse(check_pass(db, password="false"))
        print("delete test database")
        self.assertTrue(sys_db.delete_database('test'))
        # close sessions
        client.close()


if __name__ == '__main__':
    # do tests
    unittest.main()
