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

#imports de pruebas de interfaz
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException


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
        v = Voting(name='test voting',desc='Voting test', question=q)
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

        v.end_date=timezone.now()
        v.tally_votes(self.token)

        tally = v.tally
        tally.sort()
        tally = {k: len(list(x)) for k, x in itertools.groupby(tally)}

        for q in v.question.options.all():
            self.assertEqual(tally.get(q.number, 0), clear.get(q.number, 0))

        for q in v.postproc:
            self.assertEqual(tally.get(q["number"], 0), q["votes"])

        v.saveFile()
        nombre_guardado=str(v.file)
        self.assertEqual(nombre_guardado,'ficheros/'+str(v.id)+'-'+v.name+' - '+v.end_date.strftime('%d-%m-%y')+'.txt')

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
        #response = self.client.post('/voting/{}/'.format(voting.pk), data, format='json')
        #self.assertEqual(response.status_code, 401)

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


    def test_guardar_local(self):    
        voting = self.create_voting()

        self.login()

        # Inicio la votacion
        data = {'action': 'start'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')       

        # Paro la votacion
        data = {'action': 'stop'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')

        # Recuento de la votacion
        data = {'action': 'tally'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')

        # Guardo la votación 
        data = {'action': 'save'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), 'Voting has been saved in local')


    def test_guardar_local_no_admin(self):    
        voting = self.create_voting()

        self.login()

        # Inicio la votacion
        data = {'action': 'start'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')       

        # Paro la votacion
        data = {'action': 'stop'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')

        # Recuento de la votacion
        data = {'action': 'tally'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')

        # Intento guardar la votación logueado con otra cuenta que no se admin 
        self.logout
        self.login(user="noadmin")

        data = {'action': 'save'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 403)


    def test_guardar_local_antes_iniciar(self):
        voting = self.create_voting()

        self.login()

        # Intento guardar antes de empezar la votacion
        data = {'action': 'save'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Voting is not started')


    def test_guardar_local_antes_parar(self):
        voting = self.create_voting()

        self.login()
        
        #Inicio la votacion
        data = {'action': 'start'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')

        # Intento guardar antes de cerrar la votacion
        data = {'action': 'save'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Voting is not stopped')


    def test_guardar_local_antes_recuento(self):
        voting = self.create_voting()

        self.login()

        #Inicio la votacion
        data = {'action': 'start'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')       
        
        #Paro la votacion
        data = {'action': 'stop'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')

        # Intento guardar antes de hacer el recuento de la votacion
        data = {'action': 'save'}
        response = self.client.put('/voting/{}/'.format(voting.pk), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), 'Voting has not being tallied')


class VotingLocalSaveTestCase(StaticLiveServerTestCase):

    def setUp(self):
        self.base=BaseTestCase()
        self.base.setUp()

        options = webdriver.ChromeOptions()
        options.headless = True
        self.driver = webdriver.Chrome(options=options)
        super().setUp()



    # Test selenium de guardar
    def test_guardar(self):
        driver=self.driver
        User.objects.create_superuser('egcVotacion','votacion@decide.com','egcVotacion')

        # Login
        self.driver.get("http://localhost:8000/admin/login/?next=/admin/")
        self.driver.find_element_by_id("id_username").send_keys("egcVotacion")
        self.driver.find_element_by_id("id_password").send_keys("egcVotacion")
        self.driver.find_element_by_id("id_password").send_keys(Keys.ENTER)


        # Añado pregunta
        self.driver.find_element_by_link_text("Questions").click()
        self.driver.find_element_by_link_text("ADD QUESTION").click()
        self.driver.find_element(By.ID, "id_desc").click()
        self.driver.find_element(By.ID, "id_desc").send_keys("pregunta de prueba")
        self.driver.find_element_by_id("id_options-0-option").click()
        self.driver.find_element_by_id("id_options-0-option").send_keys("opcion1")
        self.driver.find_element_by_id("id_options-0-option").click()
        self.driver.find_element(By.ID, "id_options-1-option").send_keys("opcion2")
        self.driver.find_element(By.NAME, "_save").click()

        # Añado auth
        self.driver.get("http://localhost:8000/admin/")
        self.driver.find_element_by_link_text("Auths").click()
        self.driver.find_element_by_link_text("ADD AUTH").click()
        self.driver.find_element(By.ID, "id_name").click()
        self.driver.find_element(By.ID, "id_name").send_keys("localhost")
        self.driver.find_element(By.ID, "id_url").click()
        self.driver.find_element(By.ID, "id_url").send_keys("http://localhost:8000")
        self.driver.find_element(By.ID, "id_me").click()
        self.driver.find_element(By.NAME, "_save").click()

        # Añado votacion
        self.driver.get("http://localhost:8000/admin/")
        self.driver.find_element_by_link_text("Votings").click()
        self.driver.find_element_by_link_text("ADD VOTING").click()
        self.driver.find_element(By.ID, "id_name").send_keys("prueba")
        self.driver.find_element(By.ID, "id_desc").send_keys("descripcion de prueba")
        dropdown = self.driver.find_element(By.NAME, "question")
        dropdown.find_element(By.XPATH, "//option[. = 'pregunta de prueba']").click()
        Select(driver.find_element(By.ID,"id_auths")).select_by_visible_text("http://localhost:8000")
        self.driver.find_element(By.NAME, "_save").click()


        # Inicio votacion
        self.driver.get("http://localhost:8000/admin/")
        self.driver.find_element_by_link_text("Votings").click()
        self.driver.find_element(By.NAME, "_selected_action").click()
        dropdown = self.driver.find_element(By.NAME, "action")
        dropdown.find_element(By.XPATH, "//option[. = 'Start']").click()
        self.driver.find_element(By.NAME, "index").click()

        #Termino votacion
        self.driver.find_element(By.NAME, "_selected_action").click()
        dropdown = self.driver.find_element(By.NAME, "action")
        dropdown.find_element(By.XPATH, "//option[. = 'Stop']").click()
        self.driver.find_element(By.NAME, "index").click()

        #Recuento de votacion
        self.driver.find_element(By.NAME, "_selected_action").click()
        dropdown = self.driver.find_element(By.NAME, "action")
        dropdown.find_element(By.XPATH, "//option[. = 'Tally']").click()
        self.driver.find_element(By.NAME, "index").click()
       
        # Accedo a la votacion 
        self.driver.find_element(By.LINK_TEXT, "prueba").click()
        # Compruebo que está vacío el campo
        self.assertEqual("",self.driver.find_element(By.CSS_SELECTOR, ".field-file .readonly").text)
        
        # Guardo la votacion
        self.driver.find_element(By.LINK_TEXT, "Votings").click()
        self.driver.find_element(By.NAME, "_selected_action").click()
        dropdown = self.driver.find_element(By.NAME, "action")
        dropdown.find_element(By.XPATH, "//option[. = 'Save']").click()
        self.driver.find_element(By.NAME, "action").click()
        self.driver.find_element(By.NAME, "index").click()
        
        # Accedo a la votacion
        self.driver.find_element(By.LINK_TEXT, "prueba").click()
        # Compruebo que se ha guardado
        self.assertNotEqual("",self.driver.find_element(By.CSS_SELECTOR, ".field-file .readonly").text)

        # Borro la votacion
        self.driver.find_element(By.LINK_TEXT,"Delete").click()
        self.driver.find_element(By.XPATH,"//input[@value=\"Yes, I'm sure\"]").click()

        # Borro la pregunta
        self.driver.get("http://localhost:8000/admin/voting/")
        self.driver.find_element_by_link_text("Questions").click()
        self.driver.find_element(By.NAME, "_selected_action").click()
        dropdown = self.driver.find_element(By.NAME, "action").click()
        self.driver.find_element(By.XPATH, "//option[. = 'Delete selected questions']").click()
        self.driver.find_element(By.NAME, "action").click()
        self.driver.find_element(By.NAME, "index").click()
        self.driver.find_element(By.XPATH,"//input[@value=\"Yes, I'm sure\"]").click()

        # Borro el auth
        self.driver.get("http://localhost:8000/admin/base/auth/")
        self.driver.find_element(By.NAME, "_selected_action").click()
        dropdown = self.driver.find_element(By.NAME, "action").click()
        self.driver.find_element(By.XPATH, "//option[. = 'Delete selected auths']").click()
        self.driver.find_element(By.NAME, "action").click()
        self.driver.find_element(By.NAME, "index").click()
        self.driver.find_element(By.XPATH,"//input[@value=\"Yes, I'm sure\"]").click()

        

    def tearDown(self):
        super().tearDown()
        self.driver.quit()

        self.base.tearDown()
