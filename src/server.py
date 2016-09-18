#!/usr/bin/env python3

import paramiko
import paramiko.client
from flask import Flask, request, redirect
from paramiko.ssh_exception import AuthenticationException


app = Flask(__name__)

SSH_SERVER = 'vnc' # derived from docker link
VNC_PASS = 'vnc_password'
GUAC_USER = 'random_user'
GUAC_PASS = 'random_pass'
GUAC_WEBSERVER = 'localhost:8080' # port exposed from docker
USER_MAPPING_PATH = '/etc/guacamole/user-mapping.xml'


def generate_config(vnc_display, user=GUAC_USER, guac_pass=GUAC_PASS, vnc_pass=VNC_PASS):
    user_mapping = (
        '<user-mapping>\n'
        '   <authorize username="%s" password="%s">\n'
        '       <connection name="localhost">\n'
        '           <protocol>vnc</protocol>\n'
        '           <param name="hostname">%s</param>\n' 
        '           <param name="port">59%02d</param>\n' 
        '           <param name="password">%s</param>\n'
        '       </connection>\n'
        '   </authorize>\n'
        '</user-mapping>\n'
    )
    user_mapping %= (user, guac_pass, SSH_SERVER, int(vnc_display[1:]), vnc_pass)
    with open(USER_MAPPING_PATH, 'w') as f:
        f.write(user_mapping)


def set_vncpasswd(ssh_client, passwd):
    stdin, stdout, stderr = ssh_client.exec_command('vncpasswd')
    stdin.write('%s\n' % passwd)
    stdin.write('%s\n' % passwd)
    stdin.write('n\n')
    stdin.flush()
    return stdout.channel.recv_exit_status()
 

def run_command(ssh_client, cmd):
    stdin, stdout, stderr = ssh_client.exec_command(cmd)
    return stdout.channel.recv_exit_status()


def create_ssh_client(server, user, passwd):
    ssh_client = paramiko.client.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.client.WarningPolicy())
    ssh_client.connect(server, username=user, password=passwd)
    return ssh_client


def get_vnc_display(ssh_client):
    stdin, stdout, stderr = ssh_client.exec_command('vncserver -list | tail -1 | cut -f1')
    display = stdout.readline().strip()
    return display if display[0] == ':' else False


def auth_user(user, passwd):
    try:
        ssh_client = create_ssh_client(SSH_SERVER, user, passwd)        
    except AuthenticationException:
        # invalid login!
        return False
    display = get_vnc_display(ssh_client)
    if not display:
        set_vncpasswd(ssh_client, VNC_PASS)
        run_command(ssh_client, 'nohup vncserver -geometry 1680x1050')    
        display = get_vnc_display(ssh_client)
        if not display:
            return False
    generate_config(display)
    return True 

   
@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        
        return app.send_static_file('login.html')
        html = ( '<html>'
                 '<head><title>Guacamole Login</title></head>'
                 '<body>'
                 '<form action="" method="POST">'
                 'User <input type="text" name="username" /> <br />'
                 'Password <input type="password" name="password" /> <br />'
                 '<input type="submit" value="Login" />'
                 '</form>'
                 '</body>' 
                 '</html>'
               )
        return html

    else: # request.method == 'POST'
        user = request.form['username']
        passwd = request.form['password']
        if auth_user(user, passwd):
            url = "http://%s/guacamole/#/?username=%s&password=%s" % (GUAC_WEBSERVER, GUAC_USER, GUAC_PASS)
            return redirect(url, code=302)
        else:
            return "Invalid login!"

if __name__ == '__main__':
    app.run(host='0.0.0.0')
