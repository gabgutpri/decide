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
from base.tests import BaseTestCase
from mixnet.models import Auth

import time
import datetime

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
        self.driver.find_element_by_id('id_username').send_keys("decide")
        time.sleep(1)
        self.driver.find_element_by_id('id_password').send_keys("decide1234", Keys.ENTER)
        time.sleep(1)

        #Crear auths
        self.driver.find_element_by_link_text("Auths").click()
        self.driver.find_element_by_link_text("AÑADIR AUTH").click()
        self.driver.find_element(By.ID, "id_name").click()
        self.driver.find_element(By.ID, "id_name").send_keys("localhostEndDateP")
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
        self.driver.find_element(By.ID, "username").send_keys("decide")
        time.sleep(1)
        self.driver.find_element(By.ID, "password").click()
        time.sleep(1)
        self.driver.find_element(By.ID, "password").send_keys("decide1234")
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
        self.driver.find_element_by_id('id_username').send_keys("decide")
        time.sleep(1)
        self.driver.find_element_by_id('id_password').send_keys("decide1234", Keys.ENTER)
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

        # Login
        self.driver.get("http://localhost:8000/admin/login/?next=/admin/")
        self.driver.find_element_by_id("id_username").send_keys("decide")
        self.driver.find_element_by_id("id_password").send_keys("decide1234")
        time.sleep(1)
        self.driver.find_element_by_id("id_password").send_keys(Keys.ENTER)
        time.sleep(1)


        # Añado pregunta
        self.driver.find_element_by_link_text("Questions").click()
        time.sleep(1)
        self.driver.find_element_by_link_text("AÑADIR QUESTION").click()
        time.sleep(1)
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
        self.driver.find_element_by_link_text("AÑADIR AUTH").click()
        self.driver.find_element(By.ID, "id_name").click()
        self.driver.find_element(By.ID, "id_name").send_keys("localhostSave")
        self.driver.find_element(By.ID, "id_url").click()
        self.driver.find_element(By.ID, "id_url").send_keys("http://localhost:8000")
        self.driver.find_element(By.ID, "id_me").click()
        self.driver.find_element(By.NAME, "_save").click()

        # Añado votacion
        self.driver.get("http://localhost:8000/admin/")
        self.driver.find_element_by_link_text("Votings").click()
        self.driver.find_element_by_link_text("AÑADIR VOTING").click()
        self.driver.find_element(By.ID, "id_name").send_keys("prueba")
        self.driver.find_element(By.ID, "id_desc").send_keys("descripcion de prueba")
        dropdown = self.driver.find_element(By.NAME, "question")
        dropdown.find_element(By.XPATH, "//option[. = 'pregunta de prueba']").click()
        #Select(driver.find_element(By.ID,"id_auths")).select_by_visible_text("http://localhost:8000")
        dropdown = self.driver.find_element(By.ID, "id_auths")
        dropdown.find_element(By.XPATH, "//option[. = 'http://localhost:8000']").click()
        self.driver.find_element(By.NAME, "_save").click()


        # Inicio votacion
        self.driver.get("http://localhost:8000/admin/")
        self.driver.find_element_by_link_text("Votings").click()
        self.driver.find_element(By.NAME, "_selected_action").click()
        dropdown = self.driver.find_element(By.NAME, "action")
        dropdown.find_element(By.XPATH, "//option[. = 'Start']").click()
        self.driver.find_element(By.NAME, "index").click()
        time.sleep(10)
        #Termino votacion
        self.driver.find_element(By.NAME, "_selected_action").click()
        dropdown = self.driver.find_element(By.NAME, "action")
        dropdown.find_element(By.XPATH, "//option[. = 'Stop']").click()
        self.driver.find_element(By.NAME, "index").click()
        time.sleep(10)
        #Recuento de votacion
        self.driver.find_element(By.NAME, "_selected_action").click()
        dropdown = self.driver.find_element(By.NAME, "action")
        dropdown.find_element(By.XPATH, "//option[. = 'Tally']").click()
        self.driver.find_element(By.NAME, "index").click()
        time.sleep(10)
       
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

    def tearDown(self):
        super().tearDown()
        self.driver.quit()

        self.base.tearDown()

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
        self.driver.get("http://localhost:8000/admin/login/?next=/admin/")
        # Web log in
        self.driver.find_element_by_id('id_username').send_keys("decide")
        self.driver.find_element_by_id('id_password').send_keys("decide1234", Keys.ENTER)
        time.sleep(3)


        # Access to add question form
        driver.find_element_by_link_text("Questions").click()
        time.sleep(1)
        driver.find_element_by_link_text("AÑADIR QUESTION").click()
        time.sleep(1)

        # Creation of a yes/no question example
        driver.find_element_by_id('id_desc').send_keys("Si/No prueba")
        driver.find_element_by_id('id_yes_no_question').click()
        #driver.find_element_by_xpath("//form[@id='question_form']/div/fieldset/div[3]/div/label").click()
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
        self.driver.get("http://localhost:8000/admin/login/?next=/admin/")
        # Web log in
        self.driver.find_element_by_id('id_username').send_keys("decide")
        self.driver.find_element_by_id('id_password').send_keys("decide1234", Keys.ENTER)
        time.sleep(3)

        # Access to add question form
        driver.find_element_by_link_text("Questions").click()
        time.sleep(1)
        driver.find_element_by_link_text("AÑADIR QUESTION").click()
        time.sleep(1)

        # Creation of a yes/no question example with extra answers
        driver.find_element_by_id('id_desc').send_keys("Si/No prueba con extra")
        driver.find_element_by_id('id_yes_no_question').click()
        #driver.find_element_by_xpath("//form[@id='question_form']/div/fieldset/div[3]/div/label").click()
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
        self.driver.get("http://localhost:8000/admin/login/?next=/admin/")
        # Web log in
        driver.find_element_by_id('id_username').send_keys("decide")
        driver.find_element_by_id('id_password').send_keys("decide1234", Keys.ENTER)
        time.sleep(3)

        # Access to add question form
        driver.find_element_by_link_text("Questions").click()
        time.sleep(1)
        driver.find_element_by_link_text("AÑADIR QUESTION").click()
        time.sleep(1)

        # Creation of a yes/no question example
        driver.find_element_by_id('id_desc').send_keys("Si/No prueba")
        driver.find_element_by_id('id_yes_no_question').click()
        #driver.find_element_by_xpath("//form[@id='question_form']/div/fieldset/div[3]/div/label").click()
        driver.find_element_by_name("_save").click()
        time.sleep(3)

       # Creation of auth
        self.driver.get("http://localhost:8000/admin")
        driver.find_element_by_link_text("Auths").click()
        driver.find_element_by_link_text("AÑADIR AUTH").click()
        driver.find_element(By.ID, "id_name").click()
        driver.find_element(By.ID, "id_name").send_keys("localhostYesNo")
        driver.find_element(By.ID, "id_url").click()
        driver.find_element(By.ID, "id_url").send_keys("http://localhost:8000")
        driver.find_element(By.ID, "id_me").click()
        driver.find_element_by_name("_save").click()

        # Creation of a yes/no voting example
        self.driver.get("http://localhost:8000/admin")
        driver.find_element_by_link_text("Votings").click()
        driver.find_element_by_link_text("AÑADIR VOTING").click()
        driver.find_element(By.ID, "id_name").send_keys("Votacion de Si/No")
        driver.find_element(By.ID, "id_desc").send_keys("votacion con preguntas de Si")
        self.dropdown = driver.find_element(By.NAME, "question")
        self.dropdown.find_element(By.XPATH, "//option[. = 'Si/No prueba']").click()
        self.dropdown = driver.find_element(By.NAME, "auths")
        self.dropdown.find_element(By.XPATH, "//option[. = 'http://localhost:8000']").click()
        driver.find_element_by_name("_save").click()
        self.assertEqual("Votacion de Si/No", driver.find_element_by_xpath("(//a[contains(text(),'Votacion de Si/No')])[2]").text)

