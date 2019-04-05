from discord.ext import commands
from discord.ext.commands import Bot
from discord.ext.commands import MemberConverter
from discord.ext.commands import UserConverter
from discord import Status
import discord
import asyncio
import json

GROUP_FILE = 'groupsData.json'

RESERVED_WORDS = ['group', 'groups', 'all']

groupData = {}

class GroupDoesNotExistError(commands.BadArgument): pass
class GroupAlreadyExistsError(commands.BadArgument): pass
class GroupUserAlreadyInGroupError(commands.BadArgument): pass
class GroupUserNotInGroupError(commands.BadArgument): pass

#       √ Remove the 'No Description' message on command repsonses
#       Delete group confirmation
#       √ List all of a single user's groups
#       √ Cooldown on group creation
#           Needs better error management, doesn't feel very clean
#       Case insensitivity when join/leave
#       √ Convert user data to the unique identifier (snowflake?) for save and eval
#       Temporary group mute for a user
#       √ Offline ping preference setting
#           Needs a refactor for more/smarter preferences
#       √ BUG the write loop should be refactored back to on-call writing?
#       Expand on error handling to inclue more information (command causing the error, etc)
class GroupManager(commands.Cog):

    def __init__(self, bot: Bot):
        self.bot = bot
        readGroupData()

    async def cog_command_error(self, context, error):
        if hasattr(context.command, 'on_error'): return # ignore anything with a individual local error handler

        # Marks the context that we are handling the error
        setattr(context, 'error_being_handled', True)

        # Taking care of the error
        if isinstance(error, commands.CommandOnCooldown):
            await context.message.add_reaction('⌛')
            await asyncio.sleep(error.retry_after)
            await context.message.remove_reaction('⌛', context.bot.user)
            return
        if isinstance(error, GroupAlreadyExistsError):
            await context.send('The group `' + str(error) + '` already exists! Use $list to see existing groups.') # Remove $list hardcoding
            return
        if isinstance(error, GroupDoesNotExistError):
            await context.send('The group `' + str(error) + '` does not exist! Use $create <groupName> to create a new group.') # Remove hardcoding
            return
        if isinstance(error, GroupUserAlreadyInGroupError):
            await context.send('You are already in `' + str(error) + '`. There is no need to join again! Use $mysubs to see all of your group memberships.') # Remove hardcoding
            return
        if isinstance(error, GroupUserNotInGroupError):
            await context.send('You are not in group `' + str(error) + '`. Use $sub <groupName> to join a group, or $mysubs to see all of your memberships.') # Remove hardcoding
            return

        # Finished handling our errors, anything left will go to the generic handler in pwpg-bot
        setattr(context, 'error_being_handled', False)

    @commands.command(name='jsdump', hidden=True)
    async def dump(self):
        print(groupData)
        writeGroupData()

    # Return full list of all groups with member count (short descr too?)
    @commands.cooldown(1, 5, commands.BucketType.channel)
    @commands.command(name='list',
                      description='List all groups. To see members of a specific group, include the group name.',
                      brief='List all groups, or members of a group.',
                      aliases=['ls'],
                      invoke_without_command=True,
                      rest_is_raw=True,
                      pass_context=True)
    async def listGroupsCommand(self, context, groupName=None):
        messageToSend = ''
        uc = UserConverter()
        if (groupName is None) or (groupName is RESERVED_WORDS) or (groupName not in groupData): # Conditions to list all groups (no name given, reserved words, or isn't in
                                                                                                 # groupData)
            messageToSend += 'There are currently ' + str(len(groupData)) + ' groups on PWPG!\n'
            for n in groupData:
                messageToSend += n + ': '
                if groupData[n]['description'] != 'No Description': messageToSend += groupData[n]['description'] # Add the description if the group has one
                messageToSend += '\n\tMembers: ' + str(len(groupData[n]['member'])) + '\n'
        elif groupName in groupData:
            messageToSend += groupName + ' has ' + str(len(groupData[groupName]['member'])) + ' members.\n' # <groupName> has <number> members \n
            if groupData[groupName]['description'] != 'No Description': messageToSend += groupData[groupName]['description'] + '\n' # Add the description if the group has one
            messageToSend += '---------------' + '\n'
            for m in groupData[groupName]['member']: # Add each member
                member = await uc.convert(context, m)
                messageToSend += '\t' + member.name + '\n'
        else:
            print('how did this even happen?')
            messageToSend += 'THIS SHOULD NOT BE SEEN!?'

        await context.send('```' + messageToSend + '```')

    # Returns a user's full list of memberships
    @commands.cooldown(1, 10, commands.BucketType.channel)
    @commands.command(name='mysubs',
                    description='List all of your group subscriptions.',
                    brief='List all of your subs',
                    aliases=['mygroups'],
                    pass_context=True)
    async def listUsersGroups(self, context):
        messageToSend = '```' + context.author.display_name + ' is in:\n'
        for groupName in groupData:
            if str(context.author.id) in groupData[groupName]['member']:
                messageToSend += '\t' + groupName + ':\t Offline Ping: ' + str(groupData[groupName]['member'][str(context.author.id)]['offlinePing']) + '\n'
        messageToSend += '```'
        await context.send(messageToSend)

    # Joins an existing group and writes to file
    @commands.command(name='sub',
                    description='Subscribe to a group. Belonging ' + 'to a group will include you in pings.\n' + 'Use [list] to find existing groups.',
                    brief='Subscribe to a group.',
                    aliases=['subscribe','join'],
                    rest_is_raw=True)
    async def joinGroupCommand(self, context, groupName, offlinePing=False):
        if joinGroup(context, groupName, offlinePing):
            await context.send('`' + context.author.display_name + '` has been added to `' + groupName + '`')

    # Leaves a group the user is a member of
    @commands.command(name='unsub',
                    description='Unsubscribe from a group that you are a part of. Removes you from future ' + 'pings and notifications for this group.',
                    brief='Unsubscribe from a group.',
                    aliases=['unsubscribe', 'leave'],
                    rest_is_raw=True,
                    pass_context=True)
    async def leaveGroupCommand(self, context, groupName):
        if leaveGroup(context, groupName):
            await context.send('`' + context.author.display_name + '` has left `' + groupName + '`')

    # Ping a group with an optional message
    # Check if user is online, consult property
    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.command(name='ping',
                    description='Ping a group. Pinging sends a single message to all users in a group. ' + 'Include an optional message for the ping.',
                    brief='Ping a group',
                    aliases=['poke'],
                    invoke_without_command=True,
                    pass_context=True)
    async def pingGroupCommand(self, context, groupName, *, optionalMessage=None):
        if groupName in groupData:
            m = MemberConverter()
            messageToSend = '`' + context.author.display_name + '` has pinged `' + groupName + '`.'
            if optionalMessage is not None:
                messageToSend += '\n' + optionalMessage

            # For each member in the group,
            # check user status and preference for offline ping
            # send the message if online or wants offline pings
            for u in groupData[groupName]['member']:
                user = await m.convert(context, u)
                if groupData[groupName]['member'][u].get('offlinePing') or (user.status is Status.online or user.status is Status.idle):
                    await user.send(messageToSend)
                else:
                    print('no offline ping and they aren\'t online')
            return True
        else:
            raise GroupDoesNotExistError(groupName)

    # Creates a non-existing group
    # Write to GROUP_FILE
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name='create',
                      description='Make a group and add yourself to it. Add a short description of the group after the name. Groups can be pinged using [ping] <groupName>.',
                      brief='Create a group',
                      aliases=['make'],
                      pass_context=True)
    async def createGroupCommand(self, context, groupName, *, description=None):
        if addGroup(context, groupName, description):
            await context.send('Group `' + groupName + '` has been created.')

    # Deletes an existing group
    # Write to GROUP_FILE
    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.command(name='delete',
                    description='Removes an existing group. Confirmation is not implemented yet.',
                    brief='Remove a group',
                    aliases=['remove', 'del', 'rm'],
                    hidden=True,
                    pass_context=True)
    async def deleteGroupCommand(self, context, groupName):
        if removeGroup(groupName):
            await context.send('Group `' + groupName + '` has been deleted.')

    # Edits an existing group's description
    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.command(name='edit',
                    description='Edit an existing group\'s description. No quotations are needed.',
                    brief='Edit a group description',
                    aliases=['editgroup', 'editdesc'],
                    pass_context=True)
    async def editGroupDescriptionCommand(self, context, groupName, *, description=None):
        if description is None:
            if editGroupDescription(groupName, 'No Description'):
                await context.send('The description for `' + groupName + '` has been removed.')
            return
        else:
            if editGroupDescription(groupName, description):
                await context.send('The description for `' + groupName + '` has been updated.')
            return

    # Edit a user's group preference
    @commands.command(name='myprefs',
                    description='Edit your preferences for a group. Currently includes: \nOffline Ping:\t Receiving Pings when offline',
                    brief='Edit your group preferences',
                    aliases=['mypref'],
                    pass_context=True)
    async def editUsersGroupPreferenceCommand(self, context, groupName, offlinePing=False):
        preferences = {'offlinePing': offlinePing}
        updateUserGroupPreferences(context, groupName, preferences)

    def is_luke(self):
        def predicate(ctx):
            return ctx.message.author.id == 180532524068503552
        return commands.check(predicate)

    @commands.command(name='waffle', hidden=True)
    #@is_luke
    #@commands.guild_only()
    async def _stupidLuke(self, context):
        # if not isinstance(context.channel, (discord.DMChannel,
        # discord.GroupChannel)):
        await context.message.delete()
        await context.send('The word "waffle" first appears in the English language in 1725', delete_after=180)

