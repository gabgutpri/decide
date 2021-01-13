import discord
import os

dis = 'Nzk4ODg0NDIyODUzNTkxMDQx.X_7hGA'
token = '.eTn5kivzPC9JP1gRK5JDgmqzvbI'
TOKEN =  dis+token   #'Nzk4ODg0NDIyODUzNTkxMDQx.X_7hGA.eTn5kivzPC9JP1gRK5JDgmqzvbI' #dis.join(token)

client = discord.Client()

@client.event
async def on_ready():
    print(f'{client.user.name} has connected to Discord!')

#@client.command()
#async def enviarMensaje():
#   canal = client.channels.cache.find()


client.run(TOKEN)