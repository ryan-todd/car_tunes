import io

def is_raspberrypi():
    try:
        with io.open('/sys/firmware/devicetree/base/model', 'r') as m:
            if 'raspberry pi' in m.read().lower():
                return True
    except Exception: pass
    return False

running_on_rpi = is_raspberrypi()

if not running_on_rpi:
    import sys
    import fake_rpi

    sys.modules['RPi'] = fake_rpi.RPi
    sys.modules['RPi.GPIO'] = fake_rpi.RPi.GPIO

import curses
import random
import re
import RPi.GPIO
import subprocess
import sys,os
import time
import threading
import vlc
from curses import wrapper
from enum import IntEnum
from os import listdir
from os.path import isfile, join
from threading import Timer
from time import sleep

working = False
screen_update = True
status_update = True
is_playing = True
music_dir = ""
state_file = ""
loaded_artists = []
loaded_albums = []
loaded_tracks = []
artist_index = 0
album_index = 0
track_index = 0
is_no_albums = False
is_no_tracks = False
vlc_instance = None
active_player = None
gpio_bouncetime_rocker = 250
gpio_bouncetime_push = 250
backlight_on = True

class GpioAction(IntEnum):
    NONE = 0
    ARTIST_UP = 33
    ARTIST_DOWN = 29
    ALBUM_UP = 36
    ALBUM_DOWN = 32
    TRACK_UP = 22
    TRACK_DOWN = 16
    PAUSE_PLAY = 11
    SHUFFLE = 13

input_timer = None
current_action = GpioAction.NONE
current_action_held = False
current_action_index = 0
input_action_timer_delay_initial = 0.4
input_action_timer_delay = 0.2

