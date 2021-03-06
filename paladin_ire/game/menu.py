#!/usr/bin/env python3.6
#-*- coding: utf-8 -*-

import curses
import json
import random
from curses import panel

from .classes import CLASSES
from .core import NAME_LIST, GameWindow
from .core import RandomRoll
from .attributes import ATTRIBUTE_DESCRIPTIONS


class Menu(GameWindow):
    def __init__(self, stdscreen, app):
        super().__init__(stdscreen, app)
        self.first_pass = True
        self.show_stats = False

    def navigate(self, n):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.items):
            self.position = len(self.items) - 1

    def refresh_attributes(self):
        pass

    def menu_bar(self, val_list=('S: Save', 'Q: Quit', 'N: Name Player')):
        # Overriding this to extend the default menu options in the game menu
        if val_list:
            menu = ' | '.join(val_list)
            self._pre_draw(1, 2)
            self.window.addstr(1, 2, menu, curses.color_pair(3))

    def _default_selections(self, key):
        if key == curses.KEY_UP:
            self.navigate(-1)

        elif key == curses.KEY_DOWN:
            self.navigate(1)

        elif key in [ord('N'), ord('n')]:
            entry = self.msg_bar_prompt('Choose a name (Blank={}, 15 chars): ',
                                        self.get_random_name)
            self.app.player.name = entry
            self.msg_bar('Name selected: {}'.format(entry))
            self.draw_charinfo()

        elif key in [ord('S'), ord('s')]:
            if not self.app.player.init_complete:
                self.current_msg = 'You must select Attributes before saving!'
            else:
                self.save_entity()

        elif key in [ord('Q'), ord('q')]:
            self.over = None
            return False
        return True

    def draw_sidewin(self, title, msg):
        self.clear_win(self.side_win)
        self.side_win.addstr(2, self.margin + 1, title,
                             curses.A_BOLD | curses.color_pair(3)
                             )
        i = self.margin + 1
        for line in msg.split('\n'):
            self.side_win.addstr(i, self.margin + 1, line)
            i += 1

    @property
    def get_random_name(self):
        return random.choice(NAME_LIST)

    def save_entity(self):
        entry = self.msg_bar_prompt('Input a file name (Blank={}, 15 chars): ',
                                    self.getfilename)
        fname = './entities/{}'.format(entry)
        self.msg_bar('Save entity "{}"? (Y/n): '.format(fname))
        key = self.window.getch()
        if key in [ord('Y'), ord('y')]:
            self.app.player.name = entry
            attrs = self.app.player.attributes[0]
            with open(fname, 'w+') as outf:
                json.dump(
                    self.package_entity(),
                    outf
                )
            self.msg_bar('{} saved!'.format(fname))
            self.refresh_attributes()
            self.draw_charinfo()
            return False
        else:
            self.msg_bar('Entity save aborted!')
            return True

    def package_entity(self):
        return {
            'name': self.app.player.name,
            'class': self.app.player.player_class.__class__.__name__,
            'attributes': {attr: getattr(self.app.player, attr)
                           for attr in self.app.player.attributes[0]},
            'resists': {res: getattr(self.app.player, res)
                        for res in self.app.player.resists[0]},
            'meta': {fl: getattr(self.app.player, fl)
                     for fl in ('level', 'spells', 'sneaks', 'damage')},
            'status': {st: getattr(self.app.player, st)
                       for st in self.app.player.status_effects[0]}
        }

    def post_init(self, items):
        self.items = items
        self.items.append(MenuItem('Back', 'exit', len(items)))
        self.start_pos = 0

    def _pre_loop(self):
        self.maxy, self.maxx = self.window.getmaxyx()
        self.panel.top()
        self.panel.show()
        self.window.clear()
        self.window.box()
        self.first_pass = True
        self.position = self.start_pos

    def _post_loop(self):
        self.window.clear()
        self.panel.hide()
        panel.update_panels()
        curses.doupdate()

    def print_item_list(self):
        for item in self.items:
            if item.index == self.position:
                mode = curses.A_REVERSE
            else:
                if item.label == 'Set Attributes' and \
                    self.app.player.player_class is None:
                    mode = curses.A_DIM
                else:
                    mode = curses.A_NORMAL

            self.window.addstr(self.margin + item.index, 2, item.label, mode)

    def _first_pass(self):
        self.first_pass = False

    def main_loop(self):
        self.print_item_list()
        self.draw_charinfo()
        if not self.first_pass:
            return self.process_selection(self.window.getch())
        else:
            self._first_pass()
        return True

    def _msg_bar_update(self):
        if self.position == len(self.items) - 1:
            self.msg_bar('Hit ENTER to exit this menu')
        elif self.position == len(self.items) - 2:
            self.msg_bar('Press ENTER to edit game optons')
        elif self.position == len(self.items) - 3:
            self.msg_bar('Press ENTER to start the game (not implemented)')
        else:
            self.msg_bar('Hit ENTER to choose this option')

    def process_selection(self, key):
        self.last_keystroke = self._parse_keystroke(key)
        if key in [curses.KEY_ENTER, ord('\n')]:
            if self.position == len(self.items) - 1:
                return False
            else:
                self.current_msg = self.items[self.position].hook()
                self.window.box()

        result = self._default_selections(key)
        self._msg_bar_update()

        return result


