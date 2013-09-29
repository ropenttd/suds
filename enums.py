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

from libottdadmin2.enums import EnumHelper

class ServerStartStatus(EnumHelper):
    ALREADYRUNNING      = 0x00 # Server is already running
    SUCCESS             = 0x01 # Server started succesfully
    SUCCESSNOPIDFILE    = 0x02 # Server started succesfully, but no pidfile was created
    FAILNOPID           = 0x03 # Server may not have started properly, couldn't catch the PID
    FAILOSERROR         = 0x04 # Server failed to start
    FAILUNKNOWN         = 0x05 # Server failed to start, unhandled error

class RconSpecial(EnumHelper):
    SILENT              = 0X00 # Keep it quiet, its a secret
    SHUTDOWNSAVED       = 0x01 # game has been saved by the shutdown command

class ConnectionState(EnumHelper):
    DISCONNECTED        = 0x00
    CONNECTING          = 0x01
    AUTHENTICATING      = 0x02
    CONNECTED           = 0x03
    DISCONNECTING       = 0x04
