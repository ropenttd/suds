
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

from libottdadmin2.trackingclient import TrackingAdminClient
from libottdadmin2.event import Event
from libottdadmin2.enums import UpdateType, UpdateFrequency

class SoapEvents(object):
    def __init__(self):
        self.connected      = Event()
        self.disconnected   = Event()

        # self.shutdown       = Event()
        # self.new_game       = Event()

        self.new_map        = Event()
        # self.protocol       = Event()

        # self.datechanged    = Event()

        # self.clientinfo     = Event()
        self.clientjoin     = Event()
        self.clientupdate   = Event()
        self.clientquit     = Event()

        # self.companyinfo    = Event()
        # self.companynew     = Event()
        # self.companyupdate  = Event()
        # self.companyremove  = Event()
        # self.companystats   = Event()
        # self.companyeconomy = Event()

        self.chat           = Event()
        self.rcon           = Event()
        # self.console        = Event()

        self.pong           = Event()

class SoapClient(TrackingAdminClient):



    # Initialization & miscellanious functions

    def __init__(self, events = None):
        super(SoapClient, self).__init__(events)
        self.soapEvents = SoapEvents()
        self._attachEvents()
        self.rcon = 'Silent'
        self.registered = False

    def _attachEvents(self):
        self.events.connected       += self._rcvConnected
        self.events.disconnected    += self._rcvDisconnected

        self.events.new_map         += self._rcvNewMap

        self.events.clientjoin      += self._rcvClientJoin
        self.events.clientupdate    += self._rcvClientUpdate
        self.events.clientquit      += self._rcvClientQuit

        self.events.chat            += self._rcvChat
        self.events.rcon            += self._rcvRcon
        self.events.rconend         += self._rcvRconEnd

        self.events.pong            += self._rcvPong

    def copy(self):
        obj = SoapClient(self.events)
        for prop in self._settable_args:
            setattr(obj, prop, getattr(self, prop, None))
        return obj



    # Insert connection info into parameters

    def _rcvConnected(self):
        self.registered = True
        self.soapEvents.connected(self._channel)

    def _rcvDisconnected(self, canRetry):
        self.registered = False
        self.soapEvents.disconnected(self._channel, canRetry)

    def _rcvNewMap(self, mapinfo, serverinfo):
        self.soapEvents.new_map(self._channel, mapinfo, serverinfo)

    def _rcvClientJoin(self, client):
        self.soapEvents.clientjoin(self._channel, client)

    def _rcvClientQuit(self, client, errorcode):
        self.soapEvents.clientquit(self._channel, client, errorcode)

    def _rcvClientUpdate(self, old, client, changed):
        self.soapEvents.clientupdate(self._channel, old, client, changed)

    def _rcvChat(self, **kwargs):
        data = dict(kwargs.items())
        data['connChan'] = self._channel
        self.soapEvents.chat(**data)

    def _rcvRcon(self, result, colour):
        self.soapEvents.rcon(self._channel, result, colour)

    def _rcvRconEnd(self, command):
        self.rcon = 'Silent'

    def _rcvPong(self, start, end, delta):
        self.soapEvents.pong(self._channel, start, end, delta)


    # Store some extra info

    _settable_args = TrackingAdminClient._settable_args + [
        'irc', 'ID', 'channel', 'autoConnect', 'allowOps',
        'playAsPlayer', 'polling']
    _irc = None
    _ID = 'Default'
    _channel = None

    @property
    def irc(self):
        return self._irc

    @irc.setter
    def irc(self, value):
        self._irc = value

    @property
    def ID(self):
        return self._ID

    @ID.setter
    def ID(self, value):
        self._ID = value

    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, value):
        self._channel = value.lower()

    update_types = [
        (UpdateType.CLIENT_INFO,        UpdateFrequency.AUTOMATIC),
        (UpdateType.COMPANY_INFO,       UpdateFrequency.AUTOMATIC),
        (UpdateType.COMPANY_ECONOMY,    UpdateFrequency.WEEKLY),
        (UpdateType.COMPANY_STATS,      UpdateFrequency.WEEKLY),
        (UpdateType.CHAT,               UpdateFrequency.AUTOMATIC),
        # (UpdateType.CONSOLE,            UpdateFrequency.AUTOMATIC),
        (UpdateType.LOGGING,            UpdateFrequency.AUTOMATIC),
        (UpdateType.DATE,               UpdateFrequency.DAILY),
    ]
