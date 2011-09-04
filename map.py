import time

from collections import namedtuple

def instantiate(cls, mud, *args):
    return type(cls)(cls.__name__ + '_', (cls,), {'mud': mud})(*args)

# ---

class Edge:
    def __init__(self, to, name=""):
        self.to = to
        self.name = name

class Room:
    def __init__(self, text="", tag=""):
        self.text = text
        self.tag = tag

        self.exits = []
        self.x, self.y = 0, 0
        self.mark = 0
        self.comp = 0

    def __repr__(self):
        return self.tag

    def add_exit(self, room, name):
        if room.has_exit(self.mud.Direction.opposite(name)):
            raise Map.MapInconsistencyError("Duplicate exit %s in %s" % (self.mud.Direction.opposite(name), room))
        if self.has_exit(name):
            raise Map.MapInconsistencyError("Duplicate exit %s in %s" % (self, room))

        self.exits.append(instantiate(Edge, self.mud, room, name))
        room.exits.append(instantiate(Edge, self.mud, self, self.mud.Direction.opposite(name)))

    def remove_exit(self, name):
        e = self.get_exit(name)
        if e:
            self.exits.remove(e)
            oe = e.to.get_exit(self.mud.Direction.opposite(name))
            e.to.exits.remove(oe)

    def has_exit(self, name):
        for e in self.exits:
            if e.name == name:
                return True

        return False

    def get_exit(self, name):
        for e in self.exits:
            if e.name == name:
                return e
        return None

    def _update_coords(self, x, y, mark, comp):
        self.x = x
        self.y = y
        self.mark = mark
        self.comp = comp

        (max_x, max_y) = (self.x, self.y)

        for e in self.exits:
            if e.to.mark == mark:
                continue
            try:
                (nx, ny) = self.mud.Direction.calc(e.name, self.x, self.y)
                (x, y) = e.to._update_coords(nx, ny, mark, comp)
                (max_x, max_y) = (min(x, max_x), min(y, max_y))
            except self.mud.Direction.NoDirectionError:
                pass

        return (max_x, max_y)

# ---

class MapNotification:
    NEW_CYCLE = 1

class Mapper:
    def __init__(self, mud):
        self.mud = mud

        self.map = instantiate(Map, self.mud)
        self.mode = "fixed"
        self.move_stack = []
        self.last_cycle = None

    def go_to(self, direction, text=""):
        self.last_cycle = None

        if self.mode == "off":
            return

        if self.map.current_room:
            if self.map.current_room.has_exit(direction):
                self.map.current_room = self.map.current_room.get_exit(direction).to
                self.move_stack.append((self.map.current_room, direction, 0))
            else:
                if self.mode != "auto":
                    return

                new_room = instantiate(Room, self.mud, text)

                self.map.current_room._update_coords(0, 0, time.time(), 0)
                try:
                    (x, y) = self.mud.Direction.calc(direction, self.map.current_room.x, self.map.current_room.y)

                    for r in self.map.rooms:
                        if (r.x, r.y) == (x, y):
                            self.last_cycle = (self.map.current_room, new_room, direction)
                            self.map.current_room.add_exit(r, direction)
                            self.map.current_room = r
                            self.move_stack.append((self.map.current_room, direction, 1))
                            return MapNotification.NEW_CYCLE
                except self.mud.Direction.NoDirectionError:
                    pass

                self.map.add(new_room)
                self.map.current_room.add_exit(new_room, direction)
                self.map.current_room = new_room
                self.move_stack.append((self.map.current_room, direction, 2))
        else:
            if self.mode != "auto":
                return
            self.map.current_room = self.map.add(instantiate(Room, self.mud, text))
            self.move_stack.append((self.map.current_room, direction, 2))

    def undo(self):
        r, d, t = self.move_stack.pop()

        self.map.current_room = self.move_stack[-1][0]

        if t >= 1:
            self.map.current_room.remove_exit(d)
        if t == 2:
            self.map.rooms.remove(r)

        return (r, d, t)

    def run_command(self, cmd):
        if cmd == []:
            return False

        if hasattr(self, "cmd_" + cmd[0]):
            return getattr(self, "cmd_" + cmd[0])(cmd[1:])
        else:
            return False

    def cmd_undo(self, args):
        self.undo()

    def cmd_clear(self, args):
        self.map.rooms = []
        return "Map cleared."

    def cmd_nocycle(self, args):
        # TODO: use self.undo()
        if self.last_cycle == None:
            return "There was no cycle"

        last_room, new_room, d = self.last_cycle
        last_room.remove_exit(d)
        last_room.add_exit(self.map.add(new_room), d)
        self.map.current_room = new_room
        self.last_cycle = None

        return "Ok."

    def cmd_opposite(self, args):
        r, d, t = self.move_stack[-1]
        r.remove_exit(self.mud.self.mud.Direction.opposite(d))
        r.add_exit(self.move_stack[-2][0], args[0])

        return "Changed way back to: " + args[0]

    def cmd_mode(self, args):
        if args == []:
            return "Mapper mode: " + self.mode

        if args[0] in ['fixed', 'auto', 'off']:
            self.mode = args[0]
            return "Mapper mode: " + self.mode
        else:
            return "Valid modes are: fixed, auto, off"

    def cmd_move(self, args):
        if args == []:
            return "Move where?"

        e = self.map.current_room.get_exit(args[0])
        if e:
            self.map.current_room = e.to
            return True
        else:
            return "There is no way to go " + args[0]

