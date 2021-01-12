from django.test import TestCase

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

class TestContactUs():
    def setUp(self):
        options = webdriver.ChromeOptions()
        options.headless = True
        self.driver = webdriver.Chrome(options=options)
        self.driver.fullscreen_window()
  
    def test_contactUs(self):
        self.driver.get("https://picaro-decide.herokuapp.com/admin/login/?next=/admin/")
        self.driver.find_element_by_id('id_username').send_keys("admin")
        self.driver.find_element_by_id('id_password').send_keys("picarodecide")
        self.driver.find_element_by_id('login-form').click()
        self.driver.get("https://picaro-decide.herokuapp.com/visualizer/5/")
        self.driver.find_element(By.CSS_SELECTOR, ".btn-secondary:nth-child(2)").click()
        assert self.driver.find_element(By.CSS_SELECTOR, "div:nth-child(1) > h2").text == "Contact Info"

    def tearDown(self):
        self.driver.quit()

class TestContactUsBack():
    def setUp(self):
        options = webdriver.ChromeOptions()
        options.headless = True
        self.driver = webdriver.Chrome(options=options)
        self.driver.fullscreen_window()
  
    def test_contactUsBack(self):
        self.driver.get("https://picaro-decide.herokuapp.com/admin/login/?next=/admin/")
        self.driver.find_element_by_id('id_username').send_keys("admin")
        self.driver.find_element_by_id('id_password').send_keys("picarodecide")
        self.driver.find_element_by_id('login-form').click()
        self.driver.get("https://picaro-decide.herokuapp.com/visualizer/5/")
        self.driver.find_element(By.CSS_SELECTOR, ".btn-secondary:nth-child(2)").click()
        assert self.driver.find_element(By.CSS_SELECTOR, "div:nth-child(1) > h2").text == "Contact Info"
        self.driver.find_element(By.CSS_SELECTOR, ".btn-secondary").click()
        assert self.driver.find_element(By.ID, "saveAsPNG1").text == "Save as PNG"

    def tearDown(self):
        self.driver.quit()

class TestDarkMode():
    def setUp(self):
        options = webdriver.ChromeOptions()
        options.headless = True
        self.driver = webdriver.Chrome(options=options)
        self.driver.fullscreen_window()
  
    def test_darkMode(self):
        self.driver.get("https://picaro-decide.herokuapp.com/admin/login/?next=/admin/")
        self.driver.find_element_by_id('id_username').send_keys("admin")
        self.driver.find_element_by_id('id_password').send_keys("picarodecide")
        self.driver.find_element_by_id('login-form').click()
        self.driver.get("https://picaro-decide.herokuapp.com/visualizer/5/")
        self.driver.find_element(By.ID, "darkButton").click()
        assert self.driver.find_element_by_tag_name('body').get_attribute("class") == "bg-dark"
        assert self.driver.find_element(By.ID, "lightButton").text == "Light mode" 

    def tearDown(self):
        self.driver.quit()

class TestLightMode():
    def setUp(self):
        options = webdriver.ChromeOptions()
        options.headless = True
        self.driver = webdriver.Chrome(options=options)
        self.driver.fullscreen_window()
  
    def test_lightMode(self):
        self.driver.get("https://picaro-decide.herokuapp.com/admin/login/?next=/admin/")
        self.driver.find_element_by_id('id_username').send_keys("admin")
        self.driver.find_element_by_id('id_password').send_keys("picarodecide")
        self.driver.find_element_by_id('login-form').click()
        self.driver.get("https://picaro-decide.herokuapp.com/visualizer/5/")
        self.driver.find_element(By.ID, "darkButton").click()
        self.driver.find_element(By.ID, "lightButton").click()
        assert self.driver.find_element_by_tag_name('body').get_attribute("class") == "bg-light"
        assert self.driver.find_element(By.ID, "darkButton").text == "Dark mode" 

    def tearDown(self):
        self.driver.quit()
