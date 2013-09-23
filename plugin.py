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

import os
import random
import re
import socket
import subprocess
import sys
import threading
import time

from datetime import datetime

from soapclient import SoapClient
from enums import *

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
        self.connections = {}
        self.registeredConnections = {}
        for channel in self.channels:
            conn = SoapClient()
            self._attachEvents(conn)
            self._initSoapClient(conn, irc, channel)
            self.connections[channel] = conn
            if self.registryValue('autoConnect', channel):
                self._connectOTTD(irc, conn, channel)
        self.stopPoll = threading.Event()
        self.pollingThread = threading.Thread(target = self._pollThread, name = 'SoapPollingThread')
        self.pollingThread.daemon = True
        self.pollingThread.start()

    def _pollThread(self):
        timeout = 1.0

        while True:
            if len(self.registeredConnections) >= 1:
                events = self._pollObj.poll(timeout * POLL_MOD)
                for fileno, event in events:
                    conn = self.registeredConnections.get(fileno)
                    if conn == None:
                        continue
                    if (event & POLLIN) or (event & POLLPRI):
                        packet = conn.recv_packet()
                        if packet == None:
                            self._disconnect(conn, True)
                        # else:
                        #     self.log.info('%s - %s' % (conn.ID, packet))
                    elif (event & POLLERR) or (event & POLLHUP):
                        self._disconnect(conn, True)
                else:
                    time.sleep(0.1)
            # lets not use up 100% cpu if there are no active connections
            else:
                time.sleep(1)
            if self.stopPoll.isSet():
                break

    def _passwordThread(self, conn):
        pluginDir = os.path.dirname(__file__)
        pwFileName = os.path.join(pluginDir, 'passwords.txt')

        while True:
            interval = self.registryValue('passwordInterval', conn.channel)
            if conn.connectionstate != ConnectionState.CONNECTED:
                break
            if conn.rcon == RconSpecial.SILENT:
                if interval > 0:
                    newPassword = random.choice(list(open(pwFileName)))
                    newPassword = newPassword.strip()
                    newPassword = newPassword.lower()
                    command = 'set server_password %s' % newPassword
                    conn.send_packet(AdminRcon, command = command)
                    conn.clientPassword = newPassword
                    time.sleep(interval)
                else:
                    command = 'set server_password *'
                    conn.send_packet(AdminRcon, command = command)
                    conn.clientPassword = None
                    break

    def die(self):
        for conn in self.connections.itervalues():
            try:
                if conn.connectionstate == ConnectionState.CONNECTED:
                    conn.connectionstate = ConnectionState.DISCONNECTING
                    self._disconnect(conn, False)
            except NameError:
                pass
        self.stopPoll.set()
        self.pollingThread.join()

    def doJoin(self, irc, msg):
        channel = msg.args[0].lower()
        conn = None
        if msg.nick == irc.nick and self.channels.count(channel) >=1:
            conn = self.connections.get(channel)
            if conn == None:
                return
            if conn.connectionstate == ConnectionState.CONNECTED:
                text = 'Connected to %s (Version %s)' % (conn.serverinfo.name, conn.serverinfo.version)
                self._msgChannel(conn._irc, conn.channel, text)



    # Connection management

    def _attachEvents(self, conn):
        conn.soapEvents.connected       += self._connected
        conn.soapEvents.disconnected    += self._disconnected

        conn.soapEvents.shutdown        += self._rcvShutdown
        conn.soapEvents.new_game        += self._rcvNewGame

        conn.soapEvents.new_map         += self._rcvNewMap

        conn.soapEvents.clientjoin      += self._rcvClientJoin

        conn.soapEvents.chat            += self._rcvChat
        conn.soapEvents.rcon            += self._rcvRcon
        conn.soapEvents.console         += self._rcvConsole

        conn.soapEvents.pong            += self._rcvPong

    def _connectOTTD(self, irc, conn, source = None, text = 'Connecting...'):
        self._msgChannel(irc, conn.channel, text)
        if source != conn.channel and source != None:
            self._msgChannel(irc, source, text)
        conn = self._refreshConnection(conn)
        self._initSoapClient(conn, irc, conn.channel)
        conn.connectionstate = ConnectionState.CONNECTING
        if not conn.connect():
            conn.connectionstate = ConnectionState.DISCONNECTED
            text = 'Failed to connect'
            self._msgChannel(irc, conn.channel, text)

    def _connected(self, connChan):
        conn = self.connections.get(connChan)
        if conn == None:
            return

        conn.connectionstate = ConnectionState.CONNECTED
        pwInterval = self.registryValue('passwordInterval', connChan)
        if pwInterval != 0:
            pwThread = threading.Thread(target = self._passwordThread, args = [conn])
            pwThread.daemon = True
            pwThread.start()
        else:
            command = 'set server_password *'
            conn.send_packet(AdminRcon, command = command)
            conn.clientPassword = None

    def _disconnected(self, connChan, canRetry):
        conn = self.connections.get(connChan)
        if conn == None:
            return
        irc = conn.irc
        fileno = conn.filenumber

        try:
            del self.registeredConnections[fileno]
        except KeyError:
            pass
        try:
            self._pollObj.unregister(fileno)
        except KeyError:
            pass

        if conn.serverinfo.name != None:
            text = 'Disconnected from %s' % (conn.serverinfo.name)
            self._msgChannel(conn.irc, connChan, text)
            conn.serverinfo.name = None
        if conn.connectionstate == ConnectionState.CONNECTED:
            # We didn't disconnect on purpose, set this so we will reconnect
            conn.connectionstate == ConnectionState.DISCONNECTED
            text = 'Attempting to reconnect...'
            self._connectOTTD(irc, conn, text = text)
        else:
            conn.connectionstate = ConnectionState.DISCONNECTED

    def _initSoapClient(self, conn, irc, channel):
        conn.configure(
            irc         = irc,
            ID          = self.registryValue('serverID', channel),
            password    = self.registryValue('password', channel),
            host        = self.registryValue('host', channel),
            port        = self.registryValue('port', channel),
            channel     = channel,
            name        = '%s-Soap' % irc.nick)
        self._pollObj.register(conn.fileno(), POLLIN | POLLERR | POLLHUP | POLLPRI)
        conn.filenumber = conn.fileno()
        self.registeredConnections[conn.filenumber] = conn

    def _disconnect(self, conn, forced):
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

    def _ircCommandInit(self, irc, msg, serverID, needsPermission):
        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        conn = self._getConnection(source, serverID)
        if conn == None:
            self.log.info('no conn found, returning none none')
            return (None, None)
        allowOps = self.registryValue('allowOps', conn.channel)

        if not needsPermission:
            return (source, conn)
        elif self._checkPermission(irc, msg, conn.channel, allowOps):
            return (source, conn)
        else:
            return (None, 'Denied')

    def _getConnection(self, source, serverID = None):
        conn = None

        if serverID == None:
            if ircutils.isChannel(source) and source in self.channels:
                conn = self.connections.get(source)
        else:
            if ircutils.isChannel(serverID):
                conn = self.connections.get(serverID)
            else:
                for c in self.connections.itervalues():
                    if c.ID.lower() == serverID.lower():
                        conn = c
        return conn

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
        self._msgChannel(irc, conn.channel, text)

    def _refreshConnection(self, conn):
        try:
            del self.registeredConnections[conn.filenumber]
        except KeyError:
            pass
        newconn = conn.copy()
        self.connections[conn.channel] = newconn
        return newconn

    def _ircRcon(self, irc, msg, args, command):
        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        serverID = None
        firstWord = command.partition(' ')[0]
        conns = []
        for c in self.connections.itervalues():
            conns.append(c.channel)
            conns.append(c.ID)
        if firstWord in conns:
            serverID = firstWord
            command = command.partition(' ')[2]

        conn = self._getConnection(source, serverID)
        if conn == None:
            return
        allowOps = self.registryValue('allowOps', conn.channel)

        if self._checkPermission(irc, msg, conn.channel, allowOps):
            if conn.connectionstate != ConnectionState.CONNECTED:
                irc.reply('Not connected!!', prefixNick = False)
                return
            if conn.rcon != RconSpecial.SILENT:
                message = 'Sorry, still processing previous rcon command'
                irc.reply(message, prefixNick = False)
                return
            if len(command) >= NETWORK_RCONCOMMAND_LENGTH:
                message = "RCON Command too long (%d/%d)" % (len(command), NETWORK_RCONCOMMAND_LENGTH)
                irc.reply(message, prefixNick = False)
                return
            conn.rcon = source
            self.log.info('rcon command: %s' % command)
            conn.send_packet(AdminRcon, command = command)

    def _getLatestAutoSave(self, autosavedir):
        max_mtime = 0
        save = None
        for fname in os.listdir(autosavedir):
            if fname.startswith('autosave'):
                fullpath = os.path.join(autosavedir, fname)
                mtime = os.stat(fullpath).st_mtime
                if mtime > max_mtime:
                    max_mtime = mtime
                    save = fullpath
        return save

    def _checkIfRunning(self, gamedir):
        pidfilename = gamedir + 'openttd.pid'
        executable = 'openttd'

        try:
            with open(pidfilename) as pidfile:
                pid = pidfile.readline()
        except IOError:
            return False
        ps = subprocess.Popen('ps -A', shell=True, stdout=subprocess.PIPE)
        output = ps.stdout.read()
        ps.stdout.close()
        ps.wait()
        for line in output.split('\n'):
            if line != '' and line != None:
                fields = line.split()
                pspid = fields[0]
                pspname = fields[3]
                if (pspid == pid) and (executable == pspname):
                    return True
        else:
            return False

    def _startserver(self, gamedir, parameters):
        running = self._checkIfRunning(gamedir)

        if running:
            return ServerStartStatus.ALREADYRUNNING

        pidfilename = os.path.join(gamedir, 'openttd.pid')
        executable = os.path.join(gamedir, 'openttd')
        autosavedir = os.path.join(gamedir, 'save/autosave/')
        lastsave = self._getLatestAutoSave(autosavedir)

        command = []
        command.append(executable)
        command.extend(['-D', '-f'])
        if not lastsave == None and os.path.isfile(lastsave):
            command.extend(['-g', lastsave])
        if not parameters == 'None':
            command.extend(parameters)

        commandtext = ''
        for item in command:
            commandtext += item + ' '
        self.log.info('executing: %s' % commandtext)

        try:
            game = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE)
            output = game.stdout.read()
            game.stdout.close()
            game.wait()
        except OSError as e:
            return ServerStartStatus.FAILOSERROR
        except Exception as e:
            self.log.info('Except triggered: %s' % sys.exc_info()[0])
            return ServerStartStatus.FAILUNKNOWN

        pid = None
        for line in output.split('\n'):
            self.log.info('OpenTTD output: %s' % line)
            if 'Forked to background with pid' in line:
                words = line.split()
                pid = words[6]
                try:
                    with open(pidfilename, 'w') as pidfile:
                        pidfile.write(str(pid))
                except:
                    self.log.info('pidfile error: %s' % sys.exc_info()[0])
                    return ServerStartStatus.SUCCESSNOPIDFILE
                return ServerStartStatus.SUCCESS
        return ServerStartStatus.FAILNOPID



    # Packet Handlers

    def _rcvShutdown(self, connChan):
        conn = self.connections.get(connChan)
        if conn == None:
            return
        irc = conn.irc

        text = 'Server Shutting down'
        self._msgChannel(irc, conn.channel, text)

    def _rcvNewGame(self, connChan):
        conn = self.connections.get(connChan)
        if conn == None:
            return
        irc = conn.irc

        text = 'Starting new game'
        self._msgChannel(irc, conn.channel, text)

    def _rcvNewMap(self, connChan, mapinfo, serverinfo):
        conn = self.connections.get(connChan)
        if conn == None:
            return
        irc = conn.irc

        text = 'Now playing on %s (Version %s)' % (conn.serverinfo.name, conn.serverinfo.version)
        self._msgChannel(irc, conn.channel, text)

    def _rcvClientJoin(self, connChan, client):
        conn = self.connections.get(connChan)
        if conn == None or isinstance(client, (long, int)):
            return
        irc = conn.irc
        welcome = self.registryValue('welcomeMessage', conn.channel)

        if welcome != None:
            replacements = {'{clientname}':client.name, '{servername}': conn.serverinfo.name, '{serverversion}': conn.serverinfo.version}
            for line in welcome:
                for word, newword in replacements.iteritems():
                    line = line.replace(word, newword)
                conn.send_packet(AdminChat,
                    action = Action.CHAT_CLIENT,
                    destType = DestType.CLIENT,
                    clientID = client.id,
                    message = line)

    def _rcvChat(self, connChan, client, action, destType, clientID, message, data):
        conn = self.connections.get(connChan)
        if conn == None:
            return
        irc = conn.irc

        clientName = str(clientID)
        if client != clientID:
            clientName = client.name

        if action == Action.CHAT:
            if message.startswith('!admin'):
                text = '*** %s has requested an admin. (Note: Admin will read back on irc, so please do already write down your request, no need to wait.)' % clientName
                self._msgChannel(irc, conn.channel, text)
                conn.send_packet(AdminChat,
                    action = Action.CHAT,
                    destType = DestType.BROADCAST,
                    clientID = ClientID.SERVER,
                    message = text)
            elif message.startswith('!nick '):
                newName = message.partition(' ')[2]
                newName = newName.strip()
                if len(newName) > 0:
                    text = '*** %s has changed his/her name to %s' % (clientName, newName)
                    self._msgChannel(irc, conn.channel, text)
                    command = 'client_name %s %s' % (clientID, newName)
                    conn.send_packet(AdminRcon, command = command)
            else:
                text = '<%s> %s' % (clientName, message)
                self._msgChannel(irc, conn.channel, text)
        elif action == Action.COMPANY_JOIN or action == Action.COMPANY_NEW:
            clientName = clientName.lower()
            playAsPlayer = self.registryValue('playAsPlayer', conn.channel)
            if clientName.startswith('player') and not playAsPlayer:
                self._moveToSpectators(irc, conn, client)

    def _rcvRcon(self, connChan, result, colour):
        conn = self.connections.get(connChan)
        if conn == None or conn.rcon == RconSpecial.SILENT:
            return
        irc = conn.irc

        if conn.rcon == RconSpecial.SHUTDOWNSAVED:
            if result.startswith('Map successfully saved'):
                self._msgChannel(irc, conn.channel, 'Succesfully saved game as autosavesoap.sav')
                conn.connectionstate = ConnectionState.DISCONNECTING
                command = 'quit'
                conn.send_packet(AdminRcon, command = command)
            return
        self._msgChannel(irc, conn.rcon, result)

    def _rcvPong(self, connChan, start, end, delta):
        conn = self.connections.get(connChan)
        if conn == None:
            return
        irc = conn.irc

        text = 'Dong! reply took %s' % str(delta)
        self._msgChannel(irc, conn.channel, text)

    def _rcvConsole(self, connChan, origin, message):
        conn = self.connections.get(connChan)
        if conn == None:
            return
        irc = conn.irc

        if message.startswith('Game Load Failed') or message.startswith('ERROR: Game Load Failed'):
            ircMessage = message.replace("\n", ", ")
            ircMessage = ircMessage.replace("?", ", ")
            self._msgChannel(irc, conn.channel, ircMessage)
        else:
            ircMessage = message[3:]
            if ircMessage.startswith('***'):
                self._msgChannel(irc, conn.channel, ircMessage)



    # IRC commands

    def apconnect(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        connect to AdminPort of the [specified] OpenTTD server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if conn == None:
            return

        if conn.connectionstate == ConnectionState.CONNECTED:
            irc.reply('Already connected!!', prefixNick = False)
        else:
            # just in case an existing connection failed to de-register upon disconnect
            try:
                self._pollObj.unregister(conn.filenumber)
            except KeyError:
                pass
            except IOError:
                pass
            self._connectOTTD(irc, conn, source)
    apconnect = wrap(apconnect, [optional('text')])

    def apdisconnect(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        disconnect from the [specified] server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if conn == None:
            return

        if conn.connectionstate == ConnectionState.CONNECTED:
            conn.connectionstate = ConnectionState.DISCONNECTING
            self._disconnect(conn, False)
        else:
            irc.reply('Not connected!!', prefixNick = False)
    apdisconnect = wrap(apdisconnect, [optional('text')])

    def date(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        display the ingame date of the [specified] server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if conn == None:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return
        message = '%s' % conn.date.strftime('%b %d %Y')
        irc.reply(message, prefixNick = False)
    date = wrap(date, [optional('text')])

    def companies(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        display the companies on the [specified] server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if conn == None:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
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

    def clients(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        display the companies on the [specified] server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if conn == None:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
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

        self._ircRcon(irc, msg, args, command)
    rcon = wrap(rcon, ['text'])

    def content(self, irc, msg, args, command):
        """ [Server ID or channel] <content command>

        sends a rcon content command to the [specified] openttd server
        """

        command = 'content ' + command
        self._ircRcon(irc, msg, args, command)
    content = wrap(content, ['text'])

    def shutdown(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        pauses the [specified] game server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if conn == None:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return

        irc.reply('Shutting down server...', prefixNick = False)
        conn.rcon = RconSpecial.SHUTDOWNSAVED
        gamedir = self.registryValue('gamedir', conn.channel)
        autosave = os.path.join(gamedir, 'save/autosave/autosavesoap')
        command = 'save %s' % autosave
        conn.send_packet(AdminRcon, command = command)
    shutdown = wrap(shutdown, [optional('text')])

    def pause(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        pauses the [specified] game server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if conn == None:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return
        command = 'pause'
        conn.send_packet(AdminRcon, command = command)
    pause = wrap(pause, [optional('text')])

    def auto(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        unpauses the [specified] game server, or if min_active_clients >= 1,
        changes the server to autopause mode
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if conn == None:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return
        minPlayers = self.registryValue('minPlayers', conn.channel)
        if minPlayers > 0:
            command = 'set min_active_clients %s' % self.registryValue('minPlayers', conn.channel)
            conn.send_packet(AdminRcon, command = command)
        command = 'unpause'
        conn.send_packet(AdminRcon, command = command)
    auto = wrap(auto, [optional('text')])

    def unpause(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        unpauses the [specified] game server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if conn == None:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return
        command = 'set min_active_clients 0'
        conn.send_packet(AdminRcon, command = command)
        command = 'unpause'
        conn.send_packet(AdminRcon, command = command)
    unpause = wrap(unpause, [optional('text')])

    def ding(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        Dings the [specified] server, normally called ping
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if conn == None:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return
        conn.ping()
    ding = wrap(ding, [optional('text')])

    def ip(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        Replies with the [specified] server's public address for players to connect to
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if conn == None:
            return

        text = self.registryValue('publicAddress', conn.channel)
        irc.reply(text)
    ip = wrap(ip, [optional('text')])

    def password(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        tells you the current password needed for joining the [specified] game server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if conn == None:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return
        if conn.clientPassword == None:
            irc.reply('Free entry, no passwords needed')
        else:
            irc.reply(conn.clientPassword)
    password = wrap(password, [optional('text')])

    def download(self, irc, msg, args, osType, serverID):
        """ [OS type/program] [Server ID or channel]

        Returns the url to download the client for the current game. Also links to some starter programs
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if conn == None:
            return

        url = None
        if osType == 'autostart':
            url = 'http://www.openttdcoop.org/wiki/Autostart'
        elif osType == 'autottd':
            url = 'http://www.openttdcoop.org/wiki/AutoTTD'
        elif osType == 'ottdau':
            url = 'http://www.openttdcoop.org/winupdater'
        else:
            if conn.connectionstate != ConnectionState.CONNECTED:
                irc.reply('Not connected!!', prefixNick = False)
                return
            customUrl = self.registryValue('downloadUrl', conn.channel)
            if customUrl == 'None':
                version = conn.serverinfo.version
                stable = '\d\.\d\.\d'
                trunk = 'r\d{5}'
                if osType == None:
                    actionChar = conf.get(conf.supybot.reply.whenAddressedBy.chars, source)
                    irc.reply('%sdownload autostart|autottd|lin|lin64|osx|ottdau|source|win32|win64|win9x'
                        % actionChar)
                    url = 'http://www.openttd.org/en/'
                    if re.match(stable, version):
                        url += 'download-stable/%s' % version
                    elif re.match(trunk, version):
                        url += 'download-trunk/%s' % version
                    else:
                        url = None
                else:
                    url = 'http://binaries.openttd.org/'
                    if re.match(stable, version):
                        url += 'releases/%s/openttd-%s-' % (version, version)
                    elif re.match(trunk, version):
                        url += 'nightlies/trunk/%s/openttd-trunk-%s-' % (version, version)
                    else:
                        url = None
                    if not url == None:
                        if osType.startswith('lin'):
                            url += 'linux-generic-'
                            if osType == 'lin':
                                url += 'i686.tar.xz'
                            elif osType == 'lin64':
                                url += 'amd64.tar.xz'
                            else:
                                url = None
                        elif osType == 'osx':
                            url += 'macosx-universal.zip'
                        elif osType == 'source':
                            url += 'source.tar.xz'
                        elif osType.startswith('win'):
                            url += 'windows-%s.zip' % osType
                        else:
                            url = None
            else:
                url = customUrl
        if not url == None:
            irc.reply(url)
        else:
            irc.reply('Couldn\'t decipher download url')
    download = wrap(download, [optional(('literal',
        ['autostart', 'autottd', 'lin', 'lin64', 'osx', 'ottdau', 'win32', 'win64', 'win9x', 'source'])), optional('text')])




    # Relay IRC back ingame

    def doPrivmsg(self, irc, msg):

        (source, text) = msg.args
        conn = None
        source = source.lower()
        if irc.isChannel(source) and source in self.channels:
            conn = self.connections.get(source)
        if conn == None:
            return
        if conn.connectionstate != ConnectionState.CONNECTED:
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



    # Local-type only commands

    def start(self, irc, msg, args, serverID):
        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if conn == None:
            return
        if conn.connectionstate == ConnectionState.CONNECTED:
            irc.reply('I am connected to %s, so it\'s safe to assume that its already running' % conn.serverinfo.name,
                prefixNick = False)
            return
        if not self.registryValue('local', conn.channel):
            irc.reply('Sorry, this server is not set up as local', prefixNick = False)
            return
        text = 'Starting server...'
        irc.reply(text, prefixNick = False)

        gamedir = self.registryValue('gamedir', conn.channel)
        parameters = self.registryValue('parameters', conn.channel)
        result = self._startserver(gamedir, parameters)

        if result == ServerStartStatus.ALREADYRUNNING:
            text = 'Server already running. Try apconnect instead'
        elif result == ServerStartStatus.SUCCESS:
            text = 'Server started succesfully'
        elif result == ServerStartStatus.SUCCESSNOPIDFILE:
            text = 'Server started succesfully, but could not write pidfile'
        elif result == ServerStartStatus.FAILOSERROR:
            text = 'Server failed to start, couldn\'t find the executable'
        elif result == ServerStartStatus.FAILNOPID:
            text = 'Server may not have started correctly, unable to catch the PID'
        elif result == ServerStartStatus.FAILUNKNOWN:
            text = 'Server failed to start, I\'m not sure what went wrong'
        irc.reply(text, prefixNick = False)
    start = wrap(start, [optional('text')])

Class = Soap

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
