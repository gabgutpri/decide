from discord.ext import commands
import os

dis = 'Nzk4ODg0NDIyODUzNTkxMDQx.X_7hGA'
token = '.lYiyxyHWmpedGIdmmKHL-xnfq50'
TOKEN =  dis+token

client = commands.Bot(command_prefix='!')

@client.event
async def on_ready():
    print(f'{client.user.name} has connected to Discord!')

@client.command(name='exit', help='Cierra el bot')
async def salir(ctx):
    await ctx.send('Me voy, ¡adios!')
    await client.logout()
    await client.close()

@client.command(name='votaciones', help='Devuelve todas las votaciones con sus resultados')
async def votaciones(ctx):
    queryset = Voting.objects.all()
    for q in queryset:
        nombre = 'Nombre de la votacion: '+str(q.name)+'/n'
        pregunta = 'Pregunta de la votacion: '+str(q.question)+'/n'
        fechaInicio = 'Fecha de inicio: '+str(q.start_date)+'/n'
        fechaFinal = 'Fecha de fin: '+str(q.end_date)+'/n'
    response = nombre+pregunta+fechaInicio+fechaFinal+'----------------------'
    await ctx.send(response)
    
#@client.command(name='estado')
#async def enviarMensaje(ctx):
    #canal = client.get_channel(799052293080743946) # ID del canal de votaciones en el servidor de prueba.
#    await ctx.send()


client.run(TOKEN)