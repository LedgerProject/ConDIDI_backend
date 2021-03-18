from bottle import request, route, template, run
import subprocess
import tempfile

USER=""
PASS=""
DIRNAME = "/var/local/condidife/ConDIDI_frontend"

def do_update():
    out=""
    result = subprocess.run(["git", "pull"], timeout=30, capture_output=True, text=True, cwd=DIRNAME)
    out += result.stdout
    out += result.stderr
    result = subprocess.run(["npm", "install", "--force"], timeout=120, capture_output=True, text=True, cwd=DIRNAME)
    out += result.stdout
    out += result.stderr
    result = subprocess.run(["npm", "run", "build"], timeout=120, capture_output=True, text=True, cwd=DIRNAME)
    out += result.stdout
    out += result.stderr
    result = subprocess.run(["cp", "-r", "build/*", "/var/ww/html/condidi/"], timeout=30, capture_output=True, text=True, cwd=DIRNAME)
    out += result.stdout
    out += result.stderr
    return out

@route('/updateserver')
def index():
    username = request.forms.get('user')
    password = request.forms.get('pass')
    if username != USER:
        return "Nada"
    if password != PASS:
        return "Nada"
    result = do_update()
    return result


if __name__ == '__main__':
    run(host='0.0.0.0', port=8085)
