# create a user
```console
$ echo '{"name": "testuser", "email":"test@condidi.invalid", "password":"12345"}' | curl -X POST -d @- 'http://localhost:8080/api/create_user' --header "Content-Type:application/json"
{"success": "yes", "error": ""}
$ echo '{"name": "testuser", "email":"test@condidi.invalid", "password":"12345"}' | curl -X POST -d @- 'http://localhost:8080/api/create_user' --header "Content-Type:application/json"
{"success": "no", "error": "email exists"}
```
(delete the user with the arangodb console at http://0.0.0.0:8529)
