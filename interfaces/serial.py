from session import *
import sys
import readline

class Serial:
    def __init__(self):
        self.sname = ""
        self.sessions = {}

    def message(self, msg):
        print '\033[34m' + msg + '\033[0m'

    def error(self, msg):
        print '\033[33m' + msg + '\033[0m'

    def session(self):
        if self.sname == "":
            return None
        else:
            return self.sessions[self.sname]

    def run(self):
        readline.parse_and_bind("tab: complete")

        while True:
            try:
                line = raw_input()
            except EOFError, e:
                break

            words = line.split()
            if len(words) == 0:
                words = [""]

            if words[0] == ".session":
                if len(words) == 2:
                    try:
                        self.switch_session(words[1])
                    except KeyError, e:
                        self.error("No such session");
                elif len(words) < 4:
                    self.message("Syntax: .session <name> <host> <port>")
                    self.message("    or: .session <name>")
                else:
                    if words[1] in self.sessions.keys():
                        self.error("There is already a session named '%s'" % words[1])
                    else:
                        self.sessions[words[1]] = Session(words[2], int(words[3]))
                        self.switch_session(words[1])

                        self.sessions[words[1]].set_callback(self.session_cb)
                        self.sessions[words[1]].connect()

            elif words[0] == ".sessions":
                if len(self.sessions) == 0:
                    self.message("No sessions")
                else:
                    for s in self.sessions.keys():
                        self.message(s)

            elif words[0] == ".quit":
                for s in self.sessions.values():
                    s.close()
                break

            else:
                if self.session() == None:
                    self.error("Not connected")
                else:
                    self.session().stdin.writeln(line)

        self.message("Bye!")

    def session_cb(self, ob, typ, arg):
        # O(n) name lookup... ugly!
        name = ""
        for s in self.sessions.keys():
            if self.sessions[s] == ob:
                name = s
                break

        if ob == self.session() and typ == CbType.STDIO:
            sys.stdout.write(ob.out[arg].read())
            sys.stdout.flush()
        elif typ == CbType.ERROR:
            self.error(ob.stderr.read())
        elif typ == CbType.CONNECTED:
            self.message("[%s] Session connected" % name)
        elif typ == CbType.CLOSED:
            self.message("[%s] Session closed" % name)
            del self.sessions[name]
            if len(self.sessions) > 0:
                self.switch_session(self.sessions.keys()[0])
            else:
                self.sname = ""

    def switch_session(self, newsession):
        if newsession not in self.sessions:
            self.error("No such session")
        else:
            self.sname = newsession
            self.message("[%s] Switched session" % newsession);
            readline.set_completer(self.sessions[newsession].completer.complete)
            for i in self.sessions[newsession].out:
                sys.stdout.write(i.read())

