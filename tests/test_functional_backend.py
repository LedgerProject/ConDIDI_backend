import subprocess
import time
import unittest
import requests

backend = None


def startsystem():
    print("start system")
    # subprocess.run(["docker-compose", "-f" "docker-compose-deployment.yml", "up", "--force-recreate", "--build", "-d"],
    #               timeout=20, check=True, cwd="../")
    subprocess.run(["docker", "run", "-e", "ARANGO_ROOT_PASSWORD=justfortest", "-p", "8529:8529", "-d",
                    "--rm", "--name", "arangotest", "arangodb"],
                   timeout=20, check=True)
    subprocess.run(["docker", "run", "-p", "6379:6379", "-d",
                    "--rm", "--name", "redistest", "redis"],
                   timeout=20, check=True)
    # subprocess.run(["docker", "build", "-t", "backend:latest", "../src/."],
    #               timeout=20, check=True)
    time.sleep(10)
    global backend
    with open("stdout.txt", "wb") as out, open("stderr.txt", "wb") as err:
        backend = subprocess.Popen(["python3", "src/backend.py"], cwd="../", stdout=out, stderr=err)
    # give system some time to start up
    return True


def stopsystem():
    print("stop system")
    # subprocess.run(["docker-compose", "-f" "docker-compose-deployment.yml", "down"],
    #               timeout=20, check=True, cwd="../")
    # give system some time to start up
    global backend
    try:
        backend.terminate()
        backend.wait()
    except:
        pass
    try:
        subprocess.run(["docker", "stop", "arangotest"])
    except:
        pass
    try:
        subprocess.run(["docker", "stop", "redistest"])
    except:
        pass
    # subprocess.run(["docker", "stop", "condiditest"])
    time.sleep(2)
    return True


def setUpModule():
    try:
        stopsystem()
    except:
        pass
    startsystem()
    time.sleep(5)
    print("system should be ready now")


def tearDownModule():
    stopsystem()


class TestUsers(unittest.TestCase):
    def test_adduser(self):
        userdict = {"name": "testuser", "email": "test@condidi.invalid", "password": "12345"}
        # success if user is new
        r = requests.post('http://localhost:8080/api/create_user', json=userdict)
        result = r.json()
        self.assertEqual(result["success"], "yes")
        # error if user exists
        r = requests.post('http://localhost:8080/api/create_user', json=userdict)
        result = r.json()
        self.assertEqual(result["success"], "no")

    def test_session(self):
        userdict = {"email": "test@condidi.invalid", "password": "43"}
        r = requests.post('http://localhost:8080/api/login_password', json=userdict)
        result = r.json()
        self.assertEqual(result["success"], "no")
        userdict = {"email": "test@condidi.invalid", "password": "12345"}
        r = requests.post('http://localhost:8080/api/login_password', json=userdict)
        result = r.json()
        self.assertEqual(result["success"], "yes")
        token = result["token"]
        # print(token)
        sessiondict = {"token": token}
        r = requests.post('http://localhost:8080/api/logout', json=sessiondict)
        result = r.json()
        # print(result)
        self.assertEqual(result["success"], "yes")
        r = requests.post('http://localhost:8080/api/logout', json=sessiondict)
        result = r.json()
        self.assertEqual(result["success"], "yes")

    def test_events(self):
        # login
        userdict = {"email": "test@condidi.invalid", "password": "12345"}
        r = requests.post('http://localhost:8080/api/login_password', json=userdict)
        result = r.json()
        self.assertEqual(result["success"], "yes")
        token = result["token"]
        # add events
        eventdict = {"name": "test event", "url": "http://nada", "error": "False", "organiser userid": 0}
        calldict = {"token": token, "eventdict": eventdict}
        r = requests.post('http://localhost:8080/api/add_event', json=calldict)
        result = r.json()
        self.assertEqual(result["success"], "yes")
        eventdict = {"name": "test event1", "url": "http://nada", "error": "False", "organiser userid": 0}
        calldict = {"token": token, "eventdict": eventdict}
        r = requests.post('http://localhost:8080/api/add_event', json=calldict)
        result = r.json()
        self.assertEqual(result["success"], "yes")
        # retrieve event
        calldict = {"token": token}
        r = requests.post('http://localhost:8080/api/list_my_events', json=calldict)
        result = r.json()
        self.assertEqual(result["success"], "yes")
        self.assertEqual(len(result["eventlist"]), 2)
        # logout
        sessiondict = {"token": token}
        r = requests.post('http://localhost:8080/api/logout', json=sessiondict)
        result = r.json()
        # print(result)
        self.assertEqual(result["success"], "yes")


unittest.addModuleCleanup(tearDownModule)

if __name__ == '__main__':
    unittest.main()
