# -*- coding: UTF-8 -*-
# Copyright (C) 2008, Jack Zielke <jack@linuxcoffee.com>
# Copyright (C) 2008, One Laptop Per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import gtk
import pango
import time
import socket
import random
import gobject
import json

from gettext import gettext as _

from sugar import profile
from sugar.activity import activity
from sugar.bundle.activitybundle import ActivityBundle
from sugar.graphics.menuitem import MenuItem
from sugar.graphics.toolbutton import ToolButton
from xml.dom.minidom import parseString

HOST = 'rotate.aprs2.net'
#HOST = '192.168.50.14'
PORT = 14580
RECV_BUFFER = 4096

MAXLINES = 50
MAXRETRIES = 15
MAX_MSG_QUEUE = 25
MAX_PER_CALL_QUEUE = 2

FILTER = "m/300"

bundle = ActivityBundle(activity.get_bundle_path())
VERSION = bundle.get_activity_version()
del bundle

class APRSActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        self.set_title(_('APRS-XO Activity'))

        self.sock = None
        self.location = "home"
        self.sent_acks = {}
        self.recv_acks = {}
        self.timers = []
        self.bulletins = ["AIR", "DGPS", "QST", "TEL", "ALL", "DRILL", "QTH", "TEST", "AP", "DX", "RTCM", "TLM", "BEACON", "ID", "SKY", "WX", "CQ", "JAVA", "SPACE", "ZIP", "GPS", "MAIL", "SPC", "DF", "MICE", "SYM", "BLN", "NWS", "NTS"]
        self.validating = False
        self.help = True
        self.messagebox = False
        self.sequence = random.randrange(0, 7000)
        self.queue_list = {}
        self.message_list = {}
        self.seen_bulletins = {}
        self.message_marks = {}
        self.input_watch = []
        self.output_watch = []
        self.cq_watch = []
        self.current_message = {}
        self.current_message_text = {}
        self.current_message_count = {}
        self.current_message_delay = {}
        self.last_selected = ''

        titlefont = pango.FontDescription('Sans bold 8')
        mediumfont = pango.FontDescription('Sans 6.5')
        smallfont = pango.FontDescription('Sans 6')
        verysmallfont = pango.FontDescription('Sans 4')

        firstName = profile.get_nick_name().split(None, 1)[0].capitalize()

        toolbox = activity.ActivityToolbox(self)
        self.set_toolbox(toolbox)

        activity_toolbar = toolbox.get_activity_toolbar()
        activity_toolbar.share.props.visible = False

        toolbox.show()

        win = gtk.HBox(False, 10)

        leftwin = gtk.VBox(False, 10)

        # Top 'about' box
        aboutbox = gtk.VBox(False, 11)
        aboutbox.set_border_width(10)

        topaboutbox = gtk.VBox(False, 0)

        titlebox = gtk.HBox(False, 0)
        titlelabel = gtk.Label("APRS-XO:")
        titlelabel.set_alignment(0, 0)
        titlelabel.modify_font(titlefont)
        titlebox.pack_start(titlelabel, False, False, 0)
        titlelabel.show()
        aboutlabel1 = gtk.Label("This amateur radio program will update your")
        aboutlabel1.set_alignment(0, 0.8)
#        aboutlabel1.modify_font(mediumfont)
        titlebox.pack_start(aboutlabel1, False, False, 0)
        aboutlabel1.show()
        topaboutbox.pack_start(titlebox, False, False, 0)
        titlebox.show()
        aboutlabel2 = gtk.Label("positon & status on all of the global APRS web pages once\nevery 10 minutes.")
        aboutlabel2.set_alignment(0, 0)
#        aboutlabel2.modify_font(mediumfont)
        topaboutbox.pack_start(aboutlabel2, False, False, 0)
        aboutlabel2.show()
        aboutbox.pack_start(topaboutbox, False, False, 0)
        topaboutbox.show()

        sitebox = gtk.HBox(False, 10)
        sitelabel = gtk.Label("Select an APRS site:")
        sitelabel.set_alignment(0, 0.4)
        sitebox.pack_start(sitelabel, False, False, 0)
        sitelabel.show()

        findubutton = gtk.Button()
        findubutton.set_label("FindU")
        findubutton.connect("clicked", self.open_url_button, "http://www.findu.com/cgi-bin/symbol.cgi?icon=XA&limit=200")
        sitebox.pack_start(findubutton, False, False, 0)
        findubutton.show()

        aprsworldbutton = gtk.Button()
        aprsworldbutton.set_label("APRSworld")
        aprsworldbutton.connect("clicked", self.open_url_button, "http://aprsworld.net/")
        sitebox.pack_start(aprsworldbutton, False, False, 0)
        aprsworldbutton.show()

        aprsbutton = gtk.Button()
        aprsbutton.set_label("APRS")
        aprsbutton.connect("clicked", self.open_url_button, "http://aprs.org/")
        sitebox.pack_start(aprsbutton, False, False, 0)
        aprsbutton.show()

        otherbutton = gtk.Button()
        otherbutton.set_label("About")
        otherbutton.connect("clicked", self.open_url_button, "http://zielkeassociates.com/~jack/aprs-xo/")
        sitebox.pack_start(otherbutton, False, False, 0)
        otherbutton.show()

        aboutbox.pack_start(sitebox, False, False, 0)
        sitebox.show()

        leftwin.pack_start(aboutbox, False, False, 0)
        aboutbox.show()

        separator = gtk.HSeparator()
        leftwin.pack_start(separator, False, False, 0)
        separator.show()

        # identifiers box
        identbox = gtk.VBox(False, 4)
        identbox.set_border_width(10)

        identlabel = gtk.Label("Identifiers")
        identlabel.set_alignment(0, 0)
        identlabel.modify_font(titlefont)
        identbox.pack_start(identlabel, False, False, 0)
        identlabel.show()

        bottomidentbox = gtk.HBox(False, 5)

        calllabel1 = gtk.Label("Callsign: ")
        calllabel1.set_alignment(1, 0.5)
        bottomidentbox.pack_start(calllabel1, False, False, 0)
        calllabel1.show()

        self.calltext = gtk.Entry()
        self.calltext.set_max_length(9)
        self.calltext.set_width_chars(9)
        self.calltext.set_text(self.metadata.get('callsign', ""))
        self.calltext.connect("changed", self.disable_beacon)
        bottomidentbox.pack_start(self.calltext, False, False, 0)
        self.calltext.show()

        passlabel1 = gtk.Label("Password: ")
        passlabel1.set_alignment(1, 0.5)
        bottomidentbox.pack_start(passlabel1, False, False, 0)
        passlabel1.show()

        self.passtext = gtk.Entry()
        self.passtext.set_max_length(5)
        self.passtext.set_width_chars(5)
        self.passtext.set_invisible_char("x")
        self.passtext.set_visibility(False)
        bottomidentbox.pack_start(self.passtext, False, False, 0)
        self.passtext.show()

        self.passbutton = gtk.CheckButton()
        self.passbutton.set_active(True)
        self.passbutton.connect("toggled", self.hide_password)
        bottomidentbox.pack_start(self.passbutton, False, False, 0)
        self.passbutton.show()

        passbuttonbox = gtk.VBox(False, 0)

        passlabel3 = gtk.Label("Hide")
        passlabel3.set_alignment(0.5, 0.5)
        passlabel3.modify_font(smallfont)
        passbuttonbox.pack_start(passlabel3, False, False, 0)
        passlabel3.show()

        passlabel4 = gtk.Label("Password")
        passlabel4.set_alignment(0, 0.5)
        passlabel4.modify_font(smallfont)
        passbuttonbox.pack_start(passlabel4, False, False, 0)
        passlabel4.show()

        bottomidentbox.pack_start(passbuttonbox, False, False, 0)
        passbuttonbox.show()

        identbox.pack_start(bottomidentbox, False, False, 0)
        bottomidentbox.show()

        passlabel2 = gtk.Label("optional")
        passlabel2.set_alignment(0.71, 0)
        passlabel2.modify_font(smallfont)
        identbox.pack_start(passlabel2, False, False, 0)
        passlabel2.show()

        leftwin.pack_start(identbox, False, False, 0)
        identbox.show()

        separator = gtk.HSeparator()
        leftwin.pack_start(separator, False, False, 0)
        separator.show()

        # station box
        stationbox = gtk.VBox(False, 11)
        stationbox.set_border_width(10)

        stationlabel = gtk.Label("Station Comment")
        stationlabel.set_alignment(0, 0)
        stationlabel.modify_font(titlefont)
        stationbox.pack_start(stationlabel, False, False, 0)
        stationlabel.show()

        # so the text box does not fill all horizontal space
        stationtextbox = gtk.HBox()

        self.stationtext = gtk.Entry()
        self.stationtext.set_max_length(43)
        self.stationtext.set_width_chars(43)
        self.stationtext.set_text("%s's XO at home." % firstName)
        self.stationtext.connect("changed", self.disable_beacon)
        stationtextbox.pack_start(self.stationtext, False, False, 0)
        self.stationtext.show()
        stationbox.pack_start(stationtextbox, False, False, 0)
        stationtextbox.show()

        stationhelp = gtk.Label("Optional description of current position, status,\nor destination.  Enter up to 43 characters, most\nimportant first since some displays can only see\nthe first 20 or 28.")
        stationhelp.set_alignment(0, 0)
