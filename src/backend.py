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
import asyncio
import websockets
import configparser
import jolocom_backend
import qrcode


# TODO at the moment participants are independen of events. this needs more thinking.
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

# jolocom deep link
def make_jolocom_deeplink(message):
    if not isinstance(message,str):
        message = json.dumps(message)
    result = "jolocomwallet://consent/%s" % message
    return result

def generate_qr(data):
    filename = "site.png"
    # generate qr code
    img = qrcode.make(data)
    # save img to a file
    img.save(filename)
    return True

# accept data as json or data dict
def get_data():
    if request.json:
        print("Request is json")
        return request.json
    else:
        # its a form dict, we need to unpack
        print("Request is form")
        result = dict()
        for key in request.POST.dict:
            result[key] = request.POST.dict[key][0]
        return result


def clean_event_data(eventlist):
    """
    Will remove arangoDB internal keys from lists of events in place
    :param eventlist:
    :return:
    """
    if len(eventlist)>0:
        for mydict in eventlist:
            mydict["eventid"] = mydict["_key"]
            mydict.pop("_key")
            mydict.pop("_id")
            mydict.pop("_rev")


def clean_participant_data(participantlist):
    """
    Will remove arangoDB internal keys from list in place
    :param eventlist:
    :return:
    """
    if not isinstance(participantlist, list):
        participantlist = [participantlist]
    if len(participantlist) > 0:
        for mydict in participantlist:
            mydict["participantid"] = mydict["_key"]
            mydict.pop("_key")
            mydict.pop("_id")
            mydict.pop("_rev")


def check_input_data(data, required_fields):
    for item in required_fields:
        if item not in data:
            message = {"success": "no", "error": "%s missing" % item}
            return False, message
    return True, None


async def talk_to_jolocom(message):
    uri = "ws://localhost:4040"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps(message))
        ssiresponse = await ws.recv()
    return ssiresponse


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
    data = get_data()
    response.content_type = 'application/json'
    # check data structure.
    passed, message = check_input_data(data, ["email", "name", "password"])
    if not passed:
        result = message
    else:
        status, newuser = condidi_db.create_user(db=db, userdata=data)
        if not status:
            result = {"success": "no", "error": "email exists"}
        else:
            result = {"success": "yes", "error": ""}
    return json.dumps(result)


@post('/api/create_wallet_user')
def create_wallet_user():
    """
    gets json object with user data via PUT request. checks if user exist,
    if not creates user and returns true. If yes returns false.
    :return: json dict with keys "success" and "error"
    """
    data = get_data()
    if "password" in data:
        data.pop["password"]
    response.content_type = 'application/json'
    # check data structure.
    passed, message = check_input_data(data, ["email", "name"])
    if not passed:
        result = message
        return json.dumps(result)
    # start wallet communication
    # TODO: reserve the userid. Maybe we need to switch to random ids.
    claims = {"Name": data["name"], "email": data["email"]}
    print(CALLBACK_URL)
    myrequest = jolocom_backend.InitiateCredentialOffer(callbackurl=CALLBACK_URL,
                                                        credentialtype="ConDIDIUser",
                                                        claimtype="ConDIDIUser", claims=claims)
    print(myrequest)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    message = json.loads(loop.run_until_complete(talk_to_jolocom(myrequest)))
    loop.close()
    print(message)
    result = {"success": "yes", "error": "", "interactionToken": message["result"]["interactionToken"]}
    return json.dumps(result)



@post('/api/login_password')
def login_password():
    data = request.json
    # we need both email and password in the request, else fail.
    passed, message = check_input_data(data, ["email", "password"])
    if not passed:
        result = message
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


@post('/api/add_event')
def add_event():
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    passed, message = check_input_data(data, ["token", "eventdict"])
    if not passed:
        return message
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, data["token"])
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # token valid, and we have a userid
    # set organiser id to userid
    eventdict = data["eventdict"]
    eventdict["organiser userid"] = userid
    # add event to database. Bad fieldnames will automatically removed
    status, eventdata = condidi_db.create_event(db=db, neweventdata=eventdict)
    clean_event_data([eventdata])
    if status:
        result = {"success": "yes", "eventdict": eventdata}
    else:
        result = {"success": "no", "error": eventdata}
    return json.dumps(result)


