from django.test import TestCase


import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

class TestEmail():
  def setup(self):
    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument("--no-sandbox")
    self.driver = webdriver.Chrome(options=options)
  
  def teardown(self):
    self.driver.quit()
  
  def test_email(self):
    self.driver.get("https://picaro-decide.herokuapp.com/visualizer/5/")
    self.driver.set_window_size(1552, 840)
    self.driver.find_element(By.CSS_SELECTOR, ".btn-secondary:nth-child(2)").click()
    self.driver.find_element(By.NAME, "name").click()
    self.driver.find_element(By.NAME, "name").send_keys("test test")
    self.driver.find_element(By.NAME, "subject").click()
    self.driver.find_element(By.NAME, "subject").send_keys("test")
    self.driver.find_element(By.NAME, "mail").click()
    self.driver.find_element(By.NAME, "mail").send_keys("test@gmail.com")
    self.driver.find_element(By.NAME, "Comment").click()
    self.driver.find_element(By.NAME, "Comment").send_keys("test")
    self.driver.find_element(By.CSS_SELECTOR, ".inputBox:nth-child(5) > input").click()

class TestTraduccion():
  def setup(self):
    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument("--no-sandbox")
    self.driver = webdriver.Chrome(options=options)
  
  def teardown(self):
    self.driver.quit()
  
  def test_traduccion(self):
    self.driver.get("https://picaro-decide.herokuapp.com/visualizer/5/")
    self.driver.set_window_size(1552, 840)
    element = self.driver.find_element(By.CSS_SELECTOR, ".fa-language")
    actions = ActionChains(self.driver)
    actions.move_to_element(element).perform()
    self.driver.find_element(By.CSS_SELECTOR, "li:nth-child(3) img").click()
    assert self.driver.find_element(By.ID, "text").text == "Résultats"

class TestQuestion():
  def setup(self):
    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument("--no-sandbox")
    self.driver = webdriver.Chrome(options=options)
  
  def teardown(self):
    self.driver.quit()
  
  def test_question(self):
    self.driver.get("https://picaro-decide.herokuapp.com/visualizer/5/")
    self.driver.set_window_size(1552, 840)
    elements = self.driver.find_elements(By.ID, "question")
    assert len(elements) > 0

class TestMaps():
  def setup(self):
    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument("--no-sandbox")
    self.driver = webdriver.Chrome(options=options)
  
  def teardown(self):
    self.driver.quit()
  
  def test_maps(self):
    self.driver.get("https://picaro-decide.herokuapp.com/visualizer/5/")
    self.driver.set_window_size(1552, 840)
    self.driver.find_element(By.CSS_SELECTOR, ".btn-secondary:nth-child(2)").click()
    elements = self.driver.find_elements(By.CSS_SELECTOR, "a > img")
    assert len(elements) > 0
  