class TestQues(StaticLiveServerTestCase):
    def setUp(self):
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
    
    def test_ques(self):
        driver = self.driver
        driver.get("http://localhost:8000/admin/login/?next=/admin/")
        driver.find_element_by_id("id_username").click()
        driver.find_element_by_id("id_username").clear()
        driver.find_element_by_id("id_username").send_keys("decide")
        driver.find_element_by_id("id_password").click()
        driver.find_element_by_id("id_password").clear()
        driver.find_element_by_id("id_password").send_keys("decide1234", Keys.ENTER)
        #driver.find_element_by_xpath("//input[@value='Log in']").click()
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
        self.assertEqual("Test modelo",  self.driver.find_element(By.LINK_TEXT, "Test modelo").text)
 
class TestQues2(StaticLiveServerTestCase):
    def setUp(self):
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
    
    def test_ques2(self):
        driver = self.driver
        driver.get("http://localhost:8000/admin/login/?next=/admin/")
        driver.find_element_by_id("id_username").click()
        driver.find_element_by_id("id_username").clear()
        driver.find_element_by_id("id_username").send_keys("decide")
        driver.find_element_by_id("id_password").click()
        driver.find_element_by_id("id_password").clear()
        driver.find_element_by_id("id_password").send_keys("decide1234", Keys.ENTER)
        #driver.find_element_by_xpath("//input[@value='Log in']").click()
        driver.find_element_by_link_text("Questions").click()
        driver.find_element_by_class_name("addlink").click()
        driver.find_element_by_id("id_desc").click()
        driver.find_element_by_id("id_desc").clear()
        driver.find_element_by_id("id_desc").send_keys("Test modelo 2")
        driver.find_element_by_id("id_question_options").click()
        Select(driver.find_element_by_id("id_question_options")).select_by_visible_text("Preference question")
        driver.find_element_by_id("id_question_options").click()
        driver.find_element_by_id("id_options-0-option").click()
        driver.find_element_by_id("id_options-0-option").clear()
        driver.find_element_by_id("id_options-0-option").send_keys("apple")
        driver.find_element_by_id("id_options-0-number").click()
        driver.find_element_by_id("id_options-0-number").clear()
        driver.find_element_by_id("id_options-0-number").send_keys("1")
        driver.find_element_by_id("id_options-1-option").click()
        driver.find_element_by_id("id_options-1-option").clear()
        driver.find_element_by_id("id_options-1-option").send_keys("android")
        driver.find_element_by_id("id_options-1-number").click()
        driver.find_element_by_id("id_options-1-number").clear()
        driver.find_element_by_id("id_options-1-number").send_keys("2")
        driver.find_element_by_id("id_options-2-option").click()
        driver.find_element_by_id("id_options-2-option").clear()
        driver.find_element_by_id("id_options-2-option").send_keys("microsoft")
        driver.find_element_by_id("id_options-2-number").click()
        driver.find_element_by_id("id_options-2-number").clear()
        driver.find_element_by_id("id_options-2-number").send_keys("3")
        driver.find_element_by_name("_save").click()
        self.assertEqual("Test modelo 2",  self.driver.find_element(By.LINK_TEXT, "Test modelo 2").text)

