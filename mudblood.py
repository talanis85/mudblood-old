#!/usr/bin/env python

# mudblood - A mud client
#
# Copyright (c) 2011 Philip Kranz

from __future__ import absolute_import

import sys
import interfaces.serial, interfaces.curses, interfaces.urwid

from optparse import OptionParser

VERSION = "0.1"

def main():
    parser = OptionParser(usage="Usage: %prog [options] <host> <port>",
                          version="mudblood " + VERSION)

    parser.add_option("-i", "--interface",
                      action =  "store",
                      dest =    "interface",
                      type =    "choice",
                      choices = ["serial", "curses"],
                      default = "serial",
                      help =    "Choices: serial (default) or curses",)

    parser.add_option("-p", "--prefix",
                      action =  "store",
                      dest =    "prefix",
                      type =    "string",
                      default = ".",
                      help =    "Command Prefix (default: '.')")


    (options, args) = parser.parse_args()

    if options.interface == "serial":
        interfaces.serial.options = options
        s = interfaces.serial.Serial()
        r = s.run()

    elif options.interface == "curses":
        interfaces.urwid.options = options
        interfaces.urwid.args = args
        s = interfaces.urwid.Urwid()
        r = s.run()

    else:
        print "Interface not known"
        sys.exit(1)

    if r == -1:
        parser.print_usage()
        sys.exit(1)

main()