# Create a group entry with an optional name
# Returns false if group exists
def addGroup(context, name: str, description=None):
    global groupData
    if name in groupData: raise GroupAlreadyExistsError(name)
    else:
        if description is None: description = 'No Description'
        groupData[name] = {'member':{}, 'description': description}
        joinGroup(context, name)
        writeGroupData()
        return True

# Removes entire entry for a group
# Returns false if group doesn't exist
def removeGroup(name: str):
    global groupData
    if name in groupData.keys():
        groupData.pop(name)
        writeGroupData()
        return True
    else:
        raise GroupDoesNotExistError(name)
        return False

# Edits an existing group's description
# Returns false if the group doesn't exist
def editGroupDescription(name: str, description: str):
    global groupData
    if name in groupData:
        groupData[name]['description'] = description
        writeGroupData()
        return True
    else:
        raise GroupDoesNotExistError(name)
        return False

# Add author to a group
# Returns false if no matching group name or in group already
def joinGroup(context, name: str, offlinePing=True):
    global groupData
    userProps = {'offlinePing': offlinePing}
    if name in groupData:
        if str(context.author.id) in groupData[name]['member']:
            raise GroupUserAlreadyInGroupError(name)
            return False
        groupData[name]['member'][str(context.author.id)] = userProps
        writeGroupData()
        return True
    else:
        raise GroupDoesNotExistError(name)
        return False