class MenuItem():
    def __init__(self, label, hook, index, args=None, pop=True, req=True):
        self.label = label
        self.hook = hook
        self.args = args
        self.pop = pop
        self.index = index
        self.req = req


class AttributeSelection(Menu):
    """ Player attribute selection and save functionality """

    def attr_init(self, force=False):
        if not self.app.player.init_complete or force:
            # rolls initial player attributes
            rr = RandomRoll(self.app.player, 7)
            attr_list = self.app.player.attributes[0]

            # Seed initial stats
            while True:
                for a in attr_list:
                    result = rr.roll(None)
                    setattr(self.app.player, a, result)
                if self.app.player.free_attr < 16 and self.app.player.free_attr > 10:
                    break

            # Distribute remainder based on class
            cls = self.app.player.player_class
            if cls is not None:
                preferred = [attr for attr in cls.preferred_attr]
                # Set resists
                for resist in cls.resists:
                    setattr(self.app.player, resist, cls.resists[resist])
            else:
                preferred = []
            preferred.append('health')
            while self.app.player.free_attr > 5:
                a = random.choice(attr_list)
                if a in preferred:
                    setattr(self.app.player, a, getattr(self.app.player, a) + 1)

        self.refresh_attributes()

    def post_init(self):
        self.refresh_attributes()
        self.side_win, self.desc_panel = self.side_panel(12, 24, 2, 48)
        self.start_pos = 8
        self.show_stats = True

    def refresh_attributes(self):
        attrs, _ = self.app.player.attributes
        self.items = [(attr, getattr(self.app.player, attr)) for attr in attrs]
        self.items.extend([('Re-roll', ''), ('Done', '')])

    def _post_loop(self):
        self.window.clear()
        self.panel.hide()
        self.side_win.clear()
        self.desc_panel.hide()
        panel.update_panels()
        curses.doupdate()

    def _pre_loop(self):
        self.panel.top()
        self.panel.show()
        self.window.clear()
        self.window.box()
        self.position = self.start_pos

    def _draw_desc(self):
        self.desc_panel.top()
        self.desc_panel.show()
        self.side_win.clear()
        self.side_win.box()

    def _loop_begin(self):
        self.window.refresh()
        self.window.box()
        self.side_win.overlay(self.window)
        self._draw_desc()
        curses.doupdate()
        if self.show_stats:
            self._print_stats()

    def _print_stats(self):
        # Print resist values
        self.print_resist_list()
        # Calculate and print player stats
        self.print_player_stats()

    def _first_pass(self):
        assert self.app.player.player_class is not None, \
            'Player has class {}'.format(self.app.player.player_class)
        self.attr_init()
        self.first_pass = False

    def process_selection(self, key):
        self.last_keystroke = self._parse_keystroke(key)
        if key in [curses.KEY_ENTER, ord('\n')]:
            if self.position == len(self.items) - 1:
                if self.app.player.free_attr > 0:
                    self.msg_bar('{} attribute points to assign!'.format(
                        self.app.player.free_attr))
                    return True

                self.app.player.complete_init()
                self.over = None
                return False
            elif self.position == len(self.items) - 2:
                self.over = 're-roll'
                self.app.player._attr_init()
                self.attr_init(True)
                self.print_item_list()
                self.msg_bar('Attributes re-rolled')
                return True
            else:
                if self.app.player.free_attr > 0:
                    self.incr_attr()
                    if self.app.player.free_attr == 0:
                        self.app.player.complete_init()
                else:
                    # self.current_msg = 'No remaining attribute points'
                    self.msg_bar()
                    return True

        result = self._default_selections(key)

        if self.position < len(self.items) - 2:
            self.over = self.app.player.attributes[0][self.position]
            self.attribute_info()
            self.current_msg = 'Hit ENTER to increase this attribute'
        elif self.position == len(self.items) - 2:
            self.clear_win(self.side_win)
            self.over = 're-roll'
            self.current_msg = 'Hit ENTER to re-roll attributes'
        else:
            self.clear_win(self.side_win)
            self.over = 'done'
            self.current_msg = 'Hit ENTER to return to the previous menu'
        self.draw_charinfo()
        return result

    def incr_attr(self):
        self.debug_info()
        for idx, item in enumerate(self.items):
            if idx == self.position:
                setattr(self.app.player, item[0],
                        int(getattr(self.app.player, item[0]) + 1))
                self.current_msg = 'Attribute: {}, new value: {}'.format(
                    item[0],
                    getattr(self.app.player, item[0])
                )
                self.msg_bar()
        self.refresh_attributes()

    def print_item_list(self):
        self.window.addstr(self.margin, 2, 'Attributes ({})'.format(
            self.app.player.free_attr),
                           self.info_msg | curses.A_BOLD
                           )
        for idx, item in enumerate(self.items):
            attr, val = item
            if idx == self.position:
                mode = curses.A_REVERSE
            else:
                mode = curses.A_NORMAL

            self.window.addstr(self.margin + idx + 1, 2, attr, mode)
            self.window.addstr(self.margin + idx + 1, 17, str(val).rjust(2),
                               mode)

    def print_resist_list(self):
        self.window.addstr(self.margin + 11, 2, 'Resists',
                           self.info_msg | curses.A_BOLD)
        for i, resist in enumerate(self.app.player.resists[0]):
            self.window.addstr(
                self.margin + 12 + i, 2,
                resist,
                curses.color_pair(1)
            )
            self.window.addstr(
                self.margin + 12 + i, 17,
                str(getattr(self.app.player, resist)).rjust(2),
                curses.color_pair(1)
            )

    def print_player_stats(self):

        def _print_stat(s):
            self.window.addstr(self.margin + i, 22, s, mode)
            self.window.addstr(
                self.margin + i, 37,
                str(self.app.player.get_stat(s)).rjust(2),
                mode
            )

        mode = curses.color_pair(1)
        self.window.addstr(self.margin, 22, 'Player Stats',
                           self.info_msg | curses.A_BOLD
                           )
        i = 1
        __stats = self.app.player.player_stats
        for calc_stat in [s for s in __stats if not __stats[s][1]]:
            _print_stat(calc_stat)
            i += 1

        for stat in [s for s in __stats if __stats[s][1]]:
            _print_stat(stat)
            i += 1

    def attribute_info(self):
        title = self.over
        desc = ATTRIBUTE_DESCRIPTIONS[title]
        self.draw_sidewin(title, desc)