def draw_menu(stdscr):
    global working
    global screen_update
    global status_update

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

    tick = 0
    while working:
        tick = tick + 1
        sleep(0.02)

        if tick % 2 == 0:
            status_update = True

        if active_player is not None:
            if active_player.get_state() == 6:
                next_track(1, False, False)
                continue

        if screen_update or status_update:
            height, width = stdscr.getmaxyx()

        if screen_update:
            screen_update = False
            status_update = True
            stdscr.clear()

            display_weight_total = display_weight_artist + display_weight_album + display_weight_track
            artist_x = 1
            album_x = int(round((width - 4) * (display_weight_album / display_weight_total)))
            track_x = int(round((width - 4) * ((display_weight_album + display_weight_album) / display_weight_total)))
            artist_w = album_x - 2
            album_w = track_x - (album_x + 1)
            track_w = (width - 1) - track_x

            mid_y = int(height//2) - (1 if (height % 2) == 0 else 0)
            lines_above = mid_y - 3
            lines_below = height - (mid_y + 4)
            artist_list_index, artist_list = screenslice_items(loaded_artists, artist_index, lines_above, lines_below)
            album_list_index, album_list = screenslice_items(loaded_albums, album_index, lines_above, lines_below)
            track_list_index, track_list = screenslice_items(loaded_tracks, track_index, lines_above, lines_below)

            stdscr.attron(curses.color_pair(1))
            stdscr.attron(curses.A_DIM)

            y_intersections = [1, mid_y - 1, mid_y + 1, height - 2]
            hor_line = "─" * width
            for y in y_intersections:
                stdscr.addstr(y, 0, hor_line)

            for y in range(0, height - 1):
                char = "┴" if y == height - 2 else "┼" if y in y_intersections else "│"
                for x in album_x - 1, track_x - 1:
                    stdscr.addstr(y, x, char)

            stdscr.addstr(0, artist_x + int((artist_w - 6) / 2), "Artist")
            stdscr.addstr(0, album_x + int((album_w - 5) / 2), "Album")
            stdscr.addstr(0, track_x + int((track_w - 5) / 2), "Track")

            stdscr.attroff(curses.color_pair(1))
            stdscr.attroff(curses.A_DIM)

            display_column(stdscr, artist_x, artist_w, mid_y, artist_list_index, artist_list)
            display_column(stdscr, album_x, album_w, mid_y, album_list_index, album_list)
            display_column(stdscr, track_x, track_w, mid_y, track_list_index, track_list)

        if status_update:
            status_update = False
            stdscr.attron(curses.color_pair(1))
            stdscr.attron(curses.A_BOLD)

            if active_player is None:
                right_status = "00:00 / 00:00"
            else:
                t_mm, t_ss   = divmod(active_player.get_length() / 1000, 60)
                c_mm, c_ss   = divmod(active_player.get_time() / 1000, 60)
                remaining = active_player.get_state()
                right_status = ("%02d:%02d" % (c_mm, c_ss)) + (" / %02d:%02d" % (t_mm, t_ss))

            stdscr.addstr(height - 1, 1, grab_status_message())
            stdscr.addstr(height - 1, width - (len(right_status) + 1), right_status)

            stdscr.attroff(curses.color_pair(1))
            stdscr.attroff(curses.A_BOLD)

        stdscr.refresh()

def grab_status_message():
    if is_no_albums:
        return "No albums!"
    
    if is_no_tracks:
        return "No tracks!"
    
    if is_playing:
        return "Playing   "
    
    return "Paused    "

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

def next_track(direction, reverse_album, reverse_track):
    global track_index

    track_index = (track_index + (len(loaded_tracks) + direction)) % len(loaded_tracks)
    if track_index == (0 if direction == 1 else len(loaded_tracks) - 1):
        next_album(direction, reverse_album, reverse_track)
    else:
        load_track()

def next_album(direction, reverse_album, reverse_track):
    global album_index

    album_index = (album_index + (len(loaded_albums) + direction)) % len(loaded_albums)
    if album_index == (0 if direction == 1 else len(loaded_albums) - 1):
        next_artist(direction, reverse_album, reverse_track)
    else:
        load_tracks(reverse_track, False)

def next_artist(direction, reverse_album, reverse_track):
    global artist_index

    artist_index = (artist_index + (len(loaded_artists) + direction)) % len(loaded_artists)
    load_albums(reverse_album, reverse_track, False)

def do_input_action(action):
    if action == GpioAction.ARTIST_UP:
        next_artist(-1, False, False)
    elif action == GpioAction.ARTIST_DOWN:
        next_artist(1, False, False)
    elif action == GpioAction.ALBUM_UP:
        next_album(-1, True, False)
    elif action == GpioAction.ALBUM_DOWN:
        next_album(1, False, False)
    elif action == GpioAction.TRACK_UP:
        next_track(-1, True, True)
    elif action == GpioAction.TRACK_DOWN:
        next_track(1, False, False)
    elif action == GpioAction.PAUSE_PLAY:
        pause_track_toggle()

def input_timer_tick(action_index):
    global current_action
    global current_action_held
    global current_action_index
    global input_timer

    if current_action_index != action_index:
        return

    if not RPi.GPIO.input(int(current_action)):
        return

    current_action_held = True

    do_input_action(current_action)
    current_action_index = current_action_index + 1
    input_timer = Timer(input_action_timer_delay, input_timer_tick, [current_action_index])
    input_timer.start()

def handle_held_input_action(action):
    global current_action
    global current_action_held
    global current_action_index
    global input_timer
    
    current_action_index = current_action_index + 1

    if current_action_held:
        current_action = GpioAction.NONE
        current_action_held = False
        return

    current_action = action
    do_input_action(action)

    input_timer = Timer(input_action_timer_delay_initial, input_timer_tick, [current_action_index])
    input_timer.start()

def input_worker(stdscr):
    global working
    global artist_index
    global album_index
    global track_index

    while working:
        c = stdscr.getch()
        curses.flushinp()

        if c == ord('q'):
            next_artist(-1, False, False)
        elif c == ord('a'):
            next_artist(1, False, False)
        elif c == ord('w'):
            next_album(-1, True, False)
        elif c == ord('s'):
            next_album(1, False, False)
        elif c == ord('e'):
            next_track(-1, True, True)
        elif c == ord('d'):
            next_track(1, False, False)
        elif c == ord('z'):
            working = False
            RPi.GPIO.cleanup()
            backlight_on()
        elif c == ord('p'):
            pause_track_toggle()
        elif c == ord('l'):
            do_shuffle()

def do_shuffle():
    global artist_index

    new_index = 0 if len(loaded_artists) == 1 else random.randint(0, len(loaded_artists) - 2)
    artist_index = new_index if new_index < artist_index else new_index + 1

    load_albums(False, False, True)

def toggle_backlight():
    global backlight_on
    backlight_on = not backlight_on
    if backlight_on:
        subprocess.call("backlight_on.sh")
    else:
        subprocess.call("backlight_off.sh")

def load_artists():
    global loaded_artists
    global artist_index
    artist_index = 0
    artist_dir = music_dir
    loaded_artists = sorted_nicely([f for f in listdir(artist_dir) if not isfile(join(artist_dir, f)) and f != "System Volume Information"])
    load_albums(False, False, False)

def load_albums(reverse_album, reverse_track, is_shuffle):
    global loaded_albums
    global album_index
    global is_no_albums
    album_dir = join(music_dir, loaded_artists[artist_index])
    loaded_albums = sorted_nicely([f for f in listdir(album_dir) if not isfile(join(album_dir, f))])
    is_no_albums = len(loaded_albums) == 0
    if is_no_albums:
        loaded_albums = [" "]
    album_index = random.randint(0, len(loaded_albums) - 1) if is_shuffle else 0 if not reverse_album else len(loaded_albums) - 1
    load_tracks(reverse_track, is_shuffle)

def load_tracks(reverse_track, is_shuffle):
    global loaded_tracks
    global track_index
    global updated
    global is_no_tracks
    if not is_no_albums:
        track_dir = join(music_dir, loaded_artists[artist_index], loaded_albums[album_index])
        loaded_tracks = sorted_nicely([f for f in listdir(track_dir) if isfile(join(track_dir, f))])
    
    is_no_tracks = len(loaded_tracks) == 0
    if is_no_albums or is_no_tracks:
        loaded_tracks = [" "]

    track_index = random.randint(0, len(loaded_tracks) - 1) if is_shuffle else 0 if not reverse_track else len(loaded_tracks) - 1
    load_track()

def load_track():
    global vlc_instance
    global active_player
    global is_playing
    global screen_update
    if active_player is not None:
        active_player.stop()

    if not is_no_albums and not is_no_tracks:
        path = join(music_dir, loaded_artists[artist_index], loaded_albums[album_index], loaded_tracks[track_index])
        if running_on_rpi:
            active_player = vlc.MediaPlayer(vlc_instance, path)
            active_player.play()

    is_playing = True
    screen_update = True
    if working:
        save_state(True)

def load_state():
    global artist_index
    global album_index
    global track_index

    try:
        file = open(state_file, "r")
    except (FileNotFoundError):
        return

    lines = file.readlines()
    file.close()

    if not len(lines) == 3:
        return

    loaded_artist = lines[0][:-1] if len(lines[0]) > 0 else ""
    loaded_album = lines[1][:-1] if len(lines[1]) > 0 else ""
    loaded_track = lines[2][:-1] if len(lines[2]) > 0 else ""
    if loaded_artist in loaded_artists:
        artist_index = loaded_artists.index(loaded_artist)
        load_albums(False, False, False)
        if loaded_album in loaded_albums:
            album_index = loaded_albums.index(loaded_album)
            load_tracks(False, False)
            if loaded_track in loaded_tracks:
                track_index = loaded_tracks.index(loaded_track)
                load_track()

def save_state(ignore_errors):
    try:
        file = open(state_file, "w")
        file.write(loaded_artists[artist_index] + "\n")
        file.write(loaded_albums[album_index] + "\n")
        file.write(loaded_tracks[track_index] + "\n")
        file.close()
    except:
        print("Warning: Could not save state!")
        if not ignore_errors:
            raise

def pause_track_toggle():
    global is_playing
    global status_update

    is_playing = not is_playing
    status_update = True
    if active_player is None:
        return

    active_player.pause()

def sorted_nicely(l):
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ]
    return sorted(l, key = alphanum_key)

