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
from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException

import time
import datetime


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

	#Test Gonzalo URL custom
    def create_voting_withurl(self):
        q = Question(desc='test question')
        q.save()
        for i in range(5):
            opt = QuestionOption(question=q, option='option {}'.format(i+1))
            opt.save()
        v = Voting(name='test voting', question=q, link='testurl')
        v.save()

        a, _ = Auth.objects.get_or_create(url=settings.BASEURL,
                                          defaults={'me': True, 'name': 'test auth'})
        a.save()
        v.auths.add(a)

        return v

    def test_complete_voting_withurl(self):
        v = self.create_voting_withurl()
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
			
    def test_create_voting_withurl_from_api(self):
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
            'link': 'urltest',
            'question': 'I want a ',
            'question_opt': ['cat', 'dog', 'horse']
        }

        response = self.client.post('/voting/', data, format='json')
        self.assertEqual(response.status_code, 201)

    #Test Javi
    #Crear votacion con una fecha de finalizacion
    def create_voting_end_date(self):
        q = Question(desc='test end date')
        end = "2025-02-15 14:30:59.792974Z"
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
        self.assertEqual(v.end_date,"2025-02-15 14:30:59.792974Z")

        v.end_date = timezone.now() + timezone.timedelta(minutes=1)
        v.save()

        self.assertEquals(v.name, "test voting end date")
        self.assertEquals(v.question.desc, "test end date")
        self.assertEqual(v.end_date.day, (timezone.now() + timezone.timedelta(minutes=1)).day)
        self.assertEqual(v.end_date.hour, (timezone.now() + timezone.timedelta(minutes=1)).hour)
        self.assertEqual(v.end_date.minute, (timezone.now() + timezone.timedelta(minutes=1)).minute)
        self.assertEqual(v.end_date.second, (timezone.now() + timezone.timedelta(minutes=1)).second)

        v.end_date = timezone.now()
        v.save()

        self.assertEquals(v.name, "test voting end date")
        self.assertEquals(v.question.desc, "test end date")
        self.assertEqual(v.end_date.day, timezone.now().day)
        self.assertEqual(v.end_date.hour, timezone.now().hour)
        self.assertEqual(v.end_date.minute, timezone.now().minute)
        self.assertEqual(v.end_date.second, timezone.now().second)

    #Test de modelo de fecha de finalizacion caso negativo
    #Se guarda una votacion con una fecha pasada
    def test_end_date_modelo_n(self):
        v = self.create_voting_end_date()

        v.end_date = timezone.now() - timezone.timedelta(days=1)
        v.save()
        self.assertRaises(ValidationError, end_date_past, v.end_date)

        v.end_date = timezone.now() - timezone.timedelta(minutes=10)
        v.save()
        self.assertRaises(ValidationError, end_date_past, v.end_date)

        v.end_date = timezone.now() - timezone.timedelta(minutes=1)
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

    # Test del guardado en local de votaciones    
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
        time.sleep(1)
        self.driver.find_element_by_id('id_username').send_keys("practica")
        time.sleep(1)
        self.driver.find_element_by_id('id_password').send_keys("practica", Keys.ENTER)
        time.sleep(1)

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
        time.sleep(1)
        self.driver.find_element(By.CSS_SELECTOR, ".row1:nth-child(1) > .field-name").get_attribute('value')
        self.assertEqual("prueba", driver.find_element(By.CSS_SELECTOR, ".row1:nth-child(1) > .field-name").text)
        time.sleep(1)

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
        time.sleep(1)
        self.driver.find_element(By.ID, "username").click()
        time.sleep(1)
        self.driver.find_element(By.ID, "username").send_keys("practica")
        time.sleep(1)
        self.driver.find_element(By.ID, "password").click()
        time.sleep(1)
        self.driver.find_element(By.ID, "password").send_keys("practica")
        time.sleep(1)
        self.driver.find_element(By.ID, "password").send_keys(Keys.ENTER)
        time.sleep(1)
        self.driver.find_element(By.CSS_SELECTOR, "#\\__BVID__12 .custom-control-label").click()
        time.sleep(1)
        self.driver.find_element(By.CSS_SELECTOR, ".btn:nth-child(4)").click()
        time.sleep(1)
        self.driver.find_element(By.LINK_TEXT, "Logout").click()

    #Test de selenium de la fecha de finalizacion caso negativo
    def test_end_date_n(self):
        driver = self.driver

        #Iniciar sesion
        driver.get("http://localhost:8000/admin/login/?next=/admin/")
        time.sleep(1)
        self.driver.find_element_by_id('id_username').send_keys("practica")
        time.sleep(1)
        self.driver.find_element_by_id('id_password').send_keys("practica", Keys.ENTER)
        time.sleep(1)

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
        driver.get("http://localhost:8000/admin/login/?next=/admin/")
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

        self.assertEquals(len(v.question_op.all()), 2)
        self.assertEquals(v.question.yes_no_question, True)
        self.assertEquals(v.name, 'Yes/No voting test')
        self.assertEquals(v.question.all()[0].option, 'YES')
        self.assertEquals(v.question.all()[1].option, 'NO')
        self.assertEquals(v.question.all()[0].number, 1)
        self.assertEquals(v.question.all()[1].number, 2)
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

    def tearDown(self):
        super().tearDown()
        self.driver.quit()

        self.base.tearDown()

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

    def test_create_yes_no_voting(self):
        driver = self.driver
        # Creation of a super user to being able to create questions
        User.objects.create_superuser('egcVotacion', 'votacion@decide.com', 'egcVotacion')
        driver.get(f'{self.live_server_url}/admin/')
        # Web log in
        driver.find_element_by_id('id_username').send_keys("egcVotacion")
        driver.find_element_by_id('id_password').send_keys("egcVotacion", Keys.ENTER)
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

       # Creation of auth
        driver.get(f'{self.live_server_url}/admin/')
        driver.find_element_by_link_text("Auths").click()
        driver.find_element_by_link_text("Add auth").click()
        driver.find_element(By.ID, "id_name").click()
        driver.find_element(By.ID, "id_name").send_keys("localhost")
        driver.find_element(By.ID, "id_url").click()
        driver.find_element(By.ID, "id_url").send_keys("http://localhost:8000")
        driver.find_element(By.ID, "id_me").click()
        driver.find_element_by_name("_save").click()

        # Creation of a yes/no voting example
        driver.get(f'{self.live_server_url}/admin/')
        driver.find_element_by_link_text("Votings").click()
        driver.find_element_by_link_text("Add voting").click()
        driver.find_element(By.ID, "id_name").send_keys("Votacion de Si/No")
        driver.find_element(By.ID, "id_desc").send_keys("votacion con preguntas de Si")
        self.dropdown = driver.find_element(By.NAME, "question")
        self.dropdown.find_element(By.XPATH, "//option[. = 'Si/No prueba']").click()
        self.dropdown = driver.find_element(By.NAME, "auths")
        self.dropdown.find_element(By.XPATH, "//option[. = 'http://localhost:8000']").click()
        driver.find_element_by_name("_save").click()
        self.assertEqual("Votacion de Si/No", driver.find_element_by_xpath("(//a[contains(text(),'Votacion de Si/No')])[2]").text)
