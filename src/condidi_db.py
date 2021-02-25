from arango import ArangoClient
import unittest

def createuser(db, userdata):

    return False

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

def createuser(db, userdata):
    users = db.collection('users')
    # check if email is already in database


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