class TestQues2(StaticLiveServerTestCase):
    def setUp(self):
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
    
    def test_ques2(self):
        driver = self.driver
        driver.get("http://localhost:8000/admin/login/?next=/admin/")
        driver.find_element_by_id("id_username").click()
        driver.find_element_by_id("id_username").clear()
        driver.find_element_by_id("id_username").send_keys("decide")
        driver.find_element_by_id("id_password").click()
        driver.find_element_by_id("id_password").clear()
        driver.find_element_by_id("id_password").send_keys("decide1234", Keys.ENTER)
        #driver.find_element_by_xpath("//input[@value='Log in']").click()
        driver.find_element_by_link_text("Questions").click()
        driver.find_element_by_class_name("addlink").click()
        driver.find_element_by_id("id_desc").click()
        driver.find_element_by_id("id_desc").clear()
        driver.find_element_by_id("id_desc").send_keys("Test modelo 2")
        driver.find_element_by_id("id_question_options").click()
        Select(driver.find_element_by_id("id_question_options")).select_by_visible_text("Preference question")
        driver.find_element_by_id("id_question_options").click()
        driver.find_element_by_id("id_options-0-option").click()
        driver.find_element_by_id("id_options-0-option").clear()
        driver.find_element_by_id("id_options-0-option").send_keys("apple")
        driver.find_element_by_id("id_options-0-number").click()
        driver.find_element_by_id("id_options-0-number").clear()
        driver.find_element_by_id("id_options-0-number").send_keys("1")
        driver.find_element_by_id("id_options-1-option").click()
        driver.find_element_by_id("id_options-1-option").clear()
        driver.find_element_by_id("id_options-1-option").send_keys("android")
        driver.find_element_by_id("id_options-1-number").click()
        driver.find_element_by_id("id_options-1-number").clear()
        driver.find_element_by_id("id_options-1-number").send_keys("2")
        driver.find_element_by_id("id_options-2-option").click()
        driver.find_element_by_id("id_options-2-option").clear()
        driver.find_element_by_id("id_options-2-option").send_keys("microsoft")
        driver.find_element_by_id("id_options-2-number").click()
        driver.find_element_by_id("id_options-2-number").clear()
        driver.find_element_by_id("id_options-2-number").send_keys("3")
        driver.find_element_by_name("_save").click()
        self.assertEqual("Test modelo 2",  self.driver.find_element(By.LINK_TEXT, "Test modelo 2").text)

