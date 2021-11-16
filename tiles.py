
# This module contains the Tile class 
#
#
import libtcodpy as libtcod

class Tile:
    #a tile of the map and its properties
    def __init__(self, blocked, block_sight = None, type='dummy', name='dummy' ):
        self.blocked = blocked

        #all tiles start unexplored
        self.explored = False

        #by default, if a tile is blocked, it also blocks sight
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight
        
        #self.type = type #terrain options set in make_map() to show different appearance in render_all()
        
        self.name = name
        self.change_type(type)
         
    def change_type(self, type):    
        self.type = type
        
        if type == 'empty': #empty tile
            self.name = 'empty'
            self.char_light = '.'
            self.char_dark = ' '
            self.color_light = 'grey'
            self.color_dark = 'white'
            self.blocked = False
            self.block_sight = False
        elif type == 'rock wall':
            self.name = 'wall'
            self.char_light = '#'
            self.char_dark = '#'
            self.color_light = 'grey'
            self.color_dark = 'dark grey'
            self.blocked = True
            self.block_sight = True
        elif type == 'mountain':
            self.name = 'mountain'
            self.char_light = '^'
            self.char_dark = '^'
            self.color_light = 'grey'
            self.color_dark = 'dark grey'
            self.blocked = False
            self.block_sight = False
        elif type == 'house':
            self.name = 'house'
            self.char_light = chr(127)
            self.char_dark = chr(127)
            self.color_light = 'darker orange'
            self.color_dark = 'dark red'
            self.blocked = False
            self.block_sight = False
        elif type == 'street':
            self.name = 'street'
            self.char_light = '.'
            self.char_dark = '.'
            self.color_light = 'darker orange'
            self.color_dark = 'dark brown'
            self.blocked = False
            self.block_sight = False

        elif type == 'grass': #empty tile
            self.name = 'empty'
            self.char_light = '.'
            self.char_dark = ' '
            self.color_light = 'grey'
            self.color_dark = 'white'
            self.blocked = False
            self.block_sight = False
            
            i = libtcod.random_get_int(0,0,100)
            if i <= 30:
                self.color_light = 'dark green'
                self.char_light = "'"
            elif i <= 80:
                self.color_light = 'green'
                self.char_light = ','
            elif i <= 81:
                self.color_light = 'dark green'
                self.char_light = chr(5)
        else:
            self.name = 'dummy'
            self.char_light = '/'
            self.char_dark = '/'
            self.color_light = 'white'
            self.color_dark = 'blue'
            self.blocked = False
            self.block_sight = False
