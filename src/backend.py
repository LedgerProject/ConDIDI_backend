from gevent import monkey  # comment out for debugging

monkey.patch_all()  # comment out for debugging
from bottle import route, run, template, request, response, post, hook  # ,get
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
import datetime
import tempfile
import hashlib
import condidi_email


# TODO at the moment participants are independent of events. this needs more thinking.
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
    return None

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
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Access-Control-Allow-Headers, Origin, X-Requested-With, Authorization'


# end CORS compatibility snippet

# jolocom deep link
def make_jolocom_deeplink(message):
    if not isinstance(message, str):
        message = json.dumps(message)
    result = "jolocomwallet://consent/%s" % message
    return result


def generate_qr(data, filename="qrtest.png"):
    # generate qr code
    img = qrcode.make(data)
    # save img to a file
    img.save(filename)
    return True


# accept data as json or data dict
def get_data():
    if request.json:
        if DEVELOPMENT:
            print("Request is json")
        return request.json
    else:
        # its a form dict, we need to unpack
        if DEVELOPMENT:
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
    if not isinstance(eventlist, list):
        eventlist = [eventlist]
    if len(eventlist) > 0:
        for mydict in eventlist:
            mydict["eventid"] = mydict["_key"]
            mydict.pop("_key")
            mydict.pop("_id")
            mydict.pop("_rev")
    return eventlist


