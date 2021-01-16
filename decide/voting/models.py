from django.db import models
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import os
from django.core.validators import RegexValidator

from base import mods
from base.models import Auth, Key

def no_past(value):
    today = timezone.now()
    if value < today:
        raise ValidationError('End date past')


class Question(models.Model):
    desc = models.TextField()

    QUESTION_TYPE= ((1,"Simple question"),(2,"Preference question"))
    question_options = models.PositiveIntegerField(choices=QUESTION_TYPE,default=1)

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
    pref_number = models.PositiveIntegerField(blank=True, null=True)
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
    question =  models.ManyToManyField(Question, related_name='voting')
    alpha = RegexValidator("^[0-9a-zA-Z]*$", "Sólo se permiten letras y números.")
    link = models.CharField(max_length=30, default="", unique=True ,validators=[alpha],blank=True, null=True)

    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True, validators=[no_past])

    pub_key = models.OneToOneField(Key, related_name='voting', blank=True, null=True, on_delete=models.SET_NULL)
    auths = models.ManyToManyField(Auth, related_name='votings')

    tally = JSONField(blank=True, null=True)
    postproc = JSONField(blank=True, null=True)

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

    def votes_info_opciones(self):
        options = set()
        for q in self.question.all():
            for o in q.options.all():
                options.add(o)


        opts = []
        for opt in options:
            opts.append('option:'+ str(opt.option)) 
        return opts   

    def votes_info_votos(self):
        tally = self.tally
        options = set()
        for q in self.question.all():
            for o in q.options.all():
                options.add(o)


        opts = []
        for opt in options:
            if isinstance(tally, list):
                votes = tally.count(opt.number)
            else:
                votes = 0
            opts.append(
                str(votes)+" votes"
            )  
        
        return opts

    def do_postproc(self):
        tally = self.tally
        options = set()
        for q in self.question.all():
            for o in q.options.all():
                options.add(o)

        opts = []
        for opt in options:
            if isinstance(tally, list):
                votes = tally.count(opt.number)
            else:
                votes = 0
            opts.append({
                'option': opt.option,
                'number': opt.number,
                'votes': votes,
                'n_pref' : opt.pref_number
            })

        data = { 'type': 'IDENTITY', 'options': opts }
        postp = mods.post('postproc', json=data)

        self.postproc = postp
        self.save()
        
        #Guardamos en local la votación
        ruta= "ficheros/"+self.name + " - " +self.start_date.strftime('%d-%m-%y')+ ".txt"
        file = open(ruta,"w")
        file.write("Nombre: "+self.name+os.linesep)
        if len(self.desc):
            file.write("Descripción: "+self.desc+os.linesep)
        
        file.write("Fecha de inicio: "+self.start_date.strftime('%d/%m/%y %H:%M:%S')+os.linesep)
        file.write("Fecha de fin: "+self.end_date.strftime('%d/%m/%y %H:%M:%S')+os.linesep)
        file.write("Resultado: "+str(self.postproc)+os.linesep)

    def __str__(self):
        return self.name
