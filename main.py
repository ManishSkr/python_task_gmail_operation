import imaplib
import email
from email.header import decode_header
import datetime
import sqlite3
import json
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Gmail IMAP settings
IMAP_SERVER = 'imap.gmail.com'
EMAIL_ACCOUNT = os.getenv('EMAIL_ACCOUNT')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# Debugging: Print the environment variable values
print(f"EMAIL_ACCOUNT: {EMAIL_ACCOUNT}")
print(f"EMAIL_PASSWORD: {EMAIL_PASSWORD}")

if EMAIL_ACCOUNT is None or EMAIL_PASSWORD is None:
    raise ValueError("EMAIL_ACCOUNT or EMAIL_PASSWORD is not set. Check your .env file.")

def fetch_emails():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    mail.select('inbox')

    result, data = mail.search(None, 'ALL')
    email_ids = data[0].split()
    emails = []

    for email_id in email_ids:
        result, msg_data = mail.fetch(email_id, '(RFC822)')
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        emails.append(msg)
    return emails

def setup_database():
    conn = sqlite3.connect('emails.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS emails (
                 id TEXT PRIMARY KEY,
                 date TEXT,
                 from_email TEXT,
                 subject TEXT,
                 body TEXT)''')
    conn.commit()
    conn.close()

def store_emails(emails):
    conn = sqlite3.connect('emails.db')
    c = conn.cursor()
    for msg in emails:
        email_id = msg['Message-ID']
        date = msg['Date']
        from_email = msg['From']
        subject = decode_header(msg['Subject'])[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode()
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    part_payload = part.get_payload(decode=True)
                    if isinstance(part_payload, bytes):
                        body = part_payload.decode()
                    else:
                        body = part_payload
                    break
        else:
            part_payload = msg.get_payload(decode=True)
            if isinstance(part_payload, bytes):
                body = part_payload.decode()
            else:
                body = part_payload
        c.execute('''INSERT OR REPLACE INTO emails (id, date, from_email, subject, body) 
                     VALUES (?, ?, ?, ?, ?)''', 
                  (email_id, date, from_email, subject, body))
    conn.commit()
    conn.close()

def load_rules():
    with open('rules.json', 'r') as f:
        rules = json.load(f)
    return rules

def apply_conditions(email, conditions):
    results = []
    for condition in conditions:
        field, predicate, value = condition['field'], condition['predicate'], condition['value']
        email_value = ""

        if field == "From":
            email_value = email[2]
        elif field == "Subject":
            email_value = email[3]
        elif field == "Received Date":
            email_value = email[1]
            email_value = datetime.datetime.strptime(email_value, '%a, %d %b %Y %H:%M:%S %z')
            value = datetime.datetime.now() - datetime.timedelta(days=int(value))
        else:
            continue

        if predicate == "contains" and value in email_value:
            results.append(True)
        elif predicate == "not_contains" and value not in email_value:
            results.append(True)
        elif predicate == "equals" and value == email_value:
            results.append(True)
        elif predicate == "not_equals" and value != email_value:
            results.append(True)
        elif predicate == "less_than" and email_value < value:
            results.append(True)
        elif predicate == "greater_than" and email_value > value:
            results.append(True)
        else:
            results.append(False)
    return results

def process_emails(rules):
    conn = sqlite3.connect('emails.db')
    c = conn.cursor()
    c.execute("SELECT * FROM emails")
    emails = c.fetchall()
    for email_data in emails:
        for rule in rules['rules']:
            if rule['predicate'] == "All":
                if all(apply_conditions(email_data, rule['conditions'])):
                    print(f"Rule {rule['actions']} applied to email with subject: {email_data[3]}")
            elif rule['predicate'] == "Any":
                if any(apply_conditions(email_data, rule['conditions'])):
                    print(f"Rule {rule['actions']} applied to email with subject: {email_data[3]}")
    conn.close()

def main():
    emails = fetch_emails()
    setup_database()
    store_emails(emails)
    rules = load_rules()
    process_emails(rules)

if __name__ == '__main__':
    main()