#        stationhelp.modify_font(mediumfont)
        stationbox.pack_start(stationhelp, False, False, 0)
        stationhelp.show()

        leftwin.pack_start(stationbox, False, False, 0)
        stationbox.show()

        separator = gtk.HSeparator()
        leftwin.pack_start(separator, False, False, 0)
        separator.show()

        # position box
        positbox = gtk.VBox(False, 11)
        positbox.set_border_width(10)

        toppositbox = gtk.HBox(False, 0)

        topleftpositbox = gtk.VBox(False, 4)

        positlabel1 = gtk.Label("Position Data")
        positlabel1.set_alignment(0, 0)
        positlabel1.modify_font(titlefont)
        topleftpositbox.pack_start(positlabel1, False, False, 0)
        positlabel1.show()

        latpositbox = gtk.HBox(False, 4)
        latlabel1 = gtk.Label("Latitude:    ")
        latlabel1.set_alignment(0, 0.5)
        latpositbox.pack_start(latlabel1, False, False, 0)
        latlabel1.show()

        self.latDDtext = gtk.Entry()
        self.latDDtext.set_max_length(2)
        self.latDDtext.set_width_chars(4)
        self.latDDtext.set_text("DD")
        self.latDDtext.connect("changed", self.disable_beacon)
        latpositbox.pack_start(self.latDDtext, False, False, 0)
        self.latDDtext.show()

        self.latMMtext = gtk.Entry()
        self.latMMtext.set_max_length(2)
        self.latMMtext.set_width_chars(3)
        self.latMMtext.set_text("MM")
        self.latMMtext.connect("changed", self.disable_beacon)
        latpositbox.pack_start(self.latMMtext, False, False, 0)
        self.latMMtext.show()

        latlabel2 = gtk.Label(".")
        latlabel2.set_alignment(0, 1)
        latpositbox.pack_start(latlabel2, False, False, 0)
        latlabel2.show()

        self.latmmtext = gtk.Entry()
        self.latmmtext.set_max_length(2)
        self.latmmtext.set_width_chars(3)
        self.latmmtext.set_text("mm")
        self.latmmtext.connect("changed", self.disable_beacon)
        latpositbox.pack_start(self.latmmtext, False, False, 0)
        self.latmmtext.show()

        self.latcombo = gtk.combo_box_new_text()
        self.latcombo.append_text("N")
        self.latcombo.append_text("S")
        self.latcombo.set_active(0)
        latpositbox.pack_start(self.latcombo, False, False, 0)
        self.latcombo.show()

        topleftpositbox.pack_start(latpositbox, False, False, 0)
        latpositbox.show()

        lonpositbox = gtk.HBox(False, 4)
        lonlabel1 = gtk.Label("Longitude: ")
        lonlabel1.set_alignment(0, 0.5)
        lonpositbox.pack_start(lonlabel1, False, False, 0)
        lonlabel1.show()

        self.lonDDDtext = gtk.Entry()
        self.lonDDDtext.set_max_length(3)
        self.lonDDDtext.set_width_chars(4)
        self.lonDDDtext.set_text("DDD")
        self.lonDDDtext.connect("changed", self.disable_beacon)
        lonpositbox.pack_start(self.lonDDDtext, False, False, 0)
        self.lonDDDtext.show()

        self.lonMMtext = gtk.Entry()
        self.lonMMtext.set_max_length(2)
        self.lonMMtext.set_width_chars(3)
        self.lonMMtext.set_text("MM")
        self.lonMMtext.connect("changed", self.disable_beacon)
        lonpositbox.pack_start(self.lonMMtext, False, False, 0)
        self.lonMMtext.show()

        lonlabel2 = gtk.Label(".")
        lonlabel2.set_alignment(0, 1)
        lonpositbox.pack_start(lonlabel2, False, False, 0)
        lonlabel2.show()

        self.lonmmtext = gtk.Entry()
        self.lonmmtext.set_max_length(2)
        self.lonmmtext.set_width_chars(3)
        self.lonmmtext.set_text("mm")
        self.lonmmtext.connect("changed", self.disable_beacon)
        lonpositbox.pack_start(self.lonmmtext, False, False, 0)
        self.lonmmtext.show()

        self.loncombo = gtk.combo_box_new_text()
        self.loncombo.append_text("W")
        self.loncombo.append_text("E")
        self.loncombo.set_active(0)
        lonpositbox.pack_start(self.loncombo, False, False, 0)
        self.loncombo.show()

        topleftpositbox.pack_start(lonpositbox, False, False, 0)
        lonpositbox.show()

        toppositbox.pack_start(topleftpositbox, False, False, 0)
        topleftpositbox.show()

        toprightpositbox = gtk.VBox(False, 4)
        toprightpositbox.set_border_width(10)

        loclabel = gtk.Label("-OR- Zip Code:")
        loclabel.set_alignment(0.3, 0)
        toprightpositbox.pack_start(loclabel, False, False, 0)
        loclabel.show()

        self.ziptext = gtk.Entry()
        self.ziptext.set_max_length(5)
        self.ziptext.set_width_chars(5)
        self.ziptext.connect("changed", self.disable_beacon)
        toprightpositbox.pack_start(self.ziptext, False, False, 0)
        self.ziptext.show()

        toppositbox.pack_start(toprightpositbox, False, False, 0)
        toprightpositbox.show()

        positbox.pack_start(toppositbox, False, False, 0)
        toppositbox.show()

        positlabel2 = gtk.Label("If you do not know your LAT/LONG then your zip code will\nbe used to place you on the map.")
        positlabel2.set_alignment(0, 0)
