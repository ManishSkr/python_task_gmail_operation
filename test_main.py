import unittest
from unittest.mock import patch, MagicMock
import sqlite3
import os
from dotenv import load_dotenv
from main import fetch_emails, setup_database, store_emails, load_rules, apply_conditions, process_emails

class TestGmailOperations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Load environment variables
        load_dotenv()

    def setUp(self):
        # Setup in-memory SQLite database for testing
        self.conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE emails (
                               id TEXT PRIMARY KEY,
                               date TEXT,
                               from_email TEXT,
                               subject TEXT,
                               body TEXT)''')
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_env_variables(self):
        # Test if environment variables are correctly loaded
        email_account = os.getenv('EMAIL_ACCOUNT')
        email_password = os.getenv('EMAIL_PASSWORD')
        self.assertIsNotNone(email_account)
        self.assertIsNotNone(email_password)

    @patch('main.imaplib.IMAP4_SSL')
    def test_fetch_emails(self, mock_imap):
        # Mock the IMAP server and test email fetching
        mock_mail = MagicMock()
        mock_imap.return_value = mock_mail
        mock_mail.login.return_value = ('OK', [b'Logged in'])
        mock_mail.select.return_value = ('OK', [b''])
        mock_mail.search.return_value = ('OK', [b'1 2'])
        mock_mail.fetch.side_effect = [
            ('OK', [(b'1 (RFC822 {342}', b'Raw email content 1')]),
            ('OK', [(b'2 (RFC822 {456}', b'Raw email content 2')])
        ]

        emails = fetch_emails()
        self.assertEqual(len(emails), 2)

    @patch('main.email.message_from_bytes')
    def test_store_emails(self, mock_message_from_bytes):
        # Mock email messages
        mock_msg1 = MagicMock()
        mock_msg1.is_multipart.return_value = False
        mock_msg1.get_payload.return_value = "This is a test email."
        mock_msg1.__getitem__.side_effect = lambda x: {
            'Message-ID': '1',
            'Date': 'Mon, 19 Jul 2021 10:00:00 +0000',
            'From': 'sender@example.com',
            'Subject': 'Test Email 1'
        }[x]

        mock_msg2 = MagicMock()
        mock_msg2.is_multipart.return_value = False
        mock_msg2.get_payload.return_value = "This is another test email."
        mock_msg2.__getitem__.side_effect = lambda x: {
            'Message-ID': '2',
            'Date': 'Tue, 20 Jul 2021 11:00:00 +0000',
            'From': 'sender2@example.com',
            'Subject': 'Test Email 2'
        }[x]

        emails = [mock_msg1, mock_msg2]

        with patch('main.sqlite3.connect') as mock_connect:
            mock_connect.return_value = self.conn
            store_emails(emails)

            self.cursor.execute("SELECT * FROM emails")
            stored_emails = self.cursor.fetchall()
            self.assertEqual(len(stored_emails), 2)

    def test_load_rules(self):
        # Test loading rules from JSON file
        rules = load_rules()
        self.assertIn('rules', rules)

    def test_apply_conditions(self):
        # Test applying conditions to an email
        email = ('1', 'Mon, 19 Jul 2021 10:00:00 +0000', 'sender@example.com', 'Test Email 1', 'This is a test email.')
        conditions = [
            {'field': 'From', 'predicate': 'contains', 'value': 'sender@example.com'},
            {'field': 'Subject', 'predicate': 'equals', 'value': 'Test Email 1'}
        ]
        result = apply_conditions(email, conditions)
        self.assertTrue(all(result))

    def test_process_emails(self):
        # Test processing emails with rules
        emails = [
            ('1', 'Mon, 19 Jul 2021 10:00:00 +0000', 'sender@example.com', 'Test Email 1', 'This is a test email.'),
            ('2', 'Tue, 20 Jul 2021 11:00:00 +0000', 'sender2@example.com', 'Test Email 2', 'This is another test email.')
        ]
        rules = {
            'rules': [
                {
                    'predicate': 'All',
                    'conditions': [
                        {'field': 'From', 'predicate': 'contains', 'value': 'sender@example.com'},
                        {'field': 'Subject', 'predicate': 'equals', 'value': 'Test Email 1'}
                    ],
                    'actions': ['mark_as_read']
                }
            ]
        }
        setup_database()
        conn = sqlite3.connect('emails.db')
        cursor = conn.cursor()
        cursor.executemany("INSERT OR REPLACE INTO emails (id, date, from_email, subject, body) VALUES (?, ?, ?, ?, ?)", emails)
        conn.commit()
        conn.close()
        process_emails(rules)

if __name__ == '__main__':
    unittest.main()
