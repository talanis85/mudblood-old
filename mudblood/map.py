# $Id$

import time
import pickle
from operator import attrgetter

class Edge:
    """
        An edge of a graph
    """
    def __init__(self, a, a_name, b, b_name=""):
        if b_name == "":
            b_name = a.mud.Direction.opposite(a_name)
            if not b_name:
                b_name = a_name

        self.a, self.a_name, self.b, self.b_name = a, a_name, b, b_name
        self.split = False

        a.exits[a_name] = self
        b.exits[b_name] = self

    def remove(self):
        del self.a.exits[self.a_name]
        del self.b.exits[self.b_name]

    def to(self, origin):
        if self.a == origin:
            return self.b
        elif self.b == origin:
            return self.a
        else:
            raise Exception("%s is not assiciated with this edge." % str(origin))

    def set_to(self, origin, to):
        if self.a == origin:
            del self.b.exits[self.b_name]
            self.b = to
            self.b.exits[self.b_name] = self
        elif self.b == origin:
            del self.a.exits[self.a_name]
            self.a = to
            self.a.exits[self.a_name] = self
        else:
            raise Exception("%s is not assiciated with this edge." % str(origin))

    def set_name(self, origin, newname):
        """Change the name of an exit.

           An empty string means: Remove the exit in one direction (i.e.
           make the Edge one-way."""

        if self.a == origin:
            del origin.exits[self.a_name]
            self.a_name = newname
            if newname != "":
                origin.exits[newname] = self
        elif self.b == origin:
            del origin.exits[self.b_name]
            self.b_name = newname
            if newname != "":
                origin.exits[newname] = self
        else:
            raise Exception("%s is not assiciated with this edge." % str(origin))

    def set_opposite_name(self, origin, newname):
        self.set_name(self.to(origin), newname)

class Room:
    """
        A node in the graph
    """
    def __init__(self, mud, tag=""):
        self.tag = tag
        self.mud = mud
        self.roomid = -1

        # TODO: This should really be a set
        self.exits = {}
        self.x, self.y = 0, 0
        self.mark = 0
        self.comp = 0
        self.distance = 0

    def __repr__(self):
        return "Room #%d, exits: %s" % (self.roomid, ",".join(self.exits.keys()))

    def add_exit(self, room, name):
        """
            Connect two rooms in both directions, thus keeping the graph undirected.

            @param room     The room to connect self to
            @param name     The (canonical) name of the direction
        """
        Edge(self, name, room)

    def get_exit(self, name):
        if name in self.exits:
            return self.exits[name]
        return None

    def remove_exit(self, name):
        """
            Remove an exit. Again, the opposite direction is also removed.
            
            @param name     The direction to remove
        """
        self.exits[name].remove()

    def _update_coords(self, x, y, mark, comp):
        """
            Set the coordinates for this room and recurse to all
            adjacent rooms.

            @param x    The x coordinate
            @param y    The y coordinate
            @param mark A unique value to mark already visited rooms
            @param comp An integer defining the connected component
        """
        self.x = x
        self.y = y
        self.mark = mark
        self.comp = comp

        sx, sy = self.x, self.y

        for n,e in self.exits.iteritems():
            if e.to(self).mark == mark or e.split:
                continue
            try:
                (nx, ny) = self.mud.Direction.calc(n, self.x, self.y)
                e.to(self)._update_coords(nx, ny, mark, comp)
            except self.mud.Direction.NoDirectionError:
                pass

# ---

class MapNotification:
    NEW_CYCLE = 1

