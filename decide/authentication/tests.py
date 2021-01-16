from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.test import APITestCase

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.contrib.messages import get_messages  

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


class EditProfileTests(TestCase):

    #Creamos usuarios de prueba que usaremos
    def setUp(self) -> None:
        usertest = User(username="testouser", password="password1234", first_name= "pablo", last_name= "elro bot", email="testouseremail@gmail.com",is_active=True)
        usertest.save()
        self.username = 'testouser'
        self.email = 'testuseremail@gmail.com'
        self.first_name = 'pablo'
        self.last_name = 'elro bot'
        self.is_active = True
        
        login = self.client.force_login(usertest)

         #Probamos que puede acceder a su página de perfil
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage') 
    def test_profile_access(self):
        response = self.client.get("/authentication/profile/testouser")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, template_name = 'user_profile.html')

        #Probamos que no se puede acceder al perfil personal de otra persona
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage') 
    def test_profile_access(self):
        usertest2 = User(username="testouser2", password="password1234", first_name= "pablo2", last_name= "elrom bot", email="testouseremail2@gmail.com",is_active=True)
        usertest2.save()
        response = self.client.get("/authentication/profile/testouser2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'You are not authorized to see this page.')

    #Probamos que cuando se introduzca un username vacio, el username no se actualice
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
    def test_update_empty_username(self):
        usertest2 = User(username="testouser2", password="password1234", first_name= "paco", last_name= "elroa bot", email="testouseremail2@gmail.com",is_active=True)
        usertest2.save()
        self.username = 'testouser2'
        self.email = 'testuseremail2@gmail.com'
        self.first_name = 'paco'
        self.last_name = 'elroa bot'
        self.is_active = True
        login = self.client.force_login(usertest2)
        response = self.client.post("/authentication/editprofile/testouser2", follow=True, data={
            'username' : '',
            'email' : self.email,
            'first_name': self.first_name,
            'last_name' : self.last_name,
        })
        usertest2.refresh_from_db()
        #Comprobamos que el username sigue siendo el mismo
        self.assertEqual(response.status_code, 200)
        self.assertEqual(usertest2.username, "testouser2")
        self.assertTemplateUsed(response, template_name = 'edit_user_profile.html')
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'El nombre de usuario no puede estar vacío.')

    #Probamos que cuando se introduzca un username ya existente, el username no se actualice
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
    def test_taken_username(self):
        usertest2 = User(username="testouser2", password="password1234", first_name= "paco", last_name= "elroa bot", email="testouseremail2@gmail.com",is_active=True)
        usertest2.save()
        self.username = 'testouser2'
        self.email = 'testuseremail2@gmail.com'
        self.first_name = 'paco'
        self.last_name = 'elroa bot'
        self.is_active = True
        login = self.client.force_login(usertest2)
        response = self.client.post("/authentication/editprofile/testouser2", follow=True, data={
            'username' : 'testouser',
            'email' : self.email,
            'first_name': self.first_name,
            'last_name' : self.last_name,
        })
        usertest2.refresh_from_db()
        #Comprobamos que el username sigue siendo el mismo
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.username, "testouser2")
        self.assertTemplateUsed(response, template_name = 'edit_user_profile.html')
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'El nombre de usuario ya está en uso.')
    
    #Probamos que el perfil se actualiza correctamente
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
    def test_update_user(self):
        usertest2 = User(username="testouser2", password="password1234", first_name= "paco", last_name= "elroa bot", email="testouseremail2@gmail.com",is_active=True)
        usertest2.save()
        self.username = 'testouser2'
        self.email = 'testuseremail2@gmail.com'
        self.first_name = 'paco'
        self.last_name = 'elroa bot'
        self.is_active = True
        
        login = self.client.force_login(usertest2)
        response = self.client.post("/authentication/editprofile/testouser2", follow=True, data={
            'username' : 'exito',
            'email' : self.email,
            'first_name': 'prueba',
            'last_name' : 'su perada'
        })
        usertest2.refresh_from_db()
        #Comprobamos que se ha actualizado correctamente
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, template_name = 'user_profile.html')
        self.assertEqual(usertest2.username, "exito")
        self.assertEqual(usertest2.email, 'testuseremail2@gmail.com')
        self.assertEqual(usertest2.first_name, 'prueba')
        self.assertEqual(usertest2.last_name, 'su perada')

    #Probamos que no se puede acceder a la página de edición de perfil de otra persona
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage') 
    def test_profile_access(self):
        usertest2 = User(username="testouser2", password="password1234", first_name= "pablo2", last_name= "elrom bot", email="testouseremail2@gmail.com",is_active=True)
        usertest2.save()
        response = self.client.get("/authentication/editprofile/testouser2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'You are not authorized to see this page.')
   