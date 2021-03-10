from gevent import monkey

monkey.patch_all()
from bottle import route, run, template, request, response, post, get, hook
import condidi_db
import os
import json
from arango import ArangoClient
import redis
import time
import condidi_sessiondb


# all routes will be api based I guess


# NodeJS CORS compatibility
@route('/<:re:.*>', method='OPTIONS')
def enable_cors_generic_route():
    """
    This route takes priority over all others. So any request with an OPTIONS
    method will be handled by this function.
    See: https://github.com/bottlepy/bottle/issues/402
    NOTE: This means we won't 404 any invalid path that is an OPTIONS request.
    """
    add_cors_headers()


@hook('after_request')
def enable_cors_after_request_hook():
    """
    This executes after every route. We use it to attach CORS headers when
    applicable.
    """
    add_cors_headers()


def add_cors_headers():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'


# end CORS compatibility snippet


@route('/')
def index():
    name = 'you'
    return template('<b>Hello {{name}}</b>!', name=name)


@post('/api/create_user')
def create_user():
    """
    gets json object with user data via PUT request. checks if user exist,
    if not creates user and returns true. If yes returns false.
    :return: json dict with keys "success" and "error"
    """
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
    response.content_type = 'application/json'
    return json.dumps(result)


@post('/api/login_password')
def login_password():
    data = request.json
    # we need both email and password in the request, else fail.
    if "email" not in data:
        result = {"success": "no", "error": "email missing"}
    elif "password" not in data:
        result = {"success": "no", "error": "password missing"}
    else:
        # ok, now check password
        check, userid = condidi_db.check_pass(db, password=data["password"], user_email=data["email"])
        if check:
            token = condidi_sessiondb.start_session(db=redisdb, userid=userid)
            result = {"success": "yes", "error": "", "token": token}
        else:
            # password failed
            result = {"success": "no", "error": "wrong password"}
    response.content_type = 'application/json'
    return json.dumps(result)


@post('/api/logout')
def logout():
    data = request.json
    response.content_type = 'application/json'
    # we need a session token to log out
    if "token" not in data:
        result = {"success": "no", "error": "session token missing"}
    else:
        try:
            flag, dbreturn = condidi_sessiondb.close_session(db=redisdb, session_token=data["token"])
        except Exception as e:
            print("warning, got execption while trying to close session:", e)
            result = {"success": "no", "error": "DB error"}
            return json.dumps(result)
        if flag:
            result = {"success": "yes", "error": ""}
        else:
            # no such session
            result = {"success": "yes", "error": "no such session"}
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
    redisdb = redis.Redis(host=redishost, port=6379)

    if DEVELOPMENT == "True":
        # start single thread server with only localhost access, easier for debugging
        print("development mode")
        run(host='127.0.0.1', port=8080)
    else:
        # start gevent server based on greenlets with access from anywhere.
        print("deployment mode")
        run(host='0.0.0.0', port=8080, server='gevent')
    client.close()
