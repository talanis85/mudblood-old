# $Id$

import threading
import telnetlib
import socket
import traceback

from hook import Hook

def load_mud_definition(path):
    import os
    mud = __import__("mudblood.mud_base")
    if os.path.exists(path):
        execfile(path, mud.__dict__)
        mud.path = path
        return mud
    else:
        return None

class DefaultHook(Hook):
    def process(self, session, line):
        session.out[0].write(line)
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
        self.lock.notify_all();
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

class Session:
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

        self.mud.input_hooks.append(DefaultHook())

        self.completer = Completer()

        self.input_stack = []

        self.connected = False
        self.mode = 0
        self.properties = {}
        self.callback = callback
        self.fresh_data = ""

        self.biglock = threading.Lock()

    def connect(self):
        try:
            self.telnet = telnetlib.Telnet(self.mud.host, self.mud.port)
        except Exception, msg:
            self.stderr.writeln("Could not connect: %s." % msg)
            self._do_callback(Event.ERROR)
            self._do_callback(Event.CLOSED)
            return

        self.connected = True
        self._do_callback(Event.CONNECTED)

        self.input_thread.start()
        self.output_thread.start()

    def close(self):
        self.telnet.close()
        self._do_callback(Event.CLOSED)

    def current_line(self):
        return self.fresh_data.split(self.NEWLINE)[-1]

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

            self.biglock.acquire()

            data = data.replace("\r\n", self.NEWLINE)

            self.fresh_data += data

            if self.mud.strings['prompt'] in data:
                index = self.fresh_data.find(self.mud.strings['prompt'])
                try:
                    self.process_response(self.input_stack.pop(), self.fresh_data[:index].strip())
                except Exception, e:
                    self.stderr.writeln(traceback.format_exc())
                    self._do_callback(Event.ERROR)
                self.fresh_data = self.fresh_data[index+len(self.mud.strings['prompt']):]

            self.biglock.release()

            lines = data.splitlines(True)

            for l in lines:
                for h in self.mud.input_hooks:
                    l = h.process(self, l)
                    if not l:
                        break

            # Write to output stream
            #if not self.mode in self.out:
            #    self.out[self.mode] = IOStream()
            #self.out[self.mode].write(data)
            self._do_callback(Event.STDIO, 0)
    
    def _output_run(self):
        """
            Thread function that reads input from the input stream.
        """
        while self.connected:
            data = self.stdin.read(True)
            
            self.biglock.acquire()

            self.input_stack.extend(data.strip().split("\n"))

            self.biglock.release()

            try:
                self.telnet.write(data)
            except IOError, e:
                self.stderr.writeln("Connection closed.")
                self._do_callback(Event.ERROR)
                self.connected = False

    def write_to_stream(self, stream, data):
        if not stream in self.out:
            self.out[stream] = IOStream()
        self.out[stream].write(data)

    def process_response(self, call, response):
        """
            Called when we got a response to a command. Could be used for custom hook
            functions.

            @param call     The input that caused the response
            @param response The response
        """
        if response == self.mud.strings['command_not_found']:
            return

        self.completer.parse(response)

    def command(self, cmd, args):
        return False

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