@post('/api/list_my_events')
def list_my_events():
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    if "token" not in data:
        result = {"success": "no", "error": "web session token missing"}
        return result
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, data["token"])
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # token valid, and we have a userid
    # set organiser id to userid
    matchdict = dict()
    matchdict["organiser userid"] = userid
    # add event to database. Bad fieldnames will automatically removed
    eventdata = condidi_db.find_events(db=db, matchdict=matchdict)
    clean_event_data(eventdata)
    print(eventdata)
    result = {"success": "yes", "eventlist": eventdata}
    return json.dumps(result)


@post('/api/list_participants')
def list_participants():
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    passed, message = check_input_data(data, ["token", "eventid"])
    if not passed:
        result = message
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, data["token"])
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # token valid, and we have an eventid
    matchdict = dict()
    eventid = data["eventid"]
    # get event data
    eventdict = condidi_db.get_event(db, eventid)
    organiserid = eventdict["organiser userid"]
    if not userid == organiserid:
        result = {"success": "no", "error": "you are not the organiser of this event"}
        return result
    # add event to database. Bad fieldnames will automatically removed
    participants = condidi_db.list_participants(db=db, eventid=eventid)
    clean_participant_data(participants)
    result = {"success": "yes", "participants": participants}
    return json.dumps(result)


@post('/api/add_participant')
def add_participant():
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    passed, message = check_input_data(data, ["token", "participantdict"])
    if not passed:
        return message
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, data["token"])
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # add participant
    participantdict = data["participantdict"]
    result = condidi_db.create_participant(db, participantdict)
    participantid = result["_key"]
    result = {"success": "yes", "error": "", "participantid": participantid}
    # if we have an eventid, also add participant to event
    if "eventid" in data:
        if data["eventid"]:
            # first check if the user is the event owner
            # get event data
            eventdict = condidi_db.get_event(db, data["eventid"])
            organiserid = eventdict["organiser userid"]
            if not userid == organiserid:
                result = {"success": "no", "error": "you are not the organiser of this event", "participantid": participantid}
                return result
            status, listdata = condidi_db.add_participant_to_event(db, participantid, data["eventid"])
            if not status:
                result = {"success": "no", "error": "could not add participant to event", "participantid": participantid}
    return result

@post('/api/update_participant')
def update_participant():
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    passed, message = check_input_data(data, ["token", "participantdict", "participantid"])
    if not passed:
        return message
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, data["token"])
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # update participant
    participantdict = data["participantdict"]
    participantdict["participantid"] = data["participantid"]
    status, result = condidi_db.update_participant(db, participantdict)
    if not status:
        result = {"success": "no", "error": result}
        return result
    clean_participant_data(result)
    result = {"success": "yes", "error": ""}
    return result

@post('/api/remove_participant')
def remove_participant():
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    passed, message = check_input_data(data, ["token", "eventid", "participantid"])
    if not passed:
        return message
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, data["token"])
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # first check if the user is the event owner
    # get event data
    eventdict = condidi_db.get_event(db, data["eventid"])
    organiserid = eventdict["organiser userid"]
    if not userid == organiserid:
        result = {"success": "no", "error": "you are not the organiser of this event"}
        return result
    status, listdata = condidi_db.remove_participant_from_event(db, data["participantid"], data["eventid"])
    if not status:
        result = {"success": "no", "error": "could not remove participant from event"}
    result = {"success": "yes", "error": ""}
    return result




@post('/api/wallet')
def wallet_callback():
    data = request.json
    response.content_type = 'application/json'
    # send on to jolocom sdk, await response
    print("from wallet: ",data)
    if "token" in data:
        myrequest = jolocom_backend.ProcessInteractionToken(token=data['token'])
        print("to jolocom: ", myrequest)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        message = loop.run_until_complete(talk_to_jolocom(myrequest))
        loop.close()
        print("from jolocom: ", message)
    else:
        response.status = 200
        return ""
    ssiresponse = json.loads(message)
    if "token" in ssiresponse:
        response.status = 200
        return json.dumps(ssiresponse)
    else:
        response.status = 200
        return ""


if __name__ == '__main__':
    # load config
    if os.path.exists("config.ini"):
        config = configparser.ConfigParser()
        config.read('config.ini')
        CALLBACK_URL = config["network"]["callback_url"]
        print("Callback url: -%s-" %CALLBACK_URL)
    else:
        print("Warning! config.ini missing. Wallet connection will not work!")
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
        run(host='0.0.0.0', port=8080)
    else:
        # start gevent server based on greenlets with access from anywhere.
        print("deployment mode")
        run(host='0.0.0.0', port=8080, server='gevent')
    client.close()