def clean_participant_data(participantlist):
    """
    Will remove arangoDB internal keys from list in place
    :param:
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
    return participantlist

def clean_user_data(userlist):
    """
    Will remove arangoDB internal keys from list in place
    :param:
    :return:
    """
    if not isinstance(userlist, list):
        userlist = [userlist]
    if len(userlist) > 0:
        for mydict in userlist:
            mydict["userid"] = mydict["_key"]
            mydict.pop("_key")
            mydict.pop("_id")
            mydict.pop("_rev")
            mydict.pop("password")
    return userlist

def check_input_data(data, required_fields):
    """
    Tool to sanitize input json.
    :param data: json to sanitize
    :param required_fields: list of keys that must be in json
    :return: True,none or False, errormessage as dict
    """
    for item in required_fields:
        if item not in data:
            message = {"success": "no", "error": "%s missing" % item}
            return False, message
    return True, None


def check_for_token(data):
    """checks request for authorization header. if not, check data for token. returns token or None"""
    token = None
    try:
        token = request.headers['Authorization']
    except KeyError:
        if data:
            try:
                if "token" in data:
                    token = data["token"]
            except KeyError:
                pass
    return token

def request_proof_of_attendance(eventid, participantid):
    """
    Starts a authorization flow with the users wallet by sending an email asking for proof of attendance
    :param eventid: ID of event
    :param participantid: ID of participant
    :return: True
    """
    participantdict = condidi_db.get_participant(db=db, participantid=participantid)
    eventdict = condidi_db.get_event(db=db, eventid=eventid)
    description = "Please confirm that you participated in the event: %s on %s" %(eventdict["name"], eventdict["date"])
    myrequest = jolocom_backend.AuthenticationFlow(callbackurl=CALLBACK_URL, description=description)
    #print("request for PoA:", myrequest)
    # do the websocket dance
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    message = json.loads(loop.run_until_complete(talk_to_jolocom(myrequest)))
    loop.close()
    #print("Jolocom SDK response:", message)
    if DEVELOPMENT:
        print(message)
    # check for interaction id
    if not myrequest["id"] == message["id"]:
        result = {"success": "no", "error": "internal ID mismatch"}
        return False
    # just for testing
    if DEVELOPMENT:
        generate_qr(message["result"]["interactionToken"])
    # save interaction data so we don't loose the information
    interactiondict = {'type': 'proof_of_attendance', "eventid": eventid, "participantid": participantid}
    condidi_db.add_interaction(db, interactionid=message["result"]["interactionId"], interactiondict=interactiondict)
    # mark ticket as issued
    status, participant = condidi_db.update_participant(db, {"participantid": interactiondict["participantid"],
                                                             "participation": "signature requested"})
    emailmsg = condidi_email.MsgPoA(firstname=participantdict["first_name"], lastname=participantdict["last_name"],
                                           event=eventdict["name"], webtoken=message["result"]["interactionToken"])
    try:
        # TODO put this into a thread.
        # create qrcode
        qrfilename = os.path.join(TEMPDIR, hashlib.blake2b(message["result"]["interactionToken"].encode('utf-8'),
                                                         digest_size=10).hexdigest())
        generate_qr(message["result"]["interactionToken"], filename=qrfilename)
        condidi_email.send_email(myemail=SMTP_USER, mypass=SMTP_PASSWORD, mailserver=SMTP_SERVER,
                             port=SMTP_PORT, message=emailmsg, email=participantdict["email"], qrcodefile=qrfilename)
        # delete file
        os.remove(qrfilename)
    except Exception as e:
        print("could not send email: %s" % e)
    return True


async def talk_to_jolocom(message):
    """
    helper routine to communicate with the jolocom service via websockets
    :param message: message to send
    :return: ssiresponse
    """
    print("talk to jolocom sdk:\n", message)
    uri = "ws://" + JOLOCOM_URL
    async with websockets.connect(uri, timeout=10) as ws:
        await ws.send(json.dumps(message))
        ssiresponse = await asyncio.wait_for(ws.recv(), timeout=10)  # added timeout
    print("received response from J SDK: \n", ssiresponse)
    return ssiresponse


@route('/')
def index():
    """
    fun
    :return:
    """
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
    # clean database specific keys
    for key in data:
        if key[0] == "_":
            data.pop[key]
    passed, message = check_input_data(data, ["email", "password"])
    if not passed:
        result = message
    else:
        status, newuser = condidi_db.create_user(db=db, userdata=data)
        if not status:
            result = {"success": "no", "error": "email exists"}
        else:
            # get data from new user
            userid = newuser["_key"]
            userdata = condidi_db.get_user(db=db, userid=userid)
            userdata = clean_user_data(userdata)
            result = {"success": "yes", "error": "", "userdict": userdata[0]}
    return json.dumps(result)


@post('/api/create_wallet_user')
def create_wallet_user():
    """
    gets json object with user data via PUT request. checks if user exist,
    if not creates user and returns true. If yes returns false.
    :return: json dict with keys "success" and "error"
    """
    response.content_type = 'application/json'
    data = get_data()
    if "password" in data:
        data.pop("password")
    # check data structure.
    # clean database specific keys
    for key in data:
        if key[0] == "_":
            data.pop[key]
    passed, message = check_input_data(data, ["email"])
    if not passed:
        result = message
        return json.dumps(result)
    # start wallet communication
    # we won't create the user till we have the ok from the wallet. This way the user can try multiple times
    # status, newuser = condidi_db.create_user(db=db, userdata=data)
    # if not status:
    #     result = {"success": "no", "error": "could not store user"}
    #     return json.dumps(result)
    # userid = newuser["_key"]
    # if DEVELOPMENT:
    #     print(userid)
    claims = {"Name": data["first_name"] +" "+ data["last_name"], "email": data["email"]}
    if DEVELOPMENT:
        print(CALLBACK_URL)
    # request token for wallet from jolocom
    myrequest = jolocom_backend.InitiateCredentialOffer(callbackurl=CALLBACK_URL,
                                                        credentialtype="ProofOfEventOrganizerCredential",
                                                        claimtype="ProofOfEventOrganizerCredential", claims=claims)
    # do the websocket dance
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    message = json.loads(loop.run_until_complete(talk_to_jolocom(myrequest)))
    loop.close()
    # message should have the interaction Token
    # message should be of format {'jsonrpc': '2.0', 'id': myrequest["id"],
    #                               'result': {'interactionId': newID, 'interactionToken': TokenforQRcode/deeplink}}
    # now we should add this interaction token to some store so that when the wallet and
    # jolocom confirm all, we can activate the user
    if DEVELOPMENT:
        print(message)
    # check for interaction id
    if not myrequest["id"] == message["id"]:
        result = {"success": "no", "error": "internal ID mismatch"}
        return json.dumps(result)
    # just for testing
    if DEVELOPMENT:
        generate_qr(message["result"]["interactionToken"])
    # save interaction data so we don't loose the information
    interactiondict = {'type': 'create_wallet_user', 'first_name': data["first_name"], "last_name": data["last_name"], 'email': data['email']}
    condidi_db.add_interaction(db, interactionid=message["result"]["interactionId"], interactiondict=interactiondict)
    result = {"success": "yes", "error": "", "interactionToken": message["result"]["interactionToken"]}
    if DEVELOPMENT:
        print(result)
    return json.dumps(result)


@post('/api/get_user_profile')
def get_user_profile():
    """
    returns the profile of the user (identified by the session token)
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, token)
    #print(status)
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # token valid, and we have a userid
    # find user info with userid
    matchdict = dict()
    matchdict["_key"] = userid
    # add event to database. Bad fieldnames will automatically removed
    status, userdata = condidi_db.find_user(db=db, matchdict=matchdict)
    #print(userdata)
    userdata = clean_user_data(userdata)
    #print(userdata)
    result = {"success": "yes", "userdict": userdata[0]}
    return json.dumps(result)


