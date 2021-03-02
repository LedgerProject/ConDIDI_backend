# ConDIDI_backend
The Backend of the ConDIDI system.

# Install

Requirements: 
* Docker
* Docker-compose
* Python 3.8 (for development only)

Clone the repository. Then create the database folders. On linux:
```console
$ cd database
$ chmod a+x setup.x
$ ./setup.x
$ cd ..
```

That's it.

# Development of the backend
Start the database backends with 
```console
$ docker-compose -f docker-compose-development.yml up
```
Then you can run the tests and the code in the src directory. 

# Development against the backend
Start the database backends and the ConDIDI backend with 
```console
$ docker-compose -f docker-compose-deployment.yml up --force-recreate --build
```
Then you can develop your frontend that calls the ConDIDI backend at http://localhost:8080

Stop with:
```console
$ docker-compose -f docker-compose-deployment.yml down
```
to remove the containers