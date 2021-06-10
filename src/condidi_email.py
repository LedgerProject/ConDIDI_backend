import smtplib
import ssl
from email.message import EmailMessage

from backend import make_jolocom_deeplink


class MsgTicket(object):
    def __init__(self, firstname, lastname, event, webtoken):
        super().__init__()
        deeplink = make_jolocom_deeplink(webtoken)
        self.message = ""
        self.message += "Dear %s %s,\n" % (firstname, lastname)
        self.message += "please use the Jolocom smartwallet (available on Apple Appstore or Google Playstore) to load this ticktet "
        self.message += "for the event %s.\n" % (event)
        self.message += "With the smartwallet installed, click on this link: "
        self.message += '%deeplink'
        self.message += " for the event %s.\n\n" % (event)
        self.message += "This message has been automatically created by the ConDIDI project (labs.tib.eu/condidi/).\n"
        self.message += "If it has reached you in error, please let us know."
        self.subject = "Your ticket for %s" % event

    def __str__(self):
        return self.message


def send_email(myemail, mypass, mailserver, port, content, email):
    msg = EmailMessage()
    msg.set_content(str(content))
    msg['Subject'] = content.subject
    msg['From'] = myemail
    msg['To'] = email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(mailserver, port, context=context) as s:
        s.login(myemail, mypass)
        s.send_message(msg)
        s.quit()
    return True

