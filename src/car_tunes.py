import curses
import re
import sys,os
import time
import threading
from curses import wrapper
from os import listdir
from os.path import isfile, join
from time import sleep

working = True
x = 0
last_key = 0
updated = True
music_dir = "/home/user/python/environments/thing1/src/music"
loaded_artists = []
loaded_albums = []
loaded_tracks = []
artist_index = 0
album_index = 0
track_index = 0
left_status = "Paused"
right_status = "00:00 / 03:45"

def draw_menu(stdscr):
    global working
    global x
    global updated
    global last_key

    display_weight_artist = 1
    display_weight_album = 1
    display_weight_track = 2

    curses.curs_set(0)

    stdscr.clear()
    stdscr.refresh()

    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, 3, 5)

    while working:
        sleep(0.05)
        if not updated:
            continue

        updated = False
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        display_weight_total = display_weight_artist + display_weight_album + display_weight_track
        artist_x = 0
        album_x = int(round((width - 2) * (display_weight_album / display_weight_total)))
        track_x = int(round((width - 2) * ((display_weight_album + display_weight_album) / display_weight_total)))
        artist_w = album_x - 1
        album_w = track_x - (album_x + 1)
        track_w = width - track_x

        mid_y = int(height//2) - (1 if (height % 2) == 0 else 0)
        lines_above = mid_y - 3
        lines_below = height - (mid_y + 4)
        artist_list_index, artist_list = screenslice_items(loaded_artists, artist_index, lines_above, lines_below)
        album_list_index, album_list = screenslice_items(loaded_albums, album_index, lines_above, lines_below)
        track_list_index, track_list = screenslice_items(loaded_tracks, track_index, lines_above, lines_below)

        stdscr.attron(curses.color_pair(1))
        stdscr.attron(curses.A_DIM)

        hor_line = "─" * width
        for y in 1, mid_y - 1, mid_y + 1, height - 2:
            stdscr.addstr(y, 0, hor_line)

        for y in range(0, height - 1):
            char = "┼" if y in [1, mid_y - 1, mid_y + 1] else "┴" if y == (height - 2) else "│"
            for x in album_x - 1, track_x - 1:
                stdscr.addstr(y, x, char)

        stdscr.addstr(0, artist_x + int((artist_w - 6) / 2), "Artist")
        stdscr.addstr(0, album_x + int((album_w - 5) / 2), "Album")
        stdscr.addstr(0, track_x + int((track_w - 5) / 2), "Track")

        stdscr.addstr(height - 1, 1, left_status)
        stdscr.addstr(height - 1, width - (len(right_status) + 1), right_status)

        debug_message = "Testing!"
        stdscr.addstr(height - 1, (width - len(debug_message)) // 2, debug_message)

        stdscr.attroff(curses.color_pair(1))
        stdscr.attroff(curses.A_DIM)

        display_column(stdscr, artist_x, artist_w, mid_y, artist_list_index, artist_list)
        display_column(stdscr, album_x, album_w, mid_y, album_list_index, album_list)
        display_column(stdscr, track_x, track_w, mid_y, track_list_index, track_list)

        stdscr.refresh()

def display_column(stdscr, x, item_w, mid_y, list_index, item_list):
    top_y = mid_y - list_index

    for i in range(0, len(item_list)):
        y_add = 1 if i > list_index else -1 if i < list_index else 0
        x_add = 1 if i == list_index else 0
        if i == list_index:
            stdscr.attron(curses.A_BOLD)

        line = item_list[i]
        w = (item_w - 2) if i == list_index else item_w
        if len(line) > w:
            line = line[:w-3] + "..."

        stdscr.addstr(i + top_y + y_add, x + x_add, line)

        if i == list_index:
            stdscr.attroff(curses.A_BOLD)

def screenslice_items(items, index, lines_above, lines_below):
    if len(items) == 0:
        return 0, []

    sliced_items = []
    items_above = min(lines_above, index)
    if items_above > 0:
        for i in range(index - items_above, index):
            sliced_items.append(items[i])

    sliced_index = len(sliced_items)
    sliced_items.append(items[index])

    items_below = min(lines_below + 1, len(items) - index)
    if items_below > 0:
        for i in range(index + 1, index + items_below):
            sliced_items.append(items[i])

    return sliced_index, sliced_items

def input_worker(stdscr):
    global working
    global x
    global updated
    global last_key
    global artist_index
    global album_index
    global track_index

    while working:
        c = stdscr.getch()
        curses.flushinp()
        last_key = c

        if c == ord('q'):
            artist_index = (artist_index + (len(loaded_artists) - 1)) % len(loaded_artists)
            load_albums()
        elif c == ord('a'):
            artist_index = (artist_index + 1) % len(loaded_artists)
            load_albums()
        elif c == ord('w'):
            album_index = (album_index + (len(loaded_albums) - 1)) % len(loaded_albums)
            load_tracks()
        elif c == ord('s'):
            album_index = (album_index + 1) % len(loaded_albums)
            load_tracks()
        elif c == ord('e'):
            track_index = (track_index + (len(loaded_tracks) - 1)) % len(loaded_tracks)
        elif c == ord('d'):
            track_index = (track_index + 1) % len(loaded_tracks)
        elif c == ord('z'):
            working = False

        updated = True

def load_artists():
    global loaded_artists
    global artist_index
    artist_index = 0
    artist_dir = music_dir
    loaded_artists = sorted_nicely([f for f in listdir(artist_dir) if not isfile(join(artist_dir, f))])
    load_albums()

def load_albums():
    global loaded_albums
    global album_index
    album_index = 0
    album_dir = join(music_dir, loaded_artists[artist_index])
    loaded_albums = sorted_nicely([f for f in listdir(album_dir) if not isfile(join(album_dir, f))])
    load_tracks()

def load_tracks():
    global loaded_tracks
    global track_index
    global updated
    track_index = 0
    track_dir = join(music_dir, loaded_artists[artist_index], loaded_albums[album_index])
    loaded_tracks = sorted_nicely([f for f in listdir(track_dir) if isfile(join(track_dir, f))])

def sorted_nicely(l):
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ]
    return sorted(l, key = alphanum_key)

def main():
    stdscr = curses.initscr()
    stdscr.keypad(1)

    load_artists()

    t = threading.Thread(name ='daemon', target=input_worker, args=(stdscr,))
    t.setDaemon(True)
    t.start()

    curses.wrapper(draw_menu)

if __name__ == "__main__":
    main()