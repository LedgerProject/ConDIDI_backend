# create a user
```console
$ echo '{"name": "testuser", "email":"test@condidi.invalid", "password":"12345"}' | curl -X POST -d @- 'http://localhost:8080/api/create_user' --header "Content-Type:application/json"
{"success": "yes", "error": ""}
$ echo '{"name": "testuser", "email":"test@condidi.invalid", "password":"12345"}' | curl -X POST -d @- 'http://localhost:8080/api/create_user' --header "Content-Type:application/json" -v
{"success": "no", "error": "email exists"}
$ echo '{"email":"test@condidi.invalid", "password":"wrong"}' | curl -X POST -d @- 'http://localhost:8080/api/login_password' --header "Content-Type:application/json" 
{"success": "no", "error": "wrong password"}
$ echo '{"email":"test@condidi.invalid", "password":"12345"}' | curl -X POST -d @- 'http://localhost:8080/api/login_password' --header "Content-Type:application/json" 
{"success": "yes", "error": "", "token": "..."}
$ echo '{"token": "...the one from the command before..."}' | curl -X POST -d @- 'http://localhost:8080/api/logout' --header "Content-Type:application/json" 
{"success": "yes", "error": ""}
$ echo '{"token": "...the one from the command before..."}' | curl -X POST -d @- 'http://localhost:8080/api/logout' --header "Content-Type:application/json" 
{"success": "yes", "error": "no such session"}
```
(delete the test user with the arangodb console at http://0.0.0.0:8529 if you need.)
