from gevent import monkey
monkey.patch_all()
from bottle import route, run, template, request, response, post, get
import condidi_db
import os
import json
from arango import ArangoClient
import redis
import time
# all routes will be api based I guess


@route('/')
def index():
    name = 'you'
    return template('<b>Hello {{name}}</b>!', name=name)

@post('/api/create_user')
def create_user():
    '''gets json object with user data via PUT request. checks if user exist,
    if not creates user and returns true. If yes returns false.'''
    data = request.json
    # check data structure.
    if "email" not in data:
        result = {"success": "no", "error": "email missing"}
    elif "name" not in data:
        result = {"success": "no", "error": "name missing"}
    elif "password" not in data:
        result = {"success": "no", "error": "password missing"}
    else:
        status, newuser = condidi_db.create_user(db=db, userdata=data)
        if not status:
            result = {"success": "no", "error": "email exists"}
        else:
            result = {"success": "yes", "error": ""}
    return json.dumps(result)

if __name__ == '__main__':
    # start server
    if "DEVELOPMENT" in os.environ:
        DEVELOPMENT = os.environ["DEVELOPMENT"]
    else:
        DEVELOPMENT = "True"
    # connect to databases
    if "ARANGO_URL" in os.environ:
        arangourl = "http://" + os.environ["ARANGO_URL"]
        # also wait for db startup
        print("Condidi Backend: waiting 10s for database start...")
        time.sleep(10)
    else:
        arangourl = "http://localhost:8529"
    client = ArangoClient(hosts=arangourl)
    if "REDIS_HOST" in os.environ:
        redishost = os.environ["REDIS_HOST"]
    else:
        redishost = "127.0.0.1"
     # create database and collections - move to setup script later
    sys_db = client.db("_system", username="root", password="justfortest")
    condidi_db.create_database(sys_db, "condidi")
    db = client.db("condidi", username="root", password="justfortest")
    condidi_db.create_collections(db)
    server = redis.Redis(host=redishost, port=6379)

    if DEVELOPMENT == "True":
        # start single thread server with only localhost access, easier for debugging
        print("development mode")
        run(host='127.0.0.1', port=8080)
    else:
        # start gevent server based on greenlets with access from anywhere.
        print("deployment mode")
        run(host='0.0.0.0', port=8080, server='gevent')
    client.close()