class TestCrearvotacion(StaticLiveServerTestCase):
    def setUp(self):
        self.base = BaseTestCase()
        self.base.setUp()

        options = webdriver.ChromeOptions()
        options.headless = True
        self.driver = webdriver.Chrome(options=options)
        self.vars = {}

        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.driver.quit()

        self.base.tearDown() 
    
    def wait_for_window(self, timeout = 2):
        time.sleep(round(timeout / 1000))
        wh_now = self.driver.window_handles
        wh_then = self.vars["window_handles"]
        if len(wh_now) > len(wh_then):
            return set(wh_now).difference(set(wh_then)).pop()
    
    def test_check_custom_url(self):
        driver = self.driver

        #Iniciar sesion
        driver.get("http://localhost:8000/admin/login/?next=/admin/")
        time.sleep(1)
        self.driver.find_element_by_id('id_username').send_keys("decide")
        time.sleep(1)
        self.driver.find_element_by_id('id_password').send_keys("decide1234", Keys.ENTER)
        time.sleep(1)

        #Crear auths
        self.driver.find_element_by_link_text("Auths").click()
        self.driver.find_element_by_link_text("AÑADIR AUTH").click()
        self.driver.find_element(By.ID, "id_name").click()
        self.driver.find_element(By.ID, "id_name").send_keys("localhostCustom")
        self.driver.find_element(By.ID, "id_url").click()
        self.driver.find_element(By.ID, "id_url").send_keys("http://localhost:8000")
        self.driver.find_element(By.ID, "id_me").click()
        self.driver.find_element(By.NAME, "_save").click()

        #Crear votacion
        driver.get("http://localhost:8000/admin/login/?next=/admin/")
        driver.find_element_by_link_text("Votings").click()
        driver.find_element_by_link_text("AÑADIR VOTING").click()
        self.driver.find_element(By.ID, "id_name").click()
        self.driver.find_element(By.ID, "id_name").send_keys("prueba link")
        self.driver.find_element(By.ID, "id_desc").click()
        self.driver.find_element(By.ID, "id_desc").send_keys("prueba link")

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
        
        self.driver.find_element(By.ID, "id_link").click()
        time.sleep(1)
        self.driver.find_element(By.ID, "id_link").send_keys("testselenium")
        time.sleep(1)

        #Seleccionar auth
        dropdown = self.driver.find_element(By.ID, "id_auths")
        time.sleep(1)
        dropdown.find_element(By.XPATH, "//option[. = 'http://localhost:8000']").click()
        time.sleep(1)

        #Guardar la votacion
        self.driver.find_element(By.NAME, "_save").click()
        time.sleep(1)

        #Iniciar la votacion
        self.driver.get("http://localhost:8000/admin/")
        self.driver.find_element_by_link_text("Votings").click()
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

        self.driver.get("http://localhost:8000/booth/url/testselenium") 