class ClassSelection(AttributeSelection):
    def post_init(self):
        self.side_win, self.desc_panel = self.side_panel(20, 60, 2, 40)
        self.items = [(pc.__name__, pc) for pc in CLASSES]
        self.items.append(('Done', ''))
        self.start_pos = 3

    def print_item_list(self):
        self.window.addstr(self.margin, 2, 'Player Classes',
                           self.info_msg | curses.A_BOLD)
        for idx, item in enumerate(self.items):
            cls_name, cls = item
            if idx == self.position:
                mode = curses.A_REVERSE
            else:
                mode = curses.A_NORMAL

            self.window.addstr(self.margin + idx + 2, 2, cls_name, mode)

    def _first_pass(self):
        self.first_pass = False

    def process_selection(self, key):
        self.last_keystroke = self._parse_keystroke(key)
        if self.last_keystroke == 'enter':
            if self.position == len(self.items) - 1:
                self.over = None
                return False
            else:
                self.app.player.player_class = self.items[self.position][1]()
                self.current_msg = 'Class selected: {}'.format(
                    self.items[self.position][0])
                self.draw_charinfo()
                return False

        result = self._default_selections(key)

        if self.position < len(self.items) - 1:
            cls = self.items[self.position][1]
            self.over = cls.__name__
            self.class_info(cls)
            self.current_msg = 'Hit ENTER to select this class'
        else:
            self.clear_win(self.side_win)
            self.over = 'done'
            self.current_msg = 'Hit ENTER to return to the previous menu'

        self.draw_charinfo()
        return result

    def class_info(self, cls):
        title = self.over
        desc = cls.description
        self.draw_sidewin(title, desc)


