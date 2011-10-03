import re

class Hook:
    def __init__(self):
        pass

    def process(self, session, line):
        return line

class StreamHook(Hook):
    def __init__(self, condition, stream):
        self.condition = condition
        self.stream = stream

    def process(self, session, line):
        if self.condition(session, line):
            session.write_to_stream(self.stream, line)
            return None

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