import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate


def send_mail2(subject, message, email):
    #sender = 'dev.trademinister@gmail.com'
    #password = 'KmIyuBi1'
    sender = 'watchdog@trademinister.de'
    password = 'at1trademinister'

    if isinstance(email, str):
        receivers = [email]

    else:
        receivers = email

    s = smtplib.SMTP('smtp.gmail.com:587')
    s.ehlo()
    s.starttls()
    s.login(sender, password)

    if isinstance(message, bytes):
        msg = MIMEText(message, _charset='utf-8')

    else:
        msg = MIMEText(message.encode('utf-8'), _charset='utf-8')

    msg['From'] = sender
    msg['To'] = receivers[0]
    msg['Subject'] = subject
    s.sendmail(sender, receivers, msg.as_string())
    s.quit()


def send_mail_attach(subject, message, email, data=None, filename=None):
    """
    :param message:
    :param email:
    :param data: bin
    :return:
    """
    sender = 'watchdog@trademinister.de'
    password = 'at1trademinister'
    receivers = [email]

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = COMMASPACE.join(receivers)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    msg.attach(MIMEText(message.encode('utf-8'), 'html', _charset='utf-8'))

    if data and filename:
        part = MIMEApplication(data, Name=filename)
        part['Content-Disposition'] = 'attachment; filename="%s"' % filename
        msg.attach(part)

    s = smtplib.SMTP('smtp.gmail.com:587')
    s.ehlo()
    s.starttls()
    s.login(sender, password)
    s.sendmail(sender, receivers, msg.as_string())
    s.quit()
