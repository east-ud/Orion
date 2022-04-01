#!/usr/bin/env python3
import sys
#import utils
import litescrn
import _thread
#import multiprocessing
# standard imports
import backend_orionv2
import logging
import time

#my imports
import _menu

log = logging.getLogger(__name__)
log.info("Hello logging!: orion_main is up")

# prepare screen
Screen = litescrn.screenit()  # launch screen module
_timeout = 1
Screen.my_window.timeout(_timeout) # TODO this shoudl go in config file
log.info('screen up')
#
# connection class created launched as a seperate, non-blocking, async thread
Conn = backend_orionv2.conn()


def raise_sys_exit():
    raise SystemExit

def interactive_mode():
    Screen.restorescreen()
    log.info('launched interactive mode')

    try:
        __import__('code').interact(banner="launched interactive--- press ctrl+d to exit", exitmsg="exiting interactive mode now", local=dict(globals(), **locals()))
        Screen.clear_it()
    except SystemExit:
        Screen.restorescreen()
        Screen.clear_it()
    except ValueError as e:
        log.debug(f'value error from interactive mode: {e}')


def str_to_class(classname):
    return getattr(sys.modules[__name__], classname)

def listen_for_keypress():
    global menu_option
    key = Screen.my_window.getch()

    if key != -1:
        log.debug(f'keypress was= {key}')

        if key == 113 or key == 81:
            # graceful exit sequence
            Screen.restorescreen()
            menu_option = 'exit'
        if key == 33:  # shift +1 (!)
            menu_option = 'experimental'
        if key == 99:  # letter c
            menu_option = 'connect_private'
        if key == 117:  # letter u
            menu_option = 'update'
        if key == 97 or key == 65:
            menu_option = 'display_all'
        if key == 120 or key == 88:
            menu_option = 'network_debug' # use to check connectivity issues
        if key == 102 or key == 77:
            menu_option = 'funding'
        if key == 48: # number 0
            menu_option = 'clean_screen'
        if key == 100 or key == 68:
            menu_option = 'debug'
        if key == 114 or key == 92:  # letter r
            menu_option = 'risk'

        if key == 41: # number shift + 0
            menu_option = 'clean_orders'

        if key == 49: # number 1
            menu_option = 'main_screen'
        if key == 50: # number 2
            menu_option = 'screen2'
        if key == 51: # number 3
            menu_option = 'balance_and_position'
        #if key == 119 or key == 87: # number 3
        #    menu_option = 'balance_and_position'

        log.debug(f'listen for keypress hears: {menu_option}')

def screen_loop():
    global menu_option
    global menu_last

    menu_option  = menu_last = 'main_screen'

    try:
        while True:
            # main loop here

            if menu_option == 'debug':
                interactive_mode()
                menu_option = 'main_screen'

            elif menu_option == 'exit':
                Screen.restorescreen()
                log.info(f'exited')
                break
            elif menu_option == 'connect_private':
                log.info('connecting private')
                Conn.start_private()
                Screen.clear_it()
                menu_option = 'main_screen'

            elif menu_option == 'balance_and_position':
                Screen.balance_and_position(Conn)
                Screen.positions(Conn)
                #log.debug('should be showing balance and position according to orionv2')

            elif menu_option == 'risk':
                Screen.risk_dets(Conn)

            elif menu_option == 'update':
                Conn.update_fills()
                Screen.clear_it()
                menu_option = 'main_screen'

            elif menu_option == 'clean_orders':
                Conn.clean()
                Screen.clear_it()
                menu_option = 'main_screen'

            elif menu_option == 'experimental':
                log.info('running experimental')
                Screen.testing_1(Conn)



            elif menu_option == 'main_screen':
                Screen.main_screen(Conn)

            if menu_last != menu_option:
                log.debug(f'menu_last: {menu_last} and new menu_option: {menu_option}')
                Screen.clear_it()
                menu_last = menu_option

            menu_last = menu_option

            listen_for_keypress()
            #log.debug(f'main sees menu_option as {menu_option}')

            Screen.keep_fresh()  # refreshes screen

    except Exception as e:
        Screen.restorescreen()  # fixes the screen incase of a break so it doesn't look messed
        log.error(e)

def main():
    try:
        log.info('running main/orion_main')
        # run start menu
        _menu.run_menu(Conn)
        _thread.start_new_thread(screen_loop, ())
        Conn.pre_start()
        Conn.start_public()
    except Exception as e:
        Screen.restorescreen()  # fixes the screen incase of a break so it doesn't look messed
        log.error("main error : ", e)



main()