#        positlabel2.modify_font(mediumfont)
        positbox.pack_start(positlabel2, False, False, 0)
        positlabel2.show()

        leftwin.pack_start(positbox, False, False, 0)
        positbox.show()

        separator = gtk.HSeparator()
        leftwin.pack_start(separator, False, False, 0)
        separator.show()

        # defined here so clear and connect buttons have access
        self.statusview = gtk.TextView()
        self.statusbuffer = self.statusview.get_buffer()
        self.messageview = gtk.TextView()
        self.messagebuffer = self.messageview.get_buffer()

        self.connectbutton = gtk.Button()
        self.connectbutton.set_label("Connect")
        self.connectbutton.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#00b20d"))
        self.connectbutton.connect("clicked", self.connect_aprs)
        leftwin.pack_start(self.connectbutton, False, False, 12)
        self.connectbutton.show()

        win.pack_start(leftwin, False, False, 0)
        leftwin.show()

        rightwin = gtk.VBox(False, 4)
        rightwin.set_border_width(4)

        rightwintopbox = gtk.HBox(False, 4)

        clearbutton = gtk.Button()
        clearbutton.set_label(" Clear ")
        clearbutton.connect("clicked", self.clear_message_button)
        rightwintopbox.pack_start(clearbutton, False, False, 1)
        clearbutton.show()

        cancelbutton = gtk.Button()
        cancelbutton.set_label(" Cancel ")
        cancelbutton.connect("clicked", self.cancel_dialog)
        rightwintopbox.pack_start(cancelbutton, False, False, 1)
        cancelbutton.show()

        self.cqbutton = gtk.CheckButton("CQ")
        self.cqbutton.set_active(False)
        self.cqbutton.connect("toggled", self.enable_cq)
        rightwintopbox.pack_start(self.cqbutton, False, False, 3)
        self.cqbutton.show()

        self.beaconbutton = gtk.CheckButton("Beacon every 10 minutes")
        self.beaconbutton.set_active(True)
        self.beaconbutton.connect("toggled", self.enable_beacon)
        rightwintopbox.pack_start(self.beaconbutton, False, False, 2)
        self.beaconbutton.show()

        rightwin.pack_start(rightwintopbox, False, False, 0)
        rightwintopbox.show()

        self.messageview.set_editable(False)
        self.messageview.set_cursor_visible(True)
        self.messageview.set_wrap_mode(gtk.WRAP_CHAR)
        self.messageview.set_justification(gtk.JUSTIFY_LEFT)
        self.messageview.modify_font(smallfont)

        self.messagebuffer.set_text("Welcome to APRS-XO.\n\nThis program sends your position information to a server that\nwill display your location on a webpage.  This program requires an active Internet connection to work.\n\nSelect an APRS Site\nSelecting a button will copy the URI to the journal.\n\nIndentifiers\nEnter your callsign.  If you leave the password blank it will be\nautomatically generated.\n\nStation Comment\nData in the Station Comment field will appear after your\nlocation information on the website.")

        # tags for easier reading of messages
        self.messagebold = self.messagebuffer.create_tag("bold", weight=pango.WEIGHT_BOLD)

        self.messagewindow = gtk.ScrolledWindow()
        self.messagewindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.messagewindow.add(self.messageview)
        self.messageview.show()
        rightwin.pack_start(self.messagewindow, True, True, 0)
        self.messagewindow.show()

        messagebox = gtk.HBox(False, 4)

        self.messagetocall = gtk.Entry()
        self.messagetocall.set_max_length(9)
        self.messagetocall.set_width_chars(9)
        self.messagetocall.modify_font(smallfont)
        tocallcompletion = gtk.EntryCompletion()
        self.tocalllist = gtk.ListStore(str)
        self.tocalllist.append(["ALL"])
        self.tocalllist.append(["BEACON"])
        self.tocalllist.append(["CQ"])
        self.tocalllist.append(["QST"])
        self.tocalllist.append(["CQSRVR"])
        tocallcompletion.set_model(self.tocalllist)
        self.messagetocall.set_completion(tocallcompletion)
        tocallcompletion.set_text_column(0)
        self.messagetocall.set_text("TO:")
        self.messagetocall.select_region(0, -1)
        tocallcompletion.connect("match-selected", self.tocall_selected)
        messagebox.pack_start(self.messagetocall, False, False, 1)
        self.messagetocall.show()

        self.messagetext = gtk.Entry()
        self.messagetext.set_max_length(67)
        self.messagetext.set_width_chars(30)
        self.messagetext.modify_font(smallfont)
