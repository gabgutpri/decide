import random
import itertools
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.test import APITestCase
from django.core.exceptions import ValidationError

from base import mods
from base.tests import BaseTestCase
from census.models import Census
from mixnet.mixcrypt import ElGamal
from mixnet.mixcrypt import MixCrypt
from mixnet.models import Auth
from voting.models import Voting, Question, QuestionOption, end_date_past
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time

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

    #Test Javi
    #Crear votacion con una fecha de finalizacion
    def create_voting_end_date(self):
        q = Question(desc='test end date')
        end = "2025-02-15 14:30:59.993048Z"
        q.save()
        for i in range(5):
            opt = QuestionOption(question=q, option='option {}'.format(i+1))
            opt.save()
        v = Voting(name='test voting end date', question=q, end_date=end)
        v.save()
        a, _ = Auth.objects.get_or_create(url=settings.BASEURL,
                                          defaults={'me': True, 'name': 'test auth'})
        a.save()
        v.auths.add(a)
        return v

    #Test de modelo de fecha de finalizacion caso positivo
    #Se guarda una votacion con parametros correctos
    def test_end_date_modelo_p(self):
        v = self.create_voting_end_date()

        self.assertEquals(v.name, "test voting end date")
        self.assertEquals(v.question.desc, "test end date")
        self.assertEqual(v.end_date,"2025-02-15 14:30:59.993048Z")

    #Test de modelo de fecha de finalizacion caso negativo
    #Se guarda una votacion con una fecha pasada
    def test_end_date_modelo_n(self):
        v = self.create_voting_end_date()
        v.end_date = timezone.now() - timezone.timedelta(days=1)
        v.save()
        self.assertRaises(ValidationError, end_date_past, v.end_date)

    #Test de modelo de la restriccion end_date_past caso positivo
    #Se comprueba que la restriccion no devuelve ninguna excepcion cuando recibe fechas correctas
    def test_end_date_past_p(self):
        raised = False
        try:
            f = timezone.now() + timezone.timedelta(minutes=1)
            end_date_past(f)
            f = timezone.now() + timezone.timedelta(minutes=10)
            end_date_past(f)
            f = timezone.now() + timezone.timedelta(days=1)
            end_date_past(f)
            f = timezone.now() + timezone.timedelta(days=10)
            end_date_past(f)
        except:
            raised = True
        self.assertFalse(raised, 'Exception raised')

    #Test de modelo de la restriccion end_date_past caso negativo
    #Se comprueba que la restriccion devuelve un ValidationError cuando recibe fechas pasadas
    def test_end_date_past_n(self):
        f = timezone.now() - timezone.timedelta(days=10)
        self.assertRaises(ValidationError, end_date_past, f)
        f = timezone.now() - timezone.timedelta(days=1)
        self.assertRaises(ValidationError, end_date_past, f)
        f = timezone.now() - timezone.timedelta(minutes=10)
        self.assertRaises(ValidationError, end_date_past, f)
        f = timezone.now() - timezone.timedelta(minutes=1)
        self.assertRaises(ValidationError, end_date_past, f)

