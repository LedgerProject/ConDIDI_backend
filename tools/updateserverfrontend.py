from bottle import request, route, template, run
import subprocess

USER=""
PASS=""
DIRNAME = "/var/local/condidife/ConDIDI_frontend"

def do_update():
    out="<html><head></head><body>"
    result = subprocess.run(["git", "pull"], timeout=30, capture_output=True, text=True, cwd=DIRNAME)
    out += result.stdout.replace("\n","<br>")
    out += result.stderr.replace("\n","<br>")
    print(result.stdout)
    #result = subprocess.run(["npm", "install", "--force"], timeout=120, capture_output=True, text=True, cwd=DIRNAME)
    result = subprocess.run(["yarn", "install"], timeout=360, capture_output=True, text=True, cwd=DIRNAME)
    out += result.stdout.replace("\n","<br>")
    out += result.stderr.replace("\n","<br>")
    print(result.stdout)
    result = subprocess.run(["yarn", "build"], timeout=240, capture_output=True, text=True, cwd=DIRNAME)
    out += result.stdout.replace("\n","<br>")
    out += result.stderr.replace("\n","<br>")
    print(result.stdout)
    result = subprocess.run("cp -r dist/* /var/www/html/condidi/", timeout=60, capture_output=True,
                            shell=True, text=True, cwd=DIRNAME)
    out += result.stdout.replace("\n","<br>")
    out += result.stderr.replace("\n","<br>")
    print(result.stdout)
    out += "</body>"
    return out

@route('/updateserver')
def index():
    #username = request.forms.get('user')
    #password = request.forms.get('pass')
    #if username != USER:
    #    return "Nada"
    #if password != PASS:
    #    return "Nada"
    result = do_update()
    return result


if __name__ == '__main__':
    run(host='0.0.0.0', port=8085)
