from __future__ import absolute_import

import sys
import os

import re

import urwid
import urwid.curses_display
import traceback
import threading

from mudblood.session import Session, Event
from mudblood.commands import CommandChain, CommandObject
from mudblood.colors import Colors

VERSION = "0.1"


master = None



class DynamicOverlay(urwid.Overlay):

    """An extension of urwid.Overlay that forwards keystrokes to top_w
       if it exists or bottom_w otherwise."""

    def selectable(self):
        return self.top_w.selectable() or self.bottom_w.selectable()

    def keypress(self, size, key):
        if self.top_w.selectable():
            key = self.top_w.keypress(size, key)
        if key and self.bottom_w.selectable():
            return self.bottom_w.keypress(size, key)
        else:
            return key



class WindowWriter:
    def __init__(self, loop, window, callback_name=""):
        self.window = window
        self.pipe = loop.watch_pipe(self.pipe_callback)
        self.callback_name = callback_name

    def pipe_callback(self, data):
        if self.callback_name == "":
            self.window.append_data(data)
        else:
            getattr(self.window, self.callback_name)(data);

        return True

    def write(self, data, color=None):
        if color:
            os.write(self.pipe, color + data + Colors.OFF)
        else:
            os.write(self.pipe, data)



class Interface(CommandObject):
    def __init__(self, mud = None):
        global master
        master = self
        self.mud = mud

        self.current_overlay = None

    def run(self):
        self.session = Session(self.mud, self.session_callback)

        self.w_session = SessionWidget(self.session)
        self.w_status = StatusWidget()

        self.w_map = MapWidget(self.session.mapper)

        self.w_frame = urwid.Frame(self.w_session, None, self.w_status)

        # TODO: Make user_input, info and error customizable
        palette = [
                ('default', 'default', 'default'),
                ('user_input', 'brown', 'default'),
                ('info', 'dark blue', 'default'),
                ('error', 'dark red', 'default'),

                ("00", 'default', 'default'),
                ("10", 'black', 'default'),
                ("20", 'dark red', 'default'),
                ("30", 'dark green', 'default'),
                ("40", 'brown', 'default'),
                ("50", 'dark blue', 'default'),
                ("60", 'dark magenta', 'default'),
                ("70", 'dark cyan', 'default'),
                ("80", 'white', 'default'),

                ("01", 'default', 'default'),
                ("11", 'black', 'default'),
                ("21", 'light red', 'default'),
                ("31", 'light green', 'default'),
                ("41", 'yellow', 'default'),
                ("51", 'light blue', 'default'),
                ("61", 'light magenta', 'default'),
                ("71", 'light cyan', 'default'),
                ("81", 'white', 'default'),
                ]

        self.command_chain = CommandChain()
        self.command_chain.chain = [self.mud, self, self.session, self.session.mapper]

        if options.screen == "raw":
            self.screen = urwid.raw_display.Screen()
        elif options.screen == "curses":
            self.screen = urwid.curses_display.Screen()

        self.loop = urwid.MainLoop(self.w_frame,
                                       palette,
                                       self.screen,
                                       handle_mouse=False,
                                       input_filter=self.master_input)
        
        self.writer = WindowWriter(self.loop, self.w_session)

        self.session.connect()
        self.loop.run()

    def master_input(self, keys, raw):
        outk = []

        for k in keys:
            if k == "esc":
                self.end_overlay()
                self.w_status.stop_edit()
                self.w_frame.set_focus('body')
            elif k == options.prefix and self.w_frame.focus_part != 'footer':
                self.w_status.start_edit()
                self.w_frame.set_focus('footer')
            elif k in self.mud.keys:
                line = self.mud.keys[k]
                if line[0] == options.prefix:
                    line = line[1:].split()
                    self.command(line)
                else:
                    self.writer.write(line + "\n", Colors.INPUT)
                    self.w_session.session.stdin.writeln(line)
            else:
                outk.append(k)

        return outk

    def session_callback(self, ob, typ, arg):
        if typ == Event.STDIO:
            for o in ob.out:
                if ob.out[o].has_data():
                    self.writer.write(ob.out[o].read())
        if typ == Event.INFO:
            self.writer.write(ob.info.read(), Colors.INFO)
        elif typ == Event.CLOSED:
            for o in ob.out:
                if ob.out[o].has_data():
                    self.writer.write(ob.out[o].read())
            self.writer.write("Session closed.\n", Colors.INFO)
        elif typ == Event.CONNECTED:
            self.writer.write("Session started.\n", Colors.INFO)
        elif typ == Event.ERROR:
            self.writer.write(ob.stderr.read(), Colors.ERROR)
        elif typ == Event.STATUS:
            pass
        elif typ == Event.MAP:
            if self.current_overlay == self.w_map:
                self.w_map.update_map()

        self.update_status()

    def update_status(self, loop=None, data=None):
        self.w_status.set_middle(self.mud.get_middle_status())
        self.w_status.set_right(self.mud.get_right_status())

    def set_status(self, msg):
        self.w_status.set_left(msg)

    def start_overlay(self, widget, halign='center', hsize=('relative',80), valign='middle', vsize=('relative',80)):
        self.w_overlay = DynamicOverlay(urwid.LineBox(widget),
                                        self.w_session,
                                        halign, hsize,
                                        valign, vsize)
        self.w_frame.set_body(self.w_overlay)
        self.current_overlay = widget

    def end_overlay(self):
        self.w_frame.set_body(self.w_session)
        self.current_overlay = None

    def command(self, cmd):
        try:
            ret = self.command_chain.run_command(cmd)
            if ret:
                if isinstance(ret, str):
                    self.set_status(ret)
                else:
                    self.set_status("")
            else:
                self.set_status("Command not found.")
        except TypeError:
            self.set_status("Syntax Error")

        self.update_status()

    def cmd_quit(self):
        raise urwid.ExitMainLoop()

    def cmd_reload(self):
        from mudblood.session import load_mud_definition
        if self.mud.path != "":
            try:
                newmud = load_mud_definition(self.mud.path)
            except Exception, e:
                self.w_session.append_data(traceback.format_exc(), 'error')
                return "Error in definition file."
                
            self.mud = newmud
            self.session.mud = newmud
            self.command_chain.chain = [self.mud, self, self.session, self.session.mapper]
            self.mud.connect(self.session)
            return "Ok."
        else:
            return "No MUD def file used."

    def cmd_showmap(self):
        if self.current_overlay == self.w_map:
            self.end_overlay()
        else:
            self.start_overlay(self.w_map, 'top', ('relative',60), 'middle', ('relative',100))
            self.w_map.update_map()
        return "Ok."