class EndDateTestCase(StaticLiveServerTestCase):

    def setUp(self):
        self.base=BaseTestCase()
        self.base.setUp()

        options = webdriver.ChromeOptions()
        options.headless = True
        self.driver = webdriver.Chrome(options=options)
        self.vars = {}

        super().setUp()

    def wait_for_window(self, timeout = 2):
        time.sleep(round(timeout / 1000))
        wh_now = self.driver.window_handles
        wh_then = self.vars["window_handles"]
        if len(wh_now) > len(wh_then):
            return set(wh_now).difference(set(wh_then)).pop()      

    #Test de selenium de la fecha de finalizacion caso positivo
    def test_end_date_p(self):
        driver = self.driver
        
        #Iniciar sesion
        driver.get("http://localhost:8000/admin/login/?next=/admin/")
        self.driver.find_element_by_id('id_username').send_keys("practica")
        self.driver.find_element_by_id('id_password').send_keys("practica", Keys.ENTER)

        #Crear auths
        self.driver.find_element_by_link_text("Auths").click()
        self.driver.find_element_by_link_text("AÑADIR AUTH").click()
        self.driver.find_element(By.ID, "id_name").click()
        self.driver.find_element(By.ID, "id_name").send_keys("localhost")
        self.driver.find_element(By.ID, "id_url").click()
        self.driver.find_element(By.ID, "id_url").send_keys("http://localhost:8000")
        self.driver.find_element(By.ID, "id_me").click()
        self.driver.find_element(By.NAME, "_save").click()

        #Crear votacion
        self.driver.get("http://localhost:8000/admin/")
        driver.find_element_by_link_text("Votings").click()
        driver.find_element_by_link_text("AÑADIR VOTING").click()
        self.driver.find_element(By.ID, "id_name").click()
        self.driver.find_element(By.ID, "id_name").send_keys("prueba")
        self.driver.find_element(By.ID, "id_desc").click()
        self.driver.find_element(By.ID, "id_desc").send_keys("prueba")

        #Crear question dentro de crear votacion
        self.driver.find_element(By.CSS_SELECTOR, ".field-question .related-widget-wrapper").click()
        self.vars["window_handles"] = self.driver.window_handles
        self.driver.find_element(By.CSS_SELECTOR, "#add_id_question > img").click()
        self.vars["win8304"] = self.wait_for_window(2000)
        self.vars["root"] = self.driver.current_window_handle
        self.driver.switch_to.window(self.vars["win8304"])
        self.driver.find_element(By.ID, "id_desc").send_keys("prueba")
        self.driver.find_element(By.ID, "id_options-0-number").send_keys("1")
        self.driver.find_element(By.ID, "id_options-0-number").click()
        self.driver.find_element(By.ID, "id_options-1-number").send_keys("2")
        self.driver.find_element(By.ID, "id_options-1-number").click()
        self.driver.find_element(By.ID, "id_options-0-option").click()
        self.driver.find_element(By.ID, "id_options-0-option").send_keys("prueba 1")
        self.driver.find_element(By.ID, "id_options-1-option").click()
        self.driver.find_element(By.ID, "id_options-1-option").send_keys("prueba 2")
        self.driver.find_element(By.NAME, "_save").click()
        self.driver.switch_to.window(self.vars["root"])
        self.driver.find_element(By.LINK_TEXT, "Hoy").click()
        self.driver.find_element(By.ID, "id_end_date_1").click()
        self.driver.find_element(By.ID, "id_end_date_1").send_keys("23:50:00")

        #Seleccionar auth
        dropdown = self.driver.find_element(By.ID, "id_auths")
        dropdown.find_element(By.XPATH, "//option[. = 'http://localhost:8000']").click()

        #Guardar la votacion
        self.driver.find_element(By.NAME, "_save").click()

        #Iniciar la votacion
        self.driver.find_element(By.NAME, "_selected_action").click()
        dropdown = self.driver.find_element(By.NAME, "action")
        dropdown.find_element(By.XPATH, "//option[. = 'Start']").click()
        element = self.driver.find_element(By.NAME, "action")
        actions = ActionChains(self.driver)
        actions.move_to_element(element).click_and_hold().perform()
        element = self.driver.find_element(By.NAME, "action")
        actions = ActionChains(self.driver)
        actions.move_to_element(element).perform()
        element = self.driver.find_element(By.NAME, "action")
        actions = ActionChains(self.driver)
        actions.move_to_element(element).release().perform()
        self.driver.find_element(By.NAME, "action").click()
        self.driver.find_element(By.NAME, "index").click()

        #Crear censo
        driver.get("http://localhost:8000/admin/login/?next=/admin/")
        driver.find_element_by_link_text("Censuss").click()
        driver.find_element_by_link_text("AÑADIR CENSUS").click()
        self.driver.find_element(By.ID, "id_voting_id").click()
        self.driver.find_element(By.ID, "id_voting_id").send_keys("1")
        self.driver.find_element(By.ID, "id_voter_id").click()
        self.driver.find_element(By.ID, "id_voter_id").send_keys("1")
        self.driver.find_element(By.NAME, "_save").click()

        #Realizar la votacion
        driver.get("http://localhost:8000/booth/1")
        self.driver.find_element(By.ID, "username").click()
        self.driver.find_element(By.ID, "username").send_keys("practica")
        self.driver.find_element(By.ID, "password").click()
        self.driver.find_element(By.ID, "password").send_keys("practica")
        self.driver.find_element(By.ID, "password").send_keys(Keys.ENTER)
        self.driver.find_element(By.CSS_SELECTOR, "#\\__BVID__12 .custom-control-label").click()

        #Cerrar sesion
        self.driver.find_element(By.CSS_SELECTOR, ".btn:nth-child(4)").click()
        self.driver.find_element(By.LINK_TEXT, "Logout").click()

    #Test de selenium de la fecha de finalizacion caso negativo
    def test_end_date_n(self):
        driver = self.driver

        #Iniciar sesion
        driver.get("http://localhost:8000/admin/login/?next=/admin/")
        self.driver.find_element_by_id('id_username').send_keys("practica")
        self.driver.find_element_by_id('id_password').send_keys("practica", Keys.ENTER)

        #Crear auths
        self.driver.find_element_by_link_text("Auths").click()
        self.driver.find_element_by_link_text("AÑADIR AUTH").click()
        self.driver.find_element(By.ID, "id_name").click()
        self.driver.find_element(By.ID, "id_name").send_keys("localhost")
        self.driver.find_element(By.ID, "id_url").click()
        self.driver.find_element(By.ID, "id_url").send_keys("http://localhost:8000")
        self.driver.find_element(By.ID, "id_me").click()
        self.driver.find_element(By.NAME, "_save").click()

        #Crear votacion
        driver.find_element_by_link_text("Votings").click()
        driver.find_element_by_link_text("AÑADIR VOTING").click()
        self.driver.find_element(By.ID, "id_name").click()
        self.driver.find_element(By.ID, "id_name").send_keys("prueba")
        self.driver.find_element(By.ID, "id_desc").click()
        self.driver.find_element(By.ID, "id_desc").send_keys("prueba")

        #Crear question
        self.driver.find_element(By.CSS_SELECTOR, ".field-question .related-widget-wrapper").click()
        self.vars["window_handles"] = self.driver.window_handles
        self.driver.find_element(By.CSS_SELECTOR, "#add_id_question > img").click()
        self.vars["win8304"] = self.wait_for_window(2000)
        self.vars["root"] = self.driver.current_window_handle
        self.driver.switch_to.window(self.vars["win8304"])
        self.driver.find_element(By.ID, "id_desc").send_keys("prueba")
        self.driver.find_element(By.ID, "id_options-0-number").send_keys("1")
        self.driver.find_element(By.ID, "id_options-0-number").click()
        self.driver.find_element(By.ID, "id_options-1-number").send_keys("2")
        self.driver.find_element(By.ID, "id_options-1-number").click()
        self.driver.find_element(By.ID, "id_options-0-option").click()
        self.driver.find_element(By.ID, "id_options-0-option").send_keys("prueba 1")
        self.driver.find_element(By.ID, "id_options-1-option").click()
        self.driver.find_element(By.ID, "id_options-1-option").send_keys("prueba 2")
        self.driver.find_element(By.NAME, "_save").click()
        self.driver.switch_to.window(self.vars["root"])
        self.driver.find_element(By.LINK_TEXT, "Hoy").click()
        self.driver.find_element(By.ID, "id_end_date_1").click()
        self.driver.find_element(By.ID, "id_end_date_1").send_keys("00:10:00")

        #Seleccionar auth
        dropdown = self.driver.find_element(By.ID, "id_auths")
        dropdown.find_element(By.XPATH, "//option[. = 'http://localhost:8000']").click()

        #Guardar la votacion
        self.driver.find_element(By.NAME, "_save").click()
        
        #Comprobar que no se ha aceptado el guardado y sigue en la pagina de creacion
        p = driver.find_element(By.ID, "id_name")
        self.assertEqual("prueba", p.get_attribute('value'))
        d = driver.find_element(By.ID, "id_desc")
        self.assertEqual("prueba", d.get_attribute('value'))

        #Cerrar sesion
        self.driver.find_element(By.CSS_SELECTOR, "a:nth-child(4)").click()

    def tearDown(self):           
        super().tearDown()
        self.driver.quit()
        self.base.tearDown()