def main():
    global working
    global music_dir
    global state_file
    global vlc_instance
    global gpio_bouncetime
    if not len(sys.argv) == 3:
        print("Usage:")
        print("    car_tunes.py <music_path> <state_file> ")
        print("")
        print("'music_path':")
        print("    Path to directory that contains music in the format artists/albums/tracks")
        print("")
        print("'state_file':")
        print("    Path to file to store state between runs")
        return

    music_dir = sys.argv[1]
    state_file = sys.argv[2]

    RPi.GPIO.setwarnings(True)
    RPi.GPIO.setmode(RPi.GPIO.BOARD)

    RPi.GPIO.setup(int(GpioAction.PAUSE_PLAY), RPi.GPIO.IN, pull_up_down=RPi.GPIO.PUD_UP)
    for pin in GpioAction.ARTIST_UP, GpioAction.ARTIST_DOWN, GpioAction.ALBUM_UP, GpioAction.ALBUM_DOWN, GpioAction.TRACK_UP, GpioAction.TRACK_DOWN, GpioAction.SHUFFLE:
        RPi.GPIO.setup(int(pin), RPi.GPIO.IN, pull_up_down=RPi.GPIO.PUD_DOWN)

    RPi.GPIO.add_event_detect(int(GpioAction.PAUSE_PLAY), RPi.GPIO.FALLING, callback=lambda c: do_input_action(GpioAction.PAUSE_PLAY), bouncetime = gpio_bouncetime_push)

    RPi.GPIO.add_event_detect(int(GpioAction.ARTIST_UP), RPi.GPIO.BOTH, callback=lambda c: handle_held_input_action(GpioAction.ARTIST_UP), bouncetime = gpio_bouncetime_rocker)
    RPi.GPIO.add_event_detect(int(GpioAction.ARTIST_DOWN), RPi.GPIO.BOTH, callback=lambda c: handle_held_input_action(GpioAction.ARTIST_DOWN), bouncetime = gpio_bouncetime_rocker)
    RPi.GPIO.add_event_detect(int(GpioAction.ALBUM_UP), RPi.GPIO.BOTH, callback=lambda c: handle_held_input_action(GpioAction.ALBUM_UP), bouncetime = gpio_bouncetime_rocker)
    RPi.GPIO.add_event_detect(int(GpioAction.ALBUM_DOWN), RPi.GPIO.BOTH, callback=lambda c: handle_held_input_action(GpioAction.ALBUM_DOWN), bouncetime = gpio_bouncetime_rocker)
    RPi.GPIO.add_event_detect(int(GpioAction.TRACK_UP), RPi.GPIO.BOTH, callback=lambda c: handle_held_input_action(GpioAction.TRACK_UP), bouncetime = gpio_bouncetime_rocker)
    RPi.GPIO.add_event_detect(int(GpioAction.TRACK_DOWN), RPi.GPIO.BOTH, callback=lambda c: handle_held_input_action(GpioAction.TRACK_DOWN), bouncetime = gpio_bouncetime_rocker)
    RPi.GPIO.add_event_detect(int(GpioAction.SHUFFLE), RPi.GPIO.BOTH, callback=lambda c: do_shuffle(), bouncetime = gpio_bouncetime_push)

    stdscr = curses.initscr()
    stdscr.keypad(1)

    vlc_instance = vlc.Instance("--quiet")

    load_artists()
    load_state()
    save_state(False)

    working = True
    if not running_on_rpi:
        t = threading.Thread(name ='daemon', target=input_worker, args=(stdscr,))
        t.setDaemon(True)
        t.start()

    curses.wrapper(draw_menu)

if __name__ == "__main__":
    main()