@post('/api/login_password')
def login_password():
    """
    login via email and password
    :return: success json with session token, or error json
    """
    data = request.json
    #print(data)
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


@post('/api/login_wallet')
def login_wallet():
    """
    login with jolocom wallet. creates session token and the QRcode for login
    :return:
    """

    # no data needed
    response.content_type = 'application/json'
    # ask for credential
    myrequest = jolocom_backend.InitiateCredentialRequest(callbackurl=CALLBACK_URL,
                                                          credentialtype="ProofOfEventOrganizerCredential",
                                                          issuer=SSI_DID)
    # do the websocket dance
    if DEVELOPMENT:
        print(myrequest)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    message = json.loads(loop.run_until_complete(talk_to_jolocom(myrequest)))
    loop.close()
    # message should have the interaction Token
    # message should be of format {'jsonrpc': '2.0', 'id': myrequest["id"],
    #                               'result': {'interactionId': newID, 'interactionToken': TokenforQRcode/deeplink}}
    # now we should add this interaction token to some store so that when the wallet and
    # jolocom confirm all, we can activate the user
    if DEVELOPMENT:
        print(message)
    # check for interaction id
    if not myrequest["id"] == message["id"]:
        result = {"success": "no", "error": "internal ID mismatch"}
        return json.dumps(result)
    # just for testing
    if DEVELOPMENT:
        generate_qr(message["result"]["interactionToken"])
    # save interaction data so we don't loose the information
    interactiondict = {'type': 'login_wallet'}
    condidi_db.add_interaction(db, interactionid=message["result"]["interactionId"], interactiondict=interactiondict)
    # create a preliminary wallet session that needs to be activated
    session_key, interactionid = condidi_sessiondb.start_wallet_session(db=redisdb,
                                                                        ssi_token=message["result"]["interactionId"])
    result = {"success": "yes", "error": "", "interactionToken": message["result"]["interactionToken"],
              "token": session_key}
    return json.dumps(result)


@post('/api/logout')
def logout():
    """
    log out. deletes session token from the database
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    # we need a session token to log out
    token = check_for_token(data)
    if not token:
        result = {"success": "no", "error": "session token missing"}
    else:
        try:
            flag, dbreturn = condidi_sessiondb.close_session(db=redisdb, session_token=token)
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
    """
    add an event to the database
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    passed, message = check_input_data(data, ["eventdict"])
    if not passed:
        return message
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, token)
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # token valid, and we have a userid
    # set organiser id to userid
    eventdict = data["eventdict"]
    eventdict["organiser_userid"] = userid
    # add event to database. Bad fieldnames will automatically removed
    status, eventdata = condidi_db.create_event(db=db, neweventdata=eventdict)
    if not status:
        result = {"success": "no", "error": "add event in db failed"}
        return json.dumps(result)
    eventdata = condidi_db.get_event(db=db, eventid=eventdata["_key"])
    if not eventdata:
        result = {"success": "yes", "error": "eventid %s not found" % data["eventid"]}
    else:
        eventdata = clean_event_data(eventdata)
        # print("eventdata:", eventdata)
        result = {"success": "yes", "eventdict": eventdata[0]}
    return json.dumps(result)


@post('/api/list_my_events')
def list_my_events():
    """
    returns a list of all the events the user (identified by the session token) owns
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, token)
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # token valid, and we have a userid
    # set organiser id to userid
    matchdict = dict()
    matchdict["organiser_userid"] = userid
    # add event to database. Bad fieldnames will automatically removed
    eventdata = condidi_db.find_events(db=db, matchdict=matchdict)
    clean_event_data(eventdata)
    #print(eventdata)
    result = {"success": "yes", "eventlist": eventdata}
    return json.dumps(result)


@post('/api/get_event')
def get_event():
    """
    return data of a specific event
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    passed, message = check_input_data(data, ["eventid"])
    if not passed:
        result = message
        return result
    # we need a valid token for this
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, token)
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # token valid, and we have a userid
    # todo: check if user is event organiser
    eventdata = condidi_db.get_event(db=db, eventid=data["eventid"])
    if not eventdata:
        result = {"success": "yes", "error": "eventid %s not found" % data["eventid"]}
    else:
        eventdata = clean_event_data(eventdata)
        #print("eventdata:", eventdata)
        result = {"success": "yes", "eventdict": eventdata[0]}
    return json.dumps(result)


