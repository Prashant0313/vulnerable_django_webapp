import os
import json
from django.test import TestCase, Client
from LegacySite.models import Card

dirname = os.path.dirname(os.path.abspath(__file__))

# Create your tests here.
class MyTest(TestCase):
    # Django's test run with an empty database. We can populate it with
    # data by using a fixture. You can create the fixture by running:
    #    mkdir LegacySite/fixtures
    #    python manage.py dumpdata LegacySite > LegacySite/fixtures/testdata.json
    # You can read more about fixtures here:
    #    https://docs.djangoproject.com/en/4.0/topics/testing/tools/#fixture-loading
    fixtures = ["testdata.json"]

    def setUp(self):
        self.client = Client()



    #success if 'director_content != <script>alert("The director says hello.")</script>
    def test_xss(self):
        response = self.client.get('/buy.html?director=<script>alert("The director says hello.")</script>')
        self.assertEqual(response.status_code, 200)
        content = response.content
        pos = content.find(b'director')
        director_content = content[pos-45:pos+50]
        print("XSS test-> ", director_content, end="\n\n")
    
    #success if recipient = None
    def test_csrf(self):
        self.client.login(username="user1", password="user1")
        response = self.client.get('/gift/6?username=bad_user')
        self.assertEqual(response.status_code, 200)
        recipient = response.context["user"]
        print("CSRF test-> Giftcard recieved by: ", recipient, end="\n\n")

    #success "No cards found"
    def test_sqli(self):
        self.client.login(username="bad_user", password="pass123")
        filename = os.path.join(dirname, '../part1/sqli.gftcrd')
        with open(filename, "rb") as fp:
            print("SQL giftcard test: ", end="")
            response = self.client.post("/use.html", {"card_data": fp, "card_supplied": True, "card_fname": "NameYourCard"})
            self.assertEqual(response.status_code, 200)
            print("\n\n")

    #success if card binary printed and filename! = exectuable comand
    def test_os_ci(self):
        self.client.login(username="bad_user", password="pass123")
        filename = os.path.join(dirname, '../part1/cmdi.gftcrd')
        fname = "echo command_injection & ls"
        with open(filename, "rb") as fp:
            print("Command injection giftcard test-> filename = '", fname, "': ", end="")
            response = self.client.post("/use.html", {"card_data": fp, "card_supplied": True, "card_fname": fname})
            self.assertEqual(response.status_code, 200)
            print("\n\n")
