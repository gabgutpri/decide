import random
import itertools
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.test import APITestCase

from base import mods
from base.tests import BaseTestCase
from census.models import Census
from mixnet.mixcrypt import ElGamal
from mixnet.mixcrypt import MixCrypt
from mixnet.models import Auth
from voting.models import Voting, Question, QuestionOption

from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException
import unittest, time, re

from django.contrib.staticfiles.testing import StaticLiveServerTestCase

# Selenium imports
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys


class VotingTestCase(BaseTestCase):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def encrypt_msg(self, msg, v, bits=settings.KEYBITS):
        pk = v.pub_key
        p, g, y = (pk.p, pk.g, pk.y)
        k = MixCrypt(bits=bits)
        k.k = ElGamal.construct((p, g, y))
        return k.encrypt(msg)

    def create_voting(self):
        q = Question(desc='test question')
        q.save()
        for i in range(5):
            opt = QuestionOption(question=q, option='option {}'.format(i+1))
            opt.save()
        v = Voting(name='test voting', question=q)
        v.save()

        a, _ = Auth.objects.get_or_create(url=settings.BASEURL,
                                          defaults={'me': True, 'name': 'test auth'})
        a.save()
        v.auths.add(a)

        return v

    def create_voters(self, v):
        for i in range(100):
            u, _ = User.objects.get_or_create(username='testvoter{}'.format(i))
            u.is_active = True
            u.save()
            c = Census(voter_id=u.id, voting_id=v.id)
            c.save()

    def get_or_create_user(self, pk):
        user, _ = User.objects.get_or_create(pk=pk)
        user.username = 'user{}'.format(pk)
        user.set_password('qwerty')
        user.save()
        return user

    def store_votes(self, v):
        voters = list(Census.objects.filter(voting_id=v.id))
        voter = voters.pop()

        clear = {}
        for opt in v.question.options.all():
            clear[opt.number] = 0
            for i in range(random.randint(0, 5)):
                a, b = self.encrypt_msg(opt.number, v)
                data = {
                    'voting': v.id,
                    'voter': voter.voter_id,
                    'vote': { 'a': a, 'b': b },
                }
                clear[opt.number] += 1
                user = self.get_or_create_user(voter.voter_id)
                self.login(user=user.username)
                voter = voters.pop()
                mods.post('store', json=data)
        return clear

    def test_complete_voting(self):
        v = self.create_voting()
        self.create_voters(v)

        v.create_pubkey()
        v.start_date = timezone.now()
        v.save()

        clear = self.store_votes(v)

        self.login()  # set token
        v.tally_votes(self.token)

        tally = v.tally
        tally.sort()
        tally = {k: len(list(x)) for k, x in itertools.groupby(tally)}

        for q in v.question.options.all():
            self.assertEqual(tally.get(q.number, 0), clear.get(q.number, 0))

        for q in v.postproc:
            self.assertEqual(tally.get(q["number"], 0), q["votes"])

    def test_create_voting_from_api(self):
        data = {'name': 'Example'}
        response = self.client.post('/voting/', data, format='json')
        self.assertEqual(response.status_code, 401)

        # login with user no admin
        self.login(user='noadmin')
        response = mods.post('voting', params=data, response=True)
        self.assertEqual(response.status_code, 403)

        # login with user admin
        self.login()
        response = mods.post('voting', params=data, response=True)
        self.assertEqual(response.status_code, 400)

        data = {
            'name': 'Example',
            'desc': 'Description example',
            'question': 'I want a ',
            'question_opt': ['cat', 'dog', 'horse']
        }

        response = self.client.post('/voting/', data, format='json')
        self.assertEqual(response.status_code, 201)

    def test_update_voting(self):
        voting = self.create_voting()

        data = {'action': 'start'}
        response = self.client.post('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 401)

        # login with user no admin
        self.login(user='noadmin')
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 403)

        # login with user admin
        self.login()
        data = {'action': 'bad'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 400)

        # STATUS VOTING: not started
        for action in ['stop', 'tally']:
            data = {'action': action}
            response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), 'Voting is not started')

        data = {'action': 'start'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), 'Voting started')

        # STATUS VOTING: started
        data = {'action': 'start'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Voting already started')

        data = {'action': 'tally'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Voting is not stopped')

        data = {'action': 'stop'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), 'Voting stopped')

        # STATUS VOTING: stopped
        data = {'action': 'start'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Voting already started')

        data = {'action': 'stop'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Voting already stopped')

        data = {'action': 'tally'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), 'Voting tallied')

        # STATUS VOTING: tallied
        data = {'action': 'start'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Voting already started')

        data = {'action': 'stop'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Voting already stopped')

        data = {'action': 'tally'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Voting already tallied')

# Yes/No question model test
class YesNoQuestionModelTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    # Verify if a Yes/No question is created correctly
    def test_create_yes_no_question(self):
        q = Question(desc='Yes/No question test', yes_no_question=True)
        q.save()

        self.assertEquals(len(q.options.all()), 2)
        self.assertEquals(q.yes_no_question, True)
        self.assertEquals(q.options.all()[0].option, 'YES')
        self.assertEquals(q.options.all()[1].option, 'NO')
        self.assertEquals(q.options.all()[0].number, 1)
        self.assertEquals(q.options.all()[1].number, 2)

    # Verify if the extra options are not save in a Yes/No question
    def test_create_yes_no_question_with_more_options(self):
        q = Question(desc='Yes/No question test', yes_no_question=True)
        q.save()

        qo1 = QuestionOption(question = q, option = 'First option')
        qo1.save()

        qo2 = QuestionOption(question = q, option = 'Second option')
        qo2.save()

        self.assertEquals(len(q.options.all()), 2)
        self.assertEquals(q.yes_no_question, True)
        self.assertEquals(q.options.all()[0].option, 'YES')
        self.assertEquals(q.options.all()[1].option, 'NO')
        self.assertEquals(q.options.all()[0].number, 1)
        self.assertEquals(q.options.all()[1].number, 2)

    def test_create_yes_no_voting(self):
        q = Question(desc='Yes/No question test', yes_no_question=True)
        q.save()

        self.assertEquals(len(q.options.all()), 2)
        self.assertEquals(q.yes_no_question, True)

        v = Voting(name='Yes/No voting test', question=q)
        v.save()

        a, _ = Auth.objects.get_or_create(url=settings.BASEURL,
                                          defaults={'me': True, 'name': 'auth test'})
        a.save()
        v.auths.add(a)

        elf.assertEquals(len(v.questio_op.all()), 2)
        self.assertEquals(v.question.yes_no_question, True)
        
# Yes/No question view test
class YesNoQuestionViewTestCase(StaticLiveServerTestCase):

    def setUp(self):
        #Load base test functionality for decide
        self.base = BaseTestCase()
        self.base.setUp()

        options = webdriver.ChromeOptions()
        options.headless = True
        self.driver = webdriver.Chrome(options=options)

        super().setUp()     

    # Verify if a Yes/No question is created correctly
    def test_create_yes_no_question(self):       
        driver = self.driver
        # Creation of a super user to being able to create questions
        User.objects.create_superuser('egcVotacion', 'votacion@decide.com', 'egcVotacion')
        self.driver.get(f'{self.live_server_url}/admin/')
        # Web log in
        self.driver.find_element_by_id('id_username').send_keys("egcVotacion")
        self.driver.find_element_by_id('id_password').send_keys("egcVotacion", Keys.ENTER)
        time.sleep(3)

        # Access to add question form
        driver.find_element_by_link_text("Questions").click()
        time.sleep(1)
        driver.find_element_by_link_text("Add question").click()
        time.sleep(1)

        # Creation of a yes/no question example
        driver.find_element_by_id('id_desc').send_keys("Si/No prueba")
        driver.find_element_by_xpath("//form[@id='question_form']/div/fieldset/div[3]/div/label").click()
        driver.find_element_by_name("_save").click()
        time.sleep(3)

        # Verification of the creation of the question
        driver.find_element_by_xpath("(//a[contains(text(),'Si/No prueba')])[2]").click()
        time.sleep(2)
        self.assertEqual("Si/No prueba", driver.find_element_by_xpath("//textarea[@id='id_desc']").text)
        self.assertEqual("YES", driver.find_element_by_id("id_options-0-option").text)
        self.assertEqual("NO", driver.find_element_by_id("id_options-1-option").text)


    # Verify if the extra options are not save in a Yes/No question
    def test_create_yes_no_question_extra(self):
        driver = self.driver
        # Creation of a super user to being able to create questions
        User.objects.create_superuser('egcVotacion', 'votacion@decide.com', 'egcVotacion')
        self.driver.get(f'{self.live_server_url}/admin/')
        # Web log in
        self.driver.find_element_by_id('id_username').send_keys("egcVotacion")
        self.driver.find_element_by_id('id_password').send_keys("egcVotacion", Keys.ENTER)
        time.sleep(3)

        # Access to add question form
        driver.find_element_by_link_text("Questions").click()
        time.sleep(1)
        driver.find_element_by_link_text("Add question").click()
        time.sleep(1)

        # Creation of a yes/no question example with extra answers
        driver.find_element_by_id('id_desc').send_keys("Si/No prueba con extra")
        driver.find_element_by_xpath("//form[@id='question_form']/div/fieldset/div[3]/div/label").click()
        driver.find_element_by_id("id_options-0-option").send_keys("Primer extra")
        driver.find_element_by_id("id_options-1-option").send_keys("Segundo extra")
        driver.find_element_by_name("_save").click()
        time.sleep(3)

        # Verification of the creation of the question without the extra answers
        driver.find_element_by_xpath("(//a[contains(text(),'Si/No prueba con extra')])[2]").click()
        self.assertEqual("Si/No prueba con extra", driver.find_element_by_xpath("//textarea[@id='id_desc']").text)
        self.assertEqual("YES", driver.find_element_by_id("id_options-0-option").text)
        self.assertEqual("NO", driver.find_element_by_id("id_options-1-option").text)
        self.assertEqual("", driver.find_element_by_id("id_options-2-option").text)
        self.assertEqual("", driver.find_element_by_id("id_options-3-option").text)

        
#TESTS MODELO FLOR
class VotingModelTestCase(BaseTestCase):
    def setUp(self):
        q=Question(desc="Description")
        q.save()

        opt1=QuestionOption(question=q,option='option 1')
        opt1.save()

        opt2=QuestionOption(question=q,option='option 2')
        opt2.save()

        self.v =Voting(name="Votacion",question=q)
        self.v.save()
        super().setUp()
    def tearDown(self):
        super().tearDown()
        self.v = None
    
    def testExiste(self):
        v=Voting.objects.get(name="Votacion")
        self.assertEquals(v.name,"Votacion")
        self.assertEquals(v.question.desc,"Description")
        self.assertEquals(v.question.options.all()[0].option,"option 1")
        self.assertEquals(v.question.options.all()[1].option,"option 2")

        self.assertNotEquals(v.name,"Hola")
        self.assertNotEquals(v.question.desc,"Hola")
        self.assertNotEquals(v.question.options.all()[0].option,"Hello")
        self.assertNotEquals(v.question.options.all()[1].option,"Hello")
  
        
class VotacionPrefModelTestCase(BaseTestCase):

    def setUp(self):
        q=Question(desc="Pregunta de preferencia futbol",question_options=2)
        q.save()

        opt1=QuestionOption(number="1", question=q,option='betis')
        opt1.save()

        opt2=QuestionOption(number="2",question=q,option='sevilla')
        opt2.save()

        vp = Voting(name="Votacion de preferencia 1",desc="derbi de futbol",question=q )
        vp.save()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.vp = None
    
    def testExiste(self):
        vp = Voting.objects.get(name="Votacion de preferencia 1")
        self.assertEquals(vp.name,"Votacion de preferencia 1")
        self.assertEquals(vp.desc,"derbi de futbol")
        self.assertEquals(vp.question.desc,"Pregunta de preferencia futbol")
        self.assertEquals(vp.question.question_options,2)
        self.assertEquals(vp.question.options.all()[0].option,"betis")
        self.assertEquals(vp.question.options.all()[0].number,1)
        self.assertEquals(vp.question.options.all()[1].option,"sevilla")
        self.assertEquals(vp.question.options.all()[1].number,2)

        self.assertNotEquals(vp.name,"Votacion de prueba")
        self.assertNotEquals(vp.desc,"Descripcion de prueba")
        self.assertNotEquals(vp.question.desc,"Pregunta de prueba")
        self.assertNotEquals(vp.question.question_options,1)
        self.assertNotEquals(vp.question.options.all()[0].option,"ordenador")
        self.assertNotEquals(vp.question.options.all()[0].number,3)
        self.assertNotEquals(vp.question.options.all()[1].option,"movil")
        self.assertNotEquals(vp.question.options.all()[1].number,4)
              

#TEST CON SELENIUM MODELO
class TestQues(unittest.TestCase):
    def setUp(self):
        self.driver = webdriver.Firefox()
        self.driver.implicitly_wait(30)
        self.base_url = "https://www.google.com/"
        self.verificationErrors = []
        self.accept_next_alert = True
    
    def test_ques(self):
        driver = self.driver
        driver.get("http://localhost:8000/admin/login/?next=/admin/")
        driver.find_element_by_id("id_username").click()
        driver.find_element_by_id("id_username").clear()
        driver.find_element_by_id("id_username").send_keys("admin")
        driver.find_element_by_id("id_password").click()
        driver.find_element_by_id("id_password").clear()
        driver.find_element_by_id("id_password").send_keys("flocorlop")
        driver.find_element_by_xpath("//input[@value='Log in']").click()
        driver.find_element_by_link_text("Questions").click()
        driver.find_element_by_class_name("addlink").click()
        driver.find_element_by_id("id_desc").click()
        driver.find_element_by_id("id_desc").clear()
        driver.find_element_by_id("id_desc").send_keys("Test modelo")
        driver.find_element_by_id("id_question_options").click()
        Select(driver.find_element_by_id("id_question_options")).select_by_visible_text("Preference question")
        driver.find_element_by_id("id_question_options").click()
        driver.find_element_by_id("id_options-0-option").click()
        driver.find_element_by_id("id_options-0-option").clear()
        driver.find_element_by_id("id_options-0-option").send_keys("intel")
        driver.find_element_by_id("id_options-0-number").click()
        driver.find_element_by_id("id_options-0-number").clear()
        driver.find_element_by_id("id_options-0-number").send_keys("1")
        driver.find_element_by_id("id_options-1-option").click()
        driver.find_element_by_id("id_options-1-option").clear()
        driver.find_element_by_id("id_options-1-option").send_keys("amd")
        driver.find_element_by_id("id_options-1-number").click()
        driver.find_element_by_id("id_options-1-number").clear()
        driver.find_element_by_id("id_options-1-number").send_keys("2")
        driver.find_element_by_name("_save").click()
    
    def is_element_present(self, how, what):
        try: self.driver.find_element(by=how, value=what)
        except NoSuchElementException as e: return False
        return True
    
    def is_alert_present(self):
        try: self.driver.switch_to_alert()
        except NoAlertPresentException as e: return False
        return True
    
    def close_alert_and_get_its_text(self):
        try:
            alert = self.driver.switch_to_alert()
            alert_text = alert.text
            if self.accept_next_alert:
                alert.accept()
            else:
                alert.dismiss()
            return alert_text
        finally: self.accept_next_alert = True
    
    def tearDown(self):
        self.driver.quit()
        self.assertEqual([], self.verificationErrors)

if __name__ == "__main__":
    unittest.main()
