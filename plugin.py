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
import supybot.utils as utils
import supybot.ircdb as ircdb
import supybot.ircmsgs as ircmsgs
from supybot.commands import *
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.plugins as plugins

import threading
import time
import socket
from libottdadmin2.client import *


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




class Soap(callbacks.Plugin):
    """
    This plugin allows supybot to interface to OpenTTD via its built-in
    adminport protocol
    """

    def __init__(self, irc):
        self.__parent = super(Soap, self)
        self.__parent.__init__(irc)
        self.e = threading.Event()
        self._createSoapClient()

    def die(self):
        try:
            self.e.set()
        except:
            pass
        self.__parent.die()

    def _pollForData(self, irc):
        index = 1
        self.log.info('polling')
        pollcount = 0
        while not self.e.isSet():
            pollcount += 1
            try:
                packets = self.connection.poll()
                # self.log.info('polling %s', pollcount)
                if packets is None or packets is False:
                    break
                for packet, data in packets:
                    self.log.info('received at %s: %s -> %r' % (pollcount, packet, data))
            except Exception, e:
                self.log.info('exception caught at %s: %s' % (pollcount, str(e)))


        self.log.info('end polling')
        irc.queueMsg(ircmsgs.privmsg(self.connection.channel, 'Connection terminated'))
        self.connection.disconnect()

    def _createSoapClient(self):
        self.connection = SoapClient()
        self.connection.configure(
            password = self.registryValue('password'),
            host = self.registryValue('host'),
            port = self.registryValue('port'),
            name = 'Soap')
        self.connection.channel = self.registryValue('channel')
        self.connection.allowOps = self.registryValue('allowOps')
        self.connection.playAsPlayer = self.registryValue('playAsPlayer')
        self.connection.settimeout(self.registryValue('timeout'))

    def _initializeConnection(self, irc):
        irc.queueMsg(ircmsgs.privmsg(self.connection.channel, 'Connecting'))

        self.e.clear()
        self._createSoapClient()
        self.connection.connect()
        failed = False
        protocol_response = None
        welcome_response = None
        try:
            protocol_response = self.connection.recv_packet()
            self.log.info('Protocol: %s', protocol_response)
            if protocol_response is None:
                failed = True
                self.log.info('no response from server')
        except socket.error, v:
            failed = True
            self.log.info('error connecting: %s - %s' % (v[0], v[1]))
        if failed:
            irc.queueMsg(ircmsgs.privmsg(self.connection.channel, 'Unable to connect'))
        else:
            # request info on all clients, so userdb gets populated
            self.connection.send_packet(AdminPoll, pollType = 0x01,
                extra = 0xFFFFFFFF)
            irc.queueMsg(ircmsgs.privmsg(self.connection.channel, 'Connected'))

    def _startReceiveThread(self, irc):
        t = threading.Thread(target=self._pollForData, kwargs={'irc':irc})
        t.daemon = True
        t.start()
        # Change update frequency for Admin_ClientInfo to automatic
        self.connection.send_packet(AdminUpdateFrequency, updateType = 1,
            updateFreq = 0x40)
        # Change update frequency for Admin_CompanyInfo to automatic
        self.connection.send_packet(AdminUpdateFrequency, updateType = 2,
            updateFreq = 0x40)
        # Change update frequency for Admin_Chat to automatic
        self.connection.send_packet(AdminUpdateFrequency, updateType = 5,
            updateFreq = 0x40)
        # Change update frequency for Admin_CommandLogging to automatic
        self.connection.send_packet(AdminUpdateFrequency, updateType = 8,
            updateFreq = 0x40)

    def _checkPermission(self, irc, msg, allowOps):
        capable = ircdb.checkCapability(msg.prefix, 'trusted')
        opped = msg.nick in irc.state.channels[self.connection.channel].ops
        if allowOps:
            if (opped or capable):
                return True
            else:
                return False
        else:
            if capable:
                return True
            else:
                return False

    def apconnect(self, irc, msg, args):
        """
        connect to AdminPort of OpenTTD server
        """
        # irc.reply('%s - %s' % (msg, args))
        if self._checkPermission(irc, msg, self.connection.allowOps):
            if self.connection.is_connected:
                irc.queueMsg(ircmsgs.privmsg(self.connection.channel,
                    'already connected'))
            else:
                self._initializeConnection(irc)
                if self.connection.is_connected:
                    self._startReceiveThread(irc)
    apconnect = wrap(apconnect)

    def apdisconnect(self, irc, msg, args):
        """
        disconnect from server
        """

        if self._checkPermission(irc, msg, self.connection.allowOps):
            if self.connection.is_connected:
                irc.queueMsg(ircmsgs.privmsg(self.connection.channel, 'Disconnecting'))
                self.e.set()
            else:
                irc.queueMsg(ircmsgs.privmsg(self.connection.channel, 'Not connected'))
    apdisconnect = wrap(apdisconnect)

Class = Soap

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
