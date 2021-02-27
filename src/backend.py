from gevent import monkey
monkey.patch_all()
from bottle import route, run, template, request, response, post, get
import condidi_db
import os


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

    return False

if __name__ == '__main__':
    # start server
    if "DEVELOPMENT" in os.environ:
        DEVELOPMENT = os.environ["DEVELOPMENT"]
    else:
        DEVELOPMENT = "True"
    if DEVELOPMENT == "True":
        # start single thread server with only localhost access, easier for debugging
        print("development mode")
        run(host='127.0.0.1', port=8080)
    else:
        # start gevent server based on greenlets with access from anywhere.
        print("deployment mode")
        run(host='0.0.0.0', port=8080, server='gevent')
