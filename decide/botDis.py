import discord
import os

dis = 'Nzk4ODg0NDIyODUzNTkxMDQx.X_7hGA'
token = '.E04N6tkXDMNNjahAF6jwH-8KgCU'
TOKEN =  dis+token

client = discord.Client()

@client.event
async def on_ready():
    print(f'{client.user.name} has connected to Discord!')

#@client.command()
#async def enviarMensaje():
#   canal = client.channels.cache.find()


client.run(TOKEN)