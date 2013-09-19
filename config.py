###
# This file is part of Soap.
#
# Soap is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, version 2.
#
# Soap is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.
#
# See the GNU General Public License for more details. You should have received
# a copy of the GNU General Public License along with Soap. If not, see
# <http://www.gnu.org/licenses/>.
###

import supybot.conf as conf
import supybot.registry as registry
import re

class SemicolonSeparatedListOfStrings(registry.SeparatedListOf):
    Value = registry.String
    def splitter(self, s):
        return re.split(r'\s*;\s*', s)
    joiner = '; '.join


def configure(advanced):
    # This will be called by supybot to configure this module.  advanced is
    # a bool that specifies whether the user identified himself as an advanced
    # user or not.  You should effect your configuration by manipulating the
    # registry as appropriate.
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('Soap', True)


Soap = conf.registerPlugin('Soap')
# This is where your configuration variables (if any) should go.  For example:
# conf.registerGlobalValue(Soap, 'someConfigVariableName',
#     registry.Boolean(False, """Help for someConfigVariableName."""))


# General configuration settings
conf.registerGlobalValue(Soap, 'channels',
    registry.SpaceSeparatedListOfStrings('', """ The channels you wish to use
        for OpenTTD communication """))

# OpenTTD server configuration
conf.registerChannelValue(Soap, 'serverID',
    registry.String('default', """ Optional hort name for the server, used for
    issuing commands via query. no spaces allowed. Should be unique to each
    server when managing multiple game-servers """))
conf.registerChannelValue(Soap, 'host',
    registry.String('127.0.0.1', """ The hostname or IP-adress of the OpenTTD
    server you wish the bot to connect to """))
conf.registerChannelValue(Soap, 'port',
    registry.Integer(3977, """ The port of the server's adminport """))
conf.registerChannelValue(Soap, 'password',
    registry.String('password', """ The password as set in openttd.cfg """))
conf.registerChannelValue(Soap, 'publicAddress',
    registry.String('openttd.example.org', """ Address players use to connect
    to the server """))

# File-related settings
conf.registerChannelValue(Soap, 'local',
    registry.Boolean(False, """ Setting this to False will disable any commands
    requiring the below mentioned configuration options, like start and update.
    If you want this functionality, set this to True. You will need to make
    sure the bot has rwx rights on the directories, and there is a working
    install to begin with """))
conf.registerChannelValue(Soap, 'gamedir',
    registry.String('', """ The directory where the OpenTTD executable
    can be found """))
conf.registerChannelValue(Soap, 'tempdir',
    registry.String('~/tmp/', """ Temporary directory, currently used only to
    store downloaded files. This directory must exist. """))
conf.registerChannelValue(Soap, 'parameters',
    registry.SpaceSeparatedListOfStrings('None', """ Any command line parameters
    for OpenTTD. You shouldn't need to change anything here. -D, -f and -G are
    already supplied. """))


# Miscellanious server-specific settings
conf.registerChannelValue(Soap, 'autoConnect',
    registry.Boolean(False, """ Setting this to True will cause the bot to
    attempt to connect to OpenTTD automatically """))
conf.registerChannelValue(Soap, 'allowOps',
    registry.Boolean(True, """ Setting this to True will allow any op as well
    as trusted user in the channel to execute soap commands . Setting this to
    False only allows trusted users to do so """ ))
conf.registerChannelValue(Soap, 'minPlayers',
    registry.Integer(0, """ The defalt minimum number of players for the server
    to unpause itself. 0 means game never pauses unless manually paused """))
conf.registerChannelValue(Soap, 'playAsPlayer',
    registry.Boolean(True, """ True means players can play with Player as their
    name. False will get them moved to spectators any time they try to join a
    company """))
conf.registerChannelValue(Soap, 'passwordInterval',
    registry.Integer(0, """ Interval in seconds between soap changing the
    password clients use to join the server. Picks a random line from the
    included passwords.txt. If you don't want your server to have random
    passwords, leave this set at 0. People can use the password command to find
    the current password """))
conf.registerChannelValue(Soap, 'welcomeMessage',
    SemicolonSeparatedListOfStrings('None', """ Welcome message to be sent to
    players when they connect. Separate lines with semicolons. to insert (for instance)
    the client name, put {clientname} in the string, including the {}. Valid
    replacements are: {clientname} {servername} and {serverversion}. Set this to 'None'
    to disable on-join welcome messages """))

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