class SessionWidget(urwid.BoxWidget):

    class SessionList(urwid.ListWalker):
        def __init__(self, w_session):
            self.w_session = w_session
            self.focus = 0

        def get_next(self, start_from):
            if isinstance(start_from, int):
                n = start_from
            else:
                w, n = start_from
            if n >= len(self.w_session.lines) - 1:
                return (None, None)

            if self.w_session.lines[n+1] == []:
                return (urwid.Text(""), n+1)
            else:
                return (urwid.Text(self.w_session.lines[n+1]), n+1)

        def get_prev(self, start_from):
            if isinstance(start_from, int):
                n = start_from
            else:
                w, n = start_from
            if n <= 0:
                return (None, None)

            if self.w_session.lines[n-1] == []:
                return (urwid.Text(""), n-1)
            else:
                return (urwid.Text(self.w_session.lines[n-1]), n-1)

        def get_focus(self):
            if self.w_session.lines[self.focus] == []:
                return (urwid.Text(""), self.focus)
            else:
                return (urwid.Text(self.w_session.lines[self.focus]), self.focus)

        def set_focus(self, scr):
            self.focus = scr
            if self.focus > len(self.w_session.lines) - 1:
                self.focus = len(self.w_session.lines) - 1
            if self.focus < 0:
                self.focus = 0


    class SessionListBox(urwid.ListBox):
        def rows(self, (maxcol,), focus=False):
            return len(self.body.w_session.lines)


    def __init__(self, session):
        self.data_lock = threading.Lock()
        self.scrolling = False
        self.session = session
        self.data = ""
        self.lines = [[('00','')]]

        self.completer = self.session.completer
        self.completer_state = 0
        self.completer_string = ""

        self.history = [""]
        self.history_pos = 0
        
        self.input = urwid.Edit("")
        self.input_attr = urwid.AttrMap(self.input, 'user_input')
        self.text = self.SessionListBox(self.SessionList(self))

        self.current_attr = "00"

    def render(self, size, focus=False):
        """
            Compose the session window together with the input widget.
        """

        c = urwid.CompositeCanvas(urwid.SolidCanvas(" ", size[0], size[1]))

        h = min(size[1], len(self.lines))
        textc = self.text.render((size[0], h), focus)
        c.overlay(textc, 0, size[1] - h)

        if size[1] > len(self.lines) or self.text.get_focus()[1] == len(self.lines) - 1:
            x = 0
            for l in self.lines[-1]:
                x += len(l[1])
            x = x % size[0]
            r = self.input_attr.rows((size[0]-x,), focus)
            c.overlay(self.input_attr.render((size[0]-x,), focus), x, size[1]-r)

        return c

    def selectable(self):
        return True

    def keypress(self, size, key):
        ret = None

        if key == 'enter':
            self.append_data(Colors.INPUT + self.input.get_edit_text() + Colors.OFF + "\n")
            t = self.input.get_edit_text()
            self.input.set_edit_text("")
            self.history.append(t)
            self.history_pos = 0
            self.session.stdin.writeln(t)
        elif key == 'tab':
            if self.completer:
                if self.completer_state == 0:
                    self.completer_string = self.input.get_edit_text()
                comp = self.completer.complete(self.completer_string, self.completer_state)
                if not comp:
                    self.completer_state = 0
                    self.input.set_edit_text(self.completer_string)
                else:
                    newtext = " ".join(self.input.get_edit_text().split()[:-1] + [comp])
                    self.input.set_edit_text(newtext + " ")
                    self.input.set_edit_pos(len(newtext))
                    self.completer_state += 1
        elif key == 'up' or key == 'down':
            self.history_pos = max(0, min(len(self.history), (self.history_pos + (key == 'up' and 1 or -1))))
            self.input.set_edit_text(self.history[-self.history_pos])
            self.input.set_edit_pos(10000)
        elif key == 'page up' or key == 'page down':
            self.text.keypress(size, key)
        else:
            self.text.set_focus(len(self.lines)-1)
            self.completer_state = 0
            ret = self.input.keypress((size[0],), key)

        self._invalidate()

        return ret

    def append_data(self, data):
        scroll = False
        if self.text.get_focus()[1] == len(self.lines)-1:
            scroll = True

        for l in data.splitlines(True):
            newchunks = self.parse_attributes(l.strip('\n'))
            if len(self.lines[-1]) > 0 and len(newchunks) > 0 and self.lines[-1][-1][0] == newchunks[0][0]:
                self.lines[-1][-1] = (newchunks[0][0], self.lines[-1][-1][1] + newchunks[0][1])
                self.lines[-1].extend(newchunks[1:])
            else:
                self.lines[-1].extend(newchunks)
            self.lines[-1] = self.parse_backspace(self.lines[-1])

            if l[-1] == '\n':
                self.lines.append([])

        if scroll:
            self.text.set_focus(len(self.lines)-1)

        self._invalidate()

    def parse_backspace(self, line):
        result = []
        for chunk in line:
            s = ""
            i = 0
            for c in chunk[1]:
                if c == "\b":
                    if i == 0:
                        if len(result) > 0:
                            result[i-1] = (result[i][0], result[i-1][1][:-1])
                    else:
                        s = s[:-1]
                else:
                    s += c
                i += 1
            result.append((chunk[0], s))
        return result

    def parse_attributes(self, data):
        ret = []

        while data != "":
            m = re.match(r"(.*?)(\033\[\d+m)(.*)", data)
            if not m:
                ret.append((self.current_attr, data))
                return ret
            ret.append((self.current_attr, m.group(1)))

            # currently, the parser supports 8 colors and bold
            if m.group(2)[2] == "1":
                self.current_attr = self.current_attr[0] + '1'
            elif m.group(2)[2] == "3":
                self.current_attr = str(int(m.group(2)[3])+1)[0] + self.current_attr[1]
            elif m.group(2)[2] == "0":
                self.current_attr = "00"

            data = m.group(3)

        return ret