@post('/api/delete_event')
def delete_event():
    """
    delets an event if there are no participants
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # possible event data fields see condidi_db.py Event class
    passed, message = check_input_data(data, ["eventid"])
    if not passed:
        result = message
        return result
    # we need a valid token for this
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, token)
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # token valid, and we have a userid
    eventid = data["eventid"]
    # set organiser id to userid
    matchdict = dict()
    matchdict["organiser_userid"] = userid
    # add event to database. Bad fieldnames will automatically removed
    eventdata = condidi_db.find_events(db=db, matchdict=matchdict)
    # check if owner of event
    #print("eventdata", eventdata)
    myevents = [event["_key"] for event in eventdata]
    if eventid not in myevents:
        result = {"success": "no", "error": "event does not belong to user"}
        return result
    # all fine, we can delete event
    # TODO check if all participants are removed first
    status, result = condidi_db.delete_event(db=db, eventid=eventid)
    if status:
        result = {"success": "yes"}
    else:
        result = {"success": "no", "error": "event could not be removed from db"}
    return json.dumps(result)

@post('/api/list_participants')
def list_participants():
    """
    list all participants of an event. Event must be owend by user
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    passed, message = check_input_data(data, ["eventid"])
    if not passed:
        result = message
        return result
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, token)
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # token valid, and we have an eventid
    # matchdict = dict()
    eventid = data["eventid"]
    # get event data
    eventdict = condidi_db.get_event(db, eventid)
    organiserid = eventdict["organiser_userid"]
    if not userid == organiserid:
        result = {"success": "no", "error": "you are not the organiser of this event"}
        return result
    # add event to database. Bad fieldnames will automatically removed
    participants = condidi_db.list_participants(db=db, eventid=eventid)
    participants = clean_participant_data(participants)
    result = {"success": "yes", "participants": participants}
    if DEVELOPMENT:
        print(result)
    return json.dumps(result)


@post('/api/add_participant')
def add_participant():
    """
    add an participant to an event
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    passed, message = check_input_data(data, ["participantdict"])
    if not passed:
        return message
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, token)
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # add participant
    participantdict = data["participantdict"]
    result = condidi_db.create_participant(db, participantdict)
    participantid = result["_key"]
    # if we have an eventid, also add participant to event
    if "eventid" in data:
        if data["eventid"]:
            # first check if the user is the event owner
            # get event data
            eventdict = condidi_db.get_event(db, data["eventid"])
            organiserid = eventdict["organiser_userid"]
            if not userid == organiserid:
                result = {"success": "no", "error": "you are not the organiser of this event",
                          "participantid": participantid}
                return result
            status, listdata = condidi_db.add_participant_to_event(db, participantid, data["eventid"])
            if not status:
                result = {"success": "no", "error": "could not add participant to event",
                          "participantid": participantid}
    # get participant data so we can return it
    result = condidi_db.get_participant(db, participantid)
    participantlist = clean_participant_data(result)
    result = {"success": "yes", "error": "", "participantdict": participantlist[0], "participantid": participantid}
    # TODO: remove after demo
    # immediately issue ticket
    request.json["participantid"]=participantid
    issue_ticket()
    # TODO
    return result


@post('/api/update_participant')
def update_participant():
    """
    update participant data
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    passed, message = check_input_data(data, ["participantdict", "participantid"])
    if not passed:
        return message
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, token)
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # update participant
    participantdict = data["participantdict"]
    participantdict["participantid"] = data["participantid"]
    status, result = condidi_db.update_participant(db, participantdict)
    if not status:
        result = {"success": "no", "error": "update failed"}
        return result
    # get participant data so we can return it
    result = condidi_db.get_participant(db, result["_key"])
    participantlist = clean_participant_data(result)
    result = {"success": "yes", "error": "", "participantdict": participantlist[0]}
    return result


