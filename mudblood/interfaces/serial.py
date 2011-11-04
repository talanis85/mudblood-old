import sys
import readline

from mudblood.session import Session, Event
from mudblood.colors import Colors
from mudblood.commands import *

VERSION = "0.1"

class Interface:
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

        if self.session():
            self.session().connect()

        while True:
            try:
                line = raw_input()
            except EOFError, e:
                break

            words = line.split()

            if len(words) > 0 and words[0][0] == options.prefix:
                args = words[1:]
                self.command(words[0][1:], args)
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
            self.message("[%s] Switched session" % newsession);
            readline.set_completer(self.sessions[newsession].completer.complete)
            for i in self.sessions[newsession].out:
                sys.stdout.write(i.read())

    # commands ---

    def command(self, cmd, args):
        ret = None

        if hasattr(self, "cmd_" + cmd):
            try:
                ret = getattr(self, "cmd_%s" % cmd)(*args)
            except TypeError:
                self.error("Syntax error")
        else:
            ret = self.session().command(cmd, args)

        if ret:
            self.message(ret)
        else:
            self.error("Unknown command")

    def cmd_session(self, name, host="", port=0):
        """.session <name> [<host> <port>]

           Switch session or create new session."""

        if host == "" and port == 0:
            try:
                self.switch_session(name)
            except KeyError, e:
                self.error("No such session");
        else:
            if name in self.sessions.keys():
                self.error("There is already a session named '%s'" % name)
            else:
                self.sessions[name] = Session(host, int(port), self.session_cb)
                self.switch_session(name)

                self.sessions[name].connect()

    def cmd_sessions(self):
        """.sessions

           List all active sessions."""

        if len(self.sessions) == 0:
            self.message("No sessions")
        else:
            for s in self.sessions.keys():
                self.message(s)

    def cmd_help(self, topic="commands"):
        """.help [<command>]

           Show help for command"""

        if topic == "commands":
            self.message("Commands:")
            for c in dir(self):
                if c.startswith("cmd_"):
                    self.message("\t" + c[4:])
            return
        try:
            self.message("\n".join(map(lambda x: x.strip(),
                                       getattr(self, "cmd_%s" % topic).__doc__.split("\n")))
                             .replace("." + topic, options.prefix + topic))
        except AttributeError:
            self.error("Topic not found")

    def cmd_quit(self):
        """.quit

           Quit."""

        for s in self.sessions.values():
            s.close()
        self.message("Bye!")
        sys.exit(0)
