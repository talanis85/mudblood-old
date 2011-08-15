import threading
import telnetlib
import socket

class IOStream:
    def __init__(self):
        self.lock = threading.Condition()
        self.out = ""

    def has_data(self):
        return self.out == ""

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
    ERROR       = 2
    CONNECTED   = 3
    CLOSED      = 4

class Session:
    NEWLINE = "\n";

    def __init__(self, host, port, callback=None):
        self.input_thread = threading.Thread(None, self._input_run)
        self.output_thread = threading.Thread(None, self._output_run)
        self.input_thread.daemon = True
        self.output_thread.daemon = True
        self.host, self.port = host, port
        self.out = [ IOStream() ]
        self.stderr = self.out[0]
        self.stdin = IOStream()
        self.completer = Completer()

        self.connected = False
        self.mode = 0
        self.properties = {}
        self.callback = callback
        self.fresh_data = ""

    def connect(self):
        try:
            self.telnet = telnetlib.Telnet(self.host, self.port)
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
            try:
                data = self.telnet.read_very_eager()
            except EOFError, e:
                self.connected = False
                self._do_callback(Event.CLOSED)
                break
            except:
                break

            if data == "":
                continue
            
            data = data.replace("\r\n", self.NEWLINE)

            # Process complete lines
            self.fresh_data += data
            if self.NEWLINE in self.fresh_data:
                lines = self.fresh_data.split(self.NEWLINE)
                if self.fresh_data[-1] == self.NEWLINE:
                    self.fresh_data = ""
                else:
                    self.fresh_data = lines[-1]
                    lines = lines[:-1]
                for l in lines:
                    self._process_line(l)

            # Write to output stream
            if not self.mode in self.out:
                self.out[self.mode] = IOStream()
            self.out[self.mode].write(data)
            self._do_callback(Event.STDIO, self.mode)
    
    def _output_run(self):
        while self.connected:
            data = self.stdin.read(True)
            try:
                self.telnet.write(data)
            except IOError, e:
                self.stderr.writeln("Connection closed.")
                self._do_callback(Event.ERROR)
                self.connected = False

    def _process_line(self, line):
        self.completer.parse_line(line)

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

    def parse_line(self, line):
        for word in line.split():
            if word[0] >= 'A' and word[0] <= 'Z':
                self.nouns.add(filter(lambda x: x.isalpha(), word).lower())

