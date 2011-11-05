import sys
import readline

from mudblood.session import Session, Event
from mudblood.colors import Colors
from mudblood.commands import CommandChain, CommandObject

VERSION = "0.1"

class Interface(CommandObject):
    def __init__(self, mud):
        self.sname = ""
        self.sessions = {}

        if mud:
            self.sessions['default'] = Session(mud, self.session_cb)
            self.sname = "default"

    def message(self, msg):
        print Colors.MESSAGE + msg + Colors.INPUT

    def error(self, msg):
        print Colors.ERROR + msg + Colors.INPUT

    def session(self):
        if self.sname == "":
            return None
        else:
            return self.sessions[self.sname]

    def run(self):
        global options

        print "mudblood serial interface version %s" % VERSION
        print "type '%shelp' for a list of commands." % options.prefix

        readline.parse_and_bind("tab: complete")

        sys.stdout.write(Colors.INPUT)

        self.command_chain = CommandChain()

        if self.session():
            self.command_chain.chain = [self, self.session(), self.session().mapper]
            self.session().connect()
        else:
            self.command_chain.chain = [self]

        while True:
            try:
                line = raw_input()
            except EOFError, e:
                break

            words = line.split()

            if len(words) > 0 and words[0][0] == options.prefix:
                cmd = [words[0][1:]]
                cmd.extend(words[1:]) 
                try:
                    ret = self.command_chain.run_command(cmd)
                    if ret:
                        if isinstance(ret, str):
                            self.message(ret)
                    else:
                        self.error("Command not found.")
                except TypeError:
                    self.error("Syntax Error")
            else:
                if self.session() == None:
                    self.error("Not connected")
                else:
                    self.session().stdin.writeln(line)

        self.message("Bye!")

    def session_cb(self, ob, typ, arg):
        name = ""
        for s in self.sessions.keys():
            if self.sessions[s] == ob:
                name = s
                break

        if ob == self.session() and typ == Event.STDIO:
            sys.stdout.write(Colors.OFF + ob.out[arg].read() + Colors.INPUT)
            sys.stdout.flush()
        elif typ == Event.ERROR:
            self.error(ob.stderr.read())
        elif typ == Event.CONNECTED:
            self.message("[%s] Session connected" % name)
        elif typ == Event.CLOSED:
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
            self.command_chain.chain = [self, self.session(), self.session().mapper]
            readline.set_completer(self.sessions[newsession].completer.complete)
            for i in self.sessions[newsession].out:
                sys.stdout.write(i.read())

    # commands ---

    def cmd_session(self, name, host="", port=0):
        """session <name> [<host> <port>]

           Switch session or create new session."""

        if host == "" and port == 0:
            try:
                self.switch_session(name)
            except KeyError, e:
                return "No such session."
        else:
            if name in self.sessions.keys():
                return "There is already a session named '%s'" % name
            else:
                self.sessions[name] = Session(host, int(port), self.session_cb)
                self.switch_session(name)

                self.sessions[name].connect()
                return "[%s] Switched session" % name

    def cmd_sessions(self):
        """sessions

           List all active sessions."""

        if len(self.sessions) == 0:
            return "No sessions"
        else:
            return "\n".join(self.sessions.keys())

    def cmd_quit(self):
        """quit

           Quit."""

        for s in self.sessions.values():
            s.close()
        self.message("Bye!")
        sys.exit(0)
