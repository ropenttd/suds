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

class ConnectionState(EnumHelper):
    DISCONNECTED    = 0x00
    CONNECTING      = 0x01
    AUTHENTICATING  = 0x02
    CONNECTED       = 0x03
    DISCONNECTING   = 0x04
    SHUTDOWN        = 0x05

class PauseState(EnumHelper):
    UNPAUSED                = 0x00 # Unpaused
    PAUSED_NORMAL           = 0x01 # Paused manually
    PAUSED_SAVELOAD         = 0x02 # Paused for saving/loading
    PAUSED_JOIN             = 0x04 # Pause on join
    PAUSED_ERROR            = 0x08 # Pause because of a (critical) error
    PAUSED_ACTIVE_CLIENTS   = 0x10 # Pause for 'min_active_clients'
    PAUSED_GAMESCRIPT       = 0x20 # Paused by game script

class RconSpecial(EnumHelper):
    SILENT          = 0X00 # Keep it quiet, its a secret
    SHUTDOWNSAVED   = 0x01 # game has been saved by the shutdown command
    UPDATESAVED     = 0x02 # game has been saved prior to shutting down for update
