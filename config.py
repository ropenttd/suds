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
conf.registerGlobalValue(conf.supybot.plugins.Soap, 'channel',
    registry.String('', """ The channel you wish to use for OpenTTD
    communication """))

# OpenTTD server configuration
conf.registerGlobalValue(conf.supybot.plugins.Soap, 'host',
    registry.String('127.0.0.1', """ The hostname or IP-adress of the OpenTTD
    server you wish the bot to connect to """))
conf.registerGlobalValue(conf.supybot.plugins.Soap, 'port',
    registry.Int(3977, """ The port of the server's adminport """))
conf.registerGlobalValue(conf.supybot.plugins.Soap, 'password',
    registry.String('password', """ The password as set in openttd.cfg """))
conf.registerGlobalValue(conf.supybot.plugins.Soap, 'timeout',
    registry.Int(0.4, """ Timeout in seconds """))
    
# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