@post('/api/remove_participant')
def remove_participant():
    """
    remove participant from event
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    # we need a valid token for this
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    passed, message = check_input_data(data, ["eventid", "participantid"])
    if not passed:
        return message
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, token)
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # first check if the user is the event owner
    # get event data
    eventdict = condidi_db.get_event(db, data["eventid"])
    organiserid = eventdict["organiser_userid"]
    if not userid == organiserid:
        result = {"success": "no", "error": "you are not the organiser of this event"}
        return result
    status, listdata = condidi_db.remove_participant_from_event(db, data["participantid"], data["eventid"])
    if not status:
        result = {"success": "no", "error": "could not remove participant from event"}
        return result
    result = {"success": "yes", "error": ""}
    return result


@post('/api/issue_ticket')
def issue_ticket():
    """
    issue ticket to attendent. for now it returns the interaction-token to generate the qr code. at a later
    stage it will instead send the qr code and a deep link via email to attendend
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    passed, message = check_input_data(data, ["eventid", "participantid"])
    if not passed:
        return message
    eventid = data["eventid"]
    participantid = data["participantid"]
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, token)
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # first check if the user is the event owner
    # get event data
    eventdict = condidi_db.get_event(db, eventid)
    if not eventdict:
        result = {"success": "no", "error": "no such event"}
        return result
    organiserid = eventdict["organiser_userid"]
    if not userid == organiserid:
        result = {"success": "no", "error": "you are not the organiser of this event"}
        return result
    participantdict = condidi_db.get_participant(db, participantid)
    if not participantdict:
        result = {"success": "no", "error": "no such participant"}
        return result
    participantemail = participantdict["email"]
    # get ticket data
    claims = dict()
    eventdict = condidi_db.get_event(db, data["eventid"])
    claims["name"] = eventdict["name"]
    claims["presenter"] = eventdict["presenter"]
    claims["about"] = eventdict["subject"]
    claims["time"] = eventdict["date"]
    claims["location"] = eventdict["address"]
    #          "name": "Event Name", "presenter": "John Example", "about": "A event discussing topic X",
    #          "time": "2021-03-15T13:14:03.836",
    #      "location": "Conference center X"
    print("generating ticket send request...")
    myrequest = jolocom_backend.InitiateCredentialOffer(callbackurl=CALLBACK_URL,
                                                        credentialtype="EventInvitationCredential",
                                                        claimtype="EventInvitationCredential", claims=claims)
    # do the websocket dance
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    message = json.loads(loop.run_until_complete(talk_to_jolocom(myrequest)))
    loop.close()
    # message should have the interaction Token
    # message should be of format {'jsonrpc': '2.0', 'id': myrequest["id"],
    #                               'result': {'interactionId': newID, 'interactionToken': TokenforQRcode/deeplink}}
    # now we should add this interaction token to some store so that when the wallet and
    # jolocom confirm all, we can activate the user
    if DEVELOPMENT:
        print(message)
    # check for interaction id
    if not myrequest["id"] == message["id"]:
        result = {"success": "no", "error": "internal ID mismatch"}
        return json.dumps(result)
    # just for testing
    if DEVELOPMENT:
        generate_qr(message["result"]["interactionToken"])
    # save interaction data so we don't loose the information
    interactiondict = {'type': 'issue_ticket', "eventid": eventid, "participantid": participantid}
    condidi_db.add_interaction(db, interactionid=message["result"]["interactionId"], interactiondict=interactiondict)
    # mark ticket as issued
    status, participant = condidi_db.update_participant(db, {"participantid": interactiondict["participantid"],
                                                             "ticket_issued": datetime.date.today().isoformat()})
    result = {"success": "yes", "error": "", "interactionToken": message["result"]["interactionToken"]}
    emailmsg = condidi_email.MsgTicket(firstname=participantdict["first_name"], lastname=participantdict["last_name"],
                                           event=eventdict["name"], webtoken=message["result"]["interactionToken"])
    try:
        # TODO put this into a thread.
        # create qrcode
        qrfilename = os.path.join(TEMPDIR, hashlib.blake2b(message["result"]["interactionToken"].encode('utf-8'),
                                                         digest_size=10).hexdigest())
        generate_qr(message["result"]["interactionToken"], filename=qrfilename)
        condidi_email.send_email(myemail=SMTP_USER, mypass=SMTP_PASSWORD, mailserver=SMTP_SERVER,
                             port=SMTP_PORT, message=emailmsg, email=participantdict["email"], qrcodefile=qrfilename)
        # delete file
        os.remove(qrfilename)
    except Exception as e:
        print("could not send email: %s" % e)
    print("  ")
    return json.dumps(result)


@post('/api/update_ticket')
def update_ticket():
    """
    stump. idea is that at a later stage a ticket can be updated with new information
    :return:
    """
    data = request.json
    response.content_type = 'application/json'
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    passed, message = check_input_data(data, ["ticketdict"])
    if not passed:
        return message
    # TODO jolocom interaction
    result = {"success": "yes", "error": ""}
    return result


