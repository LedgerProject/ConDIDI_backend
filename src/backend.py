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
    if not isinstance(message, str):
        message = json.dumps(message)
    result = "jolocomwallet://consent/%s" % message
    return result


def generate_qr(data):
    filename = "qrtest.png"
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
    if not isinstance(eventlist, list):
        eventlist = [eventlist]
    if len(eventlist) > 0:
        for mydict in eventlist:
            mydict["eventid"] = mydict["_key"]
            mydict.pop("_key")
            mydict.pop("_id")
            mydict.pop("_rev")


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


def check_input_data(data, required_fields):
    for item in required_fields:
        if item not in data:
            message = {"success": "no", "error": "%s missing" % item}
            return False, message
    return True, None


async def talk_to_jolocom(message):
    uri = "ws://" + JOLOCOM_URL
    async with websockets.connect(uri, timeout=10) as ws:
        await ws.send(json.dumps(message))
        ssiresponse = await asyncio.wait_for(ws.recv(), timeout=10)  # added timeout
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
    response.content_type = 'application/json'
    data = get_data()
    if "password" in data:
        data.pop("password")
    # check data structure.
    passed, message = check_input_data(data, ["email", "name"])
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
    claims = {"Name": data["name"], "email": data["email"]}
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
    interactiondict = {'type': 'create_wallet_user', 'name': data['name'], 'email': data['email']}
    condidi_db.add_interaction(db, interactionid=message["result"]["interactionId"], interactiondict=interactiondict)
    result = {"success": "yes", "error": "", "interactionToken": message["result"]["interactionToken"]}
    return json.dumps(result)


@post('/api/login_password')
def login_password():
    data = request.json
    print(data)
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


@post('/api/get_event')
def get_event():
    data = request.json
    response.content_type = 'application/json'
    # possible event data fields see condidi_db.py Event class
    passed, message = check_input_data(data, ["eventid"])
    if not passed:
        result = message
        return result
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
    # todo: check if user is event organiser
    eventdata = condidi_db.get_event(db=db, eventid=data["eventid"])
    if not eventdata:
        result = {"success": "yes", "error": "eventid %s not found" % data["eventid"]}
    else:
        clean_event_data(eventdata)
        # print("eventdata:", eventdata)
        result = {"success": "yes", "eventdict": eventdata}
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
        return result
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, data["token"])
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # token valid, and we have an eventid
    # matchdict = dict()
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
                result = {"success": "no", "error": "you are not the organiser of this event",
                          "participantid": participantid}
                return result
            status, listdata = condidi_db.add_participant_to_event(db, participantid, data["eventid"])
            if not status:
                result = {"success": "no", "error": "could not add participant to event",
                          "participantid": participantid}
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
        return result
    result = {"success": "yes", "error": ""}
    return result


@post('/api/issue_ticket')
def issue_ticket():
    data = request.json
    response.content_type = 'application/json'
    passed, message = check_input_data(data, ["token", "eventid", "participantid"])
    if not passed:
        return message
    eventid = data["eventid"]
    participantid = data["participantid"]
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, data["token"])
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # first check if the user is the event owner
    # get event data
    eventdict = condidi_db.get_event(db, eventid)
    if not eventdict:
        result = {"success": "no", "error": "no such event"}
        return result
    organiserid = eventdict["organiser userid"]
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
    #          "name": "Event Name", "presenter": "John Example", "about": "A event discussing topic X", "time": "2021-03-15T13:14:03.836",
    #      "location": "Conference center X"
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
                                                             "ticked issued": datetime.date.today().isoformat()})
    result = {"success": "yes", "error": "", "interactionToken": message["result"]["interactionToken"]}
    # todo email versenden an participantemail
    return json.dumps(result)


@post('/api/update_ticket')
def update_ticket():
    data = request.json
    response.content_type = 'application/json'
    passed, message = check_input_data(data, ["token", "ticketdict"])
    if not passed:
        return message
    # TODO jolocom interaction
    result = {"success": "yes", "error": ""}
    return result


@post('/api/get_checkin_token')
def get_checkin_token():
    data = request.json
    response.content_type = 'application/json'
    passed, message = check_input_data(data, ["token", "eventid", "participantid"])
    if not passed:
        return message
    eventid = data["eventid"]
    participantid = data["participantid"]
    # check session
    status, userid = condidi_sessiondb.check_session(redisdb, data["token"])
    if not status:
        result = {"success": "no", "error": "no such session"}
        return result
    # first check if the user is the event owner
    # get event data
    eventdict = condidi_db.get_event(db, eventid)
    if not eventdict:
        result = {"success": "no", "error": "no such event"}
        return result
    organiserid = eventdict["organiser userid"]
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
    data = request.json
    response.content_type = 'application/json'
    # all we get from the wallet, we send on to jolocom sdk, await response
    if DEVELOPMENT:
        print("from wallet: ", data)
    if "token" in data:
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
            userdict = {"name": interactiondict["name"], "email": interactiondict["email"], "did": did}
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
            condidi_db.update_participant(db, {"participantid": participantid, "attendence status": "attended"})
            # eventuell credential rausschicken?
            response.status = 200
            if DEVELOPMENT:
                print("to wallet: ")
            return ""
    elif interactiondict['type'] == 'issue_ticket':
        if ssiresponse["result"]["interactionInfo"]["completed"]:
            # save credential for later
            for credential in ssiresponse["result"]["interactionInfo"]["state"]["issued"]:
                credentialid = credential["id"]
                status, credentildata = condidi_db.add_credential(db, credentialid=credentialid,
                                                                  credentialdict=credential)
            # right now I don't really care if the credential was saved
            # add ticket id
            status, participant = condidi_db.update_participant(db, {"participantid": interactiondict["participantid"],
                                                                     "ticket id": credentialid})
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
    else:
        # unknown interaction, should not happen but what do I know
        response.status = 404
        if DEVELOPMENT:
            print("to wallet: ")
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
    else:
        print("Warning! config.ini missing. Wallet connection will not work!")
    # start server
    if "DEVELOPMENT" in os.environ:
        DEVELOPMENT = os.environ["DEVELOPMENT"]
    else:
        DEVELOPMENT = "True"
    if "JOLOCOM_URL" in os.environ:
        JOLOCOM_URL = os.environ["JOLOCOM_URL"]
    else:
        JOLOCOM_URL = "localhost:4040"
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
