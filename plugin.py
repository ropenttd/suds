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
from datetime import datetime

from soapclient import SoapClient
from libottdadmin2.trackingclient import poll, POLLIN, POLLOUT, POLLERR, POLLHUP, POLLPRI, POLL_MOD
from libottdadmin2.constants import *
from libottdadmin2.enums import *
from libottdadmin2.packets import *


class Soap(callbacks.Plugin):
    """
    This plug-in allows supybot to interface to OpenTTD via its built-in
    adminport protocol
    """

    def __init__(self, irc):
        self.__parent = super(Soap, self)
        self.__parent.__init__(irc)

        self._pollObj = poll()
        self.channels = self.registryValue('channels')
        self.connections = []
        for channel in self.channels:
            conn = SoapClient()
            self._attachEvents(conn)
            self._initSoapClient(conn, irc, channel)
            self.connections.append(conn)
            if conn.autoConnect:
                self._connectOTTD(irc, conn, conn.channel)
        self.stopPoll = threading.Event()
        self.pollingThread = threading.Thread(target = self._pollThread)
        self.pollingThread.daemon = True
        self.pollingThread.start()

    def _pollThread(self):
        timeout = 1.0

        while True:
            polList = []
            for conn in self.connections:
                if conn.is_connected:
                    polList.append(conn.fileno())
            if len(polList) >= 1:
                events = self._pollObj.poll(timeout * POLL_MOD)
                for fileno, event in events:
                    if polList.count(fileno) == 0:
                        continue
                    conn = self._getConnectionFromID('fileno', fileno)
                    if (event & POLLIN) or (event & POLLPRI):
                        packet = conn.recv_packet()
                        if packet == None:
                            polList.remove(fileno)
                            self._disconnect(conn, True)
                        else:
                            #self.log.info('%s - %s' % (conn.ID, packet))
                            pass
                    elif (event & POLLERR) or (event & POLLHUP):
                        polList.remove(fileno)
                        self._disconnect(conn, True)
                else:
                    time.sleep(0.1)
            # lets not use up 100% cpu if there are no active connections
            else:
                time.sleep(1)
            if self.stopPoll.isSet():
                break

    def die(self):
        try:
            for conn in self.connections:
                self._disconnect(conn, False)
            self.stopPoll.set()
            self.pollingThread.join()
        except NameError:
            pass

    def doJoin(self, irc, msg):
        channel = msg.args[0].lower()
        conn = None
        if msg.nick == irc.nick and self.channels.count(channel) >=1:
            conn = self._getConnectionFromID('channel', channel)
            if not conn:
                return
            if conn.is_connected:
                text = 'Connected to %s (Version %s)' % (conn.serverinfo.name, conn.serverinfo.version)
                self._msgChannel(conn._irc, conn.channel, text)




    # Connection management

    def _attachEvents(self, conn):
        conn.soapEvents.new_map         += self._rcvNewMap

        conn.soapEvents.clientjoin      += self._rcvClientJoin
        conn.soapEvents.clientquit      += self._rcvClientQuit
        conn.soapEvents.clientupdate    += self._rcvClientUpdate

        conn.soapEvents.chat            += self._rcvChat
        conn.soapEvents.rcon            += self._rcvRcon

    def _connectOTTD(self, irc, conn, source = None):
        text = 'Connecting...'
        self._msgChannel(irc, conn.channel, text)
        conn = self._refreshConnection(conn)
        if source != conn.channel and source != None:
            self._msgChannel(irc, source, text)
        self._initSoapClient(conn, irc, conn.channel)
        conn.connect()
        if conn.is_connected:
            conn.polling = True

    def _initSoapClient(self, conn, irc, channel):
        conn.configure(
            irc         = irc,
            ID          = self.registryValue('serverID', channel),
            password    = self.registryValue('password', channel),
            host        = self.registryValue('host', channel),
            port        = self.registryValue('port', channel),
            channel     = channel,
            autoConnect = self.registryValue('autoConnect', channel),
            allowOps    = self.registryValue('allowOps', channel),
            minPlayers  = self.registryValue('minPlayers', channel),
            playAsPlayer = self.registryValue('playAsPlayer', channel),
            name        = '%s-Soap' % irc.nick)
        self._pollObj.register(conn.fileno(), POLLIN | POLLERR | POLLHUP | POLLPRI)

    def _disconnect(self, conn, forced):
        try:
            self._pollObj.unregister(conn.fileno())
        except:
            pass
        conn.polling = False
        if forced:
            conn.force_disconnect()
        else:
            conn.disconnect()



    # Miscelanious functions

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

    def _getConnection(self, source, serverID = None):
        if not serverID is None:
            if ircutils.isChannel(serverID):
                conn = self._getConnectionFromID('channel', serverID)
            else:
                conn = self._getConnectionFromID('ID', serverID)
        else:
            if ircutils.isChannel(source) and source in self.channels:
                conn = self._getConnectionFromID('channel', source)
            else:
                conn = None
        return conn

    def _getConnectionFromID(self, which, connID):
        if which == 'fileno':
            for conn in self.connections:
                if conn.fileno() == connID:
                    return conn
        elif which == 'channel':
            for conn in self.connections:
                if conn.channel == connID:
                    return conn
        elif which == 'ID':
            for conn in self.connections:
                if conn.ID == connID:
                    return conn
        return None

    def _msgChannel(self, irc, channel, msg):
        if channel in irc.state.channels or irc.isNick(channel):
            irc.queueMsg(ircmsgs.privmsg(channel, msg))

    def _moveToSpectators(self, irc, conn, client):
        command = 'move %s 255' % client.id

        conn.send_packet(AdminRcon, command = command)
        text = '%s: Please change your name before joining/starting a company' % client.name
        conn.send_packet(AdminChat,
            action = Action.CHAT,
            destType = DestType.BROADCAST,
            clientID = ClientID.SERVER,
            message = text)
        self._msgChannel(irc, conn._channel, text)

    def _refreshConnection(self, conn):
        conn = conn.copy()
        for i, c in enumerate(self.connections):
            if c.channel == conn.channel:
                self.connections[i] = conn
                break
        return conn



    # Packet Handlers

    def _rcvNewMap(self, connChan, mapinfo, serverinfo):
        conn = self._getConnectionFromID('channel', connChan)
        if not conn:
            return
        irc = conn.irc

        text = 'Connected to %s (Version %s)' % (serverinfo.name, serverinfo.version)
        self._msgChannel(conn._irc, connChan, text)

    def _rcvClientJoin(self, connChan, client):
        conn = self._getConnectionFromID('channel', connChan)
        if not conn or isinstance(client, (long, int)):
            return
        irc = conn.irc

        text = '*** %s (Client #%s) has joined the game' % (client.name, client.id)
        self._msgChannel(conn._irc, conn._channel, text)

    def _rcvClientQuit(self, connChan, client, errorcode):
        conn = self._getConnectionFromID('channel', connChan)
        if not conn or isinstance(client, (long, int)):
            return
        irc = conn.irc

        text = '*** %s (Client #%s) has left the game (leaving)' % (client.name, client.id)
        self._msgChannel(conn._irc, conn._channel, text)

    def _rcvClientUpdate(self, connChan, old, client, changed):
        conn = self._getConnectionFromID('channel', connChan)
        if not conn:
            return
        irc = conn.irc

        if 'name' in changed:
            text = "*** %s is now known as %s" % (old.name, client.name)
            self._msgChannel(conn._irc, conn._channel, text)

    def _rcvChat(self, connChan, client, action, destType, clientID, message, data):
        conn = self._getConnectionFromID('channel', connChan)
        if not conn:
            return
        irc = conn.irc

        clientName = str(clientID)
        clientCompany = None
        if client != clientID:
            clientName = client.name
            clientCompany = conn.companies.get(client.play_as)
        if clientCompany:
            companyName = clientCompany.name
            companyID = clientCompany.id + 1
        else:
            companyName = 'Unknown'
            companyID = '?'

        if action == Action.CHAT:
            text = '<%s> %s' % (clientName, message)
            self._msgChannel(irc, conn._channel, text)
        elif action == Action.COMPANY_SPECTATOR:
            text = '*** %s has joined spectators' % clientName
            self._msgChannel(irc, conn._channel, text)
        elif action == Action.COMPANY_JOIN:
            text = '*** %s has joined %s (Company #%s)' % (clientName, companyName, companyID)
            self._msgChannel(irc, conn._channel, text)
            clientName = clientName.lower()
            if clientName.startswith('player') and not conn.playAsPlayer:
                self._moveToSpectators(irc, conn, client)
        elif action == Action.COMPANY_NEW:
            text = '*** %s had created a new company: %s(Company #%s)' % (clientName, companyName, companyID)
            self._msgChannel(irc, conn._channel, text)
            clientName = clientName.lower()
            if clientName.startswith('player') and not conn.playAsPlayer:
                self._moveToSpectators(irc, conn, client)

    def _rcvRcon(self, connChan, result, colour):
        conn = self._getConnectionFromID('channel', connChan)
        if not conn:
            return
        if conn.rcon == 'Silent':
            return
        irc = conn.irc

        self._msgChannel(conn._irc, conn.rcon, result)



    # IRC commands

    def apconnect(self, irc, msg, args, serverID = None):
        """ [Server ID or channel]

        connect to AdminPort of the [specified] OpenTTD server
        """

        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        conn = self._getConnection(source, serverID)
        if conn == None:
            return

        if self._checkPermission(irc, msg, conn.channel, conn.allowOps):
            if conn.is_connected:
                irc.reply('Already connected!!', prefixNick = False)
            else:
                # just in case an existing connection failed to de-register upon disconnect
                try:
                    self._pollObj.unregister(conn.fileno())
                except KeyError:
                    pass
                except IOError:
                    pass
                self._connectOTTD(irc, conn, source)
    apconnect = wrap(apconnect, [optional('text')])

    def apdisconnect(self, irc, msg, args, serverID = None):
        """ [Server ID or channel]

        disconnect from the [specified] server
        """

        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        conn = self._getConnection(source, serverID)
        if conn == None:
            return

        if self._checkPermission(irc, msg, conn.channel, conn.allowOps):
            if conn.is_connected:
                irc.reply('Disconnecting')
                self._disconnect(conn, False)
                if not conn.is_connected:
                    irc.reply('Disconnected', prefixNick = False)
            else:
                irc.reply('Not connected!!', prefixNick = False)
    apdisconnect = wrap(apdisconnect, [optional('text')])

    def date(self, irc, msg, args, serverID = None):
        """ [Server ID or channel]

        display the ingame date of the [specified] server
        """

        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        conn = self._getConnection(source, serverID)
        if conn == None:
            return

        if not conn.is_connected:
            irc.reply('Not connected!!', prefixNick = False)
            return
        message = '%s' % conn.date.strftime('%b %d %Y')
        irc.reply(message, prefixNick = False)
    date = wrap(date, [optional('text')])

    def companies(self, irc, msg, args, serverID = None):
        """ [Server ID or channel]

        display the companies on the [specified] server
        """

        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        conn = self._getConnection(source, serverID)
        if conn == None:
            return

        if not conn.is_connected:
            irc.reply('Not connected!!', prefixNick = False)
            return
        companies = False
        for i in conn.companies:
            if i == 255:
                continue
            comp = None
            comp = conn.companies.get(i)
            if comp == None:
                return
            companies = True
            if comp.economy.money >= 0:
                fortune = 'Fortune: %s' % comp.economy.money
            else:
                fortune = 'Debt: %s' % comp.economy.money
            if comp.economy.currentLoan > 0:
                loan = ', Loan: %s' % comp.economy.currentLoan
            else:
                loan = ''
            vehicles = 'Vehicles (T: %s R: %s S: %s P: %s)' % (
                comp.vehicles.train, comp.vehicles.lorry + comp.vehicles.bus,
                comp.vehicles.ship, comp.vehicles.plane)
            message = "#%s Name '%s' Established %s, %s%s, %s" % (
                comp.id+1, comp.name, comp.startyear, fortune, loan, vehicles)
            irc.reply(message, prefixNick = False)
        if not companies:
            message = 'No companies'
            irc.reply(message, prefixNick = False)
    companies = wrap(companies, [optional('text')])

    def clients(self, irc, msg, args, serverID = None):
        """ [Server ID or channel]

        display the companies on the [specified] server
        """

        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        conn = self._getConnection(source, serverID)
        if conn == None:
            return

        if not conn.is_connected:
            irc.reply('Not connected!!', prefixNick = False)
            return
        clients = False
        for i in conn.clients:
            client = None
            client = conn.clients.get(i)
            if client == None:
                return
            elif client.name == '':
                continue
            clients = True
            if client.play_as == 255:
                companyName = 'Spectating'
            else:
                company = conn.companies.get(client.play_as)
                companyName = "Company: '%s'" % company.name
            message = "Client #%s, Name: '%s' %s" % (
                client.id, client.name, companyName)
            irc.reply(message, prefixNick = False)
        if not clients:
            message = 'No clients connected'
            irc.reply(message, prefixNick = False)
    clients = wrap(clients, [optional('text')])

    def rcon(self, irc, msg, args, command):
        """ [Server ID or channel] <rcon command>

        sends a rcon command to the [specified] openttd server
        """

        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        serverID = None
        firstWord = command.partition(' ')[0]
        conns = []
        for c in self.connections:
            conns.append(c.channel)
            conns.append(c.ID)
        if firstWord in conns:
            serverID = firstWord
            command = command.partition(' ')[2]

        conn = self._getConnection(source, serverID)
        if conn == None:
            return

        if self._checkPermission(irc, msg, conn.channel, conn.allowOps):
            if not conn.is_connected:
                irc.reply('Not connected!!', prefixNick = False)
                return
            if conn.rcon != 'Silent':
                message = 'Sorry, still processing previous rcon command'
                irc.reply(message, prefixNick = False)
                return
            if len(command) >= NETWORK_RCONCOMMAND_LENGTH:
                message = "RCON Command too long (%d/%d)" % (len(command), NETWORK_RCONCOMMAND_LENGTH)
                irc.reply(message, prefixNick = False)
                return
            else:
                conn.rcon = source
                conn.send_packet(AdminRcon, command = command)
    rcon = wrap(rcon, ['text'])

    def pause(self, irc, msg, args, serverID = None):
        """ [Server ID or channel]

        pauses the [specified] game server
        """

        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        conn = self._getConnection(source, serverID)
        if conn == None:
            return

        if self._checkPermission(irc, msg, conn.channel, conn.allowOps):
            if not conn.is_connected:
                irc.reply('Not connected!!', prefixNick = False)
                return
            command = 'pause'
            conn.send_packet(AdminRcon, command = command)
    pause = wrap(pause, [optional('text')])

    def auto(self, irc, msg, args, serverID = None):
        """ [Server ID or channel]

        unpauses the [specified] game server, or if min_active_clients > 1,
        changes the server to autopause mode
        """

        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        conn = self._getConnection(source, serverID)
        if conn == None:
            return

        if self._checkPermission(irc, msg, conn.channel, conn.allowOps):
            if not conn.is_connected:
                irc.reply('Not connected!!', prefixNick = False)
                return
            command = 'set min_active_clients %s' % conn.minPlayers
            conn.send_packet(AdminRcon, command = command)
            command = 'unpause'
            conn.send_packet(AdminRcon, command = command)
    auto = wrap(auto, [optional('text')])

    def unpause(self, irc, msg, args, serverID = None):
        """ [Server ID or channel]

        unpauses the [specified] game server, or if min_active_clients > 1,
        changes the server to autopause mode
        """

        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        conn = self._getConnection(source, serverID)
        if conn == None:
            return

        if self._checkPermission(irc, msg, conn.channel, conn.allowOps):
            if not conn.is_connected:
                irc.reply('Not connected!!', prefixNick = False)
                return
            command = 'set min_active_clients 0'
            conn.send_packet(AdminRcon, command = command)
            command = 'unpause'
            conn.send_packet(AdminRcon, command = command)
    unpause = wrap(unpause, [optional('text')])



    # Relay IRC back ingame

    def doPrivmsg(self, irc, msg):

        (source, text) = msg.args
        conn = None
        source = source.lower()
        if irc.isChannel(source) and source in self.channels:
            conn = self._getConnectionFromID('channel', source)
        if conn == None:
            return
        if not conn.is_connected:
            return

        actionChar = conf.get(conf.supybot.reply.whenAddressedBy.chars, source)
        if actionChar in text[:1]:
            return
        if not 'ACTION' in text:
            message = 'IRC <%s> %s' % (msg.nick, text)
        else:
            text = text.split(' ',1)[1]
            text = text[:-1]
            message = 'IRC ** %s %s' % (msg.nick, text)
        conn.send_packet(AdminChat,
            action = Action.CHAT,
            destType = DestType.BROADCAST,
            clientID = ClientID.SERVER,
            message = message)

Class = Soap

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