@post('/api/get_checkin_token')
def get_checkin_token():
    """
    get a participant specific token (QRcode) to check in a participant. This should be done on site with a tablet or
    similar.
    :return: qr code interaction token
    """
    data = request.json
    response.content_type = 'application/json'
    token = check_for_token(data)
    if not token:
        return {"success": "no", "error": "session token missing"}
    passed, message = check_input_data(data, ["eventid", "participantid"])
    if not passed:
        return message
    eventid = data["eventid"]
    participantid = data["participantid"]
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, token)
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # first check if the user is the event owner
    # get event data
    eventdict = condidi_db.get_event(db, eventid)
    if not eventdict:
        result = {"success": "no", "error": "no such event"}
        return result
    organiserid = eventdict["organiser_userid"]
    if not userid == organiserid:
        result = {"success": "no", "error": "you are not the organiser of this event"}
        return result
    participantdict = condidi_db.get_participant(db, participantid)
    if not participantdict:
        result = {"success": "no", "error": "no such participant"}
        return result
    # ask for credential
    myrequest = jolocom_backend.InitiateCredentialRequest(callbackurl=CALLBACK_URL,
                                                          credentialtype="EventInvitationCredential",
                                                          issuer=SSI_DID)
    # do the websocket dance
    if DEVELOPMENT:
        print(myrequest)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    message = json.loads(loop.run_until_complete(talk_to_jolocom(myrequest)))
    loop.close()
    # message should have the interaction Token
    # message should be of format {'jsonrpc': '2.0', 'id': myrequest["id"],
    #                               'result': {'interactionId': newID, 'interactionToken': TokenforQRcode/deeplink}}
    # now we should add this interaction token to some store so that when the wallet and
    # jolocom confirm all, we can activate the user
    if DEVELOPMENT:
        print(message)
    # check for interaction id
    if not myrequest["id"] == message["id"]:
        result = {"success": "no", "error": "internal ID mismatch"}
        return json.dumps(result)
    # just for testing
    if DEVELOPMENT:
        generate_qr(message["result"]["interactionToken"])
    # save interaction data so we don't loose the information
    interactiondict = {'type': 'checkin_token', "eventid": eventid, "participantid": participantid}
    condidi_db.add_interaction(db, interactionid=message["result"]["interactionId"], interactiondict=interactiondict)
    result = {"success": "yes", "error": "", "interactionToken": message["result"]["interactionToken"]}
    return json.dumps(result)