class Map:
    """
        The Map
    """
    class MapInconsistencyError(Exception):
        pass

    def __init__(self):
        self.rooms = []
        self.current_room = None

    def __repr__(self):
        r = ""
        for c in self.render():
            if not r == "":
                r += "\n"
            r += c + "\n"
        return r

    def add(self, room):
        self.rooms.append(room);
        return room

    def render(self):
        """
            Render the map to ASCII.

            @return The rendered ASCII art
        """
        if self.rooms == []:
            return []

        mark = time.time()
        comp = 0
        mincoords = []

        for r in self.rooms:
            if r.mark != mark:
                mincoords.append(r._update_coords(0, 0, mark, comp))
                comp += 1

        change = True
        while change:
            change = False
            for s in self.rooms:
                for r in self.rooms:
                    if (r.x, r.y, r.comp) == (s.x, s.y, s.comp) and r != s:
                        change = True
                        mod = lambda x,y: (x,y)
                        for e in s.exits:
                            if e.name == self.mud.Direction.NORTH:
                                mod = lambda x,y: y >= s.y and (x,y+1) or (x,y)
                            if e.name == self.mud.Direction.EAST:
                                mod = lambda x,y: x <= s.x and (x-1,y) or (x,y)
                            if e.name == self.mud.Direction.SOUTH:
                                mod = lambda x,y: y <= s.y and (x,y-1) or (x,y)
                            if e.name == self.mud.Direction.WEST:
                                mod = lambda x,y: x >= s.x and (x+1,y) or (x,y)
                        for o in self.rooms:
                            if s.comp != o.comp or o == s:
                                continue
                            (o.x, o.y) = mod(o.x, o.y)

        allret = []
        bridges = []

        for c in range(comp):
            comprooms = filter(lambda r: r.comp == c, self.rooms)

            minx = min([r.x for r in comprooms])
            miny = min([r.y for r in comprooms])
            maxx = max([r.x for r in comprooms])
            maxy = max([r.y for r in comprooms])

            w = maxx - minx
            h = maxy - miny

            for r in comprooms:
                r.x -= minx
                r.y -= miny

            ret = []
            for i in range((h+1) * 3):
                ret.append(bytearray("   " * (w+1), "ascii"))

            for r in comprooms:
                char = ' '
                bridge = 0

                for e in r.exits:
                    try:
                        self.mud.Direction.calc(e.name, 0, 0)
                    except self.mud.Direction.NoDirectionError:
                        for i in range(len(bridges)):
                            if e.to in bridges[i]:
                                bridges[i].add(r)
                                bridge = i+1
                        if bridge == 0:
                            bridges.append(set([r]))
                            bridge = len(bridges)


                if self.current_room == r:
                    char = "X"
                elif bridge:
                    char = chr(ord("A")+bridge-1)
                else:
                    char = "#"
                ret[r.y * 3 + 1][r.x * 3 + 1] = char


            def vert(orig):
                m = { ' ': '|',
                      '|': '|',
                      '-': '+',
                      '\\': '|',
                      '/': '|' }
                return m[orig]
            
            def horiz(orig):
                m = { ' ': '-',
                      '|': '+',
                      '-': '-',
                      '\\': '-',
                      '/': '-' }
                return m[orig]
            
            def diag1(orig):
                m = { ' ': '\\',
                      '|': '|',
                      '-': '-',
                      '\\': '\\',
                      '/': 'X' }
                return m[orig]

            def diag2(orig):
                m = { ' ': '/',
                      '|': '|',
                      '-': '-',
                      '\\': 'X',
                      '/': '/' }
                return m[orig]

            for r in comprooms:
                e = r.get_exit(self.mud.Direction.SOUTH)
                if e and e.to.x == r.x:
                    cy = r.y * 3 + 1 + 1
                    cx = r.x * 3 + 1
                    while cy < h * 3 + 1 and chr(ret[cy][cx]) not in ['#', 'X']:
                        ret[cy][cx] = vert(chr(ret[cy][cx]))
                        cy += 1

                e = r.get_exit(self.mud.Direction.EAST)
                if e and e.to.y == r.y:
                    cy = r.y * 3 + 1
                    cx = r.x * 3 + 1 + 1
                    while cx < w * 3 + 1 and chr(ret[cy][cx]) not in ['#', 'X']:
                        ret[cy][cx] = horiz(chr(ret[cy][cx]))
                        cx += 1

                e = r.get_exit(self.mud.Direction.SOUTHEAST)
                if e and e.to.y-e.to.x == r.y-r.x:
                    cy = r.y * 3 + 1 + 1
                    cx = r.x * 3 + 1 + 1
                    while cx < w * 3 + 1 and cy < h * 3 + 1 and chr(ret[cy][cx]) not in ['#', 'X']:
                        ret[cy][cx] = diag1(chr(ret[cy][cx]))
                        cx += 1
                        cy += 1

                e = r.get_exit(self.mud.Direction.SOUTHWEST)
                if e:
                    cy = r.y * 3 + 1 + 1
                    cx = r.x * 3 + 1 - 1
                    while cx >= 0 and cy < h * 3 + 1 and chr(ret[cy][cx]) not in ['#', 'X']:
                        ret[cy][cx] = diag2(chr(ret[cy][cx]))
                        cx -= 1
                        cy += 1

            allret.extend([str(l) for l in ret])
            allret.append("")

        return allret

