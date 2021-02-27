from arango import ArangoClient
import unittest
import os, subprocess, time
import bcrypt


def createuser(db, userdata):
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

def createcollections(db):
    """creates all collections needed for ConDIDI, i.e. the user collection and the event collection
       db: database connection"""
    # we use automatically created keys that are int and increment automatically.
    # maybe later add schema validation
    users = db.create_collection("users", key_generator="autoincrement")
    users.add_hash_index(fields=["email"], unique=True)
    events = db.create_collection("events", key_generator="autoincrement")
    # arango uses _id and _key for every document as unique identifiers. _id  = collectionname/_key. So
    # _key is our userid and eventid
    return True

def createdatabase(sys_db, dbname="condidi"):
    """creates the database for condidi"""
    # Create a new database named "test".
    sys_db.create_database(dbname)
    # TODO: also use specific user for access
    return True

def checkpass(db, password, useremail=None, userid=None):
    """checks the password of the user given by mail or internal id, returns True if password correct, false if not"""
    users = db.collection("users")
    if useremail:
        result = users.find({'email': useremail}, skip=0, limit=10)
    elif userid:
        result = users.find({'_key': userid}, skip=0, limit=10)
    else:
        # neither email nor id given
        return False
    if result.count() == 0:
        # user not found
        return False
    userhash = result.batch()[0]["password"]
    if bcrypt.checkpw(password.encode('utf8'), userhash.encode('utf8')):
        # password correct
        return True
    else:
        return False


class TestDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        #start docker databases
        print("start docker")
        subprocess.run(["docker-compose", "-f", "docker-compose-development.yml","up", "-d"], cwd="..", timeout=20, check=True)
        # give arango some time to start up
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        #stop docker databases
        print("stop docker")
        subprocess.run(["docker-compose", "-f", "docker-compose-development.yml","down"], cwd="..")


    def test_managedatabase(self):
        client = ArangoClient(hosts="http://localhost:8529")
        sys_db = client.db("_system", username="root", password="justfortest")
        # first try to delete the test database
        sys_db.delete_database('test', ignore_missing=True)
        print("create DB")
        self.assertTrue(createdatabase(sys_db, dbname='test'))
        db = client.db("test", username="root", password="justfortest")
        # test collection creation
        print("create collections")
        self.assertTrue(createcollections(db))
        # test create user
        print("create user")
        userdata = {"name":"Testuser", "email": "test@condidi.tib.eu", "password":"test123"}
        print(createuser(db,userdata))
        print("check existing user detection")
        self.assertFalse(createuser(db,userdata))
        print("check correct password")
        self.assertTrue(checkpass(db,password="test123", useremail="test@condidi.tib.eu"))
        print("check wrong password")
        self.assertFalse(checkpass(db, password="false", useremail="test@condidi.tib.eu"))
        print("check wrong password call")
        self.assertFalse(checkpass(db, password="false"))
        print("delete test database")
        self.assertTrue(sys_db.delete_database('test'))
        # close sessions - this should be in ArangoClient but it is not
        client.close()
        #for session in client._sessions:
        #    session.close()



if __name__ == '__main__':
    # do tests
    SETUP = False
    if SETUP:
        client = ArangoClient(hosts="http://localhost:8529")
        # Connect to "_system" database as root user.
        sys_db = client.db("_system", username="root", password="justfortest")
        createdatabase(sys_db)

        db = client.db("condidi", username="root", password="justfortest")
        createcollections(db)


