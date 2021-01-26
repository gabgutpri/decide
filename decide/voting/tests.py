
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

    def create_voting_withTag(self):
        q = Question(desc='test tag')
        tag = "Delegacion"
        q.save()
        for i in range(5):
            opt = QuestionOption(question=q, option='option {}'.format(i+1))
            opt.save()
        v = Voting(name='test voting tag', question=q, tag=tag)
        v.save()
        a, _ = Auth.objects.get_or_create(url=settings.BASEURL,
                                          defaults={'me': True, 'name': 'test auth'})
        a.save()
        v.auths.add(a)
        return v

    def test_voting_withTag(self):
        v = self.create_voting_withTag()
        self.assertEqual(v.tag,'Delegacion')

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

        self.assertEquals(len(v.question.options.all()), 2)
        self.assertEquals(v.question.yes_no_question, True)
        self.assertEquals(v.name, 'Yes/No voting test')
        
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
    def testNOExiste(self):
        v=Voting.objects.get(name="Votacion")
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
    
    def testNoExiste(self):
        vp = Voting.objects.get(name="Votacion de preferencia 1")
        self.assertNotEquals(vp.name,"Votacion de prueba")
        self.assertNotEquals(vp.desc,"Descripcion de prueba")
        self.assertNotEquals(vp.question.desc,"Pregunta de prueba")
        self.assertNotEquals(vp.question.question_options,1)
        self.assertNotEquals(vp.question.options.all()[0].option,"ordenador")
        self.assertNotEquals(vp.question.options.all()[0].number,3)
        self.assertNotEquals(vp.question.options.all()[1].option,"movil")
        self.assertNotEquals(vp.question.options.all()[1].number,4)

class VotacionPrefModelTestCase2(BaseTestCase):

    def setUp(self):
        q=Question(desc="Preferencia de transporte",question_options=2)
        q.save()

        opt1=QuestionOption(number="1", question=q,option='bus')
        opt1.save()

        opt2=QuestionOption(number="2",question=q,option='bici')
        opt2.save()
        
        opt2=QuestionOption(number="3",question=q,option='coche')
        opt2.save()

        vp = Voting(name="Votacion de preferencia movilidad",desc="Transportes",question=q)
        vp.save()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.vp = None
    
    def testExiste(self):
        vp = Voting.objects.get(name="Votacion de preferencia movilidad")
        self.assertEquals(vp.name,"Votacion de preferencia movilidad")
        self.assertEquals(vp.desc,"Transportes")
        self.assertEquals(vp.question.desc,"Preferencia de transporte")
        self.assertEquals(vp.question.question_options,2)
        self.assertEquals(vp.question.options.all()[0].option,"bus")
        self.assertEquals(vp.question.options.all()[0].number,1)
        self.assertEquals(vp.question.options.all()[1].option,"bici")
        self.assertEquals(vp.question.options.all()[1].number,2)
        self.assertEquals(vp.question.options.all()[2].option,"coche")
        self.assertEquals(vp.question.options.all()[2].number,3)

    def testNoExiste(self):
        vp = Voting.objects.get(name="Votacion de preferencia movilidad")
        self.assertNotEquals(vp.name,"Hay una votacion")
        self.assertNotEquals(vp.desc,"Se vota aqui")
        self.assertNotEquals(vp.question.desc,"Vota para el transporte")
        self.assertNotEquals(vp.question.question_options,1)
        self.assertNotEquals(vp.question.options.all()[0].option,"tren")
        self.assertNotEquals(vp.question.options.all()[0].number,2)
        self.assertNotEquals(vp.question.options.all()[1].option,"avion")
        self.assertNotEquals(vp.question.options.all()[1].number,3)
        self.assertNotEquals(vp.question.options.all()[2].option,"ave")
        self.assertNotEquals(vp.question.options.all()[2].number,1)
