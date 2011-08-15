from __future__ import absolute_import

import curses
import curses.textpad
import traceback

from session import Session, Event

VERSION = "0.1"



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
            self.clear_status()

            self.input_buffer = InputBuffer(self.status_bar, self.command)
            self.content_window = self.screen.subwin(self.h-2, self.w, 0, 0)

            self.window_stack.append(ConsoleWindow(0, 0, parent=self.content_window))
            self.window_stack.append(SessionWindow(0, 0, "localhost", 9999, self.content_window))

            self.screen.refresh()

            self.quit = False
            while not self.quit:
                c = self.screen.getch()
                cc = curses.keyname(c)

                if self.input_mode == InputMode.NORMAL:
                    if cc == options.prefix:
                        self.input_buffer.clear()
                        self.status_bar.addstr(options.prefix)
                        self.change_mode(InputMode.COMMAND)
                        self.status_bar.refresh()
                    else:
                        self.current_window().input_normal(c)
                elif self.input_mode == InputMode.COMMAND:
                    if cc == "^[":
                        self.input_buffer.clear()
                        self.clear_status()
                        self.change_mode(InputMode.NORMAL)
                    else:
                        self.input_buffer.input_char(c)
                    self.status_bar.refresh()

                while self.current_window().closed:
                    self.current_window().clear()
                    self.window_stack.pop()
                    self.screen.refresh()
                self.current_window().redraw()

            self.curses_destroy()
        except:
            self.curses_destroy()
            traceback.print_exc()

    def clear_status(self):
        self.status_bar.erase()
        self.status_bar.hline("-", self.w)
        self.status_bar.move(1, 0)
        self.status_bar.addstr(self.status_text)

    def echo_status(self, msg):
        self.status_text = msg
        self.clear_status()

    def command(self, line):
        line = line.split()

        self.echo_status("")

        if line[0] == "quit":
            self.quit = True
        elif line[0] == "help":
            self.window_stack.append(AuxWindow("this is help", self.current_window().window))
        elif self.current_window().input_command(line[0], line[1:]) == False:
            self.echo_status("Command not found")

        self.clear_status()
        self.change_mode(InputMode.NORMAL)

    def change_mode(self, mode):
        if (self.current_window().mode_mask & mode) > 0:
            self.input_mode = mode

    def curses_setup(self):
        self.screen = curses.initscr()
        self.screen.keypad(0)
        self.screen.idlok(1)
        curses.noecho()
        curses.cbreak()

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
    def __init__(self, y, x, mode_mask=InputMode.ALL, parent=None, boxed=False):
        if parent:
            self.outer = parent.subwin(y, x)
        else:
            self.outer = curses.newwin(y, x)

        if boxed:
            self.window = self.outer.derwin(1, 1)
        else:
            self.window = self.outer

        self.mode_mask = mode_mask
        self.boxed = boxed

        self.closed = False
        (self.h, self.w) = self.window.getmaxyx()

    def redraw(self):
        if self.boxed:
            self.outer.box()
        self.outer.redrawwin()
        self.outer.refresh()

    def clear(self):
        self.outer.clear()

    def write(self, string):
        self.window.addstr(string)
        self.window.refresh()

    def writeln(self, string):
        self.write(string + "\n")

    def input_normal(self, c):
        pass

    def input_command(self, command, args):
        pass

    def close(self):
        self.closed = True


class ConsoleWindow(Window):
    pass



class AuxWindow(Window):
    def __init__(self, msg, parent):
        Window.__init__(self, parent.getmaxyx()[0]-10, 0, InputMode.NORMAL, parent, True)
        self.msg = msg
        self.window.clear()
        self.window.addstr(msg)
        self.redraw()

    def input_normal(self, c):
        self.close()



class SessionWindow(Window):
    def __init__(self, y, x, host, port, parent=None):
        Window.__init__(self, y, x, (InputMode.NORMAL | InputMode.COMMAND), parent)

        self.window.move(self.h - 1, 0)
        self.window.scrollok(1)

        self.session = Session(host, port, self.session_callback)
        self.session.connect()

        self.input_buffer = InputBuffer(self.window, self.input_line, self.session.completer, True)

    def __del__(self):
        del self.session
        del self.window
        del self.input_buffer

    def session_callback(self, ob, typ, arg):
        if typ == Event.STDIO:
            self.write(ob.out[arg].read())

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
    def __init__(self, window, callback, completer=None, multiline=False):
        self.window = window
        self.callback = callback
        self.multiline = multiline
        self.completer = completer
        self.completer_state = 0
        self.completer_string = ""

        self.input_buffer = ""

    def input_char(self, c):
        if c > 127:
            return
        if is_key(c, curses.KEY_ENTER):
            if self.multiline:
                self.window.addch(c)
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
                    self.window.addstr(comp)
                    self.input_buffer += comp
                    self.completer_state += 1
        else:
            self.completer_state = 0
            self.window.addch(c)
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

