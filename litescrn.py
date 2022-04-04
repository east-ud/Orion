# Object for displaying prices on screen
from datetime import datetime, timedelta
from utils import human_time, calc_days_rem, checkfloat

#import time
#import random
import curses
import logging
#import utils
#from scipy.interpolate import interp1d
from select import select
from utils import eztimer

log = logging.getLogger(__name__)
log.info("Hello logging! screen obj is up")


screen_timer = eztimer(ignore_restarts=True)

class screenit(object):
    # object for printing stuff to screen
    def __init__(self):
        self.screen = curses.initscr()
        curses.cbreak()
        curses.noecho()
        #self.screen.keypad(1)
        self.max_y, self.max_x = self.screen.getmaxyx()  # get screen dimensions

        curses.start_color()
        curses.curs_set(0)
        self.my_window = curses.newwin(500, 500, 0, 0)
        # set up colour pairs
        curses.init_pair(1, 15, 0)
        curses.init_pair(2, 1, 0) # red?
        curses.init_pair(3, 3, 0)
        curses.init_pair(4, 4, 0) # blue
        curses.init_pair(5, 5, 0) # purple
        curses.init_pair(6, 6, 0) # light blue
        curses.init_pair(7, 7, 0) # white
        curses.init_pair(8, 8, 0) # grey
        curses.init_pair(9, 9, 0) # tan/red
        curses.init_pair(10, 10, 0) # neon green

        # preset instr colours
        self.swap_col = 6
        self.fwd1_col = 7
        self.fwd2_col = 8
        self.fwd3_col = 9

        self.count = 0
        self.prevl_posts = ''



    def keep_fresh(self):
        # in use
        self.my_window.refresh()

    def get_keypress(self):
        key = self.my_window.getch()
        return str(key)
        #self.my_window.addstr(0, 50, str(key))

    def restorescreen(self):
        self.screen.keypad(0)
        # restore "normal"--i.e. wait until hit Enter--keyboard mode
        curses.nocbreak()
        # restore keystroke echoing
        curses.echo()
        # required cleanup call
        curses.endwin()

    def clear_it(self):
        try:
            self.my_window.erase()
            self.my_window.addstr(0, 0, '')
            self.my_window.refresh()
        except Exception as e:
            log.info(f'clearing error: {e}')

    def debug(self, line):
        _x = self.max_x - 50
        self.my_window.addstr(3, _x, 'DEBUG: ', curses.color_pair(1) | curses.A_BOLD)
        self.my_window.addstr(3, _x + 10, line, curses.color_pair(1) | curses.A_BOLD)

    def show_notification(self, conn_obj):
        _x = self.max_x - 50
        self.my_window.addstr(2, _x, 'Notifications: ', curses.color_pair(1))
        self.my_window.addstr(2, _x + 18, f'{conn_obj.notification}    ', curses.color_pair(4) | curses.A_BOLD)
        self.my_window.addstr(4, _x, f'Roundtrip trades count= {conn_obj.all_count}  fills: {conn_obj.fill_count}   ', curses.color_pair(1))

        self.my_window.addstr(5, _x, 'LastPx: ', curses.color_pair(1))
        self.my_window.addstr(5, _x + 18, f'{conn_obj.all_lastLongPx} / {conn_obj.all_lastShortPx}          ', curses.color_pair(4) | curses.A_BOLD)


        # NOP
        self.my_window.addstr(7, _x, 'MrktMkng NOP: ', curses.color_pair(1))
        self.my_window.addstr(7, _x + 18, f'{conn_obj.all_longNOP} / {conn_obj.all_shortNOP}; Net:                   ', curses.color_pair(4) | curses.A_BOLD)
        if conn_obj.all_NOP != 0:
            self.my_window.addstr(7, _x + 40, f'{conn_obj.all_NOP}             ', curses.color_pair(2) | curses.A_BOLD)
        else:
            self.my_window.addstr(7, _x + 33, 'SQR             ', curses.color_pair(4) | curses.A_BOLD)

        self.my_window.addstr(8, _x, 'AvgPx: ', curses.color_pair(1) | curses.A_BOLD)
        self.my_window.addstr(8, _x + 18, f'{conn_obj.all_avgLongPx} / {conn_obj.all_avgShortPx}            ', curses.color_pair(4) | curses.A_BOLD)

        self.my_window.addstr(9, _x, 'Crnt PNL (coins):    ', curses.color_pair(1) | curses.A_BOLD)
        self.my_window.addstr(10, _x + 30, 'Fwds:    ', curses.color_pair(1) | curses.A_BOLD)
        self.my_window.addstr(9, _x + 18, f'{conn_obj.all_unbPNL}   ', curses.color_pair(5) | curses.A_BOLD)
        self.my_window.addstr(10, _x + 38, f'{conn_obj.fwds_PNL:,.5f}', curses.color_pair(5) | curses.A_BOLD)



        # Mean Reversion
        self.my_window.addstr(11, _x, 'MeanRev NOP: ', curses.color_pair(1))
        self.my_window.addstr(11, _x + 18, f'{conn_obj.MR_longNOP} / {conn_obj.MR_shortNOP}; Net:                  ', curses.color_pair(4) | curses.A_BOLD)
        if conn_obj.MR_NOP != 0:
            self.my_window.addstr(11, _x + 40, f'{conn_obj.MR_NOP}             ', curses.color_pair(2) | curses.A_BOLD)
        else:
            self.my_window.addstr(11, _x + 33, 'SQR             ', curses.color_pair(4) | curses.A_BOLD)


        self.my_window.addstr(12, _x, 'MR AvgPx: ', curses.color_pair(1) | curses.A_BOLD)
        self.my_window.addstr(12, _x + 18, f'{conn_obj.MR_bid_BE_dist} {conn_obj.MR_avgLongPx} / {conn_obj.MR_avgShortPx} {conn_obj.MR_off_BE_dist}  ', curses.color_pair(4) | curses.A_BOLD)

        self.my_window.addstr(13, _x, 'MR PNL (coins):    ', curses.color_pair(1) | curses.A_BOLD)
        self.my_window.addstr(13, _x + 18, f'{conn_obj.MR_unbPNL} ', curses.color_pair(5) | curses.A_BOLD)



        self.my_window.addstr(14, _x, f'Cumul PNL: {conn_obj.all_cumPNL:,.5f}  prev cumul PNL: {conn_obj.prev_cumPNL:,.5f}      ', curses.color_pair(5) | curses.A_BOLD)

        self.my_window.addstr(17, _x, 'Hedge priority:   ', curses.color_pair(1))
        self.my_window.addstr(17, _x + 18, f'{conn_obj.regen_timer.hedge_priority}      ', curses.color_pair(4) | curses.A_BOLD)
        # self.my_window.addstr(17, _x + 28, f'{conn_obj.regen_timer.pre_hedged}      ', curses.color_pair(4) | curses.A_BOLD)
        self.my_window.addstr(18, _x, 'Regen Percentage: ', curses.color_pair(1))
        self.my_window.addstr(18, _x + 18, f'{100*conn_obj.regen_timer.percentage():,.1f}%    ', curses.color_pair(4) | curses.A_BOLD)

        self.my_window.addstr(20, _x, f'Safety Shutdown: {conn_obj.safety_shutdown}', curses.color_pair(1) | curses.A_BOLD)



    # Sets title on top ledft hand side of mains screen
    def ltitle(self, line1, line2):
        self.my_window.addstr(0, 11, line1, curses.color_pair(1) | curses.A_BOLD)
        self.my_window.addstr(0, 31, line2)

    def latency_data(self, conn):
        start_y = 21

        timers = [conn.main_timer, conn.get_data_timer, conn.get_pm_timer,
                conn.stack_update_timer, conn.overwatch_timer, conn.update_risk_timer, conn.latencyT_swap,
                conn.latencyT_f1, conn.latencyT_f2, conn.latencyT_f3, conn.latencyT_idx, conn.vwap_timer, conn.req_timer,
                conn.update_tickets_timer, conn.check_if_update_req_timer, conn.calc_targets_timer, conn.trade_timer]
        _x = self.max_x - 55
        _x_far = self.max_x - 8

        self.my_window.addstr(start_y, _x, "Code performance/latency data  ", curses.color_pair(5))

        count = start_y + 1

        for timer in timers:
            self.my_window.addstr(count, _x, f"{timer.name} c={timer.counts} t={timer.elapsed} min={timer.min} max={timer.max}  ", curses.color_pair(3))
            self.my_window.addstr(count, _x_far, f"u={timer.mean}  ", curses.color_pair(4))
            count += 1

    def risk(self, conn_obj):
        # Shows breakdown of ccy, eqUsdd, swaps, futrures and DV01
        # on main page
        try:
            xloc = 0
            step_x = 25
            margin = 15
            start_y = yloc = 23

            _show = ['ADA']

            if not conn_obj.risk:
                return

            for ccy in _show:
                ccy_data = conn_obj.risk[ccy]
                _futs_net = float(ccy_data['FUTS']['net'])
                _swaps_net = float(ccy_data['SWAPS']['net'])
                eqUsd = float(ccy_data['eqUsd'])

                self.my_window.addstr(yloc, xloc, (f'{ccy} '), curses.color_pair(9) | curses.A_BOLD)
                yloc += 1
                self.my_window.addstr(yloc, xloc, ("upl: "), curses.color_pair(9))
                self.my_window.addstr(yloc, xloc + margin, (f"{float(ccy_data['upl']):>7,.0f}   "), curses.color_pair(9))
                yloc += 1
                self.my_window.addstr(yloc, xloc, ("eqUsd: "), curses.color_pair(9))
                self.my_window.addstr(yloc, xloc + margin, (f"{eqUsd:>7,.0f}   "), curses.color_pair(9))
                yloc += 1
                self.my_window.addstr(yloc, xloc, ("Swaps NOP: "), curses.color_pair(9))
                self.my_window.addstr(yloc, xloc + margin, (f"{_swaps_net:>7,.0f} "), curses.color_pair(9))
                yloc += 1
                self.my_window.addstr(yloc, xloc, ("Futs NOP: "), curses.color_pair(9))
                self.my_window.addstr(yloc, xloc + margin, (f"{_futs_net:>7,.0f} "), curses.color_pair(9))
                yloc += 1
                self.my_window.addstr(yloc, xloc, ("Net NOP: "), curses.color_pair(9) | curses.A_BOLD)
                self.my_window.addstr(yloc, xloc + margin, (f"{_futs_net + _swaps_net + eqUsd:>7,.0f}   "), curses.color_pair(9) | curses.A_BOLD)
                yloc += 1
                for _prod in ['SWAPS', 'FUTS']:
                    self.my_window.addstr(yloc, xloc, (f"{_prod}                            "), curses.color_pair(9) | curses.A_BOLD)
                    #self.my_window.addstr(yloc, xloc + margin, (f"{_swaps_net:>,.0f}   "), curses.color_pair(9) | curses.A_BOLD)
                    yloc += 1

                    for _side in ['long', 'short']:
                        for k, v in ccy_data[_prod][_side].items():
                            self.my_window.addstr(yloc, xloc, (f"{k}: "), curses.color_pair(self.swap_col))
                            self.my_window.addstr(yloc, xloc + margin, (f"{float(v['sz']):>7,.0f}  "), curses.color_pair(self.swap_col))
                            self.my_window.addstr(yloc, xloc + int(1.7 * margin), (f"{float(v['upl']):>8,.1f}  "), curses.color_pair(self.swap_col +1))
                            yloc += 1

                xloc += step_x
                yloc = start_y

        except Exception as e:
            log.error(f'Screen> risk : {e}', exc_info= True)


    def show_stack(self, conn):
        # use to print to screen streaming data, line by line
        try:
            if conn.data_flow:

                self.my_window.addstr(0, 0, f"{conn.swap}    ", curses.color_pair(5))
                self.my_window.addstr(1, 0, f"min: [{conn.msprd_swap:,.1f}bps] VWAP: [{conn.sprd_swap:,.1f}bps]   ", curses.color_pair(5))
                self.my_window.addstr(2, 0, f"{conn.live_swap_bspread[0]}       ", curses.color_pair(5))
                self.my_window.addstr(2, 10, f"{conn.live_swap_bspread[1]}/       ", curses.color_pair(2))
                self.my_window.addstr(2, 20, f"{conn.live_swap_ospread[0]}        ", curses.color_pair(5))
                self.my_window.addstr(2, 30, f"/{conn.live_swap_ospread[1]}      ", curses.color_pair(2))

                self.my_window.addstr(0, 40, f"{conn.fwd1} {conn.days_rem_fwd1} days    ", curses.color_pair(6))
                self.my_window.addstr(1, 40, f"min: [{conn.msprd_fwd1:,.1f}bps] VWAP: [{conn.sprd_fwd1:,.1f}bps]     ", curses.color_pair(6))
                self.my_window.addstr(2, 40, f"{conn.live_fwd1_bspread[0]}       ", curses.color_pair(5))
                self.my_window.addstr(2, 50, f"{conn.live_fwd1_bspread[1]}/        ", curses.color_pair(2))
                self.my_window.addstr(2, 60, f"{conn.live_fwd1_ospread[0]}        ", curses.color_pair(5))
                self.my_window.addstr(2, 70, f"/{conn.live_fwd1_ospread[1]}       ", curses.color_pair(2))

                self.my_window.addstr(0, 80, f"{conn.fwd2} {conn.days_rem_fwd2} days   ", curses.color_pair(7))
                self.my_window.addstr(1, 80, f"min: [{conn.msprd_fwd2:,.1f}bps] VWAP: [{conn.sprd_fwd2:,.1f}bps]  ", curses.color_pair(7))
                self.my_window.addstr(2, 80, f"{conn.live_fwd2_bspread[0]}       ", curses.color_pair(5))
                self.my_window.addstr(2, 90, f"{conn.live_fwd2_bspread[1]}/      ", curses.color_pair(2))
                self.my_window.addstr(2, 100, f"{conn.live_fwd2_ospread[0]}      ", curses.color_pair(5))
                self.my_window.addstr(2, 110, f"/{conn.live_fwd2_ospread[1]}     ", curses.color_pair(2))


                self.my_window.addstr(0, 120, f"{conn.fwd3} {conn.days_rem_fwd3} days   ", curses.color_pair(7))
                self.my_window.addstr(1, 120, f"min: [{conn.msprd_fwd3:,.1f}bps] VWAP: [{conn.sprd_fwd3:,.1f}bps]  ", curses.color_pair(7))
                self.my_window.addstr(2, 120, f"{conn.live_fwd3_bspread[0]}       ", curses.color_pair(5))
                self.my_window.addstr(2, 130, f"{conn.live_fwd3_bspread[1]}/      ", curses.color_pair(2))
                self.my_window.addstr(2, 140, f"{conn.live_fwd3_ospread[0]}      ", curses.color_pair(5))
                self.my_window.addstr(2, 150, f"/{conn.live_fwd3_ospread[1]}     ", curses.color_pair(2))

                _y = 3 # starting line for stack display
                # Indicate when we are the best bid/offer

                swap_bidcol = swap_offercol = self.swap_col
                if conn.live_swap_dist_bbid <= 0:
                    swap_bidcol = 2

                if conn.live_swap_dist_boffer <= 0:
                    swap_offercol = 2

                fwd1_bidcol = fwd1_offercol = self.fwd1_col
                if conn.live_fwd1_dist_bbid <= 0:
                    fwd1_bidcol = 2

                if conn.live_fwd1_dist_boffer <= 0:
                    fwd1_offercol = 2

                fwd2_bidcol = fwd2_offercol = self.fwd2_col
                if conn.live_fwd2_dist_bbid <= 0:
                    fwd2_bidcol = 2

                if conn.live_fwd2_dist_boffer <= 0:
                    fwd2_offercol = 2

                fwd3_bidcol = fwd3_offercol = self.fwd3_col
                if conn.live_fwd3_dist_bbid <= 0:
                    fwd3_bidcol = 2

                if conn.live_fwd3_dist_boffer <= 0:
                    fwd3_offercol = 2

                for i in enumerate(conn.stack_swap['bids']):
                    self.my_window.addstr(_y + i[0], 0, f"{float(i[1][0]):#,.6g} {i[1][1].rjust(10)}    ", curses.color_pair(swap_bidcol))
                    if i[0] == 10:
                        break

                for i in enumerate(conn.stack_swap['offers']):
                    self.my_window.addstr(_y + i[0], 20, f"{float(i[1][0]):#,.6g} {i[1][1].rjust(10)}    ", curses.color_pair(swap_offercol))
                    if i[0] == 10:
                        break


                for i in enumerate(conn.stack_fwd1['bids']):
                    self.my_window.addstr(_y + i[0], 40, f"{float(i[1][0]):#,.6g} {i[1][1].rjust(10)} ", curses.color_pair(fwd1_bidcol))
                    if i[0] == 10:
                        break

                for i in enumerate(conn.stack_fwd1['offers']):
                    self.my_window.addstr(_y + i[0], 60, f"{float(i[1][0]):#,.6g} {i[1][1].rjust(10)} ", curses.color_pair(fwd1_offercol))
                    if i[0] == 10:
                        break

                for i in enumerate(conn.stack_fwd2['bids']):
                    self.my_window.addstr(_y + i[0], 80, f"{float(i[1][0]):#,.6g} {i[1][1].rjust(10)}    ", curses.color_pair(fwd2_bidcol))
                    if i[0] == 10:
                        break

                for i in enumerate(conn.stack_fwd2['offers']):
                    self.my_window.addstr(_y + i[0], 100, f"{float(i[1][0]):#,.6g} {i[1][1].rjust(10)}  ", curses.color_pair(fwd2_offercol))
                    if i[0] == 10:
                        break

                for i in enumerate(conn.stack_fwd3['bids']):
                    self.my_window.addstr(_y + i[0], 120, f"{float(i[1][0]):#,.6g} {i[1][1].rjust(10)}    ", curses.color_pair(fwd3_bidcol))
                    if i[0] == 10:
                        break

                for i in enumerate(conn.stack_fwd3['offers']):
                    self.my_window.addstr(_y + i[0], 140, f"{float(i[1][0]):#,.6g} {i[1][1].rjust(10)}  ", curses.color_pair(fwd3_offercol))
                    if i[0] == 10:
                        break



                self.my_window.addstr(14, 0, f"index = {conn.idxPx:#,.6g} VWAP_mid = {conn.vwap_swap['mid']} ", curses.color_pair(4))
                self.my_window.addstr(15, 0, f"PerpVsIndex (VWAP mids)  =  {conn.SwapVsIndex_mid:,.2g}    ", curses.color_pair(7))
                self.my_window.addstr(16, 0, f"PerpVsIndex  = {conn.SwapVsIndex_bid:,.2g}/{conn.SwapVsIndex_offer:,.2g}     ", curses.color_pair(7))

                self.my_window.addstr(18, 0, f"Min {conn.swapVsSwap_mbid:,.1f}/{conn.swapVsSwap_moffer:,.1f} [{conn.sprd_swapVsSwap_min}bps] ", curses.color_pair(4))
                self.my_window.addstr(18, 30, f"{(conn.swapVsSwap_mbid + conn.swapVsSwap_moffer)/2:,.1f} ", curses.color_pair(4) | curses.A_BOLD)  # mid min

                if conn.orion_orders:
                    _bid = conn.orion_orders[0]['swapT_bid']
                    _offer = conn.orion_orders[0]['swapT_offer']

                    if _offer and _bid:
                        _sprd = _offer - _bid
                        bp_sprd = 10000 * _sprd / ((_offer + _bid) / 2)
                        self.my_window.addstr(19, 0, f"Target: {_bid:,.5f}/{_offer:,.5f} [{bp_sprd:,.1f}]      ", curses.color_pair(5))

                self.my_window.addstr(20, 0, f"Live to best {conn.live_swap_dist_bbid:,.1f}/{conn.live_swap_dist_boffer:,.1f}       ", curses.color_pair(5))
                self.my_window.addstr(21, 0, f"Trgt to best {conn.swap_dist_bbid:,.1f}/{conn.swap_dist_boffer:,.1f}       ", curses.color_pair(5))

                # FWD 1
                self.my_window.addstr(15, 40, f"F1VsIdx (VWAP) = {conn.fwd1VsIndex_mid:,.2g}    ", curses.color_pair(7))
                self.my_window.addstr(16, 40, "F1VsSwap ", curses.color_pair(4))
                self.my_window.addstr(17, 40, f"VWAP mid {conn.fwd1VsSwap_bid:,.1f}/{conn.fwd1VsSwap_offer:,.1f} [{conn.sprd_fwd1VsSwap}bps] ", curses.color_pair(4))
                self.my_window.addstr(17, 70, f"{conn.fwd1VsSwap_mid:,.1f} ", curses.color_pair(4) | curses.A_BOLD)   # mid price

                self.my_window.addstr(18, 40, f"Min {conn.fwd1VsSwap_mbid:,.1f}/{conn.fwd1VsSwap_moffer:,.1f} [{conn.sprd_fwd1VsSwap_min}bps] ", curses.color_pair(4))
                self.my_window.addstr(18, 70, f"{(conn.fwd1VsSwap_mbid+conn.fwd1VsSwap_moffer)/2:,.1f} ", curses.color_pair(4) | curses.A_BOLD)  # mid min

                self.my_window.addstr(20, 40, f"Live to best {conn.live_fwd1_dist_bbid:,.1f}/{conn.live_fwd1_dist_boffer:,.1f}       ", curses.color_pair(5))
                self.my_window.addstr(21, 40, f"Trgt to best {conn.fwd1_dist_bbid:,.1f}/{conn.fwd1_dist_boffer:,.1f}       ", curses.color_pair(6))

                if conn.orion_orders:
                    _bid = conn.orion_orders[0]['fwd1T_bid']
                    _offer = conn.orion_orders[0]['fwd1T_offer']
                    _sprd = _offer - _bid
                    bp_sprd = 10000 * _sprd / ((_offer + _bid) / 2)
                    self.my_window.addstr(19, 40, f"Target: {_bid:,.5f}/{_offer:,.5f} bp_sprd:[{bp_sprd:,.1f}]      ", curses.color_pair(6))

                # Fwd 2
                self.my_window.addstr(15, 80, f"Fwd2VsIndex (VWAP mids)  = {conn.fwd2VsIndex_mid:,.2g}     ", curses.color_pair(7))
                self.my_window.addstr(17, 80, f"VWAP mid {conn.fwd2VsSwap_bid:,.1f}/{conn.fwd2VsSwap_offer:,.1f} [{conn.sprd_fwd2VsSwap}bps] ", curses.color_pair(4))
                self.my_window.addstr(17, 110, f"{conn.fwd2VsSwap_mid:,.1f} ", curses.color_pair(4) | curses.A_BOLD)   # mid price


                self.my_window.addstr(18, 80, f"Min {conn.fwd2VsSwap_mbid:,.1f}/{conn.fwd2VsSwap_moffer:,.1f} [{conn.sprd_fwd2VsSwap_min}bps] ", curses.color_pair(4))
                self.my_window.addstr(18, 110, f"{(conn.fwd2VsSwap_mbid + conn.fwd2VsSwap_moffer)/2:,.1f} ", curses.color_pair(4) | curses.A_BOLD)  # mid min

                #self.my_window.addstr(19, 80, f"Fwd2VsFwd1 (VWAP mids)  = {conn.fwd2Vsfwd1_mid:,.1f}    ", curses.color_pair(4))
                #self.my_window.addstr(20, 80, f"Fwd2VsFwd1  = {conn.fwd2Vsfwd1_bid:,.1f}/{conn.fwd2Vsfwd1_offer:,.1f} [{conn.sprd_fwd2Vsfwd1}bps]    ", curses.color_pair(4))
                self.my_window.addstr(20, 80, f"Live to best {conn.live_fwd2_dist_bbid:,.1f}/{conn.live_fwd2_dist_boffer:,.1f}       ", curses.color_pair(5))
                self.my_window.addstr(21, 80, f"Trgt to best {conn.fwd2_dist_bbid:,.1f}/{conn.fwd2_dist_boffer:,.1f}       ", curses.color_pair(6))

                # swap2
                if conn.orion_orders:
                    _bid = conn.orion_orders[0]['fwd2T_bid']
                    _offer = conn.orion_orders[0]['fwd2T_offer']
                    _sprd = _offer - _bid
                    bp_sprd = 10000 * _sprd / ((_offer + _bid) / 2)
                    self.my_window.addstr(19, 80, f"Target: {_bid:,.5f}/{_offer:,.5f} [{bp_sprd:,.1f}]      ", curses.color_pair(6))

                self.my_window.addstr(15, 120, f"Fwd3VsIndex (VWAP mids)  = {conn.fwd3VsIndex_mid:,.2g}     ", curses.color_pair(7))
                self.my_window.addstr(17, 120, f"VWAP mid {conn.fwd3VsSwap_bid:,.1f}/{conn.fwd3VsSwap_offer:,.1f} [{conn.sprd_fwd3VsSwap}bps] ", curses.color_pair(4))
                self.my_window.addstr(17, 150, f"{conn.fwd3VsSwap_mid:,.1f} ", curses.color_pair(4) | curses.A_BOLD)
                self.my_window.addstr(18, 120, f"Min {conn.fwd3VsSwap_mbid:,.1f}/{conn.fwd3VsSwap_moffer:,.1f} [{conn.sprd_fwd3VsSwap_min}bps] ", curses.color_pair(4))
                self.my_window.addstr(18, 150, f"{(conn.fwd3VsSwap_mbid+conn.fwd3VsSwap_moffer)/2:,.1f} ", curses.color_pair(4) | curses.A_BOLD)  # mid min

                #self.my_window.addstr(19, 120, f"Fwd3VsFwd2 (VWAP mids)  = {conn.fwd3Vsfwd2_mid:,.1f}    ", curses.color_pair(4))
                self.my_window.addstr(20, 120, f"Live to best {conn.live_fwd3_dist_bbid:,.1f}/{conn.live_fwd3_dist_boffer:,.1f}       ", curses.color_pair(5))
                self.my_window.addstr(21, 120, f"Trgt to best {conn.fwd3_dist_bbid:,.1f}/{conn.fwd3_dist_boffer:,.1f}       ", curses.color_pair(6))
                # swap3
                if conn.orion_orders:
                    _bid= conn.orion_orders[0]['fwd3T_bid']
                    _offer = conn.orion_orders[0]['fwd3T_offer']
                    _sprd = _offer - _bid
                    bp_sprd = 10000 *_sprd / ((_offer + _bid) / 2)
                    self.my_window.addstr(19, 120, f"Target: {_bid:,.5f}/{_offer:,.5f} [{bp_sprd:,.1f}]      ", curses.color_pair(6))
            else:
                pass
                #log.error('no data for screen')

        except Exception as e:
            log.error(e, exc_info= True)

    def overwatch(self, conn_obj):
        start_l = 39
        start_y = 0
        num_conf = len(conn_obj.conf)
        num_pnd_conf = len(conn_obj.pnd_conf)
        self.my_window.addstr(start_l, start_y, (f"Order watch: outstanding_trades= {num_conf + num_pnd_conf} conf_trades: {num_conf} pnd_conf_trades: {num_pnd_conf} "), curses.color_pair(8))

        # colours
        a = 9
        b = 7

        try:
            if conn_obj.orion_orders:
                #we do two laps.  The first will create a list with lengths,
                # the second places them
                _show = ['mm_method', 'status', 'num_tx', 'trgt_swap', 'trgt_fwd1', 'trgt_fwd2', 'trgt_fwd3', 'last_fld']
                items_no = len(_show)

                l = [0] * items_no

                for i in range(len(conn_obj.orion_orders)):  # cycle through all data and find the max len stringsl track results in array
                    c = 0
                    for _ in _show:
                        v = conn_obj.orion_orders[i][_]
                        l[c] = max(len(str(v)), l[c], len(str(_)), 3) + 1
                        c += 1

                start_l += 2
                start_y = 0

                # displayh rest of data
                for i in range(len(conn_obj.orion_orders)):
                    c = 0  # array start number

                    for _ in _show:
                        v = conn_obj.orion_orders[i][_]
                        self.my_window.addstr(40, start_y, (f"{_}"), curses.color_pair(a))
                        self.my_window.addstr(start_l, start_y, (f"{v}"), curses.color_pair(b))
                        start_y += l[c]
                        c += 1

                    start_l += 1
                    start_y = 0

                    for inst in ['swap_delta', 'fwd1_delta', 'fwd2_delta', 'fwd3_delta']:

                        b_sz = conn_obj.orion_orders[i][inst]['B']['sz']
                        b_num = conn_obj.orion_orders[i][inst]['B']['num']
                        b_avg = conn_obj.orion_orders[i][inst]['B']['avg']
                        o_sz = conn_obj.orion_orders[i][inst]['O']['sz']
                        o_num = conn_obj.orion_orders[i][inst]['O']['num']
                        o_avg = conn_obj.orion_orders[i][inst]['O']['avg']

                        self.my_window.addstr(start_l, start_y, (f"{inst}: "), curses.color_pair(a))
                        self.my_window.addstr(start_l, start_y + 12, ("Buy amnt:"), curses.color_pair(a))
                        self.my_window.addstr(start_l, start_y + 22, (f"{b_sz}  "), curses.color_pair(b))
                        self.my_window.addstr(start_l, start_y + 30, ("#: "), curses.color_pair(a))
                        self.my_window.addstr(start_l, start_y + 33, (f"{b_num}  "), curses.color_pair(b))
                        self.my_window.addstr(start_l, start_y + 38, ("avg:"), curses.color_pair(a))
                        self.my_window.addstr(start_l, start_y + 42, (f"{b_avg}:"), curses.color_pair(b))

                        start_y += 42
                        self.my_window.addstr(start_l, start_y + 12, ("Sell amnt:"), curses.color_pair(a))
                        self.my_window.addstr(start_l, start_y + 22, (f"{o_sz}  "), curses.color_pair(b))
                        self.my_window.addstr(start_l, start_y + 30, ("#: "), curses.color_pair(a))
                        self.my_window.addstr(start_l, start_y + 33, (f"{o_num}  "), curses.color_pair(b))
                        self.my_window.addstr(start_l, start_y + 38, ("avg:"), curses.color_pair(a))
                        self.my_window.addstr(start_l, start_y + 42, (f"{o_avg}:"), curses.color_pair(b))

                        # add skew details
                        skew_name = inst[:5] + 'skew'
                        _skew = conn_obj.orion_orders[i][skew_name]
                        self.my_window.addstr(start_l, start_y + 55, ("Skew: "), curses.color_pair(a))
                        self.my_window.addstr(start_l, start_y + 62, (f"{_skew['bid']}/{_skew['offer']}"), curses.color_pair(b))

                        start_y = 0  # reset for next instrument
                        start_l += 1

            else:
                self.my_window.addstr(start_l, start_y, ('Watching nothing at the moment  '), curses.color_pair(9))
                self.my_window.clrtoeol()  # clear to end of the line

        except KeyError as e:
            log.error(e, exc_info=True)

        except Exception as e:
            template = "on_error exception of type {0} occurred. Arguments:\n{1!r}"
            error_message = template.format(type(e).__name__, e.args)
            log.error(f'{error_message} and self.overwatch = {conn_obj.overwatch}', exc_info=True)

    def hist_odas(self, conn_obj):
        start_l = 47  # starting line for live trades
        start_y = 0
        self.my_window.addstr(start_l - 1, 0, ('Recent Exch Orders:  '), curses.color_pair(8))

        try:
            if conn_obj.orders_hist:

                _show = ['uTime', 'clOrdId', 'instId', 'ordType', 'sz', 'state', 'posSide', 'side', 'px']

                list_sz = len(conn_obj.orders_hist)

                for i in range(-(min(5, list_sz)), 0, 1):

                    # self.my_window.clrtoeol()  # clear to end of the line
                    for _ in _show:

                        v = conn_obj.orders_hist[i][_]
                        if _ == 'uTime':
                            v = human_time(v).strftime("%d-%H:%M:%S")
                        if i == -1:
                            self.my_window.addstr(start_l, start_y, (f"{v}            "), curses.color_pair(2))
                        else:
                            self.my_window.addstr(start_l, start_y, (f"{v}            "), curses.color_pair(5))

                        start_y += 17
                    start_y = 0
                    start_l += 1


        except Exception as e:
            log.error(e)

    def executed_orders(self, conn_obj):
        start_l = 53
        start_y = 0
        # space_y = 12
        self.my_window.addstr(start_l, start_y, (f'Executed orders: '), curses.color_pair(8))
        title_l = start_l + 1

        start_l += 2
        start_y = 0

        try:
            if conn_obj.executed_orders:
                ## items to show on screen
                _show = ['uTime', 'inst1', 'inst2', 'sign', 'side2', 'impl_bps', 'target', 'size1', 'size2', 'oda_px', 'lev1', 'lev2', 'act_dist_usd', 'tx_dist_bps']

                # create template for numbver and size of items
                items_no = len(_show)
                l = [0] * items_no

                for i in range(len(conn_obj.executed_orders)):
                    c = 0
                    for _ in _show:

                        v = conn_obj.executed_orders[i][_]
                        # if timestamp, then convert to human format
                        if _ == 'uTime':
                            v = human_time(v).strftime("%d-%H:%M:%S")


                        l[c] = max(len(str(_)), len(str(v)), l[c], 4)

                        self.my_window.addstr(title_l, start_y, (f" {_}  "), curses.color_pair(9))
                        self.my_window.addstr(start_l, start_y, (f" {v}  "), curses.color_pair(9))
                        start_y += l[c] +1
                        c += 1

                    start_l += 1
                    start_y = 0


        except Exception as e:
            template = "on_error exception of type {0} occurred. Arguments:\n{1!r}"
            error_message = template.format(type(e).__name__, e.args)
            log.error (f'{error_message}', exc_info = True)
            log.debug(f'executed_orders looks like this: {conn_obj.executed_orders[0]}')

    def risk_dets(self, conn_obj):
        # get data for fills
        start_y = yloc = 2
        start_x = xloc = 0 #self.max_x - 55  # TODO: need to switch start_y ands x's to be consistent with curses
        xstep = 50

        self.my_window.addstr(0, 0, ('Risk: '), curses.color_pair(8))

        try:
            for ccy in conn_obj.risk.keys():
                self.my_window.addstr(yloc, xloc, (f'{ccy}'), curses.color_pair(7))
                yloc = start_y + 1
                for k, v in conn_obj.risk[ccy].items():
                    if k == 'FUTS' or k == 'SWAPS':
                        self.my_window.addstr(yloc, xloc, (f"{k} net: {v['net']} positions: {len(v['long'])+ len(v['short'])} "), curses.color_pair(7))
                        yloc += 1
                        for instr, dets in v['long'].items():
                            self.my_window.addstr(yloc, xloc, (f'{instr} '), curses.color_pair(7))
                            yloc += 1
                            for dets_k, dets_v in dets.items():
                                self.my_window.addstr(yloc, xloc, (f'{dets_k} '), curses.color_pair(9))
                                self.my_window.addstr(yloc, xloc + 20, (f'{float(dets_v):,.0f}  '), curses.color_pair(9))
                                yloc += 1
                            yloc += 1

                        for instr, dets in v['short'].items():
                            self.my_window.addstr(yloc, xloc, (f'{instr}'), curses.color_pair(10))
                            yloc += 1
                            for dets_k, dets_v in dets.items():
                                self.my_window.addstr(yloc, xloc, (f'{dets_k} '), curses.color_pair(9))
                                self.my_window.addstr(yloc, xloc + 20, (f'{float(dets_v):,.0f}  '), curses.color_pair(9))
                                yloc += 1
                            yloc += 1

                    elif k != 'FUTS' or k != 'SWAPS':
                        self.my_window.addstr(yloc, xloc, (f'{k} '), curses.color_pair(8))
                        self.my_window.addstr(yloc, xloc + 20, (f'{float(v):,.0f}  '), curses.color_pair(8))
                        yloc += 1
                yloc = start_y
                xloc += xstep


                ## items to show on screen
                #_show = ['ts', 'instId', 'side', 'fillSz', 'fillPx']
        except Exception as e:
            log.error(e, exc_info=True)


    def okex_fills(self, conn_obj):
        # get data for fills
        start_l = 42
        start_y = self.max_x - 55  # TODO: need to switch start_y ands x's to be consistent with curses
        self.my_window.addstr(start_l, start_y, ('System fill info: '), curses.color_pair(8))
        title_l = start_l + 1

        start_l += 2

        try:
            if conn_obj.fills:
                ## items to show on screen
                _show = ['ts', 'instId', 'side', 'fillSz', 'fillPx']

                # create template for number and size of items
                items_no = len(_show)
                l = [0] * items_no

                ## one run to get correct sizes
                for i in range(len(conn_obj.fills)):
                    c = 0
                    for _ in _show:

                        v = conn_obj.fills[i][_]
                        # if timestamp, then convert to human format
                        if _ == 'ts':
                            v = human_time(v).strftime("%a %H:%M.%S")

                        l[c] = max(len(str(_)), len(str(v)), l[c], 5)

                        self.my_window.addstr(title_l, start_y, (f"{_}  "), curses.color_pair(9))
                        self.my_window.addstr(start_l, start_y, (f"{v}  "), curses.color_pair(9))
                        start_y += l[c] + 1
                        c += 1

                    start_l += 1
                    start_y = self.max_x - 55


        except Exception as e:
            template = "on_error exception of type {0} occurred. Arguments:\n{1!r}"
            error_message = template.format(type(e).__name__, e.args)
            log.error (f'{error_message}', exc_info = True)


    def testing_1(self, conn_obj):
        for i in enumerate(conn_obj.stack_swap['bids']):
            self.my_window.addstr(5 + i[0], 20, f"{i[0]} {float(i[1][0]):#,.6g} {i[1][1].rjust(10)}    ", curses.color_pair(2))
            #if i[0] == 10:
            #    break



        #self.my_window.addstr(1, 0, (f"{conn_obj.stack_swap}  "), curses.color_pair(9))

    def balance_and_position(self, conn_obj):
        #log.debug('balance and position in litescrn is running')
        # get data for fills
        start_l = 1
        start_y = 1
        self.my_window.addstr(start_l, start_y, (f'Balance and position data: '), curses.color_pair(8))
        title_l= start_l + 1

        start_l += 2

        try:
            # the second places them
            raw_posData = conn_obj.balance_and_position['data'][0]['posData'] # 'avgPx', 'ccy', 'instId', 'instType', 'mgnMode', 'pos', 'posCcy', 'posId', 'posSide', 'tradeId', 'uTime'
            raw_balData = conn_obj.balance_and_position['data'][0]['balData'] # 'cashBal', 'ccy', 'uTime'

            _show = ['avgPx', 'ccy', 'instId', 'instType', 'mgnMode', 'pos', 'posCcy', 'posId', 'posSide', 'tradeId', 'uTime']

            items_no = len(_show)

            l = [0] * items_no
            if raw_posData:
                for i in range(len(raw_posData)):
                    c = 0
                    for _ in _show:
                        v = raw_posData[i][_]
                        l[c] = max(len(str(v)), l[c], len(str(_)), 3)
                        c += 1

                self.my_window.addstr(30, 0, (f'l =  {l}  '), curses.color_pair(7))

                for i in range(len(raw_posData)):
                    c = 0
                    for _ in _show:
                        v = raw_posData[i][_]
                        self.my_window.addstr(title_l, start_y, (f' {_}  '), curses.color_pair(7))
                        self.my_window.addstr(start_l, start_y, (f' {v}  '), curses.color_pair(9))
                        start_y += l[c] + 1
                        c += 1

                    start_y = 0
                    start_l += 1
            else:
                self.my_window.addstr(start_l, start_y, ('Nada amigo '), curses.color_pair(9))
                self.my_window.clrtoeol() # clear to end of the line

        except Exception as e:
            template = "on_error exception of type {0} occurred. Arguments:\n{1!r}"
            error_message = template.format(type(e).__name__, e.args)
            log.error (f'{error_message}')

    def positions(self, conn_obj):
        start_l = 12 # starting line
        title_l = start_l -1
        step_y = 13
        tc = 7

        try:
            if conn_obj.positions:
                posData = conn_obj.positions['data']
                trades = len(posData)
                self.my_window.addstr(start_l-2, 0, (f'Positions: (open trades: {trades}):  '), curses.color_pair(4))
                for i in range(trades):

                    start_y = 0
                    #log.debug(f'full data: {i} {posData[i]}')
                    try:

                        adl = posData[i]['adl']
                        availPos = posData[i]['availPos']

                        avgPx = posData[i]['avgPx']
                        avgPx = checkfloat(avgPx)

                        cTime = posData[i]['cTime']
                        ccy = posData[i]['ccy']

                        instType = posData[i]['instType']

                        # from currency, determine the relevant index to then calc spread
                        #rel_idx = float(conn_obj.subscription_list['OKE-' + ccy + '-USD-SWAP']['indexPrice'])
                        #rel_sprd = f'{(10000* (float(avgPx) - rel_idx)/rel_idx):,.0f}'

                        #if instType =='SWAP':
                        #    rel_sprd = 'n/a'

                        imr = posData[i]['imr']
                        imr = checkfloat(imr)

                        instId = posData[i]['instId']
                        #log.debug(f'instid at start {instId}')

                        interest = posData[i]['interest']

                        last = posData[i]['last']
                        last = checkfloat(last)

                        lever = posData[i]['lever']
                        liab = posData[i]['liab']
                        liabCcy = posData[i]['liabCcy']

                        liqPx = posData[i]['liqPx']
                        if liqPx == '':
                            liqPx = 'N/A'
                        liqPx = checkfloat(liqPx)

                        margin = posData[i]['margin']
                        margin = checkfloat(margin)

                        mgnMode = posData[i]['mgnMode']
                        mgnRatio = (posData[i]['mgnRatio'])
                        mgnRatio = checkfloat(mgnRatio)

                        mmr = posData[i]['mmr']
                        mmr = checkfloat(mmr)

                        notionalUsd = posData[i]['notionalUsd']
                        notionalUsd = checkfloat(notionalUsd)

                        pos = posData[i]['pos']
                        posCcy = posData[i]['posCcy']
                        posId = posData[i]['posId']
                        posSide = posData[i]['posSide']
                        tradeId = posData[i]['tradeId']
                        #uTime = posData[i]['uTime']

                        upl = posData[i]['upl']
                        upl = checkfloat(upl)

                        #upl_usd = float(upl) * rel_idx

                        uplRatio = posData[i]['uplRatio']
                        uplRatio = checkfloat(uplRatio)


                    except Exception as e:
                        log.error(e)

                    # update risk
                    # ID

                    self.my_window.addstr(title_l, start_y, ('no.'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{i}  '))
                    start_y += 3

                    #self.my_window.addstr(title_l, start_y, ('ccy'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{ccy}  '))
                    #start_y += step_y

                    #self.my_window.addstr(title_l, start_y, ('posId'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{posId}  '))
                    #start_y += step_y
                    self.my_window.addstr(title_l, start_y, ('instId'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{instId}  '))

                    #start_y += step_y +4
                    #self.my_window.addstr(title_l, start_y, ('inst'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{instType}  '))
                    #start_y += 8
                    #self.my_window.addstr(title_l, start_y, ('tradeId'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{tradeId}  '))
                    #start_y += step_y

                    # size/direction
                    #self.my_window.addstr(title_l, start_y, ('posCcy'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{posCcy}  '))
                    #start_y += step_y

                    self.my_window.addstr(title_l, start_y, ('notionalUSD'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{notionalUsd}  '))
                    start_y += step_y
                    self.my_window.addstr(title_l, start_y, ('pos'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{pos}  '))
                    start_y += 5
                    self.my_window.addstr(title_l, start_y, ('posSide'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{posSide}  '))
                    start_y += step_y - 2

                    #self.my_window.addstr(title_l, start_y, ('availPos'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{availPos}  '))
                    start_y += step_y

                    self.my_window.addstr(title_l, start_y, ('avgPx'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{avgPx}  '))
                    start_y += 7

                    #self.my_window.addstr(title_l, start_y, ('rel_sprd'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{rel_sprd}     '))

                    start_y += 5

                    # PNL

                    self.my_window.addstr(title_l, start_y, ('upl(coin)'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{upl}  '))
                    start_y += step_y

                    #self.my_window.addstr(title_l, start_y, ('upl($)'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{upl_usd:,.0f}  '))
                    #start_y += 10

                    self.my_window.addstr(title_l, start_y, ('uplRatio'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{uplRatio}  '))
                    start_y += step_y


                    # margin

                    self.my_window.addstr(title_l, start_y, ('liqPx'), curses.color_pair(tc) | curses.A_BOLD)
                    if liqPx:
                        self.my_window.addstr(start_l, start_y, (f'{liqPx}  '))
                    else:
                        self.my_window.addstr(start_l, start_y, (f'{liqPx}  '))
                    start_y += 9
                    #self.my_window.addstr(title_l, start_y, ('margin'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{margin}  '))
                    #start_y += step_y
                    self.my_window.addstr(title_l, start_y, ('marginRatio'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{mgnRatio}  '))
                    start_y += step_y

                    #self.my_window.addstr(title_l, start_y, ('marginMode'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{mgnMode}  '))
                    #start_y += step_y


                    self.my_window.addstr(title_l-1, start_y, ('auto'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(title_l, start_y, ('delev'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{adl}  '))
                    start_y += 6
                    self.my_window.addstr(title_l, start_y, ('i_margin'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{imr}  '))
                    start_y += step_y
                    #self.my_window.addstr(title_l, start_y, ('int'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{interest}  '))
                    #start_y += 4
                    self.my_window.addstr(title_l, start_y, ('last'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{last}  '))
                    start_y += step_y
                    self.my_window.addstr(title_l, start_y, ('lever'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{lever}  '))
                    start_y += 6
                    #self.my_window.addstr(title_l, start_y, ('liab'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{liab}  '))
                    #start_y += step_y
                    #self.my_window.addstr(title_l, start_y, ('liabCcy'), curses.color_pair(tc) | curses.A_BOLD)
                    #self.my_window.addstr(start_l, start_y, (f'{liabCcy}  '))
                    #start_y += 8
                    self.my_window.addstr(title_l, start_y, ('maint_m'), curses.color_pair(tc) | curses.A_BOLD)
                    self.my_window.addstr(start_l, start_y, (f'{mmr}  '))
                    start_y += step_y

                    start_l += 1

            else:

                self.my_window.addstr(start_l-2, 0, (f'No positions data  '), curses.color_pair(4))
        except AttributeError as e:
            log.error(e)
        except TypeError as e:
            log.error(e)
        except IndexError as e:
            log.error(e)
        except Exception as e:
            template = "on_error exception of type {0} occurred. Arguments:\n{1!r}"
            error_message = template.format(type(e).__name__, e.args)
            log.error(f'to_screen positions: {error_message} and: {e} ')

    def main_screen(self, conn_obj):
        # Main info screen

        # TODO: consider only making updates if there is a new datapoint
        # show risk
        self.show_notification(conn_obj)
        self.show_stack(conn_obj)

        self.latency_data(conn_obj)
        self.risk(conn_obj)
        # show outstanding orders
        # self.outstanding_trades(conn_obj)

        self.hist_odas(conn_obj)
        self.debug(conn_obj.msg1)

        # Show order watch
        self.overwatch(conn_obj)

        # show executed orders
        #self.executed_orders(conn_obj)

        # show filled trades as they happen
        self.okex_fills(conn_obj)
        # returns market levels for debuggig comparisons