class Mapper:
    """
        Provides automapping functionality. Client modules should interface with the mapper
        using Mapper.go_to().
    """

    def __init__(self, mud):
        self.mud = mud

        self.map = Map(self.mud)
        self.mode = "fixed"
        self.move_stack = []
        self.last_cycle = None

    def handle_input(self, l):
        if l == "" or self.mode == "off":
            return

        if l in self.map.current_room.exits or self.mode == "catchall":
            return self.go_to(l)
        else:
            d = self.mud.Direction.canonical(l)
            if d:
                return self.go_to(d)

    def go_to(self, direction):
        """
            Do what is needed to go in a certain direction. When in auto-mode, creates rooms
            as needed. When in fixed-mode, only updates current_room.

            @param direction    The direction to move
            @return             None or a MapNotification to indicate a special condition.
                                (such as a new cycle)
        """
        self.last_cycle = None

        if direction in self.map.current_room.exits:
            self.map.current_room = self.map.current_room.exits[direction].to(self.map.current_room)
            self.move_stack.append((self.map.current_room, direction, 0))
        else:
            if self.mode not in ['auto', 'catchall']:
                return

            self.map.update_coords()
            new_room = Room(self.mud)

            try:
                (x, y) = self.mud.Direction.calc(direction, self.map.current_room.x, self.map.current_room.y)

                for r in self.map.rooms.itervalues():
                    if (r.x, r.y, r.comp) == (x, y, self.map.current_room.comp):
                        self.last_cycle = (self.map.current_room, new_room, direction)
                        Edge(self.map.current_room, direction, r)
                        self.map.current_room = r
                        self.move_stack.append((self.map.current_room, direction, 1))
                        return MapNotification.NEW_CYCLE

            except self.mud.Direction.NoDirectionError:
                pass

            self.map.add(new_room)
            Edge(self.map.current_room, direction, new_room)
            self.map.current_room = new_room
            self.move_stack.append((self.map.current_room, direction, 2))

    def find_room(self, room):
        """
           Address a specific room.
           
           @param room  Either a a string "tag" or "#roomnumber" or an integer.
           @return      The room object or None if not found.
        """
        r = None
        if type(room) == str:
            if room[0] == "#":
                r = self.map.rooms[int(room[1:])]
            else:
                for ro in self.map.rooms.itervalues():
                    if ro.tag == room:
                        r = ro
                        break
        elif type(room) == int:
            r = self.map.rooms[room]

        return r

    def find_shortest_path(self, target):
        """Shortest path from current_room to target."""

        from heapq import heappush,heappop

        self.map.current_room.shortest_path = []
        pq = [(0, self.map.current_room)]
        mark = time.time()

        while len(pq) > 0:
            curdist, curroom = heappop(pq)
            curroom.mark = mark
            curroom.distance = curdist
            for name,e in curroom.exits.iteritems():
                if e.to(curroom).mark != mark or e.to(curroom).distance > curdist + 1:
                    e.to(curroom).mark = mark
                    e.to(curroom).shortest_path = curroom.shortest_path + [name]
                    heappush(pq, (curdist + 1, e.to(curroom)))

        if target.mark == mark:
            return target.shortest_path
        else:
            return None

    def join(self, other):
        """Join current_room with other.
           The other room is kept."""

        for e in self.map.current_room.exits.values():
            e.set_to(e.to(self.map.current_room), other)
        del self.map.rooms[self.map.current_room.roomid]
        self.map.current_room = other

    def undo(self):
        """
            Undo the last action.
        """
        r, d, t = self.move_stack.pop()

        self.map.current_room = self.move_stack[-1][0]

        if t >= 1:
            self.map.current_room.exits[d].remove()
        if t == 2:
            del self.map.rooms[r.roomid]

        return (r, d, t)

    # COMMANDS

    def command(self, cmd, args):
        if cmd == "":
            return False

        if hasattr(self, "cmd_" + cmd):
            return getattr(self, "cmd_" + cmd)(args)
        else:
            return False

    def cmd_undo(self, args):
        self.undo()
        return "Ok."

    def cmd_clear(self, args):
        self.map = Map(self.mud)
        return "Map cleared."

    def cmd_nocycle(self, args):
        if self.last_cycle == None:
            return "There was no cycle"

        last_room, new_room, d = self.last_cycle
        last_room.exits[d].remove()
        Edge(last_room, d, self.map.add(new_room))
        self.map.current_room = new_room
        self.last_cycle = None

        self.move_stack.pop()
        self.move_stack.append((self.map.current_room, d, 2))

        return "Ok."

    def cmd_opposite(self, args):
        r, d = self.move_stack[-2][0], self.move_stack[-1][1]
        r.exits[d].set_opposite_name(r, " ".join(args))

        return "Changed way back to: " + " ".join(args)

    def cmd_rmexit(self, args):
        if args == []:
            return "Which exit?"

        if args[0] in self.map.current_room.exits:
            self.map.current_room.exits[args[0]].set_name(self.map.current_room, "")
            return "Ok."
        else:
            return "No such exit."

    def cmd_mode(self, args):
        if args == []:
            return "Mapper mode: " + self.mode
        
        valid_modes = ['fixed', 'auto', 'catchall', 'off']

        if args[0] in valid_modes:
            self.mode = args[0]
            return "Mapper mode: " + self.mode
        else:
            return "Valid modes are: " + ", ".join(valid_modes)

    def cmd_move(self, args):
        if args == []:
            return "Move where?"

        if args[0] in self.map.current_room.exits:
            self.map.current_room = self.map_current_room.exits[args[0]].to(self.map_current_room)
            return True
        else:
            return "There is no way to go " + args[0]

    def cmd_tag(self, args):
        if args == []:
            if self.map.current_room.tag == "":
                return "This room has no tag."
            else:
                return "This room is tagged: %s" % self.map.current_room.tag
        else:
            self.map.current_room.tag = args[0]
            return "Tagged this room as: %s" % args[0]

    def cmd_goto(self, args):
        if args == []:
            return "Go where?"
        else:
            r = self.find_room(args[0])
            if r:
                self.current_room = r
                return "Ok."
            else:
                return "Tag %s not found." % args[0]

    def cmd_save(self, args):
        """Save the map to a file."""

        if len(args) > 0:
            self.map.name = args[0]
        if self.map.name == "":
            return "Please give a map name."

        with open("maps/%s" % self.map.name, "w") as f:
            MapPickler().save(self.map, f)
        return "Ok."

    def cmd_load(self, args):
        """Load a map from a file."""

        if args == []:
            return "Load which map?"
        with open("maps/%s" % args[0], "r") as f:
            self.map = MapPickler().load(self.mud, f)

        return "Map %s loaded." % args[0]

    def cmd_cycle(self, args):
        """Make a connection from current_room to args[0]."""

        if args == []:
            return "Build a cycle where?"

        other = self.find_room(args[0])
        if other:
            self.join(other)
            return "Ok. Built cycle to %s." % r.tag
        else:
            return "No such room."

    def cmd_split(self, args):
        """Open a new connected component. The map is split between the
           current and the last room."""

        r,d = self.move_stack[-2][0], self.move_stack[-1][1]

        r.exits[d].split = True
        return "Ok."
    
    def cmd_merge(self, args):
        """Merge this map with another map.
           Arguments: Name of other map
                      Roomid or tag of a room in the other map
           The current room will be joined with the room in the other map."""
        
        other = None
        with open("maps/%s" % args[0], "r") as f:
            other = MapPickler().load(self.mud, f)

        room_to_merge = self.find_room(args[1])

        for r in other.rooms.itervalues():
            self.map.add(r)

        self.join(room_to_merge)

        return "Merge successful."
    