#        self.messagetext.connect("activate", self.send_message, self.messagetext)
        self.messagetext.connect("activate", self.send_message)
        messagebox.pack_start(self.messagetext, False, False, 0)
        self.messagetext.show()

        messagebutton = gtk.Button()
        messagebutton.set_label("Send")
        messagebutton.connect("clicked", self.send_message)
        messagebox.pack_start(messagebutton, False, False, 0)
        messagebutton.show()

        rightwin.pack_start(messagebox, False, False, 0)
        messagebox.show()

        self.statusview.set_editable(False)
        self.statusview.set_cursor_visible(True)
        self.statusview.set_wrap_mode(gtk.WRAP_CHAR)
        self.statusview.set_justification(gtk.JUSTIFY_LEFT)
        self.statusview.modify_font(smallfont)

        self.statusbuffer.set_text("Position\nEnter your lat/long.  You may leave the decimal minutes (mm)\nblank for position ambiguity.  If you do not know your lat/long,\nenter your 5 digit zip code instead.\n\nCQ\nWhen selected, sends \"CQ CQ CQ From <Station Comment>\"\nto CQSRVR every 32 minutes.\n\nBeacon\nWhen selected, sends location data.  Automatically stops when\nyou edit personal information.  Must be manually reselected.\n\nThis message will self destruct when you press Connect.\n\nAPRS Copyright (c) Bob Bruninga WB4APR\n")

        self.statuswindow = gtk.ScrolledWindow()
        self.statuswindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.statuswindow.add(self.statusview)
        self.statusview.show()
        rightwin.pack_start(self.statuswindow, True, True, 0)
        self.statuswindow.show()

        self.rawbox = gtk.HBox(False, 6)

        self.rawtext = gtk.Entry()
        self.rawtext.set_max_length(128)
        self.rawtext.set_width_chars(42)
        self.rawtext.modify_font(smallfont)
        self.rawtext.connect("activate", self.raw_send)
        self.rawbox.pack_start(self.rawtext, False, False, 0)
        self.rawtext.show()

        rawbutton = gtk.Button()
        rawbutton.set_label("Send")
        rawbutton.connect("clicked", self.raw_send)
        self.rawbox.pack_start(rawbutton, False, False, 0)
        rawbutton.show()

        rightwin.pack_start(self.rawbox, False, False, 0)
        self.rawbox.show()
 
        win.pack_start(rightwin, False, False, 0)
        rightwin.show()

        self.set_canvas(win)
        win.show()
        self.calltext.grab_focus()

        # Fix window not updating until activity after alt-tab
        self.statusbuffer.create_mark("end", self.statusbuffer.get_end_iter(), False)
        # Do the same for message window, without auto delete it did not have the problem
        self.messagebuffer.create_mark("end", self.messagebuffer.get_end_iter(), False)

    def clear_status(self, button=None):
        self.statusbuffer.set_text("")

    def clear_message(self, button=None):
        self.messagebuffer.set_text("")

    def clear_message_button(self, button=None):
        temp_queue_list = self.queue_list.copy()
        temp_message_list = self.message_list.copy()
        temp_current_message = self.current_message.copy()
        temp_recv_acks = self.recv_acks.copy()

        # cancel all outgoing messages
        self.clear_msg_queue()

        # clear seen bulletin list
        self.seen_bulletins = {}

        # clear message screen
        self.clear_message()

        # re-add outgoing messages (reset text iters)
        if (temp_current_message != {}):
            for call in temp_current_message:
                sequence = temp_current_message[call]
                id = "%s-%s" % (call, sequence)
                message = self.current_message_text[call]
                count = self.current_message_count[call]
                delay = self.current_message_delay[call]
                if (temp_recv_acks[id] != 1):
                    self.send_message(None, call, message, sequence, count, delay, False)

        # re-add queued messages
        if (temp_queue_list != {}):
            for call in temp_queue_list:
                for sequence in temp_queue_list[call]:
                    id = "%s-%s" % (call, sequence)
                    message = temp_message_list[id]
                    self.send_message(None, call, message, sequence)

    def connect_aprs(self, button):
        if (self.sock == None):

            if (self.help):
                self.clear_status()
                self.messagebuffer.set_text("Message Window")
                self.messagebox = True
                self.help = False

            if (self.validate_data() == False):
                return False
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.status_write("Connecting ")
            try:
                iplist = socket.gethostbyname_ex(HOST)[2]
            except socket.error, msg:
                self.status_write("\n%s\n" % msg[1])
                self.sock = None
                return False
            server = random.choice(iplist)
            self.status_write("to %s\n" % server)
            try:
                self.sock.connect((server, PORT))
            except socket.error, msg:
                self.status_write("%s\n" % msg[1])
                self.sock = None
                return False

            self.status_write("Connected\n")
            button.set_label("Disconnect")
            button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#e6000a"))
        
            response = self.sock.recv(RECV_BUFFER)
            self.status_write("%s" % response)
            if (response.find("javAPRSSrvr") == -1):
                self.status_write("invalid response.\n")
                self.disconnect_aprs(button)
                return False

            if (response.find("Port Full") != -1):
                self.status_write("Port Full.\n")
                self.disconnect_aprs(button)
                return False

            if (self.calltext.get_text() != "" and self.passtext.get_text() != ""):
                sendme = "user %s pass %s vers aprs_xo %d filter %s\n" % (self.calltext.get_text(), self.passtext.get_text(), VERSION, FILTER)
            else:
                sendme = "user %s vers aprs_xo %d\n" % (self.calltext.get_text(), VERSION)
            self.sock.sendall(sendme)
            self.status_write("%s" % sendme)

            response = self.sock.recv(RECV_BUFFER)
            self.status_write("%s" % response)
            if (response.find("# logresp") == -1):
                self.status_write("invalid response.\n")
                self.disconnect_aprs(button)
                return False

            if (response.find("unverified") != -1):
                sendme = "# filter %s\n" % FILTER
                self.sock.sendall(sendme)
                self.status_write("%s\n" % sendme)

            self.status_write("\n")

            self.input_watch.append(gobject.io_add_watch(self.sock, gobject.IO_IN, self.recv_data))

            # send banner
            sendme = "%s>APRS-XO v%s\n" % (self.calltext.get_text(), VERSION)
            self.sock.sendall(sendme)
            self.status_write("%s>\n" % self.calltext.get_text())
            self.status_write("APRS-XO v%s\n\n" % VERSION)

            self.send_beacon()
            self.output_watch.append(gobject.timeout_add(10 * 60 * 1000, self.send_beacon))

            # Start CQ if checked
            if (self.cqbutton.get_active()):
                self.send_cq()
                self.cq_watch.append(gobject.timeout_add(32 * 60 * 1000, self.send_cq))

        else:
            self.disconnect_aprs(button)

    def disconnect(self):
        if (self.sock != None):
            # stop cq
            self.stop_cq()

            # for test server only
            if(HOST == "192.168.50.14"):
                self.sock.sendall("q")

            self.sock.close()
            self.sock = None

    def disconnect_aprs(self, button):
        self.disconnect()
        self.clear_msg_queue()

        self.status_write("Disconnected\n")

        # stop input watcher - just in case
        for source in self.input_watch:
            try:
                gobject.source_remove(source)
            except:
                pass

        # stop beacon
        for source in self.output_watch:
            try:
                gobject.source_remove(source)
            except:
                pass

        self.input_watch = []
        self.output_watch = []

        button.set_label("Connect")
        button.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#00b20d"))

    def recv_data(self, sock, condition):
        if (self.sock == None):
            return False
        while 1:
            try:
                recv_data = sock.recv(RECV_BUFFER)
            except:
                self.status_write("Server closed connection.\n")
                self.sock = None
                self.disconnect_aprs(self.connectbutton)
                return False
            if not recv_data:
                self.status_write("Server closed connection.\n")
                self.sock = None
                self.disconnect_aprs(self.connectbutton)
                return False
            else:
                # sometimes more than one packet comes in
                for packet in recv_data.split("\n"):
                    if (len(packet) < 2):
                        break
                    # find uri's http or www
                    webaddy = packet.lower().find("http")
                    if (webaddy != -1):
                        packet = ("%s\n%s" % (packet[:webaddy], packet[webaddy:]))
                    else:
                        webaddy = packet.lower().find("www")
                        if (webaddy != -1):
                            packet = ("%s\n%s" % (packet[:webaddy], packet[webaddy:]))
                    if (packet[0] == "#"):
                        self.status_write("%s\n\n" % packet)
                    else:
                        cuthere = packet.find(":")
                        self.status_write("%s\n" % packet[:cuthere+1])
                        self.status_write("%s\n\n" % packet[cuthere+1:])
                        self.msg_check(packet)
                return True

    def send_beacon(self):
        if (self.sock == None):
            return False
        if (self.beaconbutton.get_active()):
            beacon = "=%s%s.%s%sX%s%s.%s%sA%s" % (self.latDDtext.get_text(), self.latMMtext.get_text(), self.latmmtext.get_text(), self.latcombo.get_active_text(), self.lonDDDtext.get_text(), self.lonMMtext.get_text(), self.lonmmtext.get_text(), self.loncombo.get_active_text(), self.stationtext.get_text())
            if (self.send_data(beacon)):
                return True
            else:
                self.status_write("\nProblem sending beacon - STOPPED")
                return False

    def send_data(self, msg):
        if (self.sock == None):
            return False
        path = "%s>APOLPC:" % self.calltext.get_text()
        try:
            self.sock.sendall("%s%s\n" % (path, msg))
        except:
            self.status_write("Problem sending packet\n")
            self.sock = None
            self.disconnect_aprs(self.connectbutton)
            return False
        self.status_write("%s\n" % path)
        self.status_write("%s\n\n" % msg)
        return True

    def send_ack(self, tocall, sequence):
        # should check for duplicate messages in the next 30 seconds and drop them
        # aprsd does this for us - but should do it here as well
        if (tocall in self.sent_acks):
            currentack = self.sent_acks[tocall]
            if (currentack == sequence):
                ackmessage = ":%s:ack%s" % (tocall.ljust(9), sequence)
                self.send_data(ackmessage)
        return False

    def status_write(self, text):
        self.statusbuffer.insert(self.statusbuffer.get_end_iter(), text)
        statuslines = self.statusbuffer.get_line_count()
        if (statuslines > MAXLINES):
            deletehere = self.statusbuffer.get_iter_at_line(statuslines - MAXLINES)
            self.statusbuffer.delete(self.statusbuffer.get_start_iter(), deletehere)
        if (not self.statusview.is_focus()):
            self.statusbuffer.move_mark_by_name("end", self.statusbuffer.get_end_iter())
            self.statusview.scroll_mark_onscreen(self.statusbuffer.get_mark("end"))

    def message_write(self, text, bold=None):
        if (self.messagebox):
            self.clear_message()
            self.messagebox = False
        iter = self.messagebuffer.get_end_iter()
        self.messagebuffer.insert(iter, text)
        if (bold):
            bold_end = iter.copy()
            bold_end.forward_to_line_end()
            bold_start = bold_end.copy()
            bold_start.backward_chars(len(text))
            bold_start = bold_start.forward_search(">", gtk.TEXT_SEARCH_TEXT_ONLY)
            self.messagebuffer.apply_tag(self.messagebold, bold_start[1], bold_end)

        if (not self.messageview.is_focus()):
            self.messagebuffer.move_mark_by_name("end", self.messagebuffer.get_end_iter())
            self.messageview.scroll_mark_onscreen(self.messagebuffer.get_mark("end"))

    def validate_data(self):
        stop_here = False
        self.validating = True
        beaconchecked = self.beaconbutton.get_active()

        if (self.calltext.get_text() == "" and self.ziptext.get_text() == ""):
            self.status_write("A callsign or zip code must be provided.\n")
            return False

        # convert zip to position
        if (self.ziptext.get_text() != ""):
            self.status_write("Attempting to set location from zip code\n")
            self.ziptext.set_text(self.ziptext.get_text().zfill(5))
            try:
                zipsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            except socket.error, msg:
                self.status_write("[ERROR] %s\n" % msg[1])
                self.validating = False
                return False
            try:
                zipsock.connect(('local.yahooapis.com', 80))
            except socket.error, msg:
                self.status_write("[ERROR] %s\n" % msg[1])
                self.validating = False
                return False
            try:
                APPID = "XtIUm.bV34FWFtK62fv24MszIckfwgYDjHJ1mTSmxoY2.iLe4zoPvPbM7Z8D"
                zipsock.sendall("GET /MapsService/V1/geocode?appid=%s&zip=%s\n" % (APPID, self.ziptext.get_text()))
            except socket.error, msg:
                self.status_write("[ERROR] %s\n" % msg[1])
                self.validating = False
                return False
            zipsock.shutdown(1)
            try:
                response = zipsock.recv(RECV_BUFFER)
            except socket.error, msg:
                self.status_write("[ERROR] %s\n" % msg[1])
                self.validating = False
                return False
            A = random.randrange(0, 9)
            O = random.randrange(0, 9)
            if (self.calltext.get_text() == ""):
                self.calltext.set_text("X%s-%d%d" % (self.ziptext.get_text(), A, O))
                self.passtext.set_text("-1")
            try:
                zipdata = parseString(response)
                lat = (zipdata.getElementsByTagName('Latitude')[0]).childNodes[0].data.encode('iso-8859-1')
                lon = (zipdata.getElementsByTagName('Longitude')[0]).childNodes[0].data.encode('iso-8859-1')
            except:
                self.status_write("%s\n" % response)
                lat = "0"
                lon = "0"
            lat = float(lat.strip())
            lon = float(lon.strip())
            if (lat < 0):
                self.latcombo.set_active(1)	# S
            else:
                self.latcombo.set_active(0)	# N
            lat = abs(lat)
            if (lon < 0):
                self.loncombo.set_active(0)	# W
            else:
                self.loncombo.set_active(1)	# E
            lon = abs(lon)
            self.latDDtext.set_text("%02d" % int(lat))
            self.latMMtext.set_text("%02d" % int((lat - int(lat)) * 60 + 0.5))
            self.latmmtext.set_text("%d " % A)
            self.lonDDDtext.set_text("%03d" % int(lon))
            self.lonMMtext.set_text("%02d" % int((lon - int(lon)) * 60 + 0.5))
            self.lonmmtext.set_text("%d " % O)
            self.ziptext.set_text("")
        # end set loc by zip code

        if (self.latDDtext.get_text() == "DD" or self.latDDtext.get_text() == ""):
            self.status_write("Latitude Degrees are required.\n")
            stop_here = True
        if (self.latMMtext.get_text() == "MM" or self.latMMtext.get_text() == ""):
            self.status_write("Latitude Minutes are required.\n")
            stop_here = True
        if (self.lonDDDtext.get_text() == "DDD" or self.lonDDDtext.get_text() == ""):
            self.status_write("Longitude Degrees are required.\n")
            stop_here = True
        if (self.lonMMtext.get_text() == "MM" or self.lonMMtext.get_text() == ""):
            self.status_write("Longitude Minutes are required.\n")
            stop_here = True

        if (stop_here):
            self.status_write("Latitude and Longitude must be complete.\nFor position ambiguity omit decimal Minutes (mm).\nIf you do not know your lat/long, leave the letters\n(DD, MM, etc) and provide your zip code.\n")
            self.validating = False
            return False

        if (not self.latDDtext.get_text().isdigit()):
            self.status_write("Latitude Degrees must be a number.\n")
            stop_here = True
        if (not self.latMMtext.get_text().isdigit()):
            self.status_write("Latitude Minutes must be a number.\n")
            stop_here = True
        if (not self.lonDDDtext.get_text().isdigit()):
            self.status_write("Longitude Degrees must be a number.\n")
            stop_here = True
        if (not self.lonMMtext.get_text().isdigit()):
            self.status_write("Longitude Minutes must be a number.\n")
            stop_here = True

        if (stop_here):
            self.status_write("Invalid Position.\n")
            self.validating = False
            return False

        if (int(self.latDDtext.get_text()) < 0  or int(self.latDDtext.get_text()) > 90):
            self.status_write("Latitude Degrees must be between 0 and 90.\n")
            stop_here = True
        if (int(self.latMMtext.get_text()) < 0  or int(self.latMMtext.get_text()) > 60):
            self.status_write("Latitude Minutes must be between 0 and 60.\n")
            stop_here = True
        if (int(self.lonDDDtext.get_text()) < 0  or int(self.lonDDDtext.get_text()) > 180):
            self.status_write("Longitude Degrees must be between 0 and 180.\n")
            stop_here = True
        if (int(self.lonMMtext.get_text()) < 0  or int(self.lonMMtext.get_text()) > 60):
            self.status_write("Longitude Minutes must be between 0 and 60.\n")
            stop_here = True

        if (stop_here):
            self.status_write("Invalid Position.\n")
            self.validating = False
            return False

        # clean up entries
        self.latDDtext.set_text(self.latDDtext.get_text().zfill(2))
        self.latMMtext.set_text(self.latMMtext.get_text().zfill(2))
        self.lonDDDtext.set_text(self.lonDDDtext.get_text().zfill(3))
        self.lonMMtext.set_text(self.lonMMtext.get_text().zfill(2))
        self.latmmtext.set_text(self.latmmtext.get_text().ljust(2))
        self.lonmmtext.set_text(self.lonmmtext.get_text().ljust(2))
        if (self.latmmtext.get_text() == "mm"):
            self.latmmtext.set_text("  ")
        if (self.lonmmtext.get_text() == "mm"):
            self.lonmmtext.set_text("  ")
        self.calltext.set_text(self.calltext.get_text().upper())
        if (self.passtext.get_text() == ""):
            self.passtext.set_text(self.aprspass(self.calltext.get_text()))
        self.beaconbutton.set_active(beaconchecked)
        self.validating = False

    def can_close( self ):
        self.hide()
        if (self.sock != None):
            self.disconnect()
        return True

    def write_file(self, file_path):
        try:
            JournalData = {}
            JournalData['callsign'] = self.calltext.get_text()
            JournalData['password'] = self.passtext.get_text()
            JournalData['latDD'] = self.latDDtext.get_text()
            JournalData['latMM'] = self.latMMtext.get_text()
            JournalData['latmm'] = self.latmmtext.get_text()
            JournalData['lat'] = self.latcombo.get_active_text()
            JournalData['lonDDD'] = self.lonDDDtext.get_text()
            JournalData['lonMM'] = self.lonMMtext.get_text()
            JournalData['lonmm'] = self.lonmmtext.get_text()
            JournalData['lon'] = self.loncombo.get_active_text()
            JournalData['stationtext'] = self.stationtext.get_text()
            if (self.beaconbutton.get_active()):
                JournalData['beacon'] = 'True'
            else:
                JournalData['beacon'] = 'False'
            if (self.passbutton.get_active()):
                JournalData['hidepass'] = 'True'
            else:
                JournalData['hidepass'] = 'False'
            if (self.cqbutton.get_active()):
                JournalData['cq'] = 'True'
            else:
                JournalData['cq'] = 'False'

            callsignlist = []
            model = self.tocalllist
            iter = model.get_iter_first()
            while iter:
                callsignlist.append(model.get(iter, 0)[0])
                iter = model.iter_next(iter)

            JournalData['callsignlist'] = callsignlist
            if (self.help):
                JournalData['messages'] = "Message Window"
            else:
                JournalData['messages'] = self.messagebuffer.get_text(self.messagebuffer.get_start_iter(), self.messagebuffer.get_end_iter())
            data = json.write(JournalData)

            f = open(file_path, 'w')
            try:
                f.write(data)
            finally:
                f.close()

        except Exception, e:
            self.status_write("write_file(): %s\n" % e)

    def read_file(self, file_path):
        self.statusbuffer.set_text("Status Window\n\n")
        JournalData = {}
        callsignlist = []
        messages = "Message Window"
        callsign = ""
        password = ""
        latDD = "DD"
        latMM = "MM"
        latmm = "mm"
        lat = "N"
        lonDDD = "DDD"
        lonMM = "MM"
        lonmm = "mm"
        lon = "W"
        stationtext = ""
        beacon = "True"
        hidepass = "True"
        cq = "False"
        try:
            f = open(file_path, 'r')
            JournalData = json.read(f.read())
            if JournalData.has_key('callsignlist'):
                callsignlist = JournalData['callsignlist']
            if JournalData.has_key('messages'):
                messages = JournalData['messages']
            if JournalData.has_key('callsign'):
                callsign = JournalData['callsign']
            if JournalData.has_key('password'):
                password = JournalData['password']
            if JournalData.has_key('latDD'):
                latDD = JournalData['latDD']
            if JournalData.has_key('latMM'):
                latMM = JournalData['latMM']
            if JournalData.has_key('latmm'):
                latmm = JournalData['latmm']
            if JournalData.has_key('lat'):
                lat = JournalData['lat']
            if JournalData.has_key('lonDDD'):
                lonDDD = JournalData['lonDDD']
            if JournalData.has_key('lonMM'):
                lonMM = JournalData['lonMM']
            if JournalData.has_key('lonmm'):
                lonmm = JournalData['lonmm']
            if JournalData.has_key('lon'):
                lon = JournalData['lon']
            if JournalData.has_key('stationtext'):
                stationtext = JournalData['stationtext']
            if JournalData.has_key('beacon'):
                beacon = JournalData['beacon']
            if JournalData.has_key('hidepass'):
                hidepass = JournalData['hidepass']
            if JournalData.has_key('cq'):
                cq = JournalData['cq']
        except:
            pass
        finally:
            f.close()
