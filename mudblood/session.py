# $Id$

import threading
import telnetlib
import socket
import traceback

from collections import deque

from commands import CommandObject

from hook import Hook
from map import Mapper, MapNotification
from mud_base import Mud

def load_mud_definition(path):
    import os
    mud = Mud()
    if os.path.exists(path):
        d = mud.__dict__
        d['self'] = mud
        execfile(path, {"Mud": Mud}, d)
        mud.path = path
        return mud
    else:
        return None

class IOStream:
    """
        Asynchronous IO class.
    """
    def __init__(self):
        self.lock = threading.Condition()
        self.out = ""

    def has_data(self):
        return self.out != ""

    def read(self, blocking=False):
        """
            Read everything from the stream.

            @param blocking     If True, the method blocks when no data is available.
            @return             A string of new data.
        """
        self.lock.acquire();
        if self.out == "" and blocking:
            self.lock.wait()
        ret = self.out;
        self.out = ""
        self.lock.release();

        return ret;

    def write(self, data):
        """
            Write data to the stream.

            @param data     A string of data
        """
        self.lock.acquire()
        self.out += data
        self.lock.notify();
        self.lock.release()

    def writeln(self, data):
        self.write(data + "\n")

class Event:
    """
        Enum with all events that trigger the callback.
    """
    STDIO       = 1
    INFO        = 2
    ERROR       = 3
    CONNECTED   = 4
    CLOSED      = 5
    STATUS      = 6
    MAP         = 7

class Session(CommandObject):
    """
        A single game session. Asynchronous I/O is handled via a callback.
    """
    NEWLINE = "\n";

    def __init__(self, mud, callback=None):
        """
            Create a session.

            @param mud      The mud definition object.
            @param callback Callback for Async I/O
        """
        self.input_thread = threading.Thread(None, self._input_run)
        self.output_thread = threading.Thread(None, self._output_run)
        self.input_thread.daemon = True
        self.output_thread.daemon = True
        self.mud = mud
        self.out = { 0: IOStream() }
        self.stderr = self.out[0]
        self.stdin = IOStream()
        self.info = IOStream()

        self.user_status = ""

        self.mapper = Mapper(mud)

        self.completer = Completer()

        self.connected = False
        self.mode = 0
        self.callback = callback

    def connect(self):
        try:
            self.telnet = telnetlib.Telnet(self.mud.host, self.mud.port)
        except Exception, msg:
            self.stderr.writeln("Could not connect: %s." % msg)
            self._do_callback(Event.ERROR)
            self._do_callback(Event.CLOSED)
            return
        
        self.mud.connect(self)

        self.connected = True
        self._do_callback(Event.CONNECTED)

        self.input_thread.start()
        self.output_thread.start()

    def close(self):
        self.telnet.close()
        self._do_callback(Event.CLOSED)

    def _do_callback(self, typ, arg=None):
        if self.callback:
            self.callback(self, typ, arg)

    def _input_run(self):
        """
            Thread function that reads data from the server.
        """
        while self.connected:
            data = self.telnet.read_some()
            if data == "":
                self.connected = False
                self._do_callback(Event.CLOSED)
                break

            try:
                d = self.telnet.read_very_eager()
                while d != "":
                    data += d
                    d = self.telnet.read_very_eager()
            
            except EOFError, e:
                self.connected = False
                self._do_callback(Event.CLOSED)
                break
            except:
                break

            data = data.replace("\r\n", self.NEWLINE)

            for c in data:
                if ord(c) > 127:
                    self.info.writeln("Special character: %d" % ord(c))
                    self._do_callback(Event.INFO)

            lines = data.splitlines(True)

            for l in lines:
                self.completer.parse(l)
                try:
                    for h in self.mud.input_hooks:
                        l = h.process(self, l)
                        if not l:
                            break
                except Exception, e:
                    self.stderr.writeln(traceback.format_exc())
                    self._do_callback(Event.ERROR)

                if l:
                    self.out[0].write(l)

            self._do_callback(Event.STDIO, 0)
    
    def _output_run(self):
        """
            Thread function that reads input from the input stream.
        """
        while self.connected:
            data = self.stdin.read(True)
            
            for l in data.splitlines(True):
                try:
                    for h in self.mud.output_hooks:
                        l = h.process(self, l)
                        if not l:
                            break
                except Exception, e:
                    self.stderr.writeln(traceback.format_exc())
                    self._do_callback(Event.ERROR)

                if l:
                    try:
                        self.telnet.write(str(l))
                    except IOError, e:
                        self.stderr.writeln("Connection closed.")
                        self._do_callback(Event.ERROR)
                        self.connected = False

                    # Automapper
                    ret = self.mapper.handle_input(l.strip())
                    if ret == MapNotification.NEW_CYCLE:
                        self.info.writeln("Mapper: Found cycle. 'map nocycle' to disagree")
                        self._do_callback(Event.INFO)

                    if ret > 0:
                        self._do_callback(Event.MAP)

    def write_to_stream(self, stream, data):
        if not stream in self.out:
            self.out[stream] = IOStream()
        self.out[stream].write(data)
        self._do_callback(Event.STDIO)

    def cmd_walk(self, tag):
        room = self.mapper.find_room(tag)
        if not room:
            return "Target not found."

        path = self.mapper.find_shortest_path(room)

        if path:
            self.stdin.writeln("\n".join(path))
            self.info.writeln("Path is: " + str(path))
            self._do_callback(Event.INFO)
        else:
            return "No path found."

class Completer:
    nouns = set()

    def complete(self, text, state):
        if text == "":
            return None
        lastword = text.split()[-1]
        for n in self.nouns:
            if n.startswith(lastword) and n != lastword:
                if state == 0:
                    return n + " "
                state -= 1

        return None

    def parse(self, line):
        for word in line.split():
            if word[0] >= 'A' and word[0] <= 'Z':
                self.nouns.add(filter(lambda x: x.isalpha(), word).lower())

