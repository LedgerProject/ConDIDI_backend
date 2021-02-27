# ConDIDI_backend
The Backend of the ConDIDI system.

# Install
not yet ready. will consist of a setup script and the dockercompose-deployment.yml

# Development of the backend
Start the database backends with 
```console
$ docker-compose -f docker-compose-development.yml up
```
Then you can run the tests and the code in the src directory. 

# Development against the backend
Start the database backends and the ConDIDI backend with 
```console
$ docker-compose -f docker-compose-deployment.yml up
```
Then you can develop your frontend that calls the ConDIDI backend at http://localhost:8080


