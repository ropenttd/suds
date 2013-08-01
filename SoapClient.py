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

from libottdadmin2.client import AdminClient
from libottdadmin2.packets import *

class SoapClient(AdminClient):
    """
    Connection object to allow storing of additional info per server, like a
    user <-> clientId database
    """


    def __init__(self):
        super(SoapClient, self).__init__()

        # key=clientid, value=username
        self._userdb = dict()

        self._channel = None
        self._allowOps = False
        self._playAsPlayer = True
        self._serverName = 'default'
        self._serverVersion = 'default'


    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, value):
        self._channel = value

    @property
    def allowOps(self):
        return self._allowOps

    @channel.setter
    def allowOps(self, value):
        self._allowOps = value

    @property
    def playAsPlayer(self):
        return self._playAsPlayer

    @channel.setter
    def playAsPlayer(self, value):
        self._playAsPlayer = value

    @property
    def serverName(self):
        return self._serverName

    @serverName.setter
    def serverName(self, value):
        self._serverName = value

    @property
    def serverVersion(self):
        return self._serverVersion

    @serverVersion.setter
    def serverVersion(self, value):
        self.serverVersion = value


    #userdb operations
    def userdbClear(self):
        self._userdb.clear()

    def userdbSet(self, clientId, username):
        self._userdb[clientId] = username

    def userdbGet(self, clientId):
        return self._userdb.get(clientId)

    def userdbList(self):
        return self._userdb.keys()

    def userdbRemove(self, clientID):
        del self._userdb[clientId]
