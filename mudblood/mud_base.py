#
# mud_base.py
#
# MUD definition base module. Must be imported by MUD definitions.

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
        raise cls.NoDirectionError()

path = ""

host = "localhost"
port = 9999

strings = {
    'prompt': "\n> ",
    'command_not_found': "Hae?",
    }

input_hooks = []
