from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.test import APITestCase

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from base import mods


class AuthTestCase(APITestCase):

    def setUp(self):
        self.client = APIClient()
        mods.mock_query(self.client)
        u = User(username='voter1')
        u.set_password('123')
        u.save()

        u2 = User(username='admin')
        u2.set_password('admin')
        u2.is_superuser = True
        u2.save()

    def tearDown(self):
        self.client = None

    def test_login(self):
        data = {'username': 'voter1', 'password': '123'}
        response = self.client.post('/authentication/login/', data, format='json')
        self.assertEqual(response.status_code, 200)

        token = response.json()
        self.assertTrue(token.get('token'))

    def test_login_fail(self):
        data = {'username': 'voter1', 'password': '321'}
        response = self.client.post('/authentication/login/', data, format='json')
        self.assertEqual(response.status_code, 400)

    def test_getuser(self):
        data = {'username': 'voter1', 'password': '123'}
        response = self.client.post('/authentication/login/', data, format='json')
        self.assertEqual(response.status_code, 200)
        token = response.json()

        response = self.client.post('/authentication/getuser/', token, format='json')
        self.assertEqual(response.status_code, 200)

        user = response.json()
        self.assertEqual(user['id'], 1)
        self.assertEqual(user['username'], 'voter1')

    def test_getuser_invented_token(self):
        token = {'token': 'invented'}
        response = self.client.post('/authentication/getuser/', token, format='json')
        self.assertEqual(response.status_code, 404)

    def test_getuser_invalid_token(self):
        data = {'username': 'voter1', 'password': '123'}
        response = self.client.post('/authentication/login/', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Token.objects.filter(user__username='voter1').count(), 1)

        token = response.json()
        self.assertTrue(token.get('token'))

        response = self.client.post('/authentication/logout/', token, format='json')
        self.assertEqual(response.status_code, 200)

        response = self.client.post('/authentication/getuser/', token, format='json')
        self.assertEqual(response.status_code, 404)

    def test_logout(self):
        data = {'username': 'voter1', 'password': '123'}
        response = self.client.post('/authentication/login/', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Token.objects.filter(user__username='voter1').count(), 1)

        token = response.json()
        self.assertTrue(token.get('token'))

        response = self.client.post('/authentication/logout/', token, format='json')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(Token.objects.filter(user__username='voter1').count(), 0)

    def test_register_bad_permissions(self):
        data = {'username': 'voter1', 'password': '123'}
        response = self.client.post('/authentication/login/', data, format='json')
        self.assertEqual(response.status_code, 200)
        token = response.json()

        token.update({'username': 'user1'})
        response = self.client.post('/authentication/register/', token, format='json')
        self.assertEqual(response.status_code, 401)

    def test_register_bad_request(self):
        data = {'username': 'admin', 'password': 'admin'}
        response = self.client.post('/authentication/login/', data, format='json')
        self.assertEqual(response.status_code, 200)
        token = response.json()

        token.update({'username': 'user1'})
        response = self.client.post('/authentication/register/', token, format='json')
        self.assertEqual(response.status_code, 400)

    def test_register_user_already_exist(self):
        data = {'username': 'admin', 'password': 'admin'}
        response = self.client.post('/authentication/login/', data, format='json')
        self.assertEqual(response.status_code, 200)
        token = response.json()

        token.update(data)
        response = self.client.post('/authentication/register/', token, format='json')
        self.assertEqual(response.status_code, 400)

    def test_register(self):
        data = {'username': 'admin', 'password': 'admin'}
        response = self.client.post('/authentication/login/', data, format='json')
        self.assertEqual(response.status_code, 200)
        token = response.json()

        token.update({'username': 'user1', 'password': 'pwd1'})
        response = self.client.post('/authentication/register/', token, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            sorted(list(response.json().keys())),
            ['token', 'user_pk']
        )
class RegisterGuiTests(TestCase):
#Tests for the Register Form

    #Load up some data for easy access
    def setUp(self) -> None:
        self.username = 'epicTestUser'
        self.email = 'epicTestUser@gmail.com'
        self.first_name = 'Epic'
        self.last_name = 'Test User'

    #Testing the Get Access for the Register Form
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage') 
    def test_register_page_access(self):
        response = self.client.get("/authentication/registergui/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, template_name = 'register.html')

    #Testing a post request with an invalid password
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
    def test_register_form_bad_pass(self):
        response = self.client.post("/authentication/registergui/", data={
            'username' : self.username,
            'email' : self.email,
            'first_name': self.first_name,
            'last_name' : self.last_name,
            'password1' : '123',
            'password2' : '123'
        })
        #The form returns the user to the form in case of a failure
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, template_name = 'register.html')
        #Checking that the user hasn't been created
        self.assertFalse(User.objects.filter(username=self.username).exists())

    #Testing a post request with no username given
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
    def test_register_form_no_user(self):
        response = self.client.post("/authentication/registergui/", data={
            'username' : '',
            'email' : self.email,
            'first_name': self.first_name,
            'last_name' : self.last_name,
            'password1' : '123',
            'password2' : '123'
        })
        #The form returns the user to the form in case of a failure
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, template_name = 'register.html')

    #Testing a succesful post request
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage') 
    def test_register_form(self):
        response = self.client.post("/authentication/registergui/", data={
            'username' : self.username,
            'email' : self.email,
            'first_name': self.first_name,
            'last_name' : self.last_name,
            'password1' : 'ganma421',
            'password2' : 'ganma421'
        })
        #When the form is properly fulfilled it will redirect the users towards the page that ask checking their email
        self.assertEqual(response.status_code, 302)
        
        #We check if the user has been registered to the database
        user = User.objects.get(username=self.username)
        #We use asserts different to the username and check if they correspond to what we have registered with the post request
        self.assertEqual(user.email, self.email)
        self.assertEqual(user.first_name, self.first_name)