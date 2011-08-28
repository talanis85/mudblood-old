from __future__ import absolute_import

import curses
import traceback

from session import Session, Event

VERSION = "0.1"



class Colors:
    WHITE = 0
    BLUE = 1
    CYAN = 2
    GREEN = 3
    MAGENTA = 4
    RED = 5
    YELLOW = 6
    BLACK = 7

class Curses:
    def __init__(self):
        self.input_mode = InputMode.NORMAL
        self.status_text = ""
        self.window_stack = []

    def current_window(self):
        return self.window_stack[-1]

    def run(self):
        self.curses_setup()

        try:
            (self.h, self.w) = self.screen.getmaxyx()

            self.status_bar = self.screen.subwin(self.h - 2, 0)
            self.set_status("")

            self.input_buffer = InputBuffer(self.status_bar, self.command, attr=curses.color_pair(Colors.CYAN) | curses.A_BOLD)
            self.content_window = self.screen.subwin(self.h-2, self.w, 0, 0)
            self.screen.refresh()

            self.window_stack.append(ConsoleWindow(self, 0, 0, 0, 0, parent=self.content_window))
            self.window_stack.append(SessionWindow(self, 0, 0, 0, 0,
                                                   parent=self.content_window,
                                                   host="localhost", port=9999, name="lh"))

            self.current_window().redraw()

            self.quit = False
            while not self.quit:
                c = self.screen.getch()
                cc = curses.keyname(c)

                if self.input_mode == InputMode.NORMAL:
                    if cc == options.prefix:
                        self.input_buffer.clear()
                        self.set_status("")
                        self.status_bar.addstr(options.prefix)
                        self.change_mode(InputMode.COMMAND)
                        self.status_bar.refresh()
                    else:
                        self.current_window().input_normal(c)
                elif self.input_mode == InputMode.COMMAND:
                    if cc == "^[":
                        self.input_buffer.clear()
                        self.redraw_status()
                        self.change_mode(InputMode.NORMAL)
                    else:
                        self.input_buffer.input_char(c)
                    self.status_bar.refresh()

                self.current_window().refresh()

            self.curses_destroy()
        except:
            self.curses_destroy()
            traceback.print_exc()

    def update_layout(self):
        while self.current_window().closed:
            if isinstance(self.current_window(), SessionWindow):
                self.set_status("Session closed: %s" % self.current_window().name)
            self.current_window().clear()
            self.window_stack.pop()
            self.current_window().redraw()

    def redraw_status(self):
        self.status_bar.erase()
        self.status_bar.hline("-", self.w)
        self.status_bar.move(1, 0)
        self.status_bar.addstr(self.status_text)
        self.status_bar.refresh()

    def set_status(self, msg):
        self.status_text = msg
        self.redraw_status()

    def command(self, line):
        line = line.split()

        self.set_status("")

        if line[0] == "quit":
            self.quit = True
        elif line[0] == "test":
            self.window_stack.append(SessionWindow(self, 0,0,0,0,
                                                   parent=self.content_window,
                                                   host="localhost", port=9999, name="lh"))
        elif line[0] == "session":
            self.window_stack.append(SessionWindow(self, 0,0,0,0,
                                                   parent=self.content_window,
                                                   host=line[2], port=int(line[3]), name=line[1]))
            self.set_status("Switched session: %s" % line[1])
        elif line[0] == "sessions":
            sessions = "Sessions:\n"
            for s in filter(lambda w: isinstance(w, SessionWindow), self.window_stack):
                sessions += "  %s\n" % s.name
            self.window_stack.append(AuxWindow(self, msg=sessions, parent=self.content_window))

        elif line[0] == "help":
            self.window_stack.append(AuxWindow(self, msg="this\nis\nhelp", parent=self.content_window))
        elif self.current_window().input_command(line[0], line[1:]) == False:
            self.set_status("Command not found")

        self.redraw_status()
        self.change_mode(InputMode.NORMAL)

    def change_mode(self, mode):
        if (self.current_window().mode_mask & mode) > 0:
            self.input_mode = mode

    def curses_setup(self):
        self.screen = curses.initscr()
        curses.start_color()
        curses.use_default_colors()
        self.screen.keypad(0)
        self.screen.idlok(1)
        curses.noecho()
        curses.cbreak()

        for c in ["BLUE", "CYAN", "GREEN", "MAGENTA", "RED", "BLACK", "YELLOW"]:
            curses.init_pair(getattr(Colors, c), getattr(curses, "COLOR_" + c), curses.COLOR_BLACK)

    def curses_destroy(self):
        curses.echo()
        curses.nocbreak()
        curses.endwin()



class InputMode:
    NORMAL = 0x1
    INSERT = 0x2
    COMMAND = 0x4

    ALL = 0x7



