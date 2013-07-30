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

# irc-side configuration settings
conf.registerGlobalValue(Soap, 'channel',
    registry.String('#turbulent', """ The channel you wish to use for OpenTTD
    communication """))

# OpenTTD server configuration
conf.registerGlobalValue(Soap, 'host',
    registry.String('127.0.0.1', """ The hostname or IP-adress of the OpenTTD
    server you wish the bot to connect to """))
conf.registerGlobalValue(Soap, 'port',
    registry.Integer(3977, """ The port of the server's adminport """))
conf.registerGlobalValue(Soap, 'password',
    registry.String('password', """ The password as set in openttd.cfg """))
conf.registerGlobalValue(Soap, 'timeout',
    registry.Float(0.4, """ Timeout in seconds """))

# Miscellanious settings
conf.registerGlobalValue(Soap, 'autoconnect',
    registry.Boolean(True, """ Connect automatically? """))
conf.registerGlobalValue(Soap, 'allowOps',
    registry.Boolean(True, """ Setting this to True will allow any op as well
    as trusted user in the channel to execute soap commands . Setting this to
    false only allows trusted users to do so """ ))
conf.registerGlobalValue(Soap, 'playAsPlayer',
    registry.Boolean(True, """ True means players can play with Player as their
    name. False will get them moved to spectators any time they try to join a
    company """))

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
