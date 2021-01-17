from django.contrib import admin
from django.utils import timezone

from .models import QuestionOption
from .models import Question
from .models import Voting

from .filters import StartedFilter


def start(modeladmin, request, queryset):
    for v in queryset.all():
        v.create_pubkey()
        v.start_date = timezone.now()
        v.enviarTelegram("La votación "+str(v.name)+" ha comenzado")
        v.save()


def stop(ModelAdmin, request, queryset):
    for v in queryset.all():
        v.end_date = timezone.now()
        v.enviarTelegram("La votación "+str(v.name)+" ha terminado")
        v.save()


def tally(ModelAdmin, request, queryset):
    for v in queryset.filter(end_date__lt=timezone.now()):
        token = request.session.get('auth-token', '')
        v.tally_votes(token)

def save(ModelAdmin, request ,queryset):
    for v in queryset.filter(end_date__lt=timezone.now()):
        v.saveFile()

class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    fields= ('pref_number', 'option', 'number')


class QuestionAdmin(admin.ModelAdmin):
    inlines = [QuestionOptionInline]


class VotingAdmin(admin.ModelAdmin):
    #Javi
    #He eliminado end_date de readonly_fields para poder meterlo al crear una votacion
    list_display = ('name', 'start_date', 'end_date')

    readonly_fields = ('start_date', 'pub_key', 'tally', 'postproc', 'file')

    date_hierarchy = 'start_date'
    list_filter = (StartedFilter,)
    search_fields = ('name', )

    actions = [ start, stop, tally, save ]


admin.site.register(Voting, VotingAdmin)
admin.site.register(Question, QuestionAdmin)