class Window:
    def __init__(self, base, y, x, h, w, parent, mode_mask=InputMode.ALL, boxed=False):
        self.base = base

        if parent:
            (py, px) = parent.getyx()
            y = py + y
            x = px + x
            if h == 0 and w == 0:
                (ph, pw) = parent.getmaxyx()
                h = ph - y
                w = pw - x

        self.outer = curses.newwin(h, w, y, x)

        if boxed:
            self.window = self.outer.derwin(h-2, w-2, 1, 1)
        else:
            self.window = self.outer

        self.mode_mask = mode_mask
        self.boxed = boxed
        (self.h, self.w) = self.window.getmaxyx()
        self.closed = False

    def refresh(self):
        if self.base.current_window() == self:
            if self.boxed:
                self.outer.touchwin()
            self.outer.refresh()

    def redraw(self):
        self.window.touchwin()
        if self.boxed:
            self.outer.box()
        self.refresh()

    def clear(self):
        self.outer.clear()
        self.refresh()

    def write(self, string):
        try:
            self.window.addstr(string)
        except:
            pass
        self.refresh()

    def writeln(self, string):
        self.write(string + "\n")

    def back(self):
        (x, y) = self.window.getyx()
        if x > 0:
            self.window.move(y, x-1)
            self.window.delch()

    def input_normal(self, c):
        pass

    def input_command(self, command, args):
        pass

    def close(self):
        self.closed = True
        self.base.update_layout()


class ConsoleWindow(Window):
    def close(self):
        pass



class AuxWindow(Window):
    def __init__(self, base, parent, msg, attr=0):
        msg = msg.strip()
        lines = msg.split("\n")
        numlines = len(lines) + len(filter(lambda x: len(x) > parent.getmaxyx()[1], lines)) + 2

        Window.__init__(self, base, parent.getmaxyx()[0]-numlines, 0, 0, 0,
                        parent=parent,
                        mode_mask=InputMode.NORMAL,
                        boxed=True)

        if attr == 0:
            attr = curses.color_pair(Colors.CYAN)
        self.attr = attr

        self.msg = msg
        self.window.addstr(msg, self.attr)

        self.redraw()

    def input_normal(self, c):
        self.close()



class SessionWindow(Window):
    def __init__(self, base, y, x, h, w, parent, host, port, name):
        Window.__init__(self, base, y, x, h, w,
                        mode_mask=(InputMode.NORMAL | InputMode.COMMAND),
                        parent=parent)

        self.window.move(self.h - 1, 0)
        self.window.scrollok(1)

        self.name = name

        self.session = Session(host, port, self.session_callback)
        self.input_buffer = InputBuffer(self.window, self.input_line,
                                        completer=self.session.completer, multiline=True,
                                        attr=curses.color_pair(Colors.YELLOW) | curses.A_DIM)
        self.session.connect()

    def session_callback(self, ob, typ, arg):
        if typ == Event.STDIO:
            self.input_buffer.clean()
            self.write(ob.out[arg].read())
            self.input_buffer.redraw_if_modified()
        elif typ == Event.CLOSED:
            self.close()

    def input_normal(self, c):
        self.input_buffer.input_char(c)

    def input_line(self, line):
        self.session.stdin.writeln(line)

    def input_command(self, command, args):
        return False



def is_key(c, key):
    if key == curses.KEY_ENTER:
        return chr(c) == '\n'
    elif key == curses.KEY_BACKSPACE:
        return curses.keyname(c) == "^?"
    elif isinstance(key, str) and c < 127:
        return chr(c) == key
    else:
        return False

class InputBuffer:
    def __init__(self, window, callback, completer=None, multiline=False, attr=0):
        self.window = window
        self.callback = callback
        self.multiline = multiline
        self.completer = completer
        self.completer_state = 0
        self.completer_string = ""
        self.attr = attr

        self.input_buffer = ""
    
    def clean(self):
        (y, x) = self.window.getyx();
        for i in range(0, min(x, len(self.input_buffer))):
            self.window.move(y, x-i-1)
            self.window.delch()

    def redraw_if_modified(self):
        if self.input_buffer != "":
            self.window.addstr(self.input_buffer, self.attr)
            self.window.refresh()

    def input_char(self, c):
        if c > 127:
            return
        if is_key(c, curses.KEY_ENTER):
            if self.multiline:
                self.window.addch(c, self.attr)
            self.callback(self.input_buffer)
            self.input_buffer = ""
        elif is_key(c, curses.KEY_BACKSPACE):
            self.delete_chars()
        elif is_key(c, "\t"):
            if self.completer:
                if self.completer_state == 0:
                    self.completer_string = self.input_buffer
                comp = self.completer.complete(self.completer_string, self.completer_state)
                if not comp:
                    self.completer_state = 0
                else:
                    self.delete_word()
                    self.window.addstr(comp, self.attr)
                    self.input_buffer += comp
                    self.completer_state += 1
        else:
            self.completer_state = 0
            self.window.addch(c, self.attr)
            self.input_buffer += chr(c)

        self.window.refresh()

    def delete_chars(self, n=1):
        (y, x) = self.window.getyx()
        for i in range(0, min(n, len(self.input_buffer))):
            self.window.move(y, x-1-i)
            self.window.delch()
        self.input_buffer = self.input_buffer[:-min(n, len(self.input_buffer))]
        self.window.refresh()

    def delete_word(self):
        word = False
        (y, x) = self.window.getyx()
        while word == False or len(self.input_buffer) > 0 and self.input_buffer[-1] != " ":
            x -= 1
            self.window.move(y, x)
            if self.input_buffer[-1] != " ":
                word = True
            self.window.delch()
            self.input_buffer = self.input_buffer[:-1]

    def clear(self):
        self.input_buffer = ""

