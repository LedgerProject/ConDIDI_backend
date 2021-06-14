import json
import secrets


class InitiateCredentialOffer(dict):
    def __init__(self, callbackurl, credentialtype, claimtype, claims, interactionid=None):
        super().__init__()
        self["jsonrpc"] = "2.0"
        self["method"] = "initiateCredentialOffer"
        self["params"] = {"callbackURL": callbackurl, "offeredCredentials": [{"type": credentialtype}],
                        "claimData": [{"type": claimtype, "claims": claims}]}
        if not interactionid:
            interactionid = secrets.token_urlsafe(32)
        self["id"] = interactionid
        #self["interactionId"] = interactionid

    def json(self):
        return json.dumps(self)


class ProcessInteractionToken(dict):
    def __init__(self, token, interactionid=None):
        super().__init__()
        self["jsonrpc"] = "2.0"
        self["method"] = "processInteractionToken"
        self["params"] = {"interactionToken": token}
        if not interactionid:
            interactionid = secrets.token_urlsafe(32)
        self["id"] = interactionid

    def json(self):
        return json.dumps(self)


class InitiateCredentialRequest(dict):
    def __init__(self, callbackurl, credentialtype, issuer, interactionid=None):
        super().__init__()
        self["jsonrpc"] = "2.0"
        self["method"] = "initiateCredentialRequest"
        self["params"] = {"callbackURL": callbackurl,
                          "credentialRequirements": [{
                              "type": ["VerifiableCredential", credentialtype],
                              "constraints": [{
                                  "==": [{"var": "issuer"}, issuer]
                              }]}]}
        if not interactionid:
            interactionid = secrets.token_urlsafe(32)
        self["id"] = interactionid

    def json(self):
        return json.dumps(self)


class UpdatePublicProfile(dict):
    def __init__(self, name, description, image, url, interactionid=None):
        super().__init__()
        self["jsonrpc"] = "2.0"
        self["method"] = "updatePublicProfile"
        self["params"] = {"name": name,
                          "description": description,
                          "image": image,
                          "url": url}
        if not interactionid:
            interactionid = secrets.token_urlsafe(32)
        self["id"] = interactionid

    def json(self):
        return json.dumps(self)


class AuthenticationFlow(dict):
    def __init__(self, callbackurl, description, interactionid=None):
        super().__init__()
        self["jsonrpc"] = "2.0"
        self["method"] = "initiateAuthentication"
        self["params"] = {"callbackURL": callbackurl,
                          "description": description}
        if not interactionid:
            interactionid = secrets.token_urlsafe(32)
        self["id"] = interactionid

    def json(self):
        return json.dumps(self)
