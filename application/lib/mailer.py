import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_mail(subject, message, email):
    #sender = 'dev.trademinister@gmail.com'
    #password = 'KmIyuBi1'
    sender = 'watchdog@trademinister.de'
    password = 'at1trademinister'
    receivers = [email]
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
