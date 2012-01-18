import re
from mudblood.session import Hook

class StreamHook(Hook):
    def __init__(self, condition, stream):
        self.condition = condition
        self.stream = stream

    def process(self, session, line):
        if self.condition(session, line):
            session.write_to_stream(self.stream, line)
            return None

        return line

class SuppressHook(Hook):
    def __init__(self, regex):
        self.regex = regex

    def process(self, session, line):
        m = re.search(self.regex, line)
        if m:
            return None
        else:
            return line

class HighlightHook(Hook):
    def __init__(self, regex, color):
        self.regex = regex
        self.color = color

    def process(self, session, line):
        m = re.match("(.*?)(" + self.regex + ")(.*)", line)
        if m:
            return m.group(1) + ("\033[3%dm" % self.color) + m.group(2) + "\033[0m" + m.group(3) + "\n"
        else:
            return line

class HighlightLineHook(Hook):
    def __init__(self, regex, color):
        self.regex = regex
        self.color = color

    def process(self, session, line):
        m = re.search(self.regex, line)
        if m:
            return ("\033[3%dm" % self.color) + line + "\033[0m"
        else:
            return line

class FunctionHook(Hook):
    def __init__(self, cond, fun):
        self.cond = cond
        self.fun = fun

    def process(self, session, line):
        if self.cond(session, line):
            self.fun(session, line)

        return line

class TriggerList(Hook):
    def __init__(self):
        self.t = []

    def add(self, trigger):
        self.t.append(trigger)

    def remove(self, n):
        del self.t[n]

    def process(self, session, line):
        for t in self.t:
            t.process(session, line)
        return line

class Trigger(Hook):
    def __init__(self, trigger, response):
        self.trigger = trigger
        self.response = response

    def __repr__(self):
        return "%s -> %s" % (self.trigger, self.response)

    def process(self, session, line):
        m = re.search(self.trigger, line)
        if m:
            session.stdin.writeln(self.response % m.groups())
        return line
