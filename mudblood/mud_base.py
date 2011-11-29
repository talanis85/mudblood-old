#
# mud_base.py
#
# MUD definition base module. Must be imported by MUD definitions.

from commands import CommandObject
import hook

class Mud(CommandObject):

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

    def connect(self, session):
        self.session = session

    def load_map_hook(self, map):
        """Executed after a map was loaded."""
        pass

    def cmd_toggle_map_mode(self):
        if self.session.mapper.mode == "fixed":
            self.session.mapper.mode = "auto"
        elif self.session.mapper.mode == "auto":
            self.session.mapper.mode = "off"
        elif self.session.mapper.mode == "off":
            self.session.mapper.mode = "fixed"
        elif self.session.mapper.mode == "catchall":
            self.session.mapper.mode = "auto"
        return True

    def cmd_addtrigger(self, *args):
        (t, m, r) = " ".join(args).partition(" -> ")
        if m:
            self.triggers.add(hook.Trigger(t, r))
            return "Added Trigger: '%s' Response: '%s'" % (t, r)
        else:
            return "Syntax Error"

    def cmd_deltrigger(self, n):
        n = int(n)
        self.triggers.remove(n)
        return "Deleted trigger #%d" % n

    def cmd_triggers(self):
        return "\n".join(["%d: %s" % (k, str(self.triggers.t[k])) for k in range(len(self.triggers.t))])

    def get_middle_status(self):
        return ""

    def get_right_status(self):
        return "(%s) %s #%03d [%s]" % (
                 self.session.mapper.map.current_room.tag,
                 self.session.mapper.mode,
                 self.session.mapper.map.current_room.roomid,
                 self.session.mapper.map.name)

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