class Map:
    """
        The Map
    """
    class MapInconsistencyError(Exception):
        pass

    def __init__(self, mud):
        self.mud = mud
        self.name = ""
        self.rooms = {}
        self.nextid = 0
        self.current_room = self.add(Room(self.mud))

    def __repr__(self):
        r = ""
        for c in self.render():
            if not r == "":
                r += "\n"
            r += c + "\n"
        return r

    def add(self, room):
        """
            Add a room to the map.

            @param room     The room to add.
            @return         Just that room.
        """
        room.roomid = self.nextid
        self.rooms[self.nextid] = room;
        self.nextid += 1
        return room
    
    def update_coords(self):
        if self.rooms == {}:
            return 0

        mark = time.time()
        comp = 0

        # To render the graph, we have to assign each room a coordinate value that should
        # reflect the topology of the game reasonably good. For this, we do a DFS on every
        # Room we haven't visited so far (Room._update_coords()). Each DFS gives us coordinates
        # for a single connected component of the graph.
        for r in self.rooms.itervalues():
            if r.mark != mark:
                r._update_coords(0, 0, mark, comp)
                comp += 1

        return comp


    def render(self, only_current=False):
        """
            Render the map to ASCII.

            @param only_current     If True, draw only the current connected component
            @return                 A list of strings, each forming a single line.
        """

        comp = self.update_coords()

        allret = []
        bridges = []

        # Now that we have all coordinates, we can draw the map
        for c in (only_current and [self.current_room.comp] or range(comp)):
            comprooms = filter(lambda r: r.comp == c, self.rooms.itervalues())

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
            for i in range((h+1) * 3 + 1):
                ret.append(bytearray("   " * (w+1+1), "ascii"))

            for r in comprooms:
                char = ' '
                bridge = 0

                for name,e in r.exits.iteritems():
                    try:
                        self.mud.Direction.calc(name, 0, 0)
                        if e.split:
                            raise self.mud.Direction.NoDirectionError
                    except self.mud.Direction.NoDirectionError:
                        for i in range(len(bridges)):
                            if e.to(r) in bridges[i]:
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
                      '_': '+',
                      '\\': '|',
                      '/': '|' }
                if orig in m:
                    return m[orig]
                else:
                    return orig
            
            def horiz(orig):
                m = { ' ': '-',
                      '|': '+',
                      '-': '-',
                      '_': '-',
                      '\\': '-',
                      '/': '-' }
                if orig in m:
                    return m[orig]
                else:
                    return orig
            
            def diag1(orig):
                m = { ' ': '\\',
                      '|': '|',
                      '-': '-',
                      '_': '_',
                      '\\': '\\',
                      '/': 'X' }
                if orig in m:
                    return m[orig]
                else:
                    return orig

            def diag2(orig):
                m = { ' ': '/',
                      '|': '|',
                      '-': '-',
                      '_': '_',
                      '\\': 'X',
                      '/': '/' }
                if orig in m:
                    return m[orig]
                else:
                    return orig


            for r in comprooms:
                for e in r.exits:
                    if e == self.mud.Direction.SOUTH:
                        ret[r.y*3+2][r.x*3+1] = '|'
                    elif e == self.mud.Direction.SOUTHEAST:
                        ret[r.y*3+2][r.x*3+2] = '\\'
                    elif e == self.mud.Direction.EAST:
                        ret[r.y*3+1][r.x*3+2] = '-'
                    elif e == self.mud.Direction.NORTHEAST:
                        ret[r.y*3][r.x*3+2] = '/'
                    elif e == self.mud.Direction.NORTH:
                        ret[r.y*3][r.x*3+1] = '|'
                    elif e == self.mud.Direction.NORTHWEST:
                        ret[r.y*3][r.x*3] = '\\'
                    elif e == self.mud.Direction.WEST:
                        ret[r.y*3+1][r.x*3] = '-'
                    elif e == self.mud.Direction.SOUTHWEST:
                        ret[r.y*3+2][r.x*3] = '/'
                e = r.get_exit(self.mud.Direction.SOUTH)
                if e and e.to(r).comp == c:
                    cy = r.y * 3 + 1 + 1
                    cx = r.x * 3 + 1
                    if e.to(r).x == r.x:
                        while cy < h * 3 + 1 and chr(ret[cy][cx]) in [' ', '-', '/', '\\', '+']:
                            ret[cy][cx] = vert(chr(ret[cy][cx]))
                            cy += 1
                    elif e.to(r).x > r.x:
                        ret[cy][cx] = "|"
                        cx += 1
                        while cx < e.to(r).x * 3 + 1:
                            ret[cy][cx] = "_"
                            cx += 1
                        cy += 1
                        ret[cy][cx] = "|"
                    elif e.to(r).x < r.x:
                        ret[cy][cx] = "|"
                        cx -= 1
                        while cx < e.to(r).x * 3 + 1:
                            ret[cy][cx] = "_"
                            cx -= 1
                        cy += 1
                        ret[cy][cx] = "|"

                e = r.get_exit(self.mud.Direction.EAST)
                if e and e.to(r).y == r.y and e.to(r).comp == c:
                    cy = r.y * 3 + 1
                    cx = r.x * 3 + 1 + 1
                    while cx < w * 3 + 1 and chr(ret[cy][cx]) in [' ', '-', '/', '\\', '+']:
                        ret[cy][cx] = horiz(chr(ret[cy][cx]))
                        cx += 1

                e = r.get_exit(self.mud.Direction.SOUTHEAST)
                if e and e.to(r).comp == c:
                    cy = r.y * 3 + 1 + 1
                    cx = r.x * 3 + 1 + 1
                    if e.to(r).y-e.to(r).x == r.y-r.x:
                        while cx < w * 3 + 1 and cy < h * 3 + 1 and chr(ret[cy][cx]) in [' ', '-', '/', '\\', '+']:
                            ret[cy][cx] = diag1(chr(ret[cy][cx]))
                            cx += 1
                            cy += 1
                    else:
                        ret[cy][cx] = "\\"
                        cx += 1
                        while cx < e.to(r).x * 3 + 1:
                            ret[cy][cx] = "_"
                            cx += 1
                        while cy < e.to(r).y * 3 - 1:
                            ret[cy][cx] = "|"
                            cy += 1
                        cy += 1
                        ret[cy][cx] = "\\"

                e = r.get_exit(self.mud.Direction.SOUTHWEST)
                if e and e.to(r).comp == c:
                    cy = r.y * 3 + 1 + 1
                    cx = r.x * 3 + 1 - 1
                    if e.to(r).y+e.to(r).x == (r.y+r.x):
                        while cx >= 0 and cy < h * 3 + 1 and chr(ret[cy][cx]) in [' ', '-', '/', '\\', '+']:
                            ret[cy][cx] = diag2(chr(ret[cy][cx]))
                            cx -= 1
                            cy += 1
                    else:
                        ret[cy][cx] = "/"
                        cx -= 1
                        while cx > e.to(r).x * 3 + 2:
                            ret[cy][cx] = "_"
                            cx -= 1
                        cy += 1
                        while cy < e.to(r).y * 3:
                            ret[cy][cx] = "|"
                            cy += 1
                        ret[cy][cx] = "/"

            allret.extend([str(l) for l in ret])
            allret.append("")

        return allret

