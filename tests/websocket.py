from gevent import monkey

monkey.patch_all()
from bottle import route, run, template, request, response, post, get, hook
import websockets
import asyncio
import json

data1 = {"jsonrpc": "2.0",
         "method": "initiateCredentialOffer",
         "params": {
             "callbackURL": "https://localhost/interact",
             "offeredCredentials": [{"type": "ProofOfEventOrganizerRoleCredential",
                                     }],
             "claimData": [{
                 "type": "ProofOfEventOrganizerRoleCredential",
                 "claims": {
                     "name": "Joe",
                     "surname": "Tester",
                     "email": "joe@example.com"
                 }
             }]
         },
         "id": 402131}

async def test():
    uri = "ws://localhost:4040"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps(data1))
        greeting = await ws.recv()
        print(greeting)
        return greeting

@route('/')
def index():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    #name = asyncio.get_event_loop().run_until_complete(test())
    name = loop.run_until_complete(test())
    loop.close()
    return template('<b>Hello {{name}}</b>!', name=name)



#asyncio.get_event_loop().run_until_complete(test())
if __name__ == '__main__':
    # start server
    run(host='0.0.0.0', port=8080, server='gevent')
    #client.close()

