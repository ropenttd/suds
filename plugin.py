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
        self.connection = AdminClient()
        
        # for testing purposes untill config.py is active
        self.servername = 'testserver'
        self.server = '192.168.0.4'
        self.port = 3977
        self.password = 'blobber1'
        self.timeout = 0.4
        self.channel = '#turbulent'
    
    # incomplete def
    def _apreceive(self):
        cont = True
        while cont:
            packets = self.connection.poll()
            if packets is None or packets is False:
                #print("Connection lost!")
                break
            cont = len(packets) > 0
            for packet, data in packets:
                if packet == ServerRcon:
                    pass
                    #print(">>> %s" % data['result'])
                elif packet == ServerRconEnd:
                    #print("<<< END OF COMMAND >>>")
                    cont = False
                    break
                else:
                    pass
    
    def apconnect(self, irc, msg, args):
        """
        connect to AdminPort of OpenTTD server
        """
        if self.connection.is_connected:
            irc.error('already connected to server %s. ',
                'If you wish to reconnect, use !apdisconnect first.',
                self.connection.host)
        else:
            msg = 'Connecting to %s' % self.servername
            irc.queueMsg(ircmsgs.privmsg(self.channel, msg))
            irc.noReply()
            
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
                self.log.info('error connecting: %s - %s' % (error1, error2))
            
            if failed:
                irc.error('unable to connect to %s:%s. ',
                    'Check you have entered the right details and ',
                    'that the server is up',
                    (self.connection.host, self.connection.port))
            else:
                msg = 'Connected to %s' % self.connection.host
                irc.queueMsg(ircmsgs.privmsg(self.channel, msg))

    apconnect = wrap(apconnect, [('checkCapability', 'trusted')])
    
    def apdisconnect(self, irc, msg, args):
        """
        disconnect from server
        """
        
        if self.connection.is_connected:
            msg = 'Disconnecting from OpenTTD'
            irc.queueMsg(ircmsgs.privmsg(self.channel, msg))
            self.connection.disconnect()
        else:
            irc.error('Not connected!')
    apdisconnect = wrap(apdisconnect, [('checkCapability', 'trusted')])

Class = Soap

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