class StatusWidget(urwid.WidgetWrap):
    def __init__(self):
        self.w_main_status = urwid.Edit();
        self.w_right_status = urwid.Text("", align="right")
        self.w_middle_status = urwid.Text("", align="center")

        self.pile = urwid.Pile([
            urwid.Columns([
                urwid.AttrMap(self.w_main_status, 'user_input'),
                self.w_right_status
            ]),
            self.w_middle_status
        ])

        urwid.WidgetWrap.__init__(self, self.pile)

    def keypress(self, size, key):
        if key == "enter":
            global master

            words = str(self.w_main_status.get_edit_text()).split()

            if words != "":
                master.command(words)

            self.w_main_status.set_edit_text("")
            master.w_frame.set_focus('body')
        else:
            return self.w_main_status.keypress(size, key)

    def start_edit(self):
        self.w_main_status.set_caption(options.prefix)

    def stop_edit(self):
        self.w_main_status.set_caption("")
        self.w_main_status.set_edit_text("")

    def set_left(self, text):
        self.w_main_status.set_caption(text)

    def set_middle(self, text):
        self.w_middle_status.set_text(text);

    def set_right(self, text):
        self.w_right_status.set_text(text);



class MapWidget(urwid.WidgetWrap):
    def __init__(self, mapper):
        self.mapper = mapper
        self.text = urwid.Text("", align='center')

        self.mode = ""
        self.direction_buf = ""
        
        urwid.WidgetWrap.__init__(self, urwid.Filler(self.text))

        self.update_map()

    def update_map(self):
        if self.mapper.map.current_room:
            exits = ""
            for e in self.mapper.map.current_room.exits:
                exits += e.upper() + "     "

            self.text.set_text("\n".join(self.mapper.map.render(True)) + "\n" + exits)
            self._invalidate()
