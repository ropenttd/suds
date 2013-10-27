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

from supybot.commands import *
import supybot.conf as conf
import supybot.callbacks as callbacks

import os.path
import random
import socket
from subprocess import Popen, PIPE, CalledProcessError
import sys
import threading
import time

from datetime import datetime

import soaputils as utils
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
        self.connectionIds = []
        for channel in self.channels:
            conn = SoapClient(channel)
            self._attachEvents(conn)
            self._initSoapClient(conn, irc)
            self.connections[channel.lower()] = conn
            if self.registryValue('autoConnect', channel):
                self._connectOTTD(irc, conn, channel)
        self.stopPoll = threading.Event()
        self.pollingThread = threading.Thread(
            target = self._pollThread,
            name = 'SoapPollingThread')
        self.pollingThread.daemon = True
        self.pollingThread.start()

    def die(self):
        for conn in self.connections.itervalues():
            try:
                if conn.connectionstate == ConnectionState.CONNECTED:
                    conn.connectionstate = ConnectionState.DISCONNECTING
                    utils.disconnect(conn, False)
            except NameError:
                pass
        self.stopPoll.set()
        self.pollingThread.join()

    def doJoin(self, irc, msg):
        channel = msg.args[0].lower()
        conn = None
        if msg.nick == irc.nick and self.channels.count(channel) >=1:
            conn = self.connections.get(channel)
            if not conn:
                return
            if conn.connectionstate == ConnectionState.CONNECTED:
                text = 'Connected to %s (Version %s)' % (
                    conn.serverinfo.name, conn.serverinfo.version)
                utils.msgChannel(conn._irc, conn.channel, text)



    # Connection management

    def _attachEvents(self, conn):
        conn.soapEvents.connected       += self._connected
        conn.soapEvents.disconnected    += self._disconnected

        conn.soapEvents.shutdown        += self._rcvShutdown
        conn.soapEvents.new_game        += self._rcvNewGame

        conn.soapEvents.new_map         += self._rcvNewMap

        conn.soapEvents.clientjoin      += self._rcvClientJoin
        conn.soapEvents.clientupdate    += self._rcvClientUpdate
        conn.soapEvents.clientquit      += self._rcvClientQuit

        conn.soapEvents.chat            += self._rcvChat
        conn.soapEvents.rcon            += self._rcvRcon
        conn.soapEvents.console         += self._rcvConsole
        conn.soapEvents.cmdlogging      += self._rcvCmdLogging

        conn.soapEvents.pong            += self._rcvPong

    def _connectOTTD(self, irc, conn, source = None, text = 'Connecting...'):
        utils.msgChannel(irc, conn.channel, text)
        if source and not source == conn.channel:
            utils.msgChannel(irc, source, text)
        conn = utils.refreshConnection(
            self.connections, self.registeredConnections, conn)
        self._initSoapClient(conn, irc)
        conn.connectionstate = ConnectionState.CONNECTING
        if not conn.connect():
            conn.connectionstate = ConnectionState.DISCONNECTED
            text = 'Connection failed'
            utils.msgChannel(irc, conn.channel, text)

    def _connected(self, connChan):
        conn = self.connections.get(connChan)
        if not conn:
            return

        conn.connectionstate = ConnectionState.AUTHENTICATING
        pwInterval = self.registryValue('passwordInterval', conn.channel)
        if pwInterval != 0:
            pwThread = threading.Thread(
                target = self._passwordThread,
                args = [conn])
            pwThread.daemon = True
            pwThread.start()
        else:
            command = 'set server_password *'
            conn.send_packet(AdminRcon, command = command)
            conn.clientPassword = None

    def _disconnected(self, connChan, canRetry):
        conn = self.connections.get(connChan)
        if not conn:
            return
        if conn.is_connected:
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
        except IOError:
            pass

        if conn.serverinfo.name:
            text = 'Disconnected from %s' % (conn.serverinfo.name)
            utils.msgChannel(conn.irc, conn.channel, text)
            conn.serverinfo.name = None
            logMessage = '<DISCONNECTED>'
            conn.logger.info(logMessage)

        if conn.connectionstate == ConnectionState.CONNECTED:
            # We didn't disconnect on purpose, set this so we will reconnect
            conn.connectionstate == ConnectionState.DISCONNECTED
            text = 'Attempting to reconnect...'
            self._connectOTTD(irc, conn, text = text)
        else:
            conn.connectionstate = ConnectionState.DISCONNECTED

    def _initSoapClient(self, conn, irc):
        conn.configure(
            irc         = irc,
            ID          = self.registryValue('serverID', conn.channel),
            password    = self.registryValue('password', conn.channel),
            host        = self.registryValue('host', conn.channel),
            port        = self.registryValue('port', conn.channel),
            name        = '%s-Soap' % irc.nick)
        utils.initLogger(conn, self.registryValue('logdir'))
        self._pollObj.register(conn.fileno(),
            POLLIN | POLLERR | POLLHUP | POLLPRI)
        conn.filenumber = conn.fileno()
        self.registeredConnections[conn.filenumber] = conn



    # Thread functions

    def _commandThread(self, conn, irc, ofsCommand, successText = None, delay = 0):
        time.sleep(delay)
        ofs = self.registryValue('ofslocation', conn.channel)
        command = ofs + '%s' % ofsCommand
        if ofs.startswith('ssh'):
            useshell = True
        elif os.path.isdir(ofs):
            useshell = False
        else:
            irc.reply('OFS location invalid. Please review plugins.Soap.ofslocation')
            return

        self.log.info('executing: %s' % command)
        if not useshell:
            command = command.split()
        try:
            commandObject = Popen(command, shell=useshell, stdout = PIPE)
        except OSError as e:
            irc.reply('Couldn\'t start %s, Please review plugins.Soap.ofslocation'
                % ofsCommand.split()[0])
            return
        output = commandObject.stdout.read()
        commandObject.stdout.close()
        commandObject.wait()
        for line in output.splitlines():
            self.log.info('%s output: %s' % (ofsCommand.split()[0], line))
        if commandObject.returncode:
            irc.reply('%s reported an error, exitcode: %s. See bot-log for more information.'
                % (ofsCommand.split()[0], commandObject.returncode))
            return
        if successText:
            irc.reply(successText, prefixNick = False)

        if ofsCommand.startswith('ofs-svnupdate.py'):
            irc.reply('Update successfull, shutting down server...',
                prefixNick = False)
            conn.rcon = RconSpecial.UPDATESAVED
            rconcommand = 'save autosave/autosavesoap'
            conn.send_packet(AdminRcon, command = rconcommand)
        elif ofsCommand.startswith('ofs-svntobin.py'):
            ofsCommand = 'ofs-start.py'
            successText = 'Server is starting'
            cmdThread = threading.Thread(
                target = self._commandThread,
                args = [conn, irc, ofsCommand, successText])
            cmdThread.daemon = True
            cmdThread.start()

    def _passwordThread(self, conn):
        pluginDir = os.path.dirname(__file__)
        pwFileName = os.path.join(pluginDir, 'passwords.txt')

        # delay password changing untill connection is fully established,
        # abort if it takes longer than 10 seconds
        for second in range(10):
            if conn.connectionstate == ConnectionState.CONNECTED:
                break
            time.sleep(1)
        if conn.connectionstate != ConnectionState.CONNECTED:
            return

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

    def _pollThread(self):
        timeout = 1.0

        while True:
            if len(self.registeredConnections) >= 1:
                events = self._pollObj.poll(timeout * POLL_MOD)
                for fileno, event in events:
                    conn = self.registeredConnections.get(fileno)
                    if not conn:
                        continue
                    if (event & POLLIN) or (event & POLLPRI):
                        packet = conn.recv_packet()
                        if packet == None:
                            utils.disconnect(conn, True)
                        # else:
                        #     self.log.info('%s - %s' % (conn.ID, packet))
                    elif (event & POLLERR) or (event & POLLHUP):
                        utils.disconnect(conn, True)
                else:
                    time.sleep(0.1)
            # lets not use up 100% cpu if there are no active connections
            else:
                time.sleep(1)
            if self.stopPoll.isSet():
                break



    # Miscelanious functions

    def _ircCommandInit(self, irc, msg, serverID, needsPermission):
        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        conn = utils.getConnection(
            self.connections, self.channels, source, serverID)
        if not conn:
            return (None, None)
        allowOps = self.registryValue('allowOps', conn.channel)

        if not needsPermission:
            return (source, conn)
        elif utils.checkPermission(irc, msg, conn.channel, allowOps):
            return (source, conn)
        else:
            return (None, None)

    def _ircRconInit(self, irc, msg, firstWord, remainder, command, needsPermission):
        if not remainder:
            remainder = ''
        source = msg.args[0].lower()
        if source == irc.nick.lower():
            source = msg.nick
        conn = None
        for c in self.connections.itervalues():
            if (firstWord.lower() == c.channel.lower()
                    or firstWord.lower() == c.ID.lower()):
                conn = c
                if command:
                    command += ' %s' % remainder
                else:
                    command = remainder

        if not conn:
            if command:
                command += ' %s %s' % (firstWord, remainder)
            else:
                command = '%s %s' % (firstWord, remainder)
            conn = utils.getConnection(
                self.connections, self.channels, source)
            if not conn:
                return (None, None, None)

        allowOps = self.registryValue('allowOps', conn.channel)
        if not needsPermission:
            return (source, conn, command)
        elif utils.checkPermission(irc, msg, conn.channel, allowOps):
            return (source, conn, command)
        else:
            return (None, None, None)



    # Packet Handlers

    def _rcvShutdown(self, connChan):
        conn = self.connections.get(connChan)
        if not conn:
            return
        irc = conn.irc

        text = 'Server Shutting down'
        utils.msgChannel(irc, conn.channel, text)
        logMessage = '<SHUTDOWN> Server is shutting down'
        conn.logger.info(logMessage)
        conn.connectionstate = ConnectionState.SHUTDOWN

    def _rcvNewGame(self, connChan):
        conn = self.connections.get(connChan)
        if not conn:
            return
        irc = conn.irc

        text = 'Starting new game'
        utils.msgChannel(irc, conn.channel, text)
        logMessage = '<END> End of game'
        conn.logger.info(logMessage)
        if not conn.logger == None and len(conn.logger.handlers):
            for handler in conn.logger.handlers:
                handler.doRollover()
        logMessage = '<NEW> New log file started'
        conn.logger.info(logMessage)

    def _rcvNewMap(self, connChan, mapinfo, serverinfo):
        conn = self.connections.get(connChan)
        if not conn:
            return
        irc = conn.irc

        conn.connectionstate = ConnectionState.CONNECTED
        text = 'Now playing on %s (Version %s)' % (
            conn.serverinfo.name, conn.serverinfo.version)
        utils.msgChannel(irc, conn.channel, text)
        command = 'set min_active_clients %s' % self.registryValue(
            'minPlayers', conn.channel)
        conn.send_packet(AdminRcon, command = command)
        logMessage = '-' * 80
        conn.logger.info(logMessage)
        logMessage = '<CONNECTED> Version: %s, Name: \'%s\' Mapname: \'%s\' Mapsize: %dx%d' % (
            conn.serverinfo.version, conn.serverinfo.name, conn.mapinfo.name, conn.mapinfo.x, conn.mapinfo.y)
        conn.logger.info(logMessage)

    def _rcvClientJoin(self, connChan, client):
        conn = self.connections.get(connChan)
        if not conn or isinstance(client, (long, int)):
            self.log.info('received event, not conn or client is a number')
            return
        irc = conn.irc

        text = '*** %s has joined' % client.name
        logMessage = '<JOIN> Name: \'%s\' (Host: %s, ClientID: %s)' % (
            client.name, client.hostname, client.id)
        conn.logger.info(logMessage)
        welcome = self.registryValue('welcomeMessage', conn.channel)

        if welcome:
            replacements = {
                '{clientname}':client.name,
                '{servername}': conn.serverinfo.name,
                '{serverversion}': conn.serverinfo.version}
            for line in welcome:
                for word, newword in replacements.iteritems():
                    line = line.replace(word, newword)
                conn.send_packet(AdminChat,
                    action = Action.CHAT_CLIENT,
                    destType = DestType.CLIENT,
                    clientID = client.id,
                    message = line)

    def _rcvClientUpdate(self, connChan, old, client, changed):
        conn = self.connections.get(connChan)
        if not conn:
            return
        irc = conn.irc

        if 'name' in changed:
            text = '*** %s has changed his/her name to %s' % (
                old.name, client.name)
            utils.msgChannel(conn.irc, conn.channel, text)
            logMessage = '<NAMECHANGE> Old name: \'%s\' New Name: \'%s\' (Host: %s)' % (
                old.name, client.name, client.hostname)
            conn.logger.info(logMessage)

    def _rcvClientQuit(self, connChan, client, errorcode):
        conn = self.connections.get(connChan)
        if not conn:
            return
        irc = conn.irc

        if not isinstance(client, (long, int)):
            text = '*** %s had left the game' % client.name
            utils.msgChannel(irc, conn.channel, text)
            logMessage = '<QUIT> Name: \'%s\' (Host: %s, ClientID: %s)' % (
                client.name, client.hostname, client.id)
            conn.logger.info(logMessage)

    def _rcvChat(self, connChan, client, action, destType, clientID, message, data):
        conn = self.connections.get(connChan)
        if not conn:
            return
        irc = conn.irc

        clientName = str(clientID)
        if client != clientID:
            clientName = client.name

        if action == Action.CHAT:
            if message.startswith('!admin'):
                text = '*** %s has requested an admin. (Note: Admin will read back on irc, so please do already write down your request, no need to wait.)' % clientName
                utils.msgChannel(irc, conn.channel, text)
                conn.send_packet(AdminChat,
                    action = Action.CHAT,
                    destType = DestType.BROADCAST,
                    clientID = ClientID.SERVER,
                    message = text)
            elif message.startswith('!nick ') or message.startswith('!name '):
                newName = message.partition(' ')[2]
                newName = newName.strip()
                if len(newName) > 0:
                    logMessage = '<NAMECHANGE> Old Name: \'%s\' New Name: \'%s\' (Host: %s)' % (
                        clientName, newName, client.hostname)
                    text = '*** %s has changed his/her name to %s' % (
                        clientName, newName)
                    conn.logger.info(logMessage)
                    utils.msgChannel(irc, conn.channel, text)
                    command = 'client_name %s %s' % (clientID, newName)
                    conn.send_packet(AdminRcon, command = command)
            else:
                text = '<%s> %s' % (clientName, message)
                utils.msgChannel(irc, conn.channel, text)
        elif action == Action.COMPANY_JOIN or action == Action.COMPANY_NEW:
            clientName = clientName.lower()

            if not isinstance(client, (long, int)):
                company = conn.companies.get(client.play_as)
                if action == Action.COMPANY_JOIN:
                    text = ('*** %s has joined company #%d' %
                        (client.name, company.id+1))
                    joining = 'JOIN'
                else:
                    text = ('*** %s has started a new company #%d' %
                        (client.name, company.id+1))
                    joining = 'NEW'

                logMessage = '<COMPANY %s> Name: \'%s\' Company Name: \'%s\' Company ID: %s' % (
                    joining, clientName, company.name, company.id+1)
                utils.msgChannel(irc, conn.channel, text)
                conn.logger.info(logMessage)
            
            playAsPlayer = self.registryValue('playAsPlayer', conn.channel)
            if clientName.startswith('player') and not playAsPlayer:
                utils.moveToSpectators(irc, conn, client)
        elif action == Action.COMPANY_SPECTATOR:
            text = '*** %s has joined spectators' % clientName
            utils.msgChannel(irc, conn.channel, text)
            logMessage = '<SPECTATOR JOIN> Name: \'%s\'' % clientName
            conn.logger.info(logMessage)

    def _rcvRcon(self, connChan, result, colour):
        conn = self.connections.get(connChan)
        if not conn or conn.rcon == RconSpecial.SILENT:
            return
        irc = conn.irc

        if conn.rcon == RconSpecial.SHUTDOWNSAVED:
            if result.startswith('Map successfully saved'):
                utils.msgChannel(irc, conn.channel, 'Successfully saved game as autosavesoap.sav')
                conn.connectionstate = ConnectionState.SHUTDOWN
                command = 'quit'
                conn.send_packet(AdminRcon, command = command)
            return
        elif conn.rcon == RconSpecial.UPDATESAVED:
            if result.startswith('Map successfully saved'):
                message = 'Shutting down server to finish update. We\'ll be back shortly'
                utils.msgChannel(irc, conn.channel, message)
                conn.send_packet(AdminChat,
                    action = Action.CHAT,
                    destType = DestType.BROADCAST,
                    clientID = ClientID.SERVER,
                    message = message)
                conn.connectionstate = ConnectionState.SHUTDOWN
                command = 'quit'
                conn.send_packet(AdminRcon, command = command)

                ofsCommand = 'ofs-svntobin.py'
                successText = None
                cmdThread = threading.Thread(
                    target = self._commandThread,
                    args = [conn, irc, ofsCommand, successText, 15])
                cmdThread.daemon = True
                cmdThread.start()
            return
        if result[3:].startswith('***'):
            result = result[3:]
        utils.msgChannel(irc, conn.rcon, result)

    def _rcvConsole(self, connChan, origin, message):
        conn = self.connections.get(connChan)
        if not conn:
            return
        irc = conn.irc

        if (message.startswith('Game Load Failed') or
                message.startswith('ERROR: Game Load Failed')):
            ircMessage = message.replace("\n", ", ")
            ircMessage = ircMessage.replace("?", ", ")
            utils.msgChannel(irc, conn.channel, ircMessage)
        else:
            ircMessage = message[3:]
            if ircMessage.startswith('***') and 'paused' in ircMessage:
                utils.msgChannel(irc, conn.channel, ircMessage)

    def _rcvCmdLogging(self, connChan, frame, param1, param2, tile, text, company, commandID, clientID):
        conn = self.connections.get(connChan)
        if not conn:
            return

        if clientID == 1:
            name = 'Server'
        else:
            client = conn.clients.get(clientID)
            name = client.name
        commandName = conn.commands.get(commandID)
        if not commandName:
            commandName = commandID

        if commandName == 'CmdPause':
            pass

        logMessage = '<COMMAND> Frame: %s Name: \'%s\' Command: %s Tile: %s Param1: %s Param2: %s Text: \'%s\'' % (
            frame, name, commandName, tile, param1, param2, text)
        conn.logger.info(logMessage)


    def _rcvPong(self, connChan, start, end, delta):
        conn = self.connections.get(connChan)
        if not conn:
            return
        irc = conn.irc

        text = 'Dong! reply took %s' % str(delta)
        utils.msgChannel(irc, conn.channel, text)



    # IRC commands

    def apconnect(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        connect to AdminPort of the [specified] OpenTTD server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if not conn:
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
        if not conn:
            return

        if conn.connectionstate == ConnectionState.CONNECTED:
            conn.connectionstate = ConnectionState.DISCONNECTING
            utils.disconnect(conn, False)
        else:
            irc.reply('Not connected!!', prefixNick = False)
    apdisconnect = wrap(apdisconnect, [optional('text')])

    def date(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        display the ingame date of the [specified] server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if not conn:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return
        message = '%s' % conn.date.strftime('%b %d %Y')
        irc.reply(message, prefixNick = False)
    date = wrap(date, [optional('text')])

    def rcon(self, irc, msg, args, parameters):
        """ [Server ID or channel] <rcon command>

        sends a rcon command to the [specified] openttd server
        """

        command = ''
        (firstWord, dummy, remainder) = parameters.partition(' ')
        (source, conn, command) = self._ircRconInit(irc, msg, firstWord, remainder, command, True)
        if not conn:
            return
        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return
        if conn.rcon != RconSpecial.SILENT:
            message = 'Sorry, still processing previous rcon command'
            irc.reply(message, prefixNick = False)
            return
        if len(command) >= NETWORK_RCONCOMMAND_LENGTH:
            message = "RCON Command too long (%d/%d)" % (
                len(command), NETWORK_RCONCOMMAND_LENGTH)
            irc.reply(message, prefixNick = False)
            return
        conn.rcon = source
        logMessage = '<RCON> Nick: %s, command: %s' % (msg.nick, command)
        conn.logger.info(logMessage)
        conn.send_packet(AdminRcon, command = command)
    rcon = wrap(rcon, ['text'])

    def shutdown(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        pauses the [specified] game server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if not conn:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return

        irc.reply('Shutting down server...', prefixNick = False)
        conn.rcon = RconSpecial.SHUTDOWNSAVED
        command = 'save autosave/autosavesoap'
        conn.send_packet(AdminRcon, command = command)
    shutdown = wrap(shutdown, [optional('text')])

    def pause(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        pauses the [specified] game server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if not conn:
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
        if not conn:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return
        minPlayers = self.registryValue('minPlayers', conn.channel)
        if minPlayers > 0:
            command = 'set min_active_clients %s' % self.registryValue(
                'minPlayers', conn.channel)
            conn.send_packet(AdminRcon, command = command)
        command = 'unpause'
        conn.send_packet(AdminRcon, command = command)
    auto = wrap(auto, [optional('text')])

    def unpause(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        unpauses the [specified] game server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if not conn:
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
        if not conn:
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
        if not conn:
            return

        text = self.registryValue('publicAddress', conn.channel)
        irc.reply(text)
    ip = wrap(ip, [optional('text')])

    def password(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        tells you the current password needed for joining the [specified] game server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if not conn:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return
        if not conn.clientPassword:
            irc.reply('Free entry, no passwords needed')
        else:
            irc.reply(conn.clientPassword)
    password = wrap(password, [optional('text')])

    def companies(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        Show a list of players currently playing
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if not conn:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return

        if conn.companies.values():
            for company in conn.companies.values():
                if not company.id == 255:
                    companyColour = utils.getColourNameFromNumber(company.colour)
                    text = 'Company %d (%s): %s' % (company.id+1, companyColour, company.name)
                    if company.ai:
                        text = 'AI ' + text
                    irc.reply(text)
        else:
            irc.reply('There are currently no companies in existence. '\
                'I smell an opportunity...')
    companies = wrap(companies, [optional('text')])

    def players(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        Show a list of players currently playing
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if not conn:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return

        spectators = []
        players = []
        for client in conn.clients.values():
            if client.play_as == 255:
                if conn.serverinfo.dedicated and client.id == 1:
                    pass
                else:
                    spectators.append('Client %d (%s)' % (client.id, client.name))
            else:
                company = conn.companies.get(client.play_as)
                companyColour = utils.getColourNameFromNumber(company.colour)
                players.append('Client %d (%s) is %s, in company %s (%s)' %
                    (client.id, companyColour, client.name, company.id+1,
                    company.name))
        spectators.sort()
        players.sort()
        for player in players:
            irc.reply(player)
        if spectators:
            spectators = ', '.join(spectators)
            irc.reply('Spectators: %s' % spectators)
        if not players and not spectators:
            irc.reply('The server is empty, noone is connected. '\
                'Feel free to remedy this situation')
    players = wrap(players, [optional('text')])

    def playercount(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        Tells you the number of players and spectators on the server at this moment
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if not conn:
            return

        if conn.connectionstate != ConnectionState.CONNECTED:
            irc.reply('Not connected!!', prefixNick = False)
            return
        clients = len(conn.clients)
        if conn.serverinfo.dedicated:
            clients -= 1 # deduct server-client for dedicated servers
        players = 0
        for client in conn.clients.values():
            if not client.play_as == 255:
                players += 1
        spectators = clients - players
        text = 'There are currently %d players and %d spectators, '\
            'making a total of %d clients connected' % (
            (players, spectators, clients))
        irc.reply(text)
    playercount = wrap(playercount, [optional('text')])

    def download(self, irc, msg, args, osType, serverID):
        """ [OS type/program] [Server ID or channel]

        Returns the url to download the client for the current game. Also links
        to some starter programs
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, False)
        if not conn:
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
                url = utils.generateDownloadUrl(
                    irc, conn.serverinfo.version, osType)
            else:
                url = customUrl
        if not url == None:
            irc.reply(url)
        else:
            irc.reply('Couldn\'t decipher download url')
    download = wrap(download, [optional(('literal',
        ['autostart', 'autottd', 'lin', 'lin64', 'osx', 'ottdau', 'win32', 'win64', 'win9x', 'source'])),
        optional('text')])



    # Relay IRC back ingame

    def doPrivmsg(self, irc, msg):

        (source, text) = msg.args
        conn = None
        source = source.lower()
        if irc.isChannel(source) and source in self.channels:
            conn = self.connections.get(source)
        if not conn:
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



    # ofs related commands

    def getsave(self, irc, msg, args, saveUrl, serverID):
        """ [Server ID or channel] <Http Url of savegame>

        Downloads a savegame file over HTTP and saves it in the saves dir of the [specified] server
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if not conn:
            return

        if saveUrl[-4:] == '.sav':
            irc.reply('Starting download...', prefixNick = False)
            ofsCommand = 'ofs-getsave.py %s' % saveUrl
            successText = 'Savegame successfully downloaded'
            cmdThread = threading.Thread(
                target = self._commandThread,
                args = [conn, irc, ofsCommand, successText])
            cmdThread.daemon = True
            cmdThread.start()
        else:
            irc.reply('Sorry, only .sav files are supported')
    getsave = wrap(getsave, ['httpUrl', optional('text')])

    def start(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        Starts the specified server. Only available if plugins.Soap.local is True
        """
        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if not conn:
            return
        if conn.connectionstate == ConnectionState.CONNECTED:
            irc.reply('I am connected to %s, so it\'s safe to assume that its already running'
                % conn.serverinfo.name, prefixNick = False)
            return

        ofsCommand = 'ofs-start.py'
        successText = 'Server is starting...'
        cmdThread = threading.Thread(
            target = self._commandThread,
            args = [conn, irc, ofsCommand, successText])
        cmdThread.daemon = True
        cmdThread.start()
    start = wrap(start, [optional('text')])

    def update(self, irc, msg, args, serverID):
        """ [Server ID or channel]

        Updates OpenTTD to the newest revision in its branch
        """

        source, conn = self._ircCommandInit(irc, msg, serverID, True)
        if not conn:
            return

        irc.reply('Starting update...', prefixNick = False)
        if conn.connectionstate == ConnectionState.CONNECTED:
            message = 'Server is being updated, and will shut down in a bit...'
            conn.send_packet(AdminChat,
                action = Action.CHAT,
                destType = DestType.BROADCAST,
                clientID = ClientID.SERVER,
                message = message)
        ofsCommand = 'ofs-svnupdate.py'
        successText = 'Game successfully updated'
        cmdThread = threading.Thread(
            target = self._commandThread,
            args = [conn, irc, ofsCommand, successText])
        cmdThread.daemon = True
        cmdThread.start()
    update = wrap(update, [optional('text')])

Class = Soap

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
