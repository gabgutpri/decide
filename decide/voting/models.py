from django.db import models
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import os
import requests
from django.core.validators import RegexValidator

from base import mods
from base.models import Auth, Key

#Javi
#Restriccion para que no se pueda crear una votacion con una fecha de finalizacion pasada
def end_date_past(value):
    now = timezone.now()
    if value < now:
        raise ValidationError('End date past')


class Question(models.Model):
    desc = models.TextField()
    yes_no_question = models.BooleanField(default=False)

    def save(self):

        super().save()
        # In case of being a Yes/No question, we use the yesNoQuestionCreation method
        if self.yes_no_question:

            yesNoQuestionCreation(self)

    def __str__(self):
        return self.desc

# Method that creates the 'Yes' and 'No' options
def yesNoQuestionCreation(self):
    # Boolean that checks if the 'Yes' and 'No' options are created
    exists_yes = False
    exists_no = False
    # Try/except in case of not existing options
    try:
        # Search through all the options in the current question to verify the existence of the options
        options = QuestionOption.objects.all().filter(question = self)
        for element in options:
            if element.option == 'YES':
                exists_yes = True
            elif element.option == 'NO':    
                exists_no = True
            # If both are found, exit the search before finishing it
            if exists_yes and exists_no:
                break
    except:
        pass

    # Creation of 'Yes' option
    if not exists_yes:
        QuestionOption(option = 'YES', number = 1, question = self).save()

    # Creation of 'No' option
    if not exists_no:
        QuestionOption(option = 'NO', number = 2, question = self).save()

class QuestionOption(models.Model):
    question = models.ForeignKey(Question, related_name='options', on_delete=models.CASCADE)
    number = models.PositiveIntegerField(blank=True, null=True)
    option = models.TextField()

    def save(self):
        # In the case of the Yes/No question, we make sure that only the 'Yes' and 'No' options are saved
        if self.question.yes_no_question:
            if not self.option == 'YES' and not self.option == 'NO':
                return ""
        # In the case of a normal question, we proceed as usual
        else:
            if not self.number:
                self.number = self.question.options.count() + 2
        return super().save()

    def __str__(self):
        return '{} ({})'.format(self.option, self.number)


class Voting(models.Model):
    name = models.CharField(max_length=200)
    desc = models.TextField(blank=True, null=True)
    question = models.ForeignKey(Question, related_name='voting', on_delete=models.CASCADE)
    alpha = RegexValidator("^[0-9a-zA-Z]*$", "Sólo se permiten letras y números.")
    link = models.CharField(max_length=30, default="", unique=True ,validators=[alpha],blank=True, null=True)

    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True, validators=[end_date_past])

    pub_key = models.OneToOneField(Key, related_name='voting', blank=True, null=True, on_delete=models.SET_NULL)
    auths = models.ManyToManyField(Auth, related_name='votings')

    tally = JSONField(blank=True, null=True)
    postproc = JSONField(blank=True, null=True)

    file = models.FileField(blank=True)

    def create_pubkey(self):
        if self.pub_key or not self.auths.count():
            return

        auth = self.auths.first()
        data = {
            "voting": self.id,
            "auths": [ {"name": a.name, "url": a.url} for a in self.auths.all() ],
        }
        key = mods.post('mixnet', baseurl=auth.url, json=data)
        pk = Key(p=key["p"], g=key["g"], y=key["y"])
        pk.save()
        self.pub_key = pk
        self.save()

    def get_votes(self, token=''):
        # gettings votes from store
        votes = mods.get('store', params={'voting_id': self.id}, HTTP_AUTHORIZATION='Token ' + token)
        # anon votes
        return [[i['a'], i['b']] for i in votes]

    def tally_votes(self, token=''):
        '''
        The tally is a shuffle and then a decrypt
        '''

        votes = self.get_votes(token)

        auth = self.auths.first()
        shuffle_url = "/shuffle/{}/".format(self.id)
        decrypt_url = "/decrypt/{}/".format(self.id)
        auths = [{"name": a.name, "url": a.url} for a in self.auths.all()]

        # first, we do the shuffle
        data = { "msgs": votes }
        response = mods.post('mixnet', entry_point=shuffle_url, baseurl=auth.url, json=data,
                response=True)
        if response.status_code != 200:
            # TODO: manage error
            pass

        # then, we can decrypt that
        data = {"msgs": response.json()}
        response = mods.post('mixnet', entry_point=decrypt_url, baseurl=auth.url, json=data,
                response=True)

        if response.status_code != 200:
            # TODO: manage error
            pass

        self.tally = response.json()
        self.save()

        self.do_postproc()
        

    def do_postproc(self):
        tally = self.tally
        options = self.question.options.all()

        opts = []
        for opt in options:
            if isinstance(tally, list):
                votes = tally.count(opt.number)
            else:
                votes = 0
            opts.append({
                'option': opt.option,
                'number': opt.number,
                'votes': votes
            })
        msn ="Votación: "+self.name+"\n\n"
        for opt in opts:
            msn = str(msn)+str(opt.get('option'))+": "+(str(opt.get('votes')))+" votos.\n"
        data = { 'type': 'IDENTITY', 'options': opts }
        postp = mods.post('postproc', json=data)
        

        self.postproc = postp
        self.save()

        
        #Guardamos en local la votación
    def saveFile(self):
        if self.postproc:
            ruta= "ficheros/"+str(self.id)+ "-"+self.name + " - " +self.end_date.strftime('%d-%m-%y')+ ".txt"
            file = open(ruta,"w")
            file.write("Id: "+str(self.id)+os.linesep)
            file.write("Nombre: "+self.name+os.linesep)
            if self.desc:
                file.write("Descripción: "+self.desc+os.linesep)
            
            file.write("Fecha de inicio: "+self.start_date.strftime('%d/%m/%y %H:%M:%S')+os.linesep)
            file.write("Fecha de fin: "+self.end_date.strftime('%d/%m/%y %H:%M:%S')+os.linesep)
            file.write("Resultado: "+str(self.postproc)+os.linesep)
            file.close()
            self.file=ruta
            self.save()
            

       # self.enviarTelegram(msn) Comentado por mantenimiento


    def __str__(self):
        return self.name
    
    #Método para enviar datos de los resultados por telegram (Pablo Franco Sánchez, visualización)
    def enviarTelegram(self,msn): 
        id = "-406420323"
        token = "1426657690:AAEmrAP5v4KFQvmzv5AyGdGvWwrbJbZup3M"
        url = "https://api.telegram.org/bot" + token + "/sendMessage"

        params = {
        'chat_id': id,
        'text' : str(msn)
        }
        requests.post(url, params=params)