@post('/api/wallet')
def wallet_callback():
    """
    this is called by the ssi wallet. can handle different call backs
    :return:
    """
    data = request.json
    print("\n data from wallet:\n", data)
    response.content_type = 'application/json'
    # all we get from the wallet, we send on to jolocom sdk, await response
    if DEVELOPMENT:
        print("from wallet: ", data)
    if "token" in data:
        print("\n we got a token, so we send it to jSDK.\n")
        myrequest = jolocom_backend.ProcessInteractionToken(token=data['token'])
        if DEVELOPMENT:
            print("to jolocom: ", myrequest)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        message = loop.run_until_complete(talk_to_jolocom(myrequest))
        loop.close()
        if DEVELOPMENT:
            print("from jolocom: ", message)
    else:
        # anything without a token we just acknowledge and ignore
        response.status = 404
        if DEVELOPMENT:
            print("to wallet: ")
        return ""
    ssiresponse = json.loads(message)
    # if "token" in ssiresponse:
    #     response.status = 200
    #     if DEVELOPMENT:
    #         print("to wallet: ", json.dumps(ssiresponse))
    #     return json.dumps(ssiresponse)
    if "result" not in ssiresponse:
        response.status = 404
        if DEVELOPMENT:
            print("to wallet: ")
        return ""
    # we have a result, lets see what interaction we are talking about, can be an old one
    if "interactionId" not in ssiresponse["result"]:
        # no interactionId, no way to know what to do
        response.status = 404
        if DEVELOPMENT:
            print("to wallet: ")
        return ""
    interactionid = ssiresponse["result"]["interactionId"]
    status, interactiondict = condidi_db.get_interaction(db, interactionid)
    if not status:
        # no interactionId info, no way to know what to do
        response.status = 404
        if DEVELOPMENT:
            print("to wallet: ")
        return ""
    # check if it was a signup:
    # {'type': 'create_wallet_user', 'name': data['name'], 'email': data['email']}
    if interactiondict['type'] == 'create_wallet_user':
        if ssiresponse["result"]["interactionInfo"]["completed"]:
            # all clear, get user did, create user, save credential, delete interaction
            did = ssiresponse["result"]["interactionInfo"]["state"]["subject"]
            userdict = {"first_name": interactiondict["first_name"],"last_name": interactiondict["last_name"],
                        "email": interactiondict["email"], "did": did}
            status, userdata = condidi_db.create_user(db, userdata=userdict)
            if not status:
                if DEVELOPMENT:
                    print("user creation failed")
                response.status = 409
                return ""
            # save credential for later
            for credential in ssiresponse["result"]["interactionInfo"]["state"]["issued"]:
                credentialid = credential["id"]
                status, credentildata = condidi_db.add_credential(db, credentialid=credentialid,
                                                                  credentialdict=credential)
            # right now I don't really care if the credential was saved
            # delete interaction
            status = condidi_db.delete_interaction(db, interactionid=interactionid)
            # finally send back the credential to wallet
            response.status = 200
            myresponse = {"token": ssiresponse["result"]["interactionInfo"]["interactionToken"]}
            if DEVELOPMENT:
                print("to wallet: ", json.dumps(myresponse))
            # testing
            # return None
            return json.dumps(myresponse)
    elif interactiondict['type'] == 'login_wallet':
        # login with wallet
        if ssiresponse["result"]["interactionInfo"]["completed"]:
            # all clear, get user did, create user, save credential, delete interaction
            did = ssiresponse["result"]["interactionInfo"]["state"]["subject"]
            for credential in ssiresponse["result"]["interactionInfo"]["state"]["credentials"]:
                credentialid = credential["id"]
                if "ProofOfEventOrganizerCredential" not in credential["type"]:
                    continue
                # TODO check credential["expires"]
                if "email" in credential["claim"]:
                    useremail = credential["claim"]["email"]
                    # get our user data
                    status, userdict = condidi_db.find_user(db, {"email": useremail})
                    if not status:
                        response.status = 404
                        if DEVELOPMENT:
                            print("user not found", useremail)
                        return ""
                    if did != userdict["did"]:
                        response.status = 404
                        if DEVELOPMENT:
                            print("user not found", useremail)
                        return ""
                    if credential["issuer"] != SSI_DID:
                        response.status = 404
                        if DEVELOPMENT:
                            print("wrong issuer", credential["issuer"])
                        return ""
                    # ok pretty sure it is the correct user
                    # activate session
                    condidi_sessiondb.activate_wallet_session(db=redisdb, ssi_token=interactionid,
                                                              userid=userdict["_key"])
                    response.status = 200
                    if DEVELOPMENT:
                        print("to wallet: ")
                    return ""
    elif interactiondict['type'] == 'checkin_token':
        print("it is the wallet response to checkin token")
        if ssiresponse["result"]["interactionInfo"]["completed"]:
            # all
            eventid = interactiondict["eventid"]
            participantid = interactiondict["participantid"]
            #did = ssiresponse["result"]["interactionInfo"]["state"]["subject"]
            #for credential in ssiresponse["result"]["interactionInfo"]["state"]["credentials"]:
            #    credentialid = credential["id"]
            #    # actually, there is nothing in the credential as of now that is an eventid
            #    # no point in checking anything
            # participant als anwesend markieren
            condidi_db.update_participant(db, {"participantid": participantid, "attendence_status": "attended"})
            # eventuell credential rausschicken?
            response.status = 200
            if DEVELOPMENT:
                print("to wallet: ")
            return ""
    elif interactiondict['type'] == 'issue_ticket':
        print("it is the wallet response to issue ticket")
        if ssiresponse["result"]["interactionInfo"]["completed"]:
            # save credential for later
            credentialid = None
            # get DID of the person with the ticket
            participantdid = ssiresponse["result"]["interactionInfo"]["state"]["subject"]
            #participantdict = condidi_db.get_participant(db=db, participantid=interactiondict["participantid"])
            for credential in ssiresponse["result"]["interactionInfo"]["state"]["issued"]:
                credentialid = credential["id"]
                status, credentildata = condidi_db.add_credential(db, credentialid=credentialid,
                                                                  credentialdict=credential)
            # right now I don't really care if the credential was saved
            # add ticket id
            status, participant = condidi_db.update_participant(db, {"participantid": interactiondict["participantid"],
                                                                     "ticket_id": credentialid, "did": participantdid})
            # delete interaction
            status = condidi_db.delete_interaction(db, interactionid=interactionid)
            # finally send back the credential to wallet
            response.status = 200
            myresponse = {"token": ssiresponse["result"]["interactionInfo"]["interactionToken"]}
            if DEVELOPMENT:
                print("to wallet: ", json.dumps(myresponse))
            # testing
            # send out request for proof of attendace
            # TODO: request PaA only after the event, by some way of cron job
            try:
                #print("test")
                request_proof_of_attendance(eventid=interactiondict["eventid"], participantid=interactiondict["participantid"])
            except Exception as e:
                print(e)
            # return None
            print("to wallet: ", myresponse)
            return json.dumps(myresponse)
            # return None
    elif interactiondict['type'] == 'proof_of_attendance':
        print("\n its a response to proof of attendance.")
        if ssiresponse["result"]["interactionInfo"]["completed"]:
            # save credential for later
            credentialid = None
            # get DID of the person with the ticket
            participantdid = ssiresponse["result"]["interactionInfo"]["state"]["subject"]
            credentialid = hashlib.blake2b(str(data).encode('utf-8'), digest_size=20).hexdigest()
            status, credentildata = condidi_db.add_credential(db, credentialid=credentialid,
                                                                  credentialdict=data)
            # right now I don't really care if the credential was saved
            # TODO: check that DID did not change
            status, participant = condidi_db.update_participant(db, {"participantid": interactiondict["participantid"],
                                                                     "participation": "participation signed",
                                                                     "did": participantdid, "poa_id": credentialid})
            # delete interaction
            status = condidi_db.delete_interaction(db, interactionid=interactionid)
            # finally send back the credential to wallet
            response.status = 200
            myresponse = {"token": data["token"]}
            #if DEVELOPMENT:
            print("\n sending to wallet: ", json.dumps(myresponse))
            # testing
            # return None
            #return json.dumps(myresponse)
            return None
    else:
        # unknown interaction, should not happen but what do I know
        response.status = 404
        #if DEVELOPMENT:
        print("unknown interaction from wallet")
        return ""
    response.status = 404
    if DEVELOPMENT:
        print("to wallet: ")
    return ""