#        self.messagebuffer.set_text(messages)
        self.bold_messages(messages)
        self.help = False
        if (messages == "Message Window"):
            self.messagebox = True
        else:
            self.messagebox = False
        for currentcall in callsignlist:
            self.add_callsign(currentcall, False)
        self.calltext.set_text(callsign)
        self.passtext.set_text(password)
        self.latDDtext.set_text(latDD)
        self.latMMtext.set_text(latMM)
        self.latmmtext.set_text(latmm)
        if (lat == "N"):
            self.latcombo.set_active(0)
        else:
            self.latcombo.set_active(1)
        self.lonDDDtext.set_text(lonDDD)
        self.lonMMtext.set_text(lonMM)
        self.lonmmtext.set_text(lonmm)
        if (lon == "W"):
            self.loncombo.set_active(0)
        else:
            self.loncombo.set_active(1)
        if (stationtext == ""):
            firstName = profile.get_nick_name().split(None, 1)[0].capitalize()
            self.stationtext.set_text("%s's XO at home." % firstName)
        else:
            self.stationtext.set_text(stationtext)
        if (beacon == "True"):
            self.beaconbutton.set_active(True)
        else:
            self.beaconbutton.set_active(False)
        if (hidepass == "True"):
            self.passbutton.set_active(True)
        else:
            self.passbutton.set_active(False)
        if (cq == "True"):
            self.cqbutton.set_active(True)
        else:
            self.cqbutton.set_active(False)

    def msg_check(self, data):
        mycall = self.calltext.get_text().upper()
        firstcheck = data.find("::")
        secondcheck = data[firstcheck+11:firstcheck+12]
        thirdcheck = data.find("{")
        if (firstcheck != -1 and secondcheck == ":"):
            tocall = data[firstcheck+2:firstcheck+11].upper()
            strippedtocall = tocall.strip()
            fromcall = data[:data.find(">")].upper()
            isbulletin = self.bulletin_check(strippedtocall)
            # 'mycall' check allows people with bulletin looking calls to ack messages
            # this check does not fix the problem of sending messages to bulletin looking calls
            if (isbulletin and strippedtocall != mycall):
                message = data[firstcheck+12:]
                self.add_callsign(fromcall, False)
                bln_id = "%s-%s" % (fromcall, strippedtocall)
                # show bulletin if have never seen it or has been at least 1 day since last viewing
                if (not bln_id in self.seen_bulletins or time.time() - self.seen_bulletins[bln_id] > 86400):
                    self.seen_bulletins[bln_id] = time.time()
                    self.message_write("%s %s:%s> %s\n" % (time.strftime("%m/%d %H:%M", time.localtime()), fromcall, strippedtocall, message), True)
            else:
                if (strippedtocall == mycall):
                    self.add_callsign(fromcall, False)
                    if (thirdcheck != -1):
                        sequence_end = data.find("}")
                        if (sequence_end == -1):
                            sequence = data[thirdcheck + 1:]
                        else:
                            sequence = data[thirdcheck + 1:sequence_end]
                            replyack = data[sequence_end + 1:]
                            if (len(replyack) > 1):
                                ackid = "%s-%s" % (fromcall, replyack)
                                if (ackid in self.recv_acks):
                                    if (self.recv_acks[ackid] == 0):

                                        count_start = self.messagebuffer.get_iter_at_mark(self.message_marks[ackid])
                                        count_end = count_start.forward_search(">", gtk.TEXT_SEARCH_TEXT_ONLY)
                                        self.messagebuffer.delete(count_start, count_end[0])

                                        line_end = self.messagebuffer.get_iter_at_mark(self.message_marks[ackid])
                                        queue_start = self.messagebuffer.get_iter_at_mark(self.message_marks[ackid])
                                        line_end.forward_to_line_end()
                                        queue_start.forward_to_line_end()
                                        queue_start.backward_chars(12)
                                        self.messagebuffer.delete(queue_start, line_end)

                                        line_end = self.messagebuffer.get_iter_at_mark(self.message_marks[ackid])
                                        line_end.forward_to_line_end()
                                        self.messagebuffer.insert(line_end, " <*ACKED*>")

                                        self.send_msg_queue(fromcall)
                                    self.recv_acks[ackid] = 1
                        message = data[firstcheck+12:thirdcheck]
                        ackmessage = ":%s:ack%s" % (fromcall.ljust(9), data[thirdcheck + 1:])
                        self.send_data(ackmessage)
                        id = "%s-%s" % (fromcall, sequence)
                        if (id in self.sent_acks):
                            self.timers.append(gobject.timeout_add(30 * 1000, self.send_ack, tocall, sequence))
                            self.timers.append(gobject.timeout_add(60 * 1000, self.send_ack, tocall, sequence))
                            self.timers.append(gobject.timeout_add(120 * 1000, self.send_ack, tocall, sequence))
                        else:
                            # TODO beep?
                            self.message_write("%s %s> %s\n" % (time.strftime("%m/%d %H:%M", time.localtime()), fromcall, message), True)
                        self.sent_acks[id] = time.time() # to help a cleanup thread later
                        self.sent_acks[fromcall] = sequence # to help with reply acks later
                    else:
                        message = data[firstcheck+12:]
                        if (message[0:3] == "ack"):
                            sequence_end = message.find("}")
                            if (sequence_end == -1):
                                sequence = message[3:]
                            else:
                                sequence = message[3:sequence_end]
                            ackid = "%s-%s" % (fromcall, sequence)
                            if (ackid in self.recv_acks):
                                if (self.recv_acks[ackid] == 0):

                                    count_start = self.messagebuffer.get_iter_at_mark(self.message_marks[ackid])
                                    count_end = count_start.forward_search(">", gtk.TEXT_SEARCH_TEXT_ONLY)
                                    self.messagebuffer.delete(count_start, count_end[0])

                                    line_end = self.messagebuffer.get_iter_at_mark(self.message_marks[ackid])
                                    queue_start = self.messagebuffer.get_iter_at_mark(self.message_marks[ackid])
                                    line_end.forward_to_line_end()
                                    queue_start.forward_to_line_end()
                                    queue_start.backward_chars(12)
                                    self.messagebuffer.delete(queue_start, line_end)

                                    line_end = self.messagebuffer.get_iter_at_mark(self.message_marks[ackid])
                                    line_end.forward_to_line_end()
                                    self.messagebuffer.insert(line_end, " <*ACKED*>")

                                    self.send_msg_queue(fromcall)
                            self.recv_acks[ackid] = 1
                        else:
                            # TODO beep?
                            self.message_write("%s %s> %s\n" % (time.strftime("%m/%d %H:%M", time.localtime()), fromcall, message), True)

                            # TODO query check
                            if (message[0] == "?" and message[-1] == "?"):
                                pass


    def disable_beacon(self, widget):
        if (self.sock != None):
            self.beaconbutton.set_active(False)

    def enable_beacon(self, widget):
        if (not self.validating and widget.get_active()):
            self.validate_data()

    def raw_send(self, widget):
        msg = "%s\n" % self.rawtext.get_text()
        try:
            self.sock.sendall(msg)
        except:
            self.status_write("Problem sending message\n")
            self.sock = None
            self.disconnect_aprs(self.connectbutton)
            return False
        self.status_write("%s\n" % msg)
        self.rawtext.set_text("")
        return True

    def send_message(self, widget=None, tocall=None, message=None, sequence=None, count=2, delay=7, start_timer=True):
        sendnow = False

        if (tocall == None and message == None):
            tocall = self.messagetocall.get_text().upper()
            message = self.messagetext.get_text()

        if (message == ""):
            return False

        isbulletin = self.bulletin_check(tocall)

        # check for illegal characters before clearing message
        if (isbulletin):
            if (message.find("|") != -1 or message.find("~") != -1):
                self.message_write("Bulletins can not contain the following characters: | ~")
                return False
        else:
            if (message.find("|") != -1 or message.find("~") != -1 or message.find("{") != -1):
                self.message_write("Messages can not contain the following characters: | ~ {")
                return False

        # add callsign to list if just entered
        if (self.last_selected != tocall):
            self.add_callsign(tocall, True)

        # get a sequence number
        if (sequence == None):
            sequence = "%s" % self.b90()

        # in case clear window is called:
        id = "%s-%s" % (tocall, sequence)
        self.recv_acks[id] = 0

        # TODO
        # cancel message option - menu popup

        # is there a queue for this callsign?
        if (tocall not in self.queue_list):
            sendnow = True

        # add the message to the queue
        if (not self.msg_queue(tocall, sequence, message)):
            if (self.sequence > 0):
                self.sequence -= 1
            return False

        # clear the message text box
        self.messagetext.set_text("")

        if (sendnow):
            self.send_msg_queue(tocall, count, delay, start_timer)

    def b90(self):
        if (self.sequence > 8099):
            self.sequence = 0
        first = ((self.sequence / 90) % 90) + 33
        second = (self.sequence % 90) + 33
        output = "%c%c" % (first, second)
        self.sequence += 1
        return output

    def msg_timer(self, tocall, message, sequence, count, delay):
        id = "%s-%s" % (tocall, sequence)
        if (self.recv_acks[id] == 1):
            return False
        else:

            isbulletin = self.bulletin_check(tocall)
            if (isbulletin):
                self.send_data(":%s:%s" % (tocall.ljust(9), message))
            else:
                replyack = self.replyack(tocall)
                self.send_data(":%s:%s{%s}%s" % (tocall.ljust(9), message, sequence, replyack))

            count_start = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
            count_end = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
            count_end.forward_chars(len(str(count - 1)) + 1)
            self.messagebuffer.delete(count_start, count_end)
            iter = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
            self.messagebuffer.insert(iter, " %i" % count)

            # start the next timer
            count += 1
            if (count > MAXRETRIES):
                self.recv_acks[id] = 1

                count_start = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
                count_end = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
                count_end.forward_chars(len(str(count - 1)) + len(str(MAXRETRIES)) + 2)
                self.messagebuffer.delete(count_start, count_end)

                line_end = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
                queue_start = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
                line_end.forward_to_line_end()
                queue_start.forward_to_line_end()
                queue_start.backward_chars(12)
                self.messagebuffer.delete(queue_start, line_end)

                line_end = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
                line_end.forward_to_line_end()
                self.messagebuffer.insert(line_end, " <-timeout->")

                self.send_msg_queue(tocall)
                return False
            delay *=  2
            if (delay > 600):
                delay = 600
            gobject.timeout_add(delay * 1000, self.msg_timer, tocall, message, sequence, count, delay)

            # save count and delay for the clear button
            self.current_message_count[tocall] = count
            self.current_message_delay[tocall] = delay

            # and stop this timer
            return False

    def add_callsign(self, callsign, activate):
        model = self.tocalllist
        notfound = True
        iter = model.get_iter_first()
        while iter:
            currentcall = model.get(iter, 0)[0]
            if (currentcall == callsign):
                notfound = False
                break
            iter = model.iter_next(iter)
        if (notfound):
            self.tocalllist.append([callsign])
            if (activate):
                 self.messagetocall.set_text(callsign)

    def bulletin_check(self, callsign):
        # hard code CQSRVR
        if (callsign == "CQSRVR"):
            return False
        for currentcall in self.bulletins:
            length = len(currentcall)
            if (currentcall == callsign[:length]):
                return True
        return False

    def replyack(self, tocall):
        replyack = ""
        if (tocall in self.sent_acks):
            id = "%s-%s" % (tocall, self.sent_acks[tocall])
            if (time.time() - self.sent_acks[id] < 5400):
                # less than 90 minutes ago
                replyack = self.sent_acks[tocall]
        return replyack

    def msg_queue(self, call, sequence, message):
        if (len(self.message_list) >= MAX_MSG_QUEUE):
            self.message_write("Too many messages in queue.\n")
            return False
        id = "%s-%s" % (call, sequence)
        if (call in self.queue_list):
            if (len(self.queue_list[call]) >= MAX_PER_CALL_QUEUE):
                self.message_write("Too many messages to %s in queue.\n" % call)
                return False
            self.queue_list[call].append(sequence)
            self.message_list[id] = message
        else:
            self.queue_list[call] = []
            self.queue_list[call].append(sequence)
            self.message_list[id] = message
        self.message_write("%s To:%s> %s <-queued->\n" % (time.strftime("%m/%d %H:%M", time.localtime()), call, message))
        # if a message is received before the next lines are run there will be problems...
        iter = self.messagebuffer.get_iter_at_line(self.messagebuffer.get_line_count() - 2)
        iter.forward_chars(15 + len(call))
        self.message_marks[id] = self.messagebuffer.create_mark(None, iter, True)
