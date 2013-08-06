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

from libottdadmin2.trackingclient import TrackingAdminClient as TAC
from libottdadmin2.constants import *
from libottdadmin2.enums import *
from libottdadmin2.packets import *
from libottdadmin2.event import Event


class SoapClient(TAC):
    _settable_args = TAC._settable_args + ['channel', 'allowOps', 'playAsPlayer']
    _channel = None
    _allowOps = False
    _playAsPlayer = True

    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, value):
        self._channel = value

    @property
    def allowOps(self):
        return self._allowOps

    @allowOps.setter
    def allowOps(self, value):
        self._allowOps = value

    @property
    def playAsPlayer(self):
        return self._playAsPlayer

    @playAsPlayer.setter
    def playAsPlayer(self, value):
        self._playAsPlayer = value


class Soap(callbacks.Plugin):
    """
    This plug-in allows supybot to interface to OpenTTD via its built-in
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
        # make sure the listening thread is closed
        time.sleep(self.connection.timeout)
        self.__parent.die()

    def _pollForData(self):
        self.log.info('start polling')
        pollcount = 0
        while not self.e.isSet():
            pollcount += 1
            try:
                packets = self.connection.poll()
                if packets is None or packets is False:
                    break
                for packet, data in packets:
                    self.log.info('received at %s: %s -> %r' % (pollcount, packet, data))
            except Exception, e:
                self.log.info('exception caught at %s: %s' % (pollcount, str(e)))


        self.log.info('end polling')
        self.connection.disconnect()

    def _createSoapClient(self):
        self.connection = SoapClient()
        self.connection.configure(
            password = self.registryValue('password'),
            host = self.registryValue('host'),
            port = self.registryValue('port'),
            channel = self.registryValue('channel'),
            allowOps = self.registryValue('allowOps'),
            playAsPlayer = self.registryValue('playAsPlayer'),
            name = 'Soap')

    def _initializeConnection(self):
        self.e.clear()
        self._createSoapClient()
        self.connection.connect()
        protocol_response = None
        try:
            protocol_response = self.connection.recv_packet()
            self.log.debug('Protocol: %s', protocol_response)
            if protocol_response is None:
                self.log.info('no response from server')
                return False
        except socket.error, v:
            self.log.info('connection error: %s' % v)
            return False
        else:
            return True

    def _startReceiveThread(self):
        t = threading.Thread(target=self._pollForData)
        t.daemon = True
        t.start()

    def _checkPermission(self, irc, msg, channel, allowOps):
        capable = ircdb.checkCapability(msg.prefix, 'trusted')
        if capable:
            return True
        else:
            opped = msg.nick in irc.state.channels[channel].ops
            if opped and allowOps:
                return True
            else:
                return False

    def apconnect(self, irc, msg, args):
        """ no arguments
        
        connect to AdminPort of OpenTTD server
        """
        
        if isChannel(msg.arg[0]) and not msg.arg[0] == self.connection.channel:
            return
        if self._checkPermission(irc, msg, self.connection.channel, self.connection.allowOps):
            if self.connection.is_connected:
                irc.reply('Already connected!!', prefixNick = False)
            else:
                success = self._initializeConnection()
                if success:
                    self._startReceiveThread()
                    irc.reply('Connected', prefixNick = False)
                else:
                    irc.reply('Connection failed', prefixNick = False)
    apconnect = wrap(apconnect)

    def apdisconnect(self, irc, msg, args):
        """ no arguments
        
        disconnect from server
        """

        if isChannel(msg.arg[0]) and not msg.arg[0] == self.connection.channel:
            return
        if self._checkPermission(irc, msg, self.connection.channel, self.connection.allowOps):
            if self.connection.is_connected:
                self.e.set()
                time.sleep(self.connection.timeout)
                if not self.connection.connected():
                    irc.reply('Disconnected', prefixNick = False)
            else:
                irc.reply('Not connected!!', prefixNick = False)
    apdisconnect = wrap(apdisconnect)
    
    def rcon(self, irc, msg, args, command):
        """ <rcon command>
        
        sends a rcon command to openttd
        """
        
        if isChannel(msg.arg[0]) and not msg.arg[0] == self.connection.channel:
            return
        if self._checkPermission(irc, msg, self.connection.channel, self.connection.allowOps):
            
            if not self.connection.is_connected:
                irc.reply('Not connected!!', prefixNick = False)
                return
            if len(command) >= NETWORK_RCONCOMMAND_LENGTH:
                message = "RCON Command too long (%d/%d)" % (len(command), NETWORK_RCONCOMMAND_LENGTH)
                irc.reply(message, prefixNick = False)
                return
            self.connection.send_packet(AdminRcon, command = command)
        else:
                irc.reply('Not connected!!', prefixNick = False)
    rcon = wrap(rcon, ['text'])
                
Class = Soap

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