class MapPickler:
    class BadFileException(Exception):
        pass

    def save(self, map, file):
        file.write("#mudblood map file\n")
        file.write("%s\n%d\n%d\n" % (map.name, map.nextid, map.current_room.roomid))

        for r in map.rooms.itervalues():
            file.write("%d %s\n" % (r.roomid, r.tag))
        file.write("\n")
        edges = set()
        for r in map.rooms.itervalues():
            for e in r.exits.itervalues():
                edges.add(e)
        for e in edges:
            file.write("%d|%s|%d|%s|%d\n" % (e.a.roomid, e.a_name, e.b.roomid, e.b_name, (e.split and 1 or 0)))

    def load(self, mud, file):
        def readint():
            return int(file.readline().strip())
        def readln():
            return file.readline().strip()

        if readln() != "#mudblood map file":
            raise BadFileException("Magic line not found.")
        
        map = Map(mud)
        try:
            map.name = readln()
            map.nextid = readint()
            map.current_room = readint()
            l = file.readline()
            while l != "\n":
                l = l.strip().split(" ")
                room = Room(mud)
                room.roomid = int(l[0])
                room.tag = " ".join(l[1:])
                map.rooms[room.roomid] = room
                l = file.readline()
            l = file.readline()
            while l != "":
                l = l.strip().split("|")
                edge = Edge(map.rooms[int(l[0])], l[1], map.rooms[int(l[2])], l[3])
                edge.split = (l[4] == "1")
                l = file.readline()
            map.current_room = map.rooms[map.current_room]
        except:
            raise self.BadFileException("Malformed map file")
        
        return map