#        self.message_marks[id].set_visible(True)

        bold_end = iter.copy()
        bold_start = iter.copy()
        bold_end.forward_to_line_end()
        bold_end = bold_end.backward_search("<", gtk.TEXT_SEARCH_TEXT_ONLY)
        bold_start.forward_chars(2)
        self.messagebuffer.apply_tag(self.messagebold, bold_start, bold_end[0])

        return True

    def send_msg_queue(self, call, count=2, delay=7, start_timer=True):
        if (call in self.queue_list):
            if (self.queue_list[call] == []):
                del self.queue_list[call]
                return False

            sequence = self.queue_list[call].pop(0)
            id = "%s-%s" % (call, sequence)
            message = self.message_list[id]
            del self.message_list[id]

            # record this so cancel can work on current messages
            self.current_message[call] = sequence

            # record this so clear can re-add current messages
            self.current_message_text[call] = message

            # save count and delay for the clear button
            self.current_message_count[call] = count
            self.current_message_delay[call] = delay

            # send message
            isbulletin = self.bulletin_check(call)
            if (start_timer):
                if (isbulletin):
                    self.send_data(":%s:%s" % (call.ljust(9), message))
                    gobject.timeout_add(600 * 1000, self.msg_timer, call, message, sequence, count, 600)
                else:
                    replyack = self.replyack(call)
                    self.send_data(":%s:%s{%s}%s" % (call.ljust(9), message, sequence, replyack))
                    self.recv_acks["%s-%s" % (call, sequence)] = 0
                    gobject.timeout_add(delay * 1000, self.msg_timer, call, message, sequence, count, delay)

            # reset the timestamp
            line_start = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
            date_end = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
            length = line_start.get_line_offset()
            line_start.backward_chars(length)
            date_end.backward_chars(length)
            date_end.forward_chars(11)
            self.messagebuffer.delete(line_start, date_end)

            line_start = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
            length = line_start.get_line_offset()
            line_start.backward_chars(length)
            self.messagebuffer.insert(line_start, time.strftime("%m/%d %H:%M", time.localtime()))

            # clear "<-queued->"
            line_end = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
            queue_start = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
            line_end.forward_to_line_end()
            queue_start.forward_to_line_end()
            queue_start.backward_chars(11)
            self.messagebuffer.delete(queue_start, line_end)

            # add <-sending->
            line_end = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
            line_end.forward_to_line_end()
            self.messagebuffer.insert(line_end, " <-sending->")

            # add the counter
            iter = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
            self.messagebuffer.insert(iter, " %i/%s" % (count - 1, MAXRETRIES))

    def cancel_message(self, id):
        if (id in self.recv_acks and self.recv_acks[id] == 1):
            return

        self.recv_acks[id] = 1

        # remove status
        line_end = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
        line_end.forward_to_line_end()
        status_start = line_end.backward_search("<", gtk.TEXT_SEARCH_TEXT_ONLY)
        self.messagebuffer.delete(status_start[0], line_end)

        # add <-cancelled->
        line_end = self.messagebuffer.get_iter_at_mark(self.message_marks[id])
        line_end.forward_to_line_end()
        self.messagebuffer.insert(line_end, " <-cancelled->")

        # leave counter and timestamp alone

    def clear_msg_queue(self, button=None):
        if (self.queue_list != {}):
            for call in self.queue_list:
                for sequence in self.queue_list[call]:
                    id = "%s-%s" % (call, sequence)
                    del self.message_list[id]
                    self.cancel_message(id)
            self.queue_list = {}

        if (self.current_message != {}):
            for call in self.current_message:
                sequence = self.current_message[call]
                id = "%s-%s" % (call, sequence)
                self.cancel_message(id)
            self.current_message = {}

    def bold_messages(self, messages):
        self.messagebuffer.set_text("")
        for line in messages.splitlines():
            if (line[2:3] == "/" and line[5:6] == " " and line[8:9] == ":" and line[11:12] == " "):
                if (line[12:15] == "To:"):
                    self.message_write("%s\n" % line)
                    iter = self.messagebuffer.get_iter_at_line(self.messagebuffer.get_line_count() - 2)
                    bold_end = iter.copy()
                    bold_end.forward_to_line_end()
                    bold_start = bold_end.copy()
                    bold_start.backward_chars(len(line))
                    bold_start = bold_start.forward_search(">", gtk.TEXT_SEARCH_TEXT_ONLY)
                    bold_end = bold_end.backward_search("<", gtk.TEXT_SEARCH_TEXT_ONLY)
                    self.messagebuffer.apply_tag(self.messagebold, bold_start[1], bold_end[0])
                else:
                    self.message_write("%s\n" % line, True)
            else:
                self.message_write("%s\n" % line)

    def aprspass(self, callsign):
        # Note: The doHash(char*) function is Copyright Steve Dimse 1998
        # As of April 11 2000 Steve Dimse has released this code to the open source aprs community

        # remove SSID, trim callsign, convert to upper case
        cuthere = callsign.find("-")
        if (cuthere != -1):
            callsign = callsign[:cuthere]
        realcall = callsign[:10].upper()

        if (realcall == "NOCALL"):
            return "-1"

        # initialize hash
        hash = 0x73e2
        i = 0
        length = len(realcall)

        # hash callsign two bytes at a time
        while (i < length):
            hash ^= ord(realcall[i])<<8
            if (i+1 < length):
                hash ^= ord(realcall[i+1])
            i += 2

        # convert to string and mask off the high bit so number is always positive
        return str(hash & 0x7fff)

    def hide_password(self, widget):
        if (widget.get_active()):
            self.passtext.set_visibility(False)
        else:
            self.passtext.set_visibility(True)

    def open_url_button(self, widget, data):
        self._show_via_journal(data)

    # (mostly) from Chat.Activity
    def _show_via_journal(self, url):
        """Ask the journal to display a URL"""
        import os
        import time
        from sugar import profile
        from sugar.activity.activity import show_object_in_journal
        from sugar.datastore import datastore
        jobject = datastore.create()
        metadata = {
            'title': url,
            'title_set_by_user': '1',
            'icon-color': profile.get_color().to_string(),
            'activity': 'org.laptop.WebActivity',
            'mime_type': 'text/plain',
            }
        for k,v in metadata.items():
            jobject.metadata[k] = v
        file_path = os.path.join(self.get_activity_root(), 'instance',
                                 '%i_' % time.time())
        open(file_path, 'w').write('{"deleted":[],"shared_links":[],"history":[{"url":"' + url + '","title":"' + url + '"}]}')
        os.chmod(file_path, 0755)
        jobject.set_file_path(file_path)
        datastore.write(jobject)
        show_object_in_journal(jobject.object_id)
        jobject.destroy()
        os.unlink(file_path)

    def stop_cq(self):
        for source in self.cq_watch:
            try:
                gobject.source_remove(source)
            except:
                pass
        self.cq_watch = []
        if (self.cqbutton.get_active()):
            # send_message fails because disconnect happens too fast.
