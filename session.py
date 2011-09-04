import threading
import telnetlib
import socket
import traceback

from map import Mapper, Map, Room, MapNotification

class IOStream:
    def __init__(self):
        self.lock = threading.Condition()
        self.out = ""

    def has_data(self):
        return self.out != ""

    def read(self, blocking=False):
        self.lock.acquire();
        if self.out == "" and blocking:
            self.lock.wait()
        ret = self.out;
        self.out = ""
        self.lock.release();

        return ret;

    def write(self, data):
        self.lock.acquire()
        self.out += data
        self.lock.notify_all();
        self.lock.release()

    def writeln(self, data):
        self.write(data + "\n")

class Event:
    STDIO       = 1
    INFO        = 2
    ERROR       = 3
    CONNECTED   = 4
    CLOSED      = 5

class Session:
    NEWLINE = "\n";

    def __init__(self, mud, callback=None):
        self.input_thread = threading.Thread(None, self._input_run)
        self.output_thread = threading.Thread(None, self._output_run)
        self.input_thread.daemon = True
        self.output_thread.daemon = True
        self.mud = mud
        self.out = [ IOStream() ]
        self.stderr = self.out[0]
        self.stdin = IOStream()
        self.info = IOStream()

        self.completer = Completer()
        self.mapper = Mapper(mud)

        self.input_buf = ""

        self.connected = False
        self.mode = 0
        self.properties = {}
        self.callback = callback
        self.fresh_data = ""

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

            self.fresh_data += data

            if self.mud.strings['prompt'] in data:
                index = self.fresh_data.find(self.mud.strings['prompt'])
                try:
                    self.process_response(self.input_buf, self.fresh_data[:index].strip())
                except Exception, e:
                    self.stderr.writeln(traceback.format_exc())
                    self._do_callback(Event.ERROR)
                self.input_buf = ""
                self.fresh_data = self.fresh_data[index+len(self.mud.strings['prompt']):]

            # Write to output stream
            if not self.mode in self.out:
                self.out[self.mode] = IOStream()
            self.out[self.mode].write(data)
            self._do_callback(Event.STDIO, self.mode)
    
    def _output_run(self):
        while self.connected:
            data = self.stdin.read(True)
            self.input_buf = data.strip()
            try:
                self.telnet.write(data)
            except IOError, e:
                self.stderr.writeln("Connection closed.")
                self._do_callback(Event.ERROR)
                self.connected = False

    def process_response(self, call, response):
        if response == self.mud.strings['command_not_found']:
            return

        d = self.mud.Direction.canonical(call)
        if d:
            ret = self.mapper.go_to(d, response)
            if ret == MapNotification.NEW_CYCLE:
                self.info.writeln("Mapper: Found cycle. 'map nocycle' to disagree")
                self._do_callback(Event.INFO)

        self.completer.parse(response)

    def run_command(self, cmd):
        if cmd[0] == "map":
            return self.mapper.run_command(cmd[1:])
        else:
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

