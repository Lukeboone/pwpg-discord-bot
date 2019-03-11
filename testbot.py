# Work with Python 3.6
import discord
import random
import json
from datetime import datetime
from discord.ext.commands import Bot
from discord.ext.commands import HelpFormatter
from discord.ext.commands import MemberConverter
from configparser import SafeConfigParser

BOT_PREFIX = ("!","$")

config = SafeConfigParser()
client = Bot(command_prefix=BOT_PREFIX)
memConverter = MemberConverter()

config.read('config.ini')
TOKEN = config.get('main', 'token')

# create group to sub to
# list groups
# list users in a group

# sub to the group
# unsub from group
# notify group

# Helper function
# Reload the Group List from file
def retrieveGroupList():
    with open('groups.json', 'r') as f:
        return json.load(f)
        
# Helper function
# Write the Current Group List to file
def writeGroupList(data):
    with open('groups.json', 'w') as f:
            json.dump(data, f, indent=4) 

# Helper function
# Retrieves current userList
def getUserList(groupName, groupList):
    if groupName in groupList:
        return groupList.get(groupName)
    else:
        return False

# Helper function
# Returns a formatted Bot_Prefix
def botPrefixFormatted():
    return '[' + '|'.join(BOT_PREFIX) + ']'

# Joins an existing group and writes to file
@client.command(name='join',
                description='Join a test group.',
                rest_is_raw=True,
                pass_context=True
                )
async def joinGroup(context, groupName):    
    # if no group is provided, reference on_command_error
    groupList = retrieveGroupList() # update group list
    username = str(context.message.author) # helper for author's username
    
    if groupName in groupList: # check for group existance
        userList = getUserList(groupName, groupList) # create userlist

        # user already in group
        if username in userList:
            await context.send('`' + username + '` is already in `' + groupName + '`.')
            return

        userList.append(username) # add new user
        groupList[groupName] = userList # set userList to the group
        writeGroupList(groupList) # write to file
        await context.send('Username `' + str(context.message.author) + '` has been added to the group `' +
                         groupName + '`.')
        await context.send('`' + groupName + '` now has ' + str(len(userList)) + ' members.')
    else:
        await context.send('The group `' + groupName + '` doesn\'t exist.\n' +
                         'Use `!create <name>` to create a group')

# Leaves a group the user is a member of
@client.command(name='leave',
                description='Leave a group that you are a part of.',
                rest_is_raw=True,
                pass_context=True
                )
async def leaveGroup(context, groupName):
    # if no group is provided, reference on_command_error
    groupList = retrieveGroupList()
    username = str(context.message.author)

    userList = getUserList(groupName, groupList)

    if username in userList:
        userList.remove(username)
        print('userlist \n' + str(userList))
        groupList[groupName] = userList
        print('grouplist \n' + str(groupList))
        writeGroupList(groupList)
        await context.send('`' + username + '` has been removed from `' + groupName + '`.')
    else:
        await context.send('`' + username + '` is not a part of the `' + groupName + '` group.')

# Retrieves current group or member list 
@client.command(name='list',
                description='List members of a group.',
                rest_is_raw=True,
                pass_context=True
                )
async def listGroups(context, groupName=None):

    groupList = retrieveGroupList()

    # If no groupName is provided, list all groups
    if groupName is None:
        groupList = retrieveGroupList()
        temp = ''
        for tempgroup in groupList:
            temp += '\n' + tempgroup
        await context.send('There are `' + str(len(groupList)) + '` groups.```' + temp + '```')
        return

    elif groupName in groupList:
        userList = getUserList(groupName, groupList)
        
        # List the members of the given group name
        if userList:
            temp = ''
            for tempuser in userList:
                temp += tempuser + '\n'
            await context.send('The group `' + groupName + '` has `' + str(len(userList)) + '` members.```' +
                             temp + '```')
        else:
            await context.send('The group `' + groupName + '` is empty! Use `!join <groupName>` to join.')

    # The groupName doesn't exist
    else:
        await context.send('The group `' + groupName + '` doesn\'t exist.\n' +
                         'Use `!create <name>` to create a group')
        
# Creates a non-existing group and writes to file
@client.command(name='create',
                description='Make group',
                pass_context=True
                )
async def createGroup(context, groupName):
    groupList = retrieveGroupList()
    if groupName in groupList:
        await context.send('The group `' + groupName + '` already exists.\n' +
                         'Use `!join ' + groupName + '` to join the group')
        return
    else:
        groupList[groupName] = [str(context.message.author),]
        writeGroupList(groupList)
        await context.send('The group `' + groupName + '` has been created.\n' +
                         'User `' + str(context.message.author) + '` has been added.')

@client.command(name='ping')
async def pingGroup(context, groupName):
    groupList = retrieveGroupList()
    if groupName in groupList:
        for user in getUserList(groupName, groupList):
            temp = await memConverter.convert(context, user)
            await temp.send('GAMES')
    else:
        await context.send('The group `' + groupName + '` doesn\'t exist.\n Use `' + createGroup.signature + '`')

@client.event
async def on_command_error(context, exception):
    print ('errored ' + str(exception))

    f = HelpFormatter()
    helpPages = await f.format_help_for(context, context.command)
    for p in helpPages:
        await context.send(p)

    # await context.send('Usage is `' + context.command.signature + '`') Maybe use this instead?
    return

@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
    print(discord.__version__)

client.run(TOKEN)