#            self.send_message(None, "CQSRVR", "U CQ")
            message = ":CQSRVR   :U CQ{%s" % self.b90()
            self.send_data(message)

    def enable_cq(self, widget):
        if (self.sock != None):
            if (self.cqbutton.get_active()):
                self.send_cq()
                self.cq_watch.append(gobject.timeout_add(32 * 60 * 1000, self.send_cq))
            else:
                self.stop_cq()
                self.send_message(None, "CQSRVR", "U CQ")

    def send_cq(self):
        if (self.sock == None):
            return False
        if (self.cqbutton.get_active()):
            self.send_message(None, "CQSRVR", "CQ CQ CQ From %s" % self.stationtext.get_text())

    def cancel_dialog(self, widget):
        # I want this to be a palette popup menu instead of a dialog

        canceldialog = gtk.Dialog("Cancel Messages", None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE))

        if (self.queue_list == {} and self.current_message == {}):
            label = gtk.Label("  No messages to cancel  ")
            canceldialog.vbox.pack_start(label, False, False, 0)
            label.show()

            separator = gtk.HSeparator()
            canceldialog.vbox.pack_start(separator, False, False, 6)
            separator.show()

        else:

            label = gtk.Label("  Click button to cancel message  ")
            canceldialog.vbox.pack_start(label, False, False, 0)
            label.show()

            separator = gtk.HSeparator()
            canceldialog.vbox.pack_start(separator, False, False, 6)
            separator.show()

            if (self.current_message != {}):
                label = gtk.Label("  Sending  ")
                canceldialog.vbox.pack_start(label, False, False, 0)
                label.show()

                for call in self.current_message:
                    sequence = self.current_message[call]
                    id = "%s-%s" % (call, sequence)
                    if (self.recv_acks[id] != 1):
                        button = gtk.Button()
                        button.set_label(str(call) + ", " + str(self.current_message_text[call]))
                        button.connect("clicked", self.cancel_cur_msg_button, call, sequence, id)
                        canceldialog.vbox.pack_start(button, False, False, 3)
                        button.show()

                separator = gtk.HSeparator()
                canceldialog.vbox.pack_start(separator, False, False, 6)
                separator.show()

            if (self.queue_list != {}):
                label = gtk.Label("  In queue  ")
                canceldialog.vbox.pack_start(label, False, False, 0)
                label.show()

                for call in self.queue_list:
                    for sequence in self.queue_list[call]:
                        id = "%s-%s" % (call, sequence)
                        button = gtk.Button()
                        button.set_label(str(call) + ", " + str(self.message_list[id]))
                        button.connect("clicked", self.cancel_queue_msg_button, call, sequence, id)
                        canceldialog.vbox.pack_start(button, False, False, 3)
                        button.show()

                separator = gtk.HSeparator()
                canceldialog.vbox.pack_start(separator, False, False, 6)
                separator.show()

            button = gtk.Button()
            button.set_label("Cancel All")
            button.connect("clicked", self.cancel_all_button)
            canceldialog.vbox.pack_start(button, False, False, 3)
            button.show()

        canceldialog.run()
        canceldialog.destroy()

    def cancel_all_button(self, widget):
        # button.vbox.dialog.destroy()
        widget.parent.parent.destroy()
        self.clear_msg_queue()

    def cancel_cur_msg_button(self, widget, call, sequence, id):
        # button.vbox.dialog.destroy()
        widget.parent.parent.destroy()
        if (sequence == self.current_message[call]):
            self.cancel_message(id)
            del self.current_message[call]
            self.send_msg_queue(call)

    def cancel_queue_msg_button(self, widget, call, sequence, id):
        # button.vbox.dialog.destroy()
        widget.parent.parent.destroy()
        if (sequence in self.queue_list[call]):
            self.cancel_message(id)
            del self.message_list[id]
            self.queue_list[call].remove(sequence)
            if (self.queue_list[call] == []):
                del self.queue_list[call]

    def tocall_selected(self, completion, model, iter):
        self.last_selected = model[iter][0]
