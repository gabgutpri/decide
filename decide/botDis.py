from discord.ext import commands
from voting import admin
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
    

    response = 'Hola, estoy funcionando.'
    await ctx.send(response)
    
@client.command(name='estado')
async def enviarMensaje(ctx):
    #canal = client.get_channel(799052293080743946) # ID del canal de votaciones en el servidor de prueba.
    await ctx.send(admin.ESTADO)


client.run(TOKEN)