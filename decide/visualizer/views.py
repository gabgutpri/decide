import json
from django.views.generic import TemplateView
from django.conf import settings
from django.http import Http404
from voting.models import Voting
from django.conf import settings

from base import mods


class VisualizerView(TemplateView):
    template_name = 'visualizer/visualizer.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vid = kwargs.get('voting_id', 0)
        
        try:
            r = mods.get('voting', params={'id': vid})
            context['voting'] = json.dumps(r[0])
            if r[0]['start_date'] is None:
                print('Votación no comenzada')
            elif r[0]['end_date'] is None:
                
                context['options'] = json.dumps(r[0]['question']['options']) # Datos para gráfica en tiempo real. (gabgutpri, visualización)
                opciones = r[0]['question']['options']
                numOp=[]
                
                for i in range(len(opciones)):
                    numOp.append(opciones[i]['number'])
                
                votos = mods.get('store',params={'voting_id':vid})
                print('buenas a todos')
                votosPorOpcion = []
                for op in numOp:
                    cuenta = 0
                    for v in votos:
                        if(op==v['b']):
                            cuenta = cuenta + 1
                    votosPorOpcion.append(cuenta)
                
                context['votosOpcion'] = votosPorOpcion                         # Fin de datos para gráfica

                
                numero_votos= len(votos)
                context['numero_votos'] = numero_votos
                
        except:
            raise Http404

        return context


class ContactUs(TemplateView):
    try:
        template_name = 'visualizer/contactUs.html'
    except:
        raise Http404

class AboutUs(TemplateView):
    try:
        template_name = 'visualizer/aboutUs.html'
    except:
        raise Http404

class VisualizerHome(TemplateView):
    template_name = 'visualizer/visualizer_home.html'
    # Método para obtener los votos de todas las votaciones (gabgutpri, visualización)

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = Voting.objects.all()
        def get_todos_votos(votings):
            listaVotos = []
            for voting in votings:
                votos = mods.get('store',params={'voting_id':voting.id})
                cuenta = [v['voting_id'] for v in votos]
                listaVotos.append(len(cuenta))
            return listaVotos

        # Parte de la gráfica --- gabgutpri (visualizacion)
        votaciones = mods.get('voting', params={}) # Todas las votaciones
        context['votaciones']= json.dumps(votaciones) # Transformación para que no de problemas en el script JS
        votos = get_todos_votos(queryset) # Traer todos los votos de cada votación
        context['votos'] = votos
        # ------------

        context.update({'votings': queryset})
        return context
    
    

    
    