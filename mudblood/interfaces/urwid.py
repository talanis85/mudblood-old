from __future__ import absolute_import

import sys
import os

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

        self.w_frame = urwid.Frame(self.w_session, None, urwid.AttrMap(self.w_status, 'user_input'))

        palette = [
                ('default', 'default', 'default'),
                ('user_input', 'brown', 'default'),
                ('info', 'dark blue', 'default'),
                ('error', 'dark red', 'default'),
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
            elif k == options.prefix:
                self.w_status.set_caption(options.prefix)
                self.w_frame.set_focus('footer')
            else:
                outk.append(k)

        return outk

    def session_callback(self, ob, typ, arg):
        if typ == Event.STDIO:
            self.w_session.append_data(ob.out[arg].read()) 
        if typ == Event.INFO:
            self.w_session.append_data(ob.info.read(), 'info') 
        elif typ == Event.CLOSED:
            for o in ob.out:
                if o.has_data():
                    self.w_session.append_data(o.read()) 
            self.w_session.append_data("Session closed.\n", 'info')
        elif typ == Event.CONNECTED:
            self.w_session.append_data("Session started.\n", 'info')
        elif typ == Event.ERROR:
            self.w_session.append_data(ob.stderr.read() + "\n", 'error')

        self.loop.draw_screen()

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

    def cmd_quit(self):
        raise urwid.ExitMainLoop()



class SessionWidget(urwid.BoxWidget):
    class SessionList(urwid.ListWalker):
        def __init__(self, w_session):
            self.w_session = w_session

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
            n = len(self.w_session.lines) - 1
            return (urwid.Text(self.w_session.lines[n]), n)

        def set_focus(self, focus):
            pass

    class SessionListBox(urwid.ListBox):
        def rows(self, (maxcol,), focus=False):
            return len(self.body.w_session.lines)

    def __init__(self, session):
        self.data_lock = threading.Lock()

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

        self.text = self.SessionListBox(self.SessionList(self))

    def render(self, size, focus=False):
        c = urwid.CompositeCanvas(urwid.SolidCanvas(" ", size[0], size[1]))

        h = min(size[1], len(self.lines))
        textc = self.text.render((size[0], h), focus)
        c.overlay(textc, 0, size[1] - h)

        x = 0
        for l in self.lines[-1]:
            x += len(l[1])
        c.overlay(self.input_attr.render((size[0]-x,), focus), x, size[1]-1)

        return c

    def selectable(self):
        return True

    def keypress(self, size, key):
        ret = None

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
        else:
            self.completer_state = 0
            ret = self.input.keypress((size[0],), key)

        self.data_lock.acquire()
        self._invalidate()
        self.data_lock.release()

        return ret

    def append_data(self, data, attr='default', redraw=False):
        self.data_lock.acquire()

        self.data += data

        (a,b,c) = data.partition("\n")
        self.lines[-1].append((attr, a))
        while b == "\n":
            self.lines.append([])
            (a,b,c) = c.partition("\n")
            self.lines[-1].append((attr, a))

        self._invalidate()
        self.text._invalidate()

        self.data_lock.release()



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