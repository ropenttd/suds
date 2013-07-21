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

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks

import threading
import socket
from libottdadmin2.client import (AdminClient, AdminRcon, ServerRcon,
    ServerRconEnd)


class Soap(callbacks.Plugin):
    """
    This plugin allows supybot to interface to OpenTTD via its built-in
    adminport protocol
    """

    def __init__(self, irc):
        self.__parent = super(Soap, self)
        self.__parent.__init__(irc)
        self.e = threading.Event()
        self.connection = AdminClient()
        
        # for testing purposes untill config.py is active
        self.servername = 'testserver'
        self.server = '192.168.0.4'
        self.port = 3977
        self.password = 'blobber1'
        self.timeout = 0.4
        self.channel = '#turbulent'
    
    # incomplete def
    def _pollForData(self, irc):
        index = 1
        self.log.info('polling')
        self.log.info('value of isSet: %s' % self.e.isSet())
        while not self.e.isSet():
            index += 1
            self.log.info('poll')
    
    def apconnect(self, irc, msg, args):
        """
        connect to AdminPort of OpenTTD server
        """
        if self.connection.is_connected:
            msg = ('already connected to server %s. If you wish to reconnect, use !apdisconnect first.' % self.connection.host)
            irc.error(msg)
        else:
            msg = 'Connecting to %s' % self.servername
            irc.reply(msg, prefixNick=False)
            
            self.e.clear()
            self.connection = AdminClient()
            self.connection.configure(password = self.password,
                host = self.server, port = self.port)
            self.connection.settimeout(0.4)
            self.connection.connect()
            failed = False
            protocol_response = None
            welcome_response = None
            try:
                protocol_response = self.connection.recv_packet()
                self.log.info('Protocol response received: %s',
                    protocol_response)
                welcome_response = self.connection.recv_packet()
                self.log.info('Welcome response received: %s',
                    welcome_response)
                if protocol_response is None or welcome_response is None:
                    failed = True
                    self.log.info('no response from server')
            except socket.error, v:
                failed = True
                error1 = v[0]
                error2 = v[1]
                errormsg = 'error connecting: %s - %s' % (error1, error2)
                self.log.info(errormsg)
            
            if failed:
                msg = 'unable to connect to %s:%s. Check you have entered the right details and that the server is up' % (self.connection.host, self.connection.port)
                self.log.info(msg)
            else:
                msg = 'Connected to %s' % self.connection.host
                irc.reply(msg, prefixNick=False)
                t = threading.Thread(target=self._pollForData, kwargs={'irc':irc})
                t.start()
                
    apconnect = wrap(apconnect, [('checkCapability', 'trusted')])
    
    def apdisconnect(self, irc, msg, args):
        """
        disconnect from server
        """
        
        if self.connection.is_connected:
            msg = 'Disconnecting from OpenTTD'
            irc.reply(msg, prefixNick=False)
            self.e.set()
            self.connection.disconnect()
        else:
            irc.error('Not connected!', prefixNick=False)
    apdisconnect = wrap(apdisconnect, [('checkCapability', 'trusted')])

Class = Soap

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