class OptionMenu(AttributeSelection):
    def post_init(self):
        args = self.app.args
        self._filter_printed_arguments()
        self.side_win, self.desc_panel = self.side_panel(20, 60, 2, 40)
        self.start_pos = 2

    def _filter_printed_arguments(self):
        # Filters and refreshes the argument list
        exclude = ['create', 'dimensions', 'verbose']
        self.items = [(k, self.app.args.__dict__[k]) for k in
                      self.app.args.__dict__ if k not in exclude]
        self.items.append(('Done', ''))

    def print_item_list(self):
        self._filter_printed_arguments()
        self.window.addstr(self.margin, 2, 'Game Options',
                           self.info_msg | curses.A_BOLD)
        for idx, item in enumerate(self.items):
            option, value = item
            if idx == self.position:
                mode = curses.A_REVERSE
            else:
                mode = curses.A_NORMAL

            self.window.addstr(self.margin + idx + 2, 2, option, mode)
            self.window.addstr(self.margin + idx + 2, 17, str(value), mode)

    def _first_pass(self):
        self.first_pass = False

    def _increment_value(self, v, max_val=5):
        if isinstance(v, (bool)):
            v = not v
        elif isinstance(v, (int)):
            if self.last_keystroke == 'enter':
                if v < max_val:
                    v += 1
                else:
                    self.msg_bar('Option at max!')
            if self.last_keystroke == 'backspace':
                if v > 0:
                    v -= 1
                else:
                    self.msg_bar('Already at 0!')
        return v

    def process_selection(self, key):
        self.last_keystroke = self._parse_keystroke(key)

        if self.last_keystroke == 'enter':
            if self.position == len(self.items) - 1:
                self.over = None
                return False

        if self.last_keystroke in ['enter', 'backspace']:
            for idx, item in enumerate(self.items):
                if idx == self.position:
                    setattr(self.app.args, item[0],
                            self._increment_value(item[1]))
                    return True

            self.print_item_list()

        result = self._default_selections(key)

        if self.position < len(self.items) - 1:
            self.over = self.items[self.position][0]
            self.option_info()
            self.msg_bar('Hit ENTER / DELETE to toggle this Game Option')
        else:
            self.clear_win(self.side_win)
            self.over = 'done'
            self.msg_bar('Hit ENTER to return to the previous menu')

        return result

    def option_info(self):
        # Option menu side window descriptions
        descriptions = {
            'debug': "Debug run, enables in-game\ndebug options and status\ndisplay",
            'difficulty': "Set game difficulty",
            'done': ''
        }
        title = self.over.lower()
        self.draw_sidewin(title, descriptions[title])
