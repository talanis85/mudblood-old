from __future__ import absolute_import

import sys
import os

import re

import urwid
import urwid.curses_display
import traceback
import threading

from mudblood.session import Session, Event

VERSION = "0.1"


master = None


class ThreadSafeMainLoop(urwid.MainLoop):
    def __init__(self, widget, palette=[], screen=None, handle_mouse=True, input_filter=None, unhandled_input=None, event_loop=None):
        self.draw_lock = threading.Lock()

        urwid.MainLoop.__init__(self, widget, palette, screen, handle_mouse, input_filter, unhandled_input, event_loop)

    def draw_screen(self):
        self.draw_lock.acquire()
        if self.screen._started:
            urwid.MainLoop.draw_screen(self)
        self.draw_lock.release()



class DynamicOverlay(urwid.Overlay):
    def selectable(self):
        return self.top_w.selectable() or self.bottom_w.selectable()

    def keypress(self, size, key):
        if self.top_w.selectable():
            key = self.top_w.keypress(size, key)
        if key and self.bottom_w.selectable():
            return self.bottom_w.keypress(size, key)
        else:
            return key



class Interface:
    def __init__(self, mud = None):
        global master
        master = self
        self.mud = mud

    def run(self):
        self.session = Session(self.mud, self.session_callback)

        self.w_session = SessionWidget(self.session)
        self.w_status = StatusWidget()

        self.w_map = MapWidget(self.session.mapper)
        self.w_map_status = urwid.Text("", align="right")

        self.w_bottom_bar = urwid.Columns([urwid.AttrMap(self.w_status, 'user_input'), self.w_map_status])

        self.w_frame = urwid.Frame(self.w_session, None, self.w_bottom_bar)

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

                # Unfortunately no 'bold' support in curses_display
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

        screen = urwid.curses_display.Screen()

        self.loop = ThreadSafeMainLoop(self.w_frame, palette, screen, handle_mouse=False, input_filter=self.master_input)

        self.session.connect()

        self.loop.run()

    def master_input(self, keys, raw):
        outk = []

        for k in keys:
            if k == "esc":
                self.end_overlay()
                self.w_status.set_caption("")
                self.w_status.set_edit_text("")
                self.w_frame.set_focus('body')
            elif k == options.prefix and self.w_frame.focus_part != 'footer':
                self.w_status.set_caption(options.prefix)
                self.w_frame.set_focus('footer')
            else:
                outk.append(k)

        return outk

    def session_callback(self, ob, typ, arg):
        if typ == Event.STDIO:
            for o in ob.out:
                if ob.out[o].has_data():
                    self.w_session.append_data(ob.out[o].read()) 
        if typ == Event.INFO:
            self.w_session.append_data(ob.info.read(), 'info') 
        elif typ == Event.CLOSED:
            for o in ob.out:
                if ob.out[o].has_data():
                    self.w_session.append_data(ob.out[o].read()) 
            self.w_session.append_data("Session closed.\n", 'info')
        elif typ == Event.CONNECTED:
            self.w_session.append_data("Session started.\n", 'info')
        elif typ == Event.ERROR:
            self.w_session.append_data(ob.stderr.read() + "\n", 'error')

        self.w_map.update_map()
        self.update_map_status()
        self.loop.draw_screen()

    def update_map_status(self):
        self.w_map_status.set_text("(%s) %s #%03d [%s]" % (self.session.mapper.map.current_room.tag, self.session.mapper.mode, self.session.mapper.map.current_room.roomid, self.session.mapper.map.name))
        self.w_map_status._invalidate()

    def set_status(self, msg):
        self.w_status.set_caption(msg)

    def start_overlay(self, widget):
        self.w_overlay = DynamicOverlay(urwid.LineBox(widget), self.w_session, 'center', ('relative', 80), 'middle', ('relative', 80))
        self.w_frame.set_body(self.w_overlay)

    def end_overlay(self):
        self.w_frame.set_body(self.w_session)

    def command(self, cmd, args):
        if hasattr(self, "cmd_" + cmd):
            ret = getattr(self, "cmd_" + cmd)(*args)
        else:
            ret = self.session.command(cmd, args)

        if ret:
            if isinstance(ret, str):
                self.set_status(ret)
            else:
                self.set_status("")
        else:
            self.set_status("Command not found.")

        self.update_map_status()

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
            return "Ok."
        else:
            return "No MUD def file used."

    def cmd_showmap(self):
        self.w_map.update_map()
        self.start_overlay(self.w_map)
        return True

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
            return (urwid.Text(self.w_session.lines[n+1]), n+1)

        def get_prev(self, start_from):
            if isinstance(start_from, int):
                n = start_from
            else:
                w, n = start_from
            if n <= 0:
                return (None, None)
            return (urwid.Text(self.w_session.lines[n-1]), n-1)

        def get_focus(self):
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
        self.lines = [[]]

        self.completer = self.session.completer
        self.completer_state = 0
        self.completer_string = ""

        self.history = [""]
        self.history_pos = 0
        
        self.input = urwid.Edit("")
        self.input_attr = urwid.AttrMap(self.input, 'user_input')

        self.current_attr = "00"

        self.text = self.SessionListBox(self.SessionList(self))

    def render(self, size, focus=False):
        c = urwid.CompositeCanvas(urwid.SolidCanvas(" ", size[0], size[1]))

        h = min(size[1], len(self.lines))
        textc = self.text.render((size[0], h), focus)
        c.overlay(textc, 0, size[1] - h)

        if size[1] > len(self.lines) or self.text.get_focus()[1] == len(self.lines) - 1:
            x = 0
            for l in self.lines[-1]:
                x += len(l[1])
            c.overlay(self.input_attr.render((size[0]-x,), focus), x, size[1]-1)

        return c

    def selectable(self):
        return True

    def keypress(self, size, key):
        ret = None

        self.scrolling = False
        if key == 'enter':
            self.append_data(self.input.get_edit_text() + "\n", 'user_input')
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
            self.history_pos = (self.history_pos + (key == 'up' and 1 or -1)) % len(self.history)
            self.input.set_edit_text(self.history[-self.history_pos])
            self.input.set_edit_pos(10000)
        elif key == 'page up' or key == 'page down':
            self.scrolling = True
            self.text.keypress(size, key)
        else:
            self.text.set_focus(len(self.lines)-1)
            self.completer_state = 0
            ret = self.input.keypress((size[0],), key)

        self.data_lock.acquire()
        self._invalidate()
        self.data_lock.release()

        return ret

    def append_data(self, data, attr='00', redraw=False):
        self.data_lock.acquire()

        last_attr = self.current_attr
        if attr != '00':
            self.current_attr = attr

        (a,b,c) = data.partition("\n")
        self.lines[-1].extend(self.parse_attributes(a))
        while b == "\n":
            self.lines.append([])
            (a,b,c) = c.partition("\n")
            self.lines[-1].extend(self.parse_attributes(a))

        if not self.scrolling:
            self.text.set_focus(len(self.lines)-1)

        self.current_attr = last_attr

        self._invalidate()
        self.text._invalidate()

        self.data_lock.release()

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

class StatusWidget(urwid.Edit):
    def keypress(self, size, key):
        if key == "enter":
            global master

            words = self.get_edit_text().split()

            master.command(words[0], words[1:])
            self.set_edit_text("")
            master.w_frame.set_focus('body')
        else:
            return urwid.Edit.keypress(self, size, key)

class MapWidget(urwid.WidgetWrap):
    def __init__(self, mapper):
        self.mapper = mapper
        self.text = urwid.Text("", align='center')

        self.mode = ""
        self.direction_buf = ""
        
        urwid.WidgetWrap.__init__(self, urwid.Filler(self.text))

        self.update_map()

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == "f2":
            if self.mapper.map.current_room:
                self.mapper.map.current_room.preferred_correction = (self.mapper.map.current_room.preferred_correction + 1) % 9
                self.update_map()
        else:
            return key

    def update_map(self):
        if self.mapper.map.current_room:
            try:
                self.text.set_text("\n".join(self.mapper.map.render(True)) + "\n" + str(self.mapper.map.current_room))
            except Exception, e:
                global master
                master.w_session.append_data(traceback.format_exc(), 'error')
            self._invalidate()