if __name__ == '__main__':
    # load config
    if os.path.exists("config.ini"):
        config = configparser.ConfigParser()
        config.read('config.ini')
        CALLBACK_URL = config["network"]["callback_url"].strip('\"')
        SSI_DID = config["ssi"]["did"].strip('\"')
        print("Callback url: -%s-" % CALLBACK_URL)
        print("SSI DID: -%s-" % SSI_DID)
        try:
            SMTP_SERVER = config["mail"]["smtp_server"].strip('\"')
            SMTP_PORT = config["mail"]["smtp_port"].strip('\"')
            SMTP_USER = config["mail"]["smtp_user"].strip('\"')
            SMTP_PASSWORD = config["mail"]["smtp_password"].strip('\"')
        except KeyError as e:
            print("Error in mail part of config.ini, \nEmail sending deactivated.\n" ,e)
            SMTP_SERVER = None
            SMTP_PORT = None
            SMTP_USER = None
            SMTP_PASSWORD = None
        SSI_NAME = config["ssi"]["name"].strip('\"')
        SSI_URL = config["ssi"]["url"].strip('\"')
        SSI_DESCRIPTION = config["ssi"]["description"].strip('\"')
        SSI_IMAGE = config["ssi"]["image"].strip('\"')

    else:
        print("Warning! config.ini missing. Wallet connection will not work!")
    # start server
    if "DEVELOPMENT" in os.environ:
        if os.environ["DEVELOPMENT"].lower()=="false":
            DEVELOPMENT = False
        else:
            DEVELOPMENT = True
    else:
        DEVELOPMENT = "True"
    if DEVELOPMENT:
        print("Development mode, no gevent")
    if "JOLOCOM_URL" in os.environ:
        JOLOCOM_URL = os.environ["JOLOCOM_URL"]
    else:
        JOLOCOM_URL = "localhost:4040"
    # set description
    if "FIRSTRUN" in os.environ:
        # set ssi description
        print("FIRSTRUN active, setting up SSI ID")
        time.sleep(10)
        myrequest = jolocom_backend.UpdatePublicProfile(name=SSI_NAME, description=SSI_DESCRIPTION, image=SSI_IMAGE, url=SSI_URL)
        # do the websocket dance
        if DEVELOPMENT:
            print(myrequest)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            message = json.loads(loop.run_until_complete(talk_to_jolocom(myrequest)))
            loop.close()
        except:
            print("timeout, will ignore")
            pass
    # create tempdir
    TEMPDIR = tempfile.mkdtemp()
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
