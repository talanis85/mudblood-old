import threading
import telnetlib
import socket

class IOStream:
    def __init__(self):
        self.lock = threading.Condition()
        self.out = ""
        self.backlog = ""

    def read(self, blocking=False):
        self.lock.acquire();
        if self.out == "" and blocking:
            self.lock.wait()
        tmp = self.out;
        self.out = ""
        self.lock.release();

        return tmp;

    def has_data(self):
        return self.out == ""

    def write(self, data):
        self.lock.acquire()
        self.out += data
        self.backlog += data
        self.lock.notify_all();
        self.lock.release()

    def writeln(self, data):
        self.write(data + "\n")

class CbType:
    STDIO       = 1
    ERROR       = 2
    CONNECTED   = 3
    CLOSED      = 4

class Session:
    NEWLINE = "\n";
    connected = False
    mode = 0
    properties = {}
    callback = None
    fresh_data = ""
    completer = None

    def __init__(self, host, port):
        self.input_thread = threading.Thread(None, self.input_run)
        self.output_thread = threading.Thread(None, self.output_run)
        self.input_thread.daemon = True
        self.output_thread.daemon = True
        self.host, self.port = host, port
        self.out = [ IOStream() ]
        self.stderr = self.out[0]
        self.stdin = IOStream()
        self.completer = Completer()

    def set_callback(self, callback):
        self.callback = callback
    
    def do_callback(self, typ, arg=None):
        if self.callback:
            self.callback(self, typ, arg)

    def connect(self):
        try:
            self.telnet = telnetlib.Telnet(self.host, self.port)
        except Exception, msg:
            self.stderr.writeln("Could not connect: %s." % msg)
            self.do_callback(CbType.ERROR)
            self.do_callback(CbType.CLOSED)
            return

        self.connected = True
        self.do_callback(CbType.CONNECTED)

        self.input_thread.start()
        self.output_thread.start()

    def close(self):
        self.telnet.close()
        self.do_callback(CbType.CLOSED)

    def input_run(self):
        while self.connected:
            try:
                data = self.telnet.read_very_eager()
            except EOFError, e:
                self.connected = False
                self.do_callback(CbType.CLOSED)
                break
            except:
                break

            if data == "":
                continue

            self.fresh_data += data
            if self.NEWLINE in self.fresh_data:
                lines = self.fresh_data.split(self.NEWLINE)
                if self.fresh_data[-1] == self.NEWLINE:
                    self.fresh_data = ""
                else:
                    self.fresh_data = lines[-1]
                    lines = lines[:-1]
                for l in lines:
                    self.process_line(l)

            if not self.mode in self.out:
                self.out[self.mode] = IOStream()
            self.out[self.mode].write(data)
            self.do_callback(CbType.STDIO, self.mode)
    
    def output_run(self):
        while self.connected:
            data = self.stdin.read(True)
            try:
                self.telnet.write(data)
            except IOError, e:
                self.stderr.writeln("Connection closed.")
                self.do_callback(CbType.ERROR)
                self.connected = False

    def current_line(self):
        return self.fresh_data.split(self.NEWLINE)[-1]

    def process_line(self, line):
        self.completer.parse_line(line)

class Completer:
    nouns = set()

    def complete(self, text, state):
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

