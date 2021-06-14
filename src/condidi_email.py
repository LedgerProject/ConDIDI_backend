import smtplib
import ssl
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

from backend import make_jolocom_deeplink


class MsgTicket(object):
    def __init__(self, firstname, lastname, event, webtoken):
        super().__init__()
        deeplink = make_jolocom_deeplink(webtoken)
        self.text = """\
        Dear %s %s,
        please use the Jolocom smartwallet (available on Apple Appstore or Google Playstore) to load this ticktet 
        for the event %s.
            
        With the smartwallet installed, click on this link: 
        %s
        or scan the attached image with your smartwallet
        
        This message has been automatically created by the ConDIDI project (labs.tib.eu/condidi/).
        If it has reached you in error, please let us know.
        """ %(firstname,lastname,event,deeplink)
        self.html = """\
        <html>
        <head></head>
        <body>
        <p>
        Dear %s %s,<br>
        please use the Jolocom smartwallet (available on Apple Appstore or Google Playstore) to load this ticktet 
        for the event %s.
        </p>
        <p>
        With the smartwallet installed, click on this link: 
        <a href="%s">%s</a>
        </p>
        <p>
        Or scan this image with your smartwallet:<br>
        <img src="cid:image1" alt="qrcode">
        </p>
        <p>
        This message has been automatically created by the ConDIDI project (labs.tib.eu/condidi/).
        If it has reached you in error, please let us know.</p>
        """  %(firstname,lastname,event,deeplink, deeplink)
        self.subject = "Your ticket for %s" % event


def send_email(myemail, mypass, mailserver, port, message, email, qrcodefile=None):
    msg = MIMEMultipart('alternative')
    msg['From'] = myemail
    msg['To'] = email
    msg['Subject'] = message.subject
    msg.attach(MIMEText(message.text, 'plain'))
    msg.attach(MIMEText(message.html, 'html'))
    if qrcodefile:
        with open(qrcodefile, 'rb') as fp
            msgImage = MIMEImage(fp.read())
            fp.close()
        msgImage.add_header('Content-ID', '<image1>')
        msg.attach(msgImage)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(mailserver, port, context=context) as s:
        s.login(myemail, mypass)
        s.send_message(msg)
        s.quit()
    return True