# Remove author from a group
# Returns false if not in the group, or if the group doesn't exist
def leaveGroup(context, name: str):
    global groupData
    if name in groupData:
        if str(context.author.id) in groupData[name]['member']:
            groupData[name]['member'].pop(str(context.author.id))
            writeGroupData()
            return True
        else:
            raise GroupUserNotInGroupError(name)
            return False
    else:
        raise GroupDoesNotExistError(name)
        return False

# Replace user preferences for a group with dictionary
# Returns false if not in group or no matching group
#  throw error if no dict provided (missing arg)
def updateUserGroupPreferences(context, name: str, properties: dict):
    global groupData
    if name in groupData:
        if str(context.author.id) not in groupData[name]['member']:
            print('throw error, not in group')
            return False
        groupData[name]['member'][str(context.author.id)] = properties
        writeGroupData()
        return True
    else:
        raise GroupDoesNotExistError(name)
        return False

# Write groupData dict to GROUP_FILE, return True if sucessful
# Writes every TICK_RATE inside groupManagerLoop(int)
def writeGroupData():
    with open(GROUP_FILE, 'w') as f:
        json.dump(groupData, f, indent=4)
        print('Group Data Written')
        return True
    return None

# Read GROUP_FILE and assign to groupData dict, return groupData
def readGroupData():
    with open(GROUP_FILE, 'r') as f:
        global groupData
        groupData = json.load(f)
        print('Group Data Loaded')
        return groupData
    return None


def setup(bot):
    bot.add_cog(GroupManager(bot))

def teardown(bot):
    writeGroupData()
    bot.remove_cog('GroupManager')
