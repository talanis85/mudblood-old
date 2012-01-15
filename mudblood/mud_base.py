#
# mud_base.py
#
# MUD definition base module. Must be imported by MUD definitions.

import hook

def pass_command(cmd):
    if hasattr(this, "cmd_" + cmd[0]):
        ret = getattr(this, "cmd_" + cmd[0])(*(cmd[1:]))
        if not ret:
            return True
        return ret
    else:
        return False

class Direction:
    class NoDirectionError(Exception):
        pass

    NONE = ""
    NORTH = "n"
    NORTHWEST = "nw"
    WEST = "w"
    SOUTHWEST = "sw"
    SOUTH = "s"
    SOUTHEAST = "so"
    EAST = "o"
    NORTHEAST = "no"

    directions = [
            (['n', 'norden'],       's'),
            (['nw', 'nordwesten'],  'so'),
            (['w', 'westen'],       'o'),
            (['sw', 'suedwesten'],  'no'),
            (['s', 'sueden'],       'n'),
            (['so', 'suedosten'],   'nw'),
            (['o', 'osten'],        'w'),
            (['no', 'nordosten'],   'sw'),
        ]

    @classmethod
    def canonical(cls, d):
        for ds in cls.directions:
            if d in ds[0]:
                return ds[0][0]
        return None

    @classmethod
    def calc(cls, d, x, y, step=1):
        funcs = {
                cls.NORTH:        lambda x,y: (x, y-step),
                cls.NORTHWEST:    lambda x,y: (x-step, y-step),
                cls.WEST:         lambda x,y: (x-step, y),
                cls.SOUTHWEST:    lambda x,y: (x-step, y+step),
                cls.SOUTH:        lambda x,y: (x, y+step),
                cls.SOUTHEAST:    lambda x,y: (x+step, y+step),
                cls.EAST:         lambda x,y: (x+step, y),
                cls.NORTHEAST:    lambda x,y: (x+step, y-step),
                }

        try:
            return funcs[d](x, y)
        except KeyError:
            raise cls.NoDirectionError()

    @classmethod
    def opposite(cls, d):
        for ds in cls.directions:
            if d in ds[0]:
                return ds[1]
        return None

session = None

def connect(s):
    global session
    session = s

def cmd_toggle_map_mode():
    if session.mapper.mode == "fixed":
        session.mapper.mode = "auto"
    elif session.mapper.mode == "auto":
        session.mapper.mode = "off"
    elif session.mapper.mode == "off":
        session.mapper.mode = "fixed"
    elif session.mapper.mode == "catchall":
        session.mapper.mode = "auto"
    return True

def cmd_addtrigger(*args):
    (t, m, r) = " ".join(args).partition(" -> ")
    if m:
        triggers.add(hook.Trigger(t, r))
        return "Added Trigger: '%s' Response: '%s'" % (t, r)
    else:
        return "Syntax Error"

def cmd_deltrigger(n):
    n = int(n)
    triggers.remove(n)
    return "Deleted trigger #%d" % n

def cmd_triggers():
    return "\n".join(["%d: %s" % (k, str(triggers.t[k])) for k in range(len(triggers.t))])

def get_middle_status():
    return ""

def get_right_status():
    if session:
        return "(%s) %s #%03d [%s]" % (
                 session.mapper.map.current_room.tag,
                 session.mapper.mode,
                 session.mapper.map.current_room.roomid,
                 session.mapper.map.name)
    else:
        return ""

keys = {
        "f5": "#showmap",
        "f4": "#toggle_map_mode",
        }

import os
mapdir = os.path.expanduser("~/.config/mudblood/maps")

path = ""

host = "localhost"
port = 9999

strings = {
    'prompt': "\n> ",
    'command_not_found': "Hae?",
    }

triggers = hook.TriggerList()

input_hooks = [triggers]
output_hooks = []
