#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import libtcodpy as libtcod
import PyBearLibTerminal as T
import math
import numpy as np
import textwrap
import shelve
import time
import random
import re
import os, shutil
from collections import defaultdict

import monsters
import items
import tiles
import timer


#actual size of the window
SCREEN_WIDTH = 90
SCREEN_HEIGHT = 23

#size of the map
MAP_WIDTH = 40
MAP_HEIGHT = 16

BAR_WIDTH = 15

#Monster lines to the right
MLINE_HEIGHT = SCREEN_HEIGHT
MLINE_WIDTH = (SCREEN_WIDTH - MAP_WIDTH) / 2
MLINE_Y = 3
MLINE_X = MAP_WIDTH

#Player messages to the right
PLINE_HEIGHT = SCREEN_HEIGHT
PLINE_WIDTH = (SCREEN_WIDTH - MAP_WIDTH) / 2
PLINE_Y = 3
PLINE_X = MAP_WIDTH + MLINE_WIDTH

#System messages at the bottom
SLINE_HEIGHT = SCREEN_HEIGHT - MAP_HEIGHT
SLINE_WIDTH = MAP_WIDTH
SLINE_Y = MAP_HEIGHT + 1
SLINE_X = 0 + 1

#sizes and coordinates relevant for the GUI
MSG_WIDTH = MLINE_WIDTH #PANEL_WIDTH - MSG_X - 2
MSG_HEIGHT = SCREEN_HEIGHT - 5 #PANEL_HEIGHT - 3
SYS_MSG_HEIGHT = 6

INVENTORY_WIDTH = SCREEN_WIDTH - 20

#parameters for dungeon generator
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True  #light walls or not

LIMIT_FPS = 20  #20 frames-per-second maximum

dist_corner = 0,0

dot_pattern = [ (0,0) ]
plus_pattern = [ (1,0), (-1,0), (0,1), (0,-1)  ]
x_pattern = [ (-1,-1), (1,1), (-1,1), (1,-1) ]
diamond_pattern = [ (0,2), (0,-2), (-2,0), (2,0) ] + x_pattern + plus_pattern + dot_pattern
hole_diamond_pattern = [ (0,2), (0,-2), (-2,0), (2,0) ] + x_pattern + plus_pattern



#---------------------------------------------------------------------------------------------------------
# class Tile: now in tiles.py module

class Rect:
    #a rectangle on the map. used to characterize a room.
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)

    def intersect(self, other):
        #returns true if this rectangle intersects with another one
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)

class Object:
#this is a generic object the player, a monster, an item, the stairs
#it's always represented by a character on screen.
    def __init__(self, x, y, z, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None, equipment=None):
        self.x = x
        self.y = y
        self.z = z
        self.char = char
        self.base_name = name
        self.color = color
        self.blocks = blocks
        self.always_visible = always_visible
        self.fighter = fighter
        if self.fighter:  #let the fighter component know who owns it
            self.fighter.owner = self

        self.ai = ai
        if self.ai:  #let the AI component know who owns it
            self.ai.owner = self

        self.item = item
        if self.item:  #let the Item component know who owns it
            self.item.owner = self      
            
        self.equipment = equipment
        if self.equipment:  #let the Equipment component know who owns it
            self.equipment.owner = self

            #there must be an Item component for the Equipment component to work properly
            if not self.item:    
                self.item = Item()
                self.item.owner = self
        
        self.desc = name
        
    @property
    def name(self):  #return actual name, by summing up the possible components
        return self.base_name
    
    @property
    def color_(self):
        color = self.color
        return color
    
    @property
    def char(self):
        return self.char
    
    def move(self, dx, dy):
        #check if leaving the map
        if self.x + dx < 0 or self.x + dx >= MAP_WIDTH or self.y + dy < 0 or self.y + dy >= MAP_HEIGHT:
            return
            
        #move by the given amount, if the destination is not blocked
        render_all()
        if not is_blocked(self.x + dx, self.y + dy, self.z):
            self.x += dx
            self.y += dy
            T.refresh()            
            T.delay(50) 
            
    def move_away_from(self, target_x, target_y):
        #vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        #normalize it to length 1 (preserving direction), then round it and
        #convert to integer so the movement is restricted to the map grid
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(-dx, -dy)
                        
    def move_towards(self, target_x, target_y):
        # #vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        
        ddx = 0 
        ddy = 0
        if dx > 0:
            ddx = 1
        elif dx < 0:
            ddx = -1
        if dy > 0:
            ddy = 1
        elif dy < 0:
            ddy = -1
        if not is_blocked(self.x + ddx, self.y + ddy, self.z):
            self.move(ddx, ddy)
        else:
            if ddx != 0:
                if not is_blocked(self.x + ddx, self.y, self.z):
                    self.move(ddx, 0)
                    return
            if ddy != 0:
                if not is_blocked(self.x, self.y + ddy, self.z):
                    self.move(0, ddy)
                    return
    
    def distance_to(self, other):
        #return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def distance(self, x, y):
        #return the distance to some coordinates
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def send_to_back(self):
        #make this object be drawn first, so all others appear above it if they're in the same tile.
        global objects
        objects[self.z].remove(self)
        objects[self.z].insert(0, self)

    def draw(self):
        #only show if it's visible to the player; or it's set to "always visible" and on an explored tile
        if (visible_to_player(self.x,self.y) or
                (self.always_visible and map[self.z][self.x][self.y].explored)):
            T.color(self.color)
            T.print_(self.x, self.y, self.char)
            # if self.fighter:
                # #if T.TK_COMPOSITION:
                # T.composition(T.TK_ON)
                # T.print_(self.x, self.y, 'Y')
                # T.print_(self.x, self.y, '_')
                # T.composition(T.TK_OFF)
                

    def clear(self):
        #erase the character that represents this object
        if visible_to_player(self.x,self.y):
            #libtcod.console_put_char_ex(con, self.x, self.y, '.', libtcod.light_grey, libtcod.black)
            T.color('grey')
            T.print_(self.x, self.y, '.')
            
    def delete(self):
        #easy way to trigger removal from object
        for obj in objects[self.z]:
            if obj.fighter:
                if self in obj.fighter.inventory:
                    obj.fighter.inventory.remove(self)
            if self in objects[self.z]:
                objects[self.z].remove(self)
        self.clear()
        
class Fighter:
    #combat-related properties and methods (monster, player, NPC).
    def __init__(self, hp, damage, armor, wit, strength, spirit, limbs={}, death_function=None):

        self.base_hp = hp
        self.hp = hp
        
        self.hp_plus = 0 #additional hp granted later in the game
        
        self.base_damage = damage
        self.base_armor = armor
        
        self.base_wit = wit
        self.base_strength = strength
        self.base_spirit = spirit
        
        self.limbs = limbs
        
        self.death_function = death_function
        
        self.inventory = []

    @property
    def max_hp(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = 0 #sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_hp + self.hp_plus + bonus
        
    @property
    def damage(self):  #return actual damage, by summing up the bonuses from all equipped items
        bonus = sum(equipment.damage_bonus for equipment in get_all_equipped(self.owner))
        return self.base_damage + bonus
    
    @property
    def armor(self):  #return actual defense, by summing up the bonuses from all equipped items
        bonus = sum(equipment.armor_bonus for equipment in get_all_equipped(self.owner))
        return self.base_armor + bonus

    @property
    def wit(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = 0 #sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_wit + bonus
        
    @property
    def str(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = 0 #sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return  self.base_strength + bonus
        
    @property
    def spirit(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = 0 #sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_spirit + bonus
    
    def attack(self, target):
        #combat system was changed to deterministic, at and pa were commented out for time being
        
        message(self.owner.name.capitalize() + ' hits ' + target.name + '.', get_identity(self.owner))
        
        do_damage(target, self.damage, 0)
    
    def take_damage(self, damage, fire_damage): 
        #apply damage if possible
        damage = int(round(damage))
        damage -= self.armor
        
        start = self.hp
        
        if damage > 0:
            self.hp -= damage
            message(self.owner.name.capitalize() + ' gets ' + str(damage) + ' damage.', 'red', get_identity(self.owner))
       
        if self.hp < start:
            pass#fight_effect(self.owner.x, self.owner.y, 'red', '/')
        else:
            message('No damage done.', 'grey', get_identity(self.owner))
            #fight_effect(self.owner.x, self.owner.y, 'grey', self.owner.char)
        
        #check for death. if there's a death function, call it
        if self.hp <= 0:
            self.hp = 0
            function = self.death_function
            if function is not None:
                function(self.owner)
        
    def heal(self, amount):
        #heal by the given amount, without going over the maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp
            

class Monster:
    #combat-related properties and methods (monster, player, NPC).
    def __init__(self, wit, strength, spirit, organs=[], limbs=[], moves=[], death_function=None):
        
        self.base_wit = wit
        self.base_strength = strength
        self.base_spirit = spirit
        
        self.base_hp = libtcod.random_get_int(0,25,40)
        self.hp = self.base_hp
        
        self.organs = organs
        self.limbs = limbs
        self.moves = moves
        
        self.death_function = death_function

    @property
    def max_hp(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = 0 #sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_hp
        
    @property
    def armor(self):  #return actual defense, by summing up the bonuses from all equipped items
        bonus = 0 #sum(equipment.armor_bonus for equipment in get_all_equipped(self.owner))
        return bonus

    @property
    def wit(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(part.wit_bonus for part in self.organs)
        return self.base_wit + bonus
        
    @property
    def str(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(part.strength_bonus for part in self.organs)
        return  self.base_strength + bonus
        
    @property
    def spirit(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(part.spirit_bonus for part in self.organs)
        return self.base_spirit + bonus
    
    def attack(self, target):
        #combat system was changed to deterministic, at and pa were commented out for time being
        
        message(self.owner.name.capitalize() + ' hits ' + target.name + '.', get_identity(self.owner))
        
        do_damage(target, self.damage, 0)
    
    def take_damage(self, damage, fire_damage): 
        #apply damage if possible
        damage = int(round(damage))
        damage -= self.armor
        
        start = self.hp
        
        if damage > 0:
            self.hp -= damage
            message(self.owner.name.capitalize() + ' gets ' + str(damage) + ' damage.', 'red', get_identity(self.owner))
       
        if self.hp < start:
            pass#fight_effect(self.owner.x, self.owner.y, 'red', '/')
        else:
            message('No damage done.', 'grey', get_identity(self.owner))
            #fight_effect(self.owner.x, self.owner.y, 'grey', self.owner.char)
        
        #check for death. if there's a death function, call it
        if self.hp <= 0:
            self.hp = 0
            function = self.death_function
            if function is not None:
                function(self.owner)
        
    def heal(self, amount):
        #heal by the given amount, without going over the maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp
            
            
class PlayerAI:
    '''Is actually the one who plays TPB. Needed to be scheduled. Takes keyboard input and calls handle_keys
    Renders screen and exits game, kind of the actual main loop together with play_game.
    '''
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.ticker.schedule_turn(self.speed, self)
        
    def take_turn(self):
        '''called by scheduler on the players turn, contains the quasi main loop'''
        global key, mouse, fov_recompute
        action_speed = self.speed
        
        while True:
            key = T.read()
            
            player_action = handle_keys()
            
            render_all()
            T.refresh()
            
            if player_action == 'exit' or game_state == 'exit':
                break
                main_menu()
            
            if player_action != 'didnt-take-turn':
                fov_recompute = True
                break
            
        self.ticker.schedule_turn(action_speed, self)
            

class Sword:
    def __init__(self, ticker, speed, max_cooldown = 100):
        self.ticker = ticker
        self.speed = 1
        self.cooldown = 0
        self.max_cooldown = 150
        self.ticker.schedule_turn(self.speed, self)
        
    def take_turn(self):      
        if self.cooldown == self.max_cooldown:
            return self.ticker.schedule_turn(self.speed, self)
            
        self.cooldown += 1
        self.ticker.schedule_turn(self.speed, self)
        
    def do(self,dx,dy):
        if self.cooldown < self.max_cooldown:
            return
        
        #the coordinates the player is moving to/attacking
        s = player.x + dx
        p = player.y + dy
        x = player.x + 2*dx
        y = player.y + 2*dy
        x1 = player.x + 3*dx
        y1 = player.y + 3*dy
        
        if check_direct(dx,dy) == 'up' or check_direct(dx,dy) == 'down':
            f = '|'
        else:
            f = '-'
        
        render_all()
        message('You attack with sword', 'light green', get_identity(self.owner))
        self.cooldown = 0
        T.print_(s,p, '[color=white]' + f)
        T.print_(x,y, '[color=white]x')
        T.print_(x1,y1, '[color=white]x')
        T.refresh()            
        T.delay(50) 
    
        #try to find an attackable object there
        target = None
        for object in objects[player.z]:
            if (object.fighter and object.x == x and object.y == y) or (object.fighter and object.x == x1 and object.y == y1):
                target = object
                break
        if target is not None:
            message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'light green', get_identity(self.owner))
            do_damage(target, 2, 0)
            
def get_relative_direct(dx, dy):
    if dx <= 0 and dy < 0:
        return 'up'
    elif dx < 0 and dy >= 0:
        return 'left'
    elif dx >= 0 and dy > 0:
        return 'down'
    elif dx > 0 and dy <= 0:
        return 'right'
    
def check_direct(dx,dy):
    if dx > 0 and dy == 0:
        return 'right'
    elif dx < 0 and dy == 0:
        return 'left'
    elif dx == 0 and dy < 0:
        return 'up'
    elif dx == 0 and dy > 0:
        return 'down'
            
class SwordStrong:
    def __init__(self, ticker, speed, max_cooldown = 100):
        self.ticker = ticker
        self.speed = 1
        self.cooldown = 0
        self.max_cooldown = 200
        self.busy = 0
        self.a = 0
        self.b = 0
        self.ticker.schedule_turn(self.speed, self)
        
    def take_turn(self):      
        if self.cooldown == self.max_cooldown:
            return self.ticker.schedule_turn(self.speed, self)
            
        if not self.busy:    
            self.cooldown += 1
            return self.ticker.schedule_turn(self.speed, self)
        
        self.up = [ (-1, -2), (0,-2), (1,-3), (0,-3), (0,-2), (0,-3), (0,-4) ]
        self.down = [ (1, 2), (0,2), (-1,3), (0,3), (0,2), (0,3), (0,4) ]
        self.left = [ (-2, 1), (-2,0), (-3,-1), (-3,0), (-2,0), (-3,0), (-4,0) ]
        self.right = [ (2, -1), (2,0), (3,1), (3,0), (2,0), (3,0), (4,0) ]
        
        if self.busy == 3:
            self.busy -= 1
            
            render_all()
            T.layer(7)
            message('You swipe with the sword', 'light green', get_identity(self.owner))
            
            for i in range(2):
                T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
                t = getattr(self, check_direct(self.a, self.b))
                (dx,dy) = t[i]
                x = player.x + dx
                y = player.y + dy
            
                if i == 0 and check_direct(self.a, self.b) == 'up':
                    T.print_(player.x-1,player.y-1, '[color=white]\\')
                elif i == 1 and check_direct(self.a, self.b) == 'up':
                    T.print_(player.x,player.y-1, '[color=white]|')
                
                if i == 0 and check_direct(self.a, self.b) == 'down':
                    T.print_(player.x+1,player.y+1, '[color=white]\\')
                elif i == 1 and check_direct(self.a, self.b) == 'down':
                    T.print_(player.x,player.y+1, '[color=white]|')
                    
                    
                if i == 0 and check_direct(self.a, self.b) == 'left':
                    T.print_(player.x-1,player.y+1, '[color=white]/')
                elif i == 1 and check_direct(self.a, self.b) == 'left':
                    T.print_(player.x-1,player.y, '[color=white]-')
                    
                if i == 0 and check_direct(self.a, self.b) == 'right':
                    T.print_(player.x+1,player.y-1, '[color=white]/')
                elif i == 1 and check_direct(self.a, self.b) == 'right':
                    T.print_(player.x+1,player.y, '[color=white]-')
            
            
                T.print_(x,y, '[color=white]x')
                T.refresh()            
                T.delay(80) 
                
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == x and object.y == y:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, 2, 0)
            
            return self.ticker.schedule_turn(10, self)
        elif self.busy == 2:
            self.busy -= 1
            
            render_all()
            T.layer(7)
            message('You swipe with the sword', 'light green', get_identity(self.owner))
            
            for i in range(2):
                T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
                t = getattr(self, check_direct(self.a, self.b))
                (dx,dy) = t[i+2]
            
                x = player.x + dx
                y = player.y + dy
            
            
                if i == 0 and check_direct(self.a, self.b) == 'up':
                    T.print_(player.x+1,player.y-1, '[color=white]/')
                    T.print_(player.x+1,player.y-2, '[color=white]|')
                elif i == 1 and check_direct(self.a, self.b) == 'up':
                    T.print_(player.x,player.y-1, '[color=white]|')
                    T.print_(player.x,player.y-2, '[color=white]|')
                
                if i == 0 and check_direct(self.a, self.b) == 'down':
                    T.print_(player.x-1,player.y+1, '[color=white]/')
                    T.print_(player.x-1,player.y+2, '[color=white]|')
                elif i == 1 and check_direct(self.a, self.b) == 'down':
                    T.print_(player.x,player.y+1, '[color=white]|')
                    T.print_(player.x,player.y+2, '[color=white]|')
                    
                    
                if i == 0 and check_direct(self.a, self.b) == 'left':
                    T.print_(player.x-1,player.y-1, '[color=white]\\')
                    T.print_(player.x-2,player.y-1, '[color=white]-')
                elif i == 1 and check_direct(self.a, self.b) == 'left':
                    T.print_(player.x-1,player.y, '[color=white]-')
                    T.print_(player.x-2,player.y, '[color=white]-')
                    
                if i == 0 and check_direct(self.a, self.b) == 'right':
                    T.print_(player.x+1,player.y+1, '[color=white]\\')
                    T.print_(player.x+2,player.y+1, '[color=white]-')
                elif i == 1 and check_direct(self.a, self.b) == 'right':
                    T.print_(player.x+1,player.y, '[color=white]-')
                    T.print_(player.x+2,player.y, '[color=white]-')
            
            
                T.print_(x,y, '[color=white]x')
                T.refresh()            
                T.delay(100) 
        
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == x and object.y == y:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, 2, 0)
            
            return self.ticker.schedule_turn(10, self)
        
        elif self.busy == 1:
            self.busy -= 1
            
            render_all()
            message('You slash with the sword', 'light green', get_identity(self.owner))
            (dx,dy) = (self.a,self.b)
            s = player.x + dx
            p = player.y + dy
            x = player.x + 2*dx
            y = player.y + 2*dy
            x1 = player.x + 3*dx
            y1 = player.y + 3*dy
            x2 = player.x + 4*dx
            y2 = player.y + 4*dy
            
            if check_direct(dx,dy) == 'up' or check_direct(dx,dy) == 'down':
                f = '|'
            else:
                f = '-'
            
            T.print_(s,p, '[color=white]' + f)          
            T.print_(x,y, '[color=white]x')
            T.print_(x1,y1, '[color=white]x')
            T.print_(x2,y2, '[color=white]x')
            
            T.refresh()            
            T.delay(80) 

            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if (object.fighter and object.x == x and object.y == y) or (object.fighter and object.x == x1 and object.y == y1) or (object.fighter and object.x == x2 and object.y == y2):
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                do_damage(target, 2, 0)
        
            self.ticker.schedule_turn(10, self)
            
    def do(self,dx,dy):
        if self.cooldown < self.max_cooldown:
            return
        
        if self.busy == 0:
            self.busy = 3
            self.cooldown = 0
            self.a = dx
            self.b = dy

            
class Morningstar:
    def __init__(self, ticker, speed, max_cooldown = 100):
        self.ticker = ticker
        self.speed = 1
        self.cooldown = 0
        self.max_cooldown = 100
        self.max_cooldown = 100
        self.busy = 0
        self.a = 0
        self.b = 0
        self.ticker.schedule_turn(self.speed, self)
        
    def take_turn(self):      
        if self.cooldown == self.max_cooldown:
            return self.ticker.schedule_turn(self.speed, self)
            
        if not self.busy:    
            self.cooldown += 1
            return self.ticker.schedule_turn(self.speed, self)
        
        self.up = [ (-1, -1), (-1,-2), (-2,-2), (1,-1), (1,-2), (2,-2), (-1,0), (1,0) ]
        self.down = [ (1, 1), (1,2), (2,2), (-1,1), (-1,2), (-2,2), (1,0),(-1,0) ]
        self.left = [ (-1, 1), (-2,1), (-2,2), (-1,-1), (-2,-1), (-2,-2), (0,1), (0,-1) ]
        self.right = [ (1, -1), (2,-1), (2,-2), (1,1), (2,1), (2,2), (0,-1), (0,1) ]
        
        if self.busy == 3:
            self.busy -= 1
            message('You firmly grab the morningstar', 'light orange', get_identity(self.owner))
            return self.ticker.schedule_turn(10, self)
        
        if self.busy == 2:
            render_all()
            self.busy -= 1
            T.layer(7)
            message('You swipe with the morningstar', 'light orange', get_identity(self.owner))
            
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            t = getattr(self, check_direct(self.a, self.b))
            (dx,dy) = t[0]
            (da,db) = t[1]
            (ds,dp) = t[2]
                
            x = player.x + dx
            y = player.y + dy
            a = player.x + da
            b = player.y + db
            s = player.x + ds
            p = player.y + dp
        
            T.print_(x,y, '[color=white]x')
            T.print_(a,b, '[color=white]x')
            T.print_(s,p, '[color=white]x')
            T.refresh()            
            T.delay(80) 
        
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if (object.fighter and object.x == x and object.y == y) or (object.fighter and object.x == a and object.y == b) or (object.fighter and object.x == s and object.y == p):
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                do_damage(target, 5, 0)
        
            t = getattr(self, check_direct(self.a, self.b))
            (dx,dy) = t[6]
            message(self.owner.name + ' tumbles', 'light orange', get_identity(self.owner))
            self.owner.move_towards(player.x+dx, player.y+dy)
            
            
            return self.ticker.schedule_turn(10, self)
        
        elif self.busy == 1:
            render_all()
            self.busy -= 1
            T.layer(7)
            message('You swipe with the morningstar', 'light orange', get_identity(self.owner))
            
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            t = getattr(self, check_direct(self.a, self.b))
            (dx,dy) = t[3]
            (da,db) = t[4]
            (ds,dp) = t[5]
                
            x = player.x + dx
            y = player.y + dy
            a = player.x + da
            b = player.y + db
            s = player.x + ds
            p = player.y + dp
        
            T.print_(x,y, '[color=white]x')
            T.print_(a,b, '[color=white]x')
            T.print_(s,p, '[color=white]x')
            T.refresh()            
            T.delay(80) 
        
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if (object.fighter and object.x == x and object.y == y) or (object.fighter and object.x == a and object.y == b) or (object.fighter and object.x == s and object.y == p):
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                do_damage(target, 5, 0)
        
            t = getattr(self, check_direct(self.a, self.b))
            (dx,dy) = t[7]
            message(self.owner.name + ' tumbles', 'light orange', get_identity(self.owner))
            self.owner.move_towards(player.x+dx, player.y+dy)
            
            return self.ticker.schedule_turn(10, self)
            
    def do(self,dx,dy):
        if self.cooldown < self.max_cooldown:
            return
        
        if self.busy == 0:
            self.busy = 3
            self.cooldown = 0
            self.a = dx
            self.b = dy

class MorningstarStrong:
    def __init__(self, ticker, speed, max_cooldown = 100):
        self.ticker = ticker
        self.speed = 1
        self.cooldown = 0
        self.max_cooldown = 250
        self.busy = 0
        self.a = 0
        self.b = 0
        self.ticker.schedule_turn(self.speed, self)
        
    def take_turn(self):      
        if self.cooldown == self.max_cooldown:
            return self.ticker.schedule_turn(self.speed, self)
            
        if not self.busy:    
            self.cooldown += 1
            return self.ticker.schedule_turn(self.speed, self)
        
        if self.busy <= 5 and self.busy > 1:
            self.busy -= 1
            message('You charge up the morningstar', 'light orange', get_identity(self.owner))
            return self.ticker.schedule_turn(10, self)
        
        if self.busy == 1:
            self.busy -= 1
            T.layer(7)
            message('You smash the ground with the morningstar', 'light orange', get_identity(self.owner))
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            
            if check_direct(self.a,self.b) == 'up' or check_direct(self.a,self.b) == 'down':
                f = '|'
            else:
                f = '-'
                
            render_all()
            for i in plus_pattern + dot_pattern:
                x,y = player.x + 3*self.a + i[0], player.y + 3*self.b + i[1]
                
                T.print_(x, y, '[color=white]x')
                T.print_(player.x+self.a, player.y+self.b, '[color=white]' + f)
                
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == x and object.y == y:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, 5, 0)
                
            T.refresh()
            T.layer(0)            
            T.delay(200)    
            
                      
            return self.ticker.schedule_turn(self.speed, self)
            
    def do(self,dx,dy):
        if self.cooldown < self.max_cooldown:
            return
        
        if self.busy == 0:
            self.busy = 5
            self.cooldown = 0
            self.a = dx
            self.b = dy


class Spear:
    def __init__(self, ticker, speed, max_cooldown = 100):
        self.ticker = ticker
        self.speed = 1
        self.cooldown = 0
        self.max_cooldown = 200
        self.busy = 0
        self.a = 0
        self.b = 0
        self.ticker.schedule_turn(self.speed, self)
        
    def take_turn(self):      
        if self.cooldown == self.max_cooldown:
            return self.ticker.schedule_turn(self.speed, self)
            
        if not self.busy:    
            self.cooldown += 1
            return self.ticker.schedule_turn(self.speed, self)
        
        if self.busy == 2:
            self.busy -= 1
            
            message('You poke with the spear', 'light red', get_identity(self.owner))
            #the coordinates the player is moving to/attacking
            s,p = player.x + self.a, player.y + self.b
            x = player.x + 2*self.a
            y = player.y + 2*self.b
            x1 = player.x + 3*self.a
            y1 = player.y + 3*self.b
            
            if check_direct(self.a,self.b) == 'up' or check_direct(self.a,self.b) == 'down':
                f = '|'
            else:
                f = '-'
            
            render_all()
            T.print_(s,p, '[color=white]' + f)
            T.print_(x,y, '[color=white]x')
            T.print_(x1,y1, '[color=white]x')
            T.refresh()            
            T.delay(50) 
        
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if (object.fighter and object.x == x and object.y == y) or (object.fighter and object.x == x1 and object.y == y1):
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'light green', get_identity(self.owner))
                do_damage(target, 2, 0)
                
            return self.ticker.schedule_turn(10, self)
        
        elif self.busy == 1:
            self.busy -= 1
            message('You poke with the spear', 'light red', get_identity(self.owner))
            #the coordinates the player is moving to/attacking
            s,p = player.x + self.a, player.y + self.b
            s1,p1 = player.x + 2*self.a, player.y + 2*self.b
            s2,p2 = player.x + 3*self.a, player.y + 3*self.b
            x = player.x + 4*self.a
            y = player.y + 4*self.b
            x1 = player.x + 5*self.a
            y1 = player.y + 5*self.b
            
            if check_direct(self.a,self.b) == 'up' or check_direct(self.a,self.b) == 'down':
                f = '|'
            else:
                f = '-'
            
            render_all()
            T.print_(s,p, '[color=white]' + f)
            T.print_(s1,p1, '[color=white]' + f)
            T.print_(s2,p2, '[color=white]' + f)
            
            T.print_(x,y, '[color=white]x')
            T.print_(x1,y1, '[color=white]x')
            T.refresh()            
            T.delay(50) 
        
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if (object.fighter and object.x == x and object.y == y) or (object.fighter and object.x == x1 and object.y == y1):
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'light green', get_identity(self.owner))
                do_damage(target, 2, 0)
                
            return self.ticker.schedule_turn(10, self)
        
    def do(self,dx,dy):
        if self.cooldown < self.max_cooldown:
            return
        
        if self.busy == 0:
            self.busy = 2
            self.cooldown = 0
            self.a = dx
            self.b = dy

            

class SpearStrong:
    def __init__(self, ticker, speed, max_cooldown = 100):
        self.ticker = ticker
        self.speed = 1
        self.cooldown = 0
        self.max_cooldown = 200
        self.busy = 0
        self.a = 0
        self.b = 0
        self.ticker.schedule_turn(self.speed, self)
        
    def take_turn(self):      
        if self.cooldown == self.max_cooldown:
            return self.ticker.schedule_turn(self.speed, self)
            
        if not self.busy:    
            self.cooldown += 1
            return self.ticker.schedule_turn(self.speed, self)
        
        if self.busy > 0:
            self.busy -= 1
            
            message('You poke with the spear', 'light red', get_identity(self.owner))
            #the coordinates the player is moving to/attacking
            x = player.x + self.a
            y = player.y + self.b
            
            message('You leap forward', 'green', get_identity(self.owner))
            self.owner.move_towards(x, y)
            
            x = player.x + self.a
            y = player.y + self.b
            
            render_all()
            T.print_(x, y, '[color=white]x')
            T.refresh()            
            T.delay(50) 
        
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if object.fighter and object.x == x and object.y == y:
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'light green', get_identity(self.owner))
                do_damage(target, 2, 0)
                
            return self.ticker.schedule_turn(4, self)
        
    def do(self,dx,dy):
        if self.cooldown < self.max_cooldown:
            return
        
        if self.busy == 0:
            self.busy = 5
            self.cooldown = 0
            self.a = dx
            self.b = dy

            
class Dagger:
    def __init__(self, ticker, speed, max_cooldown = 100):
        self.ticker = ticker
        self.speed = 1
        self.cooldown = 0
        self.max_cooldown = 40
        self.ticker.schedule_turn(self.speed, self)
        
    def take_turn(self):      
        if self.cooldown == self.max_cooldown:
            return self.ticker.schedule_turn(self.speed, self)
            
        self.cooldown += 1
        self.ticker.schedule_turn(self.speed, self)
        
    def do(self,dx,dy):
        if self.cooldown < self.max_cooldown:
            return
        
        if dx == 0 and dy == 1:
            da,db = 1,1
        elif dx == 0 and dy == -1:
            da,db = -1,-1
        elif dx == 1 and dy == 0:
            da,db = 1,-1
        elif dx == -1 and dy == 0:
            da,db = -1,1
        
        #the coordinates the player is moving to/attacking
        x = player.x + dx
        y = player.y + dy
        a = player.x + da
        b = player.y + db
        render_all()
        message('You attack with dagger', 'green', get_identity(self.owner))
        self.cooldown = 0
        T.print_(x,y, '[color=white]x')
        T.print_(a,b, '[color=white]x')
        T.refresh()            
        T.delay(50) 
    
        #try to find an attackable object there
        target = None
        for object in objects[player.z]:
            if (object.fighter and object.x == x and object.y == y) or (object.fighter and object.x == a and object.y == b):
                target = object
                break
        if target is not None:
            message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
            do_damage(target, 2, 0)

class DaggerStrong:
    def __init__(self, ticker, speed, max_cooldown = 100):
        self.ticker = ticker
        self.speed = 1
        self.cooldown = 0
        self.max_cooldown = 150
        self.busy = 0
        self.a = 0
        self.b = 0
        self.ticker.schedule_turn(self.speed, self)
        
    def take_turn(self):      
        if self.cooldown == self.max_cooldown:
            return self.ticker.schedule_turn(self.speed, self)
            
        if not self.busy:    
            self.cooldown += 1
            return self.ticker.schedule_turn(self.speed, self)
        
        if self.busy %2 == 0:
            self.busy -= 1
            
            #render_all()
            #message('You grab the dagger', 'green', get_identity(self.owner))
            message('You leap forward', 'green', get_identity(self.owner))
            message('You leap forward', 'green', get_identity(self.owner))
            self.owner.move_towards(player.x + self.a, player.y + self.b)
            self.owner.move_towards(player.x + self.a, player.y + self.b)
            
            self.ticker.schedule_turn(3, self)
        elif self.busy % 2 != 0:
            self.busy -= 1

            x = player.x + self.a
            y = player.y + self.b
            
            render_all()
            message('You stab with your dagger', 'green', get_identity(self.owner))
            
            T.print_(x,y, '[color=white]x')
            T.refresh()            
            T.delay(50) 
    
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if object.fighter and object.x == x and object.y == y:
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                do_damage(target, 2, 0)

            self.ticker.schedule_turn(3, self)
                       
    def do(self,dx,dy):
        if self.cooldown < self.max_cooldown:
            return
        
        if self.busy == 0:
            self.busy = 2
            self.cooldown = 0
            self.a = dx
            self.b = dy

            
class CautiousLegs:
    '''AI for a basic monster. Schedules the turn depending on speed and decides whether to move or attack.
    Owned by all monsters apart from bosses.
    '''
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.name = 'chicke legs'
        self.desc = 'the legs of a bird'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        '''checks whether monster and player are still alive, decides on move or attack'''
        #a basic monster takes its turn.
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
        
        #move towards player if far away
        if int(monster.distance_to(player)) >= 3:
            (x,y) = monster.x, monster.y
            monster.move_towards(player.x, player.y)
            render_all()
            T.refresh()
            T.delay(50)
            if monster.x == x and monster.y == y: #not moved?
                monster.move(libtcod.random_get_int(0,-1,1), libtcod.random_get_int(0,-1,1)) #try again randomly
           
        elif int(monster.distance_to(player)) < 3:
            monster.move_away_from(player.x, player.y)
        
        message(monster.name + ' moves cautiously', 'white', get_identity(monster))
        
        
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)      

              
class NormalLegs:
    '''AI for a basic monster. Schedules the turn depending on speed and decides whether to move or attack.
    Owned by all monsters apart from bosses.
    '''
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.name = 'human legs'
        self.desc = 'human legs'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        '''checks whether monster and player are still alive, decides on move or attack'''
        #a basic monster takes its turn.
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
        
        #move towards player if far away
        if int(monster.distance_to(player)) >= 1:
            (x,y) = monster.x, monster.y
            monster.move_towards(player.x, player.y)
            render_all()
            T.refresh()
            T.delay(50)
            if monster.x == x and monster.y == y: #not moved?
                monster.move(libtcod.random_get_int(0,-1,1), libtcod.random_get_int(0,-1,1)) #try again randomly
            
            message(monster.name + ' moves', 'white', get_identity(monster))
        
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)     
        

              
class Flee:
    '''AI for a basic monster. Schedules the turn depending on speed and decides whether to move or attack.
    Owned by all monsters apart from bosses.
    '''
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.name = 'lizard legs'
        self.desc = 'lizard legs'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        '''checks whether monster and player are still alive, decides on move or attack'''
        #a basic monster takes its turn.
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
        
        #move towards player if far away
        (x,y) = monster.x, monster.y
        monster.move_away_from(player.x, player.y)
        render_all()
        T.refresh()
        T.delay(50)
        if monster.x == x and monster.y == y: #not moved?
            monster.move(libtcod.random_get_int(0,-1,1), libtcod.random_get_int(0,-1,1)) #try again randomly
        
        message(monster.name + ' moves backwards', 'white', get_identity(monster))
    
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)     
             
   
class BonusBodypart:
    #all parts that give bonuses to the base attributes
    def __init__(self, name, desc, wit_bonus=0, strength_bonus=0, spirit_bonus=0):
        self.name = name
        self.desc = desc
        self.wit_bonus = wit_bonus
        self.strength_bonus = strength_bonus
        self.spirit_bonus = spirit_bonus
   

class FrogLegs: #movement class for monster
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = 100
        self.name = 'frog legs'
        self.desc = 'giant legs of a frog' 
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        message(monster.name + ' leaps with its frog legs', 'green', get_identity(monster))
        x,y = player.x, player.y #store player position
        monster.move_towards(x,y)
        monster.move_towards(x,y)
    
        self.ticker.schedule_turn(self.speed, self)      


class BatWings: #movement class for monster
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = 100
        self.busy = 0
        self.name = 'bat wings'
        self.desc = 'rotten skinny wings like a bat' 
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
        
        if self.busy == 0:
            self.busy = 3
            return self.ticker.schedule_turn(self.speed, self)      
        elif self.busy != 0:
            self.busy -= 1
            dx = libtcod.random_get_int(0,-3,4)
            dy = libtcod.random_get_int(0,-3,4)
            message('Monster flaps with bat wings', 'grey', get_identity(monster))        
            monster.move_towards(monster.x+dx, monster.y+dy)
            return self.ticker.schedule_turn(10, self)

# class Swipe:
    # def __init__(self, ticker, speed):
        # self.ticker = ticker
        # self.speed = speed
        # self.ticker.schedule_turn(self.speed, self)
    
    # def take_turn(self):
        # monster = self.owner
        
        # if not monster.fighter: #most likely because monster is dead
            # return
        # #stop when the player is already dead
        # if game_state == 'dead':
            # return
        
        # #wait if player on different floor 
        # if monster.z != player.z:
            # self.ticker.schedule_turn(self.speed, self)            
            # return
    
        # dx = self.owner.x - player.x
        # dy = self.owner.y - player.y
        
        # range = 3
        # matrix = [ (-3,-1), (-3,0), (-3,1) ]
        
        # alpha = math.atan2(dy,dx)
        

        # matrix2 = [
        
        # turn_point(matrix[0][0], matrix[0][1], alpha),
        # turn_point(matrix[1][0], matrix[1][1], alpha),
        # turn_point(matrix[2][0], matrix[2][1], alpha)
        
        # ]
        
        
        # for i in matrix2:
            # T.layer(3)
            # T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            # T.print_(monster.x+i[0], monster.y+i[1], '[color=white]q')
            # T.refresh()
            # T.layer(0)            
            # T.delay(150)
            
        # message('Swipe', 'white', get_identity(monster))
            
        
        
        # #schedule next turn
        # self.ticker.schedule_turn(self.speed, self)      

class IronFist:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = 200
        self.telegraph = True
        self.a = 0
        self.b = 0
        self.name = 'brutal fist'
        self.desc = 'an iron fist'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        
        if self.telegraph:
            message(monster.name + ' raises the iron fist', 'red', get_identity(monster))
            self.telegraph = not self.telegraph
            self.a, self.b = player.x, player.y
            return self.ticker.schedule_turn(30, self)

        if monster.distance_to(player) > 8:
            
            self.telegraph = not self.telegraph    
            
            message('It relaxes his fist', 'red', get_identity(monster))
        
            #schedule next turn
            self.ticker.schedule_turn(self.speed, self)
            return
        
        message('It smashes the iron fist to the ground', 'red', get_identity(monster))
        
        render_all()
        for i in diamond_pattern:
            x,y = self.a + i[0], self.b + i[1]
            T.print_(x, y, '[color=red]x')
            
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if object.fighter and object.x == x and object.y == y and object != self.owner:
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                do_damage(target, monster.fighter.str*2, 0)
            
        T.refresh()
        T.layer(0)            
        T.delay(200)    
        
         
        self.telegraph = not self.telegraph    
        
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)      
        
        
class SpikedClub:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.telegraph = True
        self.name = 'spiked club'
        self.desc = 'a spiked club in hand'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        
        if self.telegraph:
            message(monster.name + ' focusses on you', 'light red', get_identity(monster))
            self.telegraph = not self.telegraph
            
            return self.ticker.schedule_turn(self.speed, self)
        
        #making longer line. When player is too close, it gets counted over the player coordinates
        dx = player.x - self.owner.x
        dy = player.y - self.owner.y
        
        message(monster.name + ' smashes the club', 'light red', get_identity(monster))
        libtcod.line_init(self.owner.x, self.owner.y, player.x+4*dx, player.y+4*dy)
        range = 0
        while True:
            (a, b) = libtcod.line_step()
            T.layer(3)
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            if not a: 
                break
            
            if range == 4:
                #monster.move_towards(player.x, player.y)
                #monster.move_towards(player.x, player.y)
                
                render_all()
                for i in plus_pattern + [(0,0)]:
                    T.print_(a + i[0], b + i[1], '[color=light red]x')
                    #try to find an attackable object there
                    target = None
                    for object in objects[player.z]:
                        if object.fighter and object.x == a+i[0] and object.y == b+i[1] and object != self.owner:
                            target = object
                            break
                    if target is not None:
                        message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                        do_damage(target, monster.fighter.str, 0)
                    
                T.refresh()
                T.layer(0)            
                T.delay(100)    
                break
            
            range += 1
        self.telegraph = not self.telegraph    
        
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)      
        

class Circle1: #movement
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.reach = 20
        self.intervall = 50
        self.a = 0
        self.b = 0
        self.name = 'legs of a goat, the left one crippled'
        self.desc = 'legs of a goat, the left one crooked'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        if self.reach <= 20 and self.reach > 15: #sequence up
            i = monster.x
            j = monster.y
            self.a = monster.x + 0
            self.b = monster.y - 1
            monster.move_towards(self.a,self.b)
            
            if i == monster.x and j == monster.y: #did it move? if not go to next sequence
                self.reach = 15
            else:
                self.reach -= 1
            message(monster.name + ' moves', 'lighter blue', get_identity(monster))
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach <= 15 and self.reach > 10:
            i = monster.x
            j = monster.y
            self.a = monster.x - 1
            self.b = monster.y + 0
            monster.move_towards(self.a,self.b)
            
            if i == monster.x and j == monster.y: #did it move? if not go to next sequence
                self.reach = 10
            else:
                self.reach -= 1
            message(monster.name + ' moves', 'lighter blue', get_identity(monster))
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach <= 10 and self.reach > 5:
            i = monster.x
            j = monster.y
            self.a = monster.x
            self.b = monster.y + 1
            monster.move_towards(self.a,self.b)
            
            if i == monster.x and j == monster.y: #did it move? if not go to next sequence
                self.reach = 5
            else:
                self.reach -= 1
            message(monster.name + ' moves', 'lighter blue', get_identity(monster))
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach <= 5 and self.reach > 0:
            i = monster.x
            j = monster.y
            self.a = monster.x + 1
            self.b = monster.y + 0
            monster.move_towards(self.a,self.b)
            
            if i == monster.x and j == monster.y: #did it move? if not go to next sequence
                self.reach = 0
            else:
                self.reach -= 1
            message(monster.name + ' moves', 'lighter blue', get_identity(monster))
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach == 0:
            self.reach = 20
        
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)      
        

class Circle2: #movement
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.reach = 20
        self.intervall = 70
        self.a = 0
        self.b = 0
        self.name = 'legs of a goat, the right one crippled'
        self.desc = 'legs of a goat, the right one crooked'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        if self.reach <= 20 and self.reach > 15: #sequence up
            i = monster.x
            j = monster.y
            self.a = monster.x + 0
            self.b = monster.y + 1
            monster.move_towards(self.a,self.b)
            
            if i == monster.x and j == monster.y: #did it move? if not go to next sequence
                self.reach = 15
            else:
                self.reach -= 1
            message(monster.name + ' moves', 'lighter blue', get_identity(monster))
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach <= 15 and self.reach > 10:
            i = monster.x
            j = monster.y
            self.a = monster.x - 1
            self.b = monster.y + 0
            monster.move_towards(self.a,self.b)
            
            if i == monster.x and j == monster.y: #did it move? if not go to next sequence
                self.reach = 10
            else:
                self.reach -= 1
            message(monster.name + ' moves', 'lighter blue', get_identity(monster))
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach <= 10 and self.reach > 5:
            i = monster.x
            j = monster.y
            self.a = monster.x
            self.b = monster.y - 1
            monster.move_towards(self.a,self.b)
            
            if i == monster.x and j == monster.y: #did it move? if not go to next sequence
                self.reach = 5
            else:
                self.reach -= 1
            message(monster.name + ' moves', 'lighter blue', get_identity(monster))
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach <= 5 and self.reach > 0:
            i = monster.x
            j = monster.y
            self.a = monster.x + 1
            self.b = monster.y + 0
            monster.move_towards(self.a,self.b)
            
            if i == monster.x and j == monster.y: #did it move? if not go to next sequence
                self.reach = 0
            else:
                self.reach -= 1
            message(monster.name + ' moves', 'lighter blue', get_identity(monster))
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach == 0:
            self.reach = 20
        
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)      
        
 
class Charge: #movement
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.reach = 5
        self.intervall = 10
        self.a = 0
        self.b = 0
        self.name = 'legs of a bull'
        self.desc = 'legs of a bull'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        if self.reach == 5: #beginning of sequence
            dx = player.x - self.owner.x
            dy = player.y - self.owner.y
            
            self.a,self.b = player.x+4*dx, player.y+4*dy #store player position
            
            monster.move_towards(self.a,self.b)
            self.reach -= 1
            message('It charges', 'blue', get_identity(monster))
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach < 5 and self.reach != 0:
            monster.move_towards(self.a,self.b)
            self.reach -= 1
            message('It charges', 'blue', get_identity(monster))
            return self.ticker.schedule_turn(self.intervall, self)
        
        if self.reach == 0:
            self.reach = 5
            message('It breathes', 'blue', get_identity(monster))
            return self.ticker.schedule_turn(self.speed, self)
        
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)      
        

class Charge2: #movement
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.reach = 5
        self.intervall = 20
        self.a = 0
        self.b = 0
        self.name = 'legs of a cow'
        self.desc = 'legs of a cow'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        if self.reach == 5: #beginning of sequence
            self.a,self.b = player.x, player.y #store player position
            
            monster.move_towards(self.a,self.b)
            self.reach -= 1
            message('It charges', 'blue', get_identity(monster))
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach < 5 and self.reach != 0:
            monster.move_towards(self.a,self.b)
            self.reach -= 1
            message('It charges', 'blue', get_identity(monster))
            
            if monster.x == self.a and monster.y == self.b:
                self.reach = 0
            return self.ticker.schedule_turn(self.intervall, self)
        
        if self.reach == 0:
            self.reach = 5
            message('It breathes', 'blue', get_identity(monster))
            return self.ticker.schedule_turn(self.speed, self)
        
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)      
        
        
class Tentacle:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.reach = 4
        self.intervall = speed
        self.a = 0
        self.b = 0
        self.name = 'tentacle'
        self.desc = 'a slimy tentacle'
        #self.ticker.schedule_turn(self.speed, self)
        self.list = [
        
        [ (-2,-1), (-2,-2), (-1,-2) ],
        [ (1,-2), (2,-2), (2,-1) ],
        [ (1,2), (2,2), (2,1) ],
        [ (-1,2), (-2,2), (-2,1) ]
        
        ]
        
        random.shuffle(self.list)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        
        if self.reach <= 4 and self.reach != 0: #beginning of sequence
            
            render_all()
            T.layer(7)
            message(monster.name + ' swipes with a tentacle', 'dark green', get_identity(self.owner))
            
            for i in range(3):    
                T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
                (dx,dy) = self.list[self.reach-1][i]
                x = monster.x + dx
                y = monster.y + dy
            
                T.print_(x,y, '[color=dark green]x')
                T.refresh()            
                T.delay(200) 
                
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == x and object.y == y:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, monster.fighter.spirit, 0)
            
            self.reach -= 1
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach == 0:
            self.reach = 4
            return self.ticker.schedule_turn(self.speed, self)
        
class FieryBreath:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.reach = 3
        self.intervall = 25
        self.a = 0
        self.b = 0
        self.c = 0
        self.name = 'fiery breath'
        self.desc = 'a gland for fire breathing'
        #self.ticker.schedule_turn(self.speed, self)
        
        self.coord = {
        
        'up': [(0,-2), (-1,-3), (0,-3), (1,-3), (-2,-4), (-1,-4), (0,-4), (1,-4), (2,-4) ],
        'down': [(0,2), (-1,3), (0,3), (1,3), (-2,4), (-1,4), (0,4), (1,4), (2,4) ],
        'right': [(2,0), (3,-1), (3,0), (3,1), (4,-2), (4,-1), (4,0), (4,1), (4,2) ],
        'left': [(-2,0), (-3,-1), (-3,0), (-3,1), (-4,-2), (-4,-1), (-4,0), (-4,1), (-4,2) ]
        
        }
        
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        
        if self.reach == 3: #beginning of sequence
            self.a = monster.x
            self.b = monster.y
            
            self.dx = player.x - self.owner.x
            self.dy = player.y - self.owner.y
    
            self.c = get_relative_direct(self.dx,self.dy)
            if self.c == 'up':
                dk, dl = 0,-1
            elif self.c == 'down':
                dk, dl = 0,1
            elif self.c == 'left':
                dk, dl = -1,0
            elif self.c == 'right':
                dk, dl = 1,0
            
            render_all()
            T.layer(7)
            message(monster.name + ' breathes fire', 'dark red', get_identity(self.owner))
            
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            (dx,dy) = self.coord[self.c][0]
            x = self.a + dx
            y = self.b + dy
            k = self.a + dk
            l = self.b + dl
        
            T.print_(x,y, '[color=dark red]x')
            T.print_(k,l, '[color=dark red]x')
            T.refresh()            
            T.delay(200) 
            
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if (object.fighter and object.x == x and object.y == y) or (object.fighter and object.x == k and object.y == l):
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                do_damage(target, monster.fighter.spirit, 0)
        
            self.reach -= 1
            return self.ticker.schedule_turn(self.intervall, self)      
        
        
        if self.reach == 2: #beginning of sequence
            
            render_all()
            T.layer(7)
            
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            for i in range(3):
                (dx,dy) = self.coord[self.c][i+1]
                x = self.a + dx
                y = self.b + dy
                T.print_(x,y, '[color=dark red]x')
                
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == x and object.y == y:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, monster.fighter.spirit, 0)
                
            T.refresh()            
            T.delay(200) 
            
            self.reach -= 1
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach == 1: #beginning of sequence
            render_all()
            T.layer(7)
            
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            for i in range(5):
                (dx,dy) = self.coord[self.c][i+4]
                x = self.a + dx
                y = self.b + dy
                T.print_(x,y, '[color=dark red]x')
                
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == x and object.y == y:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, monster.fighter.spirit, 0)
                
            T.refresh()            
            T.delay(200) 
            
            self.reach -= 1
            return self.ticker.schedule_turn(self.intervall, self)      

        
        if self.reach == 0:
            self.reach = 3
            return self.ticker.schedule_turn(self.speed, self)
        

class Tail:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.reach = 4
        self.intervall = speed
        self.a = 0
        self.b = 0
        self.name = 'tail'
        self.desc = 'a tail like a whip'
        #self.ticker.schedule_turn(self.speed, self)
        self.list = [
        
        [ (-2,0), (-3,0) ],
        [ (2,0), (3,0) ],
        [ (0,2), (0,3) ],
        [ (0,-2), (0,-3) ]
        
        ]
        
        random.shuffle(self.list)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
     
        render_all()
        T.layer(7)
        message(monster.name + ' whips his tail', 'light grey', get_identity(self.owner))
        
        T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
        (dx,dy) = self.list[0][0]
        (da,db) = self.list[0][1]
        x = monster.x + dx
        y = monster.y + dy
        a = monster.x + da
        b = monster.y + db
    
        T.print_(x,y, '[color=light grey]x')
        T.print_(a,b, '[color=light grey]x')
        
        #try to find an attackable object there
        target = None
        for object in objects[player.z]:
            if (object.fighter and object.x == x and object.y == y) or (object.fighter and object.x == a and object.y == b):
                target = object
                break
        if target is not None:
            message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
            do_damage(target, monster.fighter.spirit, 0)
        T.refresh()            
        T.delay(150) 
        

        self.ticker.schedule_turn(self.speed, self)      
    
        
        
class FatBackside: 
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.intervall = 70
        self.telegraph = True
        self.name = 'fat backside'
        self.desc = 'a fat backside'
        #self.ticker.schedule_turn(self.speed, self)
        
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        if self.telegraph:
            message(monster.name + ' jumps in the air', 'dark orange', get_identity(self.owner))
            self.telegraph = not self.telegraph
            return self.ticker.schedule_turn(self.intervall, self)

        render_all()
        message(monster.name + ' shakes the ground', 'dark orange', get_identity(self.owner))
        T.layer(7)
        T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
        for i in hole_diamond_pattern:
            x = monster.x + i[0]
            y = monster.y + i[1]
            T.print_(x, y, '[color=dark orange]x')
            
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if object.fighter and object.x == x and object.y == y and object != self.owner:
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                do_damage(target, monster.fighter.str, 0)
            
        T.refresh()
        T.layer(0)            
        T.delay(300)    
         
        self.telegraph = not self.telegraph    
        
        self.ticker.schedule_turn(self.speed, self)      
        
        
class ClawBlade:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.reach = 5
        self.intervall = 10
        self.a = 0
        self.b = 0
        self.dx = 0
        self.dy = 0
        self.name = 'claw'
        self.desc = 'a razor sharp claw'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        self.up = [ (-1, -2), (0,-2), (1,-2) ]
        self.down = [ (1, 2), (0,2), (-1,2) ]
        self.left = [ (-2, 1), (-2,0), (-2,-1) ]
        self.right = [ (2, -1), (2,0), (2,1) ]
        
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
            
        if self.reach == 5:
            self.dx = player.x - self.owner.x
            self.dy = player.y - self.owner.y
    
        if self.reach <= 5 and self.reach != 0:
            
            c = get_relative_direct(self.dx,self.dy)
            if c == 'up':
                self.a, self.b = 0,-1
            elif c == 'down':
                self.a, self.b = 0,1
            elif c == 'left':
                self.a, self.b = -1,0
            elif c == 'right':
                self.a, self.b = 1,0

            monster.move_towards(monster.x+self.a,monster.y+self.b)
            self.reach -= 1
            message('It charges and swipes the claw', 'grey', get_identity(monster))
            
            render_all()
            T.layer(7)
            
            for i in range(3):
                T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
                t = getattr(self, get_relative_direct(self.dx,self.dy))
                (da,db) = t[i]
                x = monster.x + da
                y = monster.y + db
            
                T.print_(x,y, '[color=grey]x')
                T.refresh()            
                T.delay(80) 
                
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == x and object.y == y:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, monster.fighter.str, 0)
            
            return self.ticker.schedule_turn(self.intervall, self)      
        
        # if self.reach < 5 and self.reach != 0:
            # dx = player.x - self.owner.x
            # dy = player.y - self.owner.y
            
            # c = get_relative_direct(dx,dy)
            # if c == 'up':
                # self.a, self.b = 0,-1
            # elif c == 'down':
                # self.a, self.b = 0,1
            # elif c == 'left':
                # self.a, self.b = -1,0
            # elif c == 'right':
                # self.a, self.b = 1,0

            # monster.move_towards(monster.x+self.a,monster.y+self.b)
            # self.reach -= 1
            # message('Monster charges', 'blue', get_identity(monster))
            
            # # + attack!
            
            # return self.ticker.schedule_turn(self.intervall, self)
        
        if self.reach == 0:
            self.reach = 5
            message('It breathes', 'grey', get_identity(monster))
            return self.ticker.schedule_turn(self.speed, self)
    

class TripleStomp:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.reach = 4
        self.intervall = 30
        self.a = 0
        self.b = 0
        self.dx = 0
        self.dy = 0
        self.name = '3stomp'
        self.desc = 'three arms on the chest'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        self.up = [ (-2, -2), (2,-2), (0,-3) ]
        self.down = [ (-2, 2), (2,2), (0,3) ]
        self.left = [ (-2, 2), (-2,-2), (-3,0) ]
        self.right = [ (2, -2), (2,2), (3,0) ]
        
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
            
        
        if self.reach == 4:
            message(self.owner.name + "'s three arms wave!", 'light blue', get_identity(monster))            
            self.reach -= 1
            return self.ticker.schedule_turn(self.intervall, self)      
        
        if self.reach == 3:
            self.dx = player.x - self.owner.x
            self.dy = player.y - self.owner.y
            
            self.reach -= 1
            message('1st arm smashes', 'light blue', get_identity(monster))
                   
            c = get_relative_direct(self.dx,self.dy)
            self.a,self.b = getattr(self, c)[0]
            
            render_all()
            for i in diamond_pattern:
                x,y = monster.x + self.a + i[0], monster.y + self.b + i[1]
                T.print_(x, y, '[color=light blue]x')
                
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == x and object.y == y and object != self.owner:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, monster.fighter.str, 0)
                
            T.refresh()
            T.layer(0)            
            T.delay(200)    
            return self.ticker.schedule_turn(self.intervall, self)      
        
        
        if self.reach == 2:
            self.reach -= 1
            message('2nd arm smashes', 'light blue', get_identity(monster))
                   
            c = get_relative_direct(self.dx,self.dy)
            
            self.a,self.b = getattr(self, c)[1]
            
            render_all()
            for i in diamond_pattern:
                x,y = monster.x + self.a + i[0], monster.y + self.b + i[1]
                T.print_(x, y, '[color=light blue]x')
                
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == x and object.y == y and object != self.owner:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, monster.fighter.str, 0)
                
            T.refresh()
            T.layer(0)            
            T.delay(200)    
            return self.ticker.schedule_turn(self.intervall, self)      
        
        
        if self.reach == 1:
            self.reach -= 1
            message('3rd arm smashes', 'light blue', get_identity(monster))
                   
            c = get_relative_direct(self.dx,self.dy)
            
            self.a,self.b = getattr(self, c)[2]
            
            render_all()
            for i in diamond_pattern:
                x,y = monster.x + self.a + i[0], monster.y + self.b + i[1]
                T.print_(x, y, '[color=light blue]x')
                
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == x and object.y == y and object != self.owner:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, monster.fighter.str, 0)
                
            T.refresh()
            T.layer(0)            
            T.delay(200)    
            return self.ticker.schedule_turn(self.intervall, self)      
        
        
        if self.reach == 0:
            self.reach = 4
            #message('Monster breathes', 'blue', get_identity(monster))
            return self.ticker.schedule_turn(self.speed, self)
        
class RabbitTeeth:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.reach = 2
        self.intervall = 10
        self.a = 0
        self.b = 0
        self.name = 'rabbit teeth'
        self.desc = 'rabbit teeth'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        if self.reach > 0: #beginning of sequence    
            self.reach -= 1
            render_all()
            libtcod.line_init(self.owner.x, self.owner.y, player.x, player.y)
            range = 0
            while True:
                (a, b) = libtcod.line_step()
                T.layer(3)
                T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
                T.print_(a, b, '[color=yellow]x')
                if range == 1:
                    break
                if not a: 
                    break
                T.refresh()
                T.layer(0)            
                message(self.owner.name + ' bites with his rabbit teeth', 'yellow', get_identity(monster))
                
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == a and object.y == b:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, int(self.owner.fighter.str), 0)

                T.delay(50)
                range += 1
            return self.ticker.schedule_turn(self.intervall, self)
        
        else:
            self.reach = 2
            return self.ticker.schedule_turn(self.speed, self)
        
        
class PlayerCharge: #movement

    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = 200
        self.reach = 5
        self.a = 0
        self.b = 0
        self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        global key, mouse, fov_recompute
        monster = self.owner
        action_speed = self.speed
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        if self.reach != 5:
            return self.charge()
        
        message_sys('Use your Charge with Shift+Direction or wait with a', 'green')
        
        while True:
            key = T.read()
            
            player_action = action_keys()
            
            render_all()
            T.refresh()
            
            # if player_action == 'exit' or game_state == 'exit':
                # break
                # main_menu()
            
            # if player_action != 'didnt-take-turn':
                # fov_recompute = True
                # break
                
            if player_action == 'up':
                self.a, self.b = 0,-1
                self.charge()
                break
            elif player_action == 'down':
                self.a, self.b = 0,1
                self.charge()
                break
            elif player_action == 'left':
                self.a, self.b = -1,0
                self.charge()
                break
            elif player_action == 'right':
                self.a, self.b = 1,0
                self.charge()
                break
    
    def charge(self):
        monster = self.owner
        monster.move_towards(monster.x+self.a, monster.y+self.b)
        message('Player charges', 'blue', get_identity(monster))
        self.reach -= 1
        
        if self.reach == 0:
            self.reach = 5
            self.ticker.schedule_turn(200, self)    
        else:
            self.ticker.schedule_turn(10, self)    
        
            
            
class PaleTeeth:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.name = 'pale teeth'
        self.desc = 'pale teeth'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        render_all()
        libtcod.line_init(self.owner.x, self.owner.y, player.x, player.y)
        range = 0
        while True:
            (a, b) = libtcod.line_step()
            T.layer(3)
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            T.print_(a, b, '[color=yellow]x')
            if range == 1:
                break
            if not a: 
                break
            T.refresh()
            T.layer(0)            
            message(self.owner.name + ' bites with his pale teeth', 'yellow', get_identity(monster))
            
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if object.fighter and object.x == a and object.y == b:
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                do_damage(target, int(self.owner.fighter.str / 2)+1, 0)

            T.delay(50)
            range += 1
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)


class Estus:
    def __init__(self, ticker, speed, max_cooldown = 100):
        self.ticker = ticker
        self.speed = 1
        self.cooldown = 0
        self.max_cooldown = 1000
        self.ticker.schedule_turn(self.speed, self)
        
    def take_turn(self):      
        if self.cooldown == self.max_cooldown:
            return self.ticker.schedule_turn(self.speed, self)
            
        self.cooldown += 1
        self.ticker.schedule_turn(self.speed, self)

    def do(self,dx,dy):
        if self.cooldown < self.max_cooldown:
            return
        player.fighter.heal(10)
        self.cooldown = 0
        message('You drink a potion flask', 'dark green', 'player')
        

class Regeneration:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.name = 'regeneration'
        self.desc = 'a regeneration gland'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
        
        if monster.fighter.hp < monster.fighter.max_hp:
            monster.fighter.hp += 1
            message(monster.name + ' regenerates', 'green', get_identity(monster))
        
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)

class HandSlap:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.name = 'slapping hand'
        self.desc = 'a hand with seven fingers'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        #making longer line. When player is too close, it gets counted over the player coordinates
        dx = player.x - self.owner.x
        dy = player.y - self.owner.y
        
        message(self.owner.name + ' slaps with his hand', 'red', get_identity(monster))
        
        libtcod.line_init(self.owner.x, self.owner.y, player.x+4*dx, player.y+4*dy)
        range = 0
        while True:
            (a, b) = libtcod.line_step()
            T.layer(3)
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            if not a: 
                break
            
            if range == 3:
                render_all()
            
                T.print_(a, b, '[color=red]x')
                
                #try to find an attackable object there
                target = None
                for object in objects[player.z]:
                    if object.fighter and object.x == a and object.y == b:
                        target = object
                        break
                if target is not None:
                    message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                    do_damage(target, int(self.owner.fighter.str / 2)+1, 0)
                
                T.refresh()
                T.layer(0)            
                T.delay(100)    
                break
            
            range += 1
       
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)      
            
class WolfFangs:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.name = 'wolf fangs'
        self.desc = 'wolf fangs'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        render_all()
        libtcod.line_init(self.owner.x, self.owner.y, player.x, player.y)
        range = 0
        while True:
            (a, b) = libtcod.line_step()
            T.layer(3)
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            T.print_(a, b, '[color=yellow]x')
            if range == 1:
                break
            if not a: 
                break
            T.refresh()
            T.layer(0)            
            message(self.owner.name + ' bites with wolf fangs', 'yellow', get_identity(monster))
            
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if object.fighter and object.x == a and object.y == b:
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                do_damage(target, int(self.owner.fighter.str), 0)

            T.delay(150)
            range += 1
        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)


class TentacleMouth:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.intervall = speed
        self.a = 0
        self.b = 0
        self.name = 'tentacle mouth'
        self.desc = 'a mouth surrounded by tentacles'
        #self.ticker.schedule_turn(self.speed, self)
        self.list = [
        
        [ (-2,-1), (-2,1), (-1,0) ],
        [ (2,1), (2,-1), (1,0) ],
        [ (1,2), (-1,2), (0,1) ],
        [ (1,-2), (-1,-2), (0,-1) ]
        
        ]
        
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        self.dx = player.x - self.owner.x
        self.dy = player.y - self.owner.y
    
        c = get_relative_direct(self.dx,self.dy)
        if c == 'up':
            self.a, self.b, self.c = self.list[3]
        elif c == 'down':
            self.a, self.b, self.c = self.list[2]
        elif c == 'left':
            self.a, self.b, self.c = self.list[0]
        elif c == 'right':
            self.a, self.b, self.c = self.list[1]

        render_all()
        T.layer(7)
        message(monster.name + ' bites with tentacles', 'green', get_identity(self.owner))
        
        T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
        (dx,dy) = self.a
        (da,db) = self.b
        (di,dj) = self.c
        x = monster.x + dx
        y = monster.y + dy
        a = monster.x + da
        b = monster.y + db
        i = monster.x + di
        j = monster.y + dj
    
        T.print_(x,y, '[color=green]x')
        T.print_(a,b, '[color=green]x')
        T.print_(i,j, '[color=green]x')
        
        #try to find an attackable object there
        target = None
        for object in objects[player.z]:
            if (object.fighter and object.x == x and object.y == y) or (object.fighter and object.x == a and object.y == b) or (object.fighter and object.x == i and object.y == j):
                target = object
                break
        if target is not None:
            message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
            do_damage(target, monster.fighter.spirit, 0)
        T.refresh()            
        T.delay(150) 
    
        self.ticker.schedule_turn(self.speed, self)      
    
class RavenBeak:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.name = "raven's beak"
        self.desc = "a raven's beak"
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
        
        message(self.owner.name + ' moves', 'light green', get_identity(self.owner))
        self.owner.move_towards(player.x, player.y)
            
        render_all()
        libtcod.line_init(self.owner.x, self.owner.y, player.x, player.y)
        range = 0
        while True:
            (a, b) = libtcod.line_step()
            T.layer(3)
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            T.print_(a, b, '[color=light green]x')
            if range == 1:
                break
            if not a: 
                break
            T.refresh()
            T.layer(0)            
            message(self.owner.name + ' picks with beak', 'light green', get_identity(monster))
            
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if object.fighter and object.x == a and object.y == b:
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                do_damage(target, int(self.owner.fighter.str / 2)+1, 0)

            T.delay(50)
            range += 1
        #schedule next turn
        self.ticker.schedule_turn(45 - self.owner.fighter.wit, self)

class SnakeTeeth:
    def __init__(self, ticker, speed):
        self.ticker = ticker
        self.speed = speed
        self.name = 'snake teeth'
        self.desc = 'snake teeth'
        #self.ticker.schedule_turn(self.speed, self)
    
    def take_turn(self):
        monster = self.owner
        
        if not monster.fighter: #most likely because monster is dead
            return
        #stop when the player is already dead
        if game_state == 'dead':
            return
        
        #wait if player on different floor 
        if monster.z != player.z:
            self.ticker.schedule_turn(self.speed, self)            
            return
    
        render_all()
        libtcod.line_init(self.owner.x, self.owner.y, player.x, player.y)
        message(self.owner.name + ' bites with snake teeth', 'yellow', get_identity(monster))
        range = 0
        coord = []
        while True:
            (a, b) = libtcod.line_step()
            coord.append((a,b))
            if range == 2:
                break
            if not a: 
                break
            
            #try to find an attackable object there
            target = None
            for object in objects[player.z]:
                if object.fighter and object.x == a and object.y == b:
                    target = object
                    break
            if target is not None:
                message(self.owner.name.capitalize() + ' hits ' + target.name + '.', 'red', get_identity(self.owner))
                do_damage(target, int(self.owner.fighter.str / 2)+1, 0)
            range += 1
        
        T.layer(3)
        T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
        
        T.print_(coord[0][0], coord[0][1], '[color=yellow]x')
        T.print_(coord[1][0], coord[1][1], '[color=yellow]x')
        
        T.refresh()
        T.layer(0)            
        
        T.delay(80)

        #schedule next turn
        self.ticker.schedule_turn(self.speed, self)        

            
            
# class Tentacle:
    # '''AI for a basic monster. Schedules the turn depending on speed and decides whether to move or attack.
    # Owned by all monsters apart from bosses.
    # '''
    # def __init__(self, ticker, speed, range):
        # self.ticker = ticker
        # self.speed = speed
        # self.range = range
        # self.ticker.schedule_turn(self.speed, self)
    
    # def take_turn(self):
        # '''checks whether monster and player are still alive, decides on move or attack'''
        # #a basic monster takes its turn.
        # monster = self.owner
        
        # if not monster.fighter: #most likely because monster is dead
            # return
        # #stop when the player is already dead
        # if game_state == 'dead':
            # return
        
        # #wait if player on different floor 
        # if monster.z != player.z:
            # self.ticker.schedule_turn(self.speed, self)            
            # return
        
        # message('The tentacle strikes', 'green', get_identity(self.owner))
        # for y in range(MAP_HEIGHT):
            # for x in range(MAP_WIDTH):
                # if int(monster.distance(x,y)) == self.range:
                    # T.print_(x,y, '/')
                    # T.refresh()
        
        
        # #close enough, attack! (if the player is still alive.)
        # if int(monster.distance_to(player)) == self.range:
            # monster.fighter.attack(player)
        
        # #schedule next turn
        # self.ticker.schedule_turn(self.speed, self)      
        
class Item:
    #an item that can be picked up and used.
    def __init__(self, buc=None, conditions=[None, 'blackened', 'burned', 'charred'], use_function=None):

        self.buc = buc #blessed, uncursed, cursed
        self.conditions = conditions #things like rusty, rotten, burned etc.
        self.condition = None
        self.use_function = use_function
        
    def useful(self):
        if self.condition == self.conditions[len(self.conditions)-1]:
            return False
        return True
        
    def pick_up(self, picker):
        #add to the player's inventory and remove from the map
        if len(picker.fighter.inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', 'red', 'player')
        else:
            picker.fighter.inventory.append(self.owner)
            self.owner.x = 0
            self.owner.y = 0
            objects[self.owner.z].remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', 'green', 'player')

    def drop(self, dropper):
        #special case: if the object has the Equipment component, dequip it before dropping
        if self.owner.equipment:
            self.owner.equipment.dequip(dropper)

        #add to the map and remove from the player's inventory. also, place it at the player's coordinates
        objects[dropper.z].append(self.owner)
        dropper.fighter.inventory.remove(self.owner)
        self.owner.x = dropper.x
        self.owner.y = dropper.y
        self.owner.z = dropper.z
        message(dropper.name + ' dropped a ' + self.owner.name + '.', 'yellow')
        
    def throw(self, thrower):
        message('Left-click a target tile to throw the ' + self.owner.name+ ', or right-click to cancel.', 'blue')
        (x, y) = target_tile()
        if x is None: return 'cancelled'
   
        #special case: if the object has the Equipment component, dequip it before throwing
        if self.owner.equipment:
            self.owner.equipment.dequip(thrower)
            
        throw_effect(player.x, player.y, x, y, self.owner.color, self.owner.char)
        
        #add to the map and remove from the player's inventory. also, run animation and place it at the new coordinates
        objects[thrower.z].append(self.owner)
        thrower.fighter.inventory.remove(self.owner)
        self.owner.x = x
        self.owner.y = y
        self.owner.z = thrower.z
        #self.owner.send_to_back()
        message(thrower.name + ' throws a ' + self.owner.name + '.', 'yellow')
        for obj in objects[thrower.z]:
            if obj.x == x and obj.y == y and obj.fighter:
                do_damage(obj, 2, 0)
        if libtcod.random_get_int(0,0,100) < 10 or not self.useful():
            self.owner.delete()

    def use(self, user):
        #just call the "use_function" if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function(self.owner) != 'cancelled':
                user.fighter.inventory.remove(self.owner)  #destroy after use, unless it was cancelled for some reason
    
    def trigger_condition(self):
        #items can erode through the list of conditions
        for i in range(0,len(self.conditions)-1):
            if self.condition == self.conditions[i]:
                self.condition = self.conditions[i+1]
                break
        
        if not self.useful():
            self.owner.flammable_prob = 0
            self.use_function = None
            if self.owner.equipment:
                if self.owner.equipment.is_equipped:
                    self.owner.equipment.is_equipped = False
                               
def do_damage(target, damage, fire_damage):
    #deal
    target.fighter.take_damage(damage, fire_damage)
        
class Equipment:
    #an object that can be equipped, yielding bonuses. automatically adds the Item component.
    def __init__(self, slot, max_hp_bonus=0, damage_bonus=0, armor_bonus=0, wit_bonus=0, strength_bonus=0, spirit_bonus=0): #, protection=None, enchanted=None):
        
        self.max_hp_bonus = max_hp_bonus
        self.damage_bonus = damage_bonus
        self.armor_bonus = armor_bonus
        self.wit_bonus = wit_bonus
        self.strength_bonus = strength_bonus
        self.spirit_bonus = spirit_bonus
        
        self.slot = slot
        self.is_equipped = False

    def toggle_equip(self, user):  #toggle equip/dequip status
        if self.is_equipped:
            self.dequip(user)
        else:
            self.equip(user)

    def equip(self, owner):
        #if the slot is already being used, dequip whatever is there first
        old_equipment = get_equipped_in_slot(self.slot, owner)
        if old_equipment is not None:
            old_equipment.dequip(owner)

        #equip object and show a message about it
        self.is_equipped = True
        #message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)

    def dequip(self, user):
        #dequip object and show a message about it
        if not self.is_equipped: return
        self.is_equipped = False
        #message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)
        

def get_equipped_in_slot(slot, owner):  #returns the equipment in a slot, or None if it's empty
    for obj in owner.fighter.inventory:
        if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
            return obj.equipment
    return None

def get_all_equipped(wearer):  #returns a list of equipped items someone wears
    equipped_list = []
    for item in wearer.fighter.inventory:
        if item.equipment and item.equipment.is_equipped:
            equipped_list.append(item.equipment)
    return equipped_list

    
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def make_map(type):
    global map, dist_corner
    #general function for decision, which map to make
    #print direction,dungeon_level, 'DEBUG'
    
    map = []
    temp = [[ tiles.Tile(True, type = 'grass')
             for y in range(MAP_HEIGHT) ]
           for x in range(MAP_WIDTH) ]
    map.append(temp)
    
    map = make_mountains(map)
    map = make_village(map)

    x,y = get_farest_corner()
    if type == 'new':
        dist_corner = x,y
            #store farest corner for demon selection
     
    #Training always same...
    elif type == 'training':
        monster = create_training_monster('demon', x, y, 0)
        objects[0].append(monster)

def place_demon(name):
    global dist_corner
    x,y = dist_corner
    
    file = shelve.open('monsters\\' + name, 'r')
    monster = file['monster']
    file.close()
    monster.x = x
    monster.y = y
    objects[0].append(monster)
    
    #tie it to reality
    for i in monster.fighter.limbs:
        i.ticker = ticker
        i.ticker.schedule_turn(i.speed, i)
    for j in monster.fighter.moves:
        j.ticker = ticker
        j.ticker.schedule_turn(j.speed, j)    
    
def get_farest_corner():
    list = [ (2,2), (2,MAP_HEIGHT-3), (MAP_WIDTH-3, 2), (MAP_WIDTH-3,MAP_HEIGHT-3)  ]
    farest_corner = None
    farest_dist = 1  #start with (slightly more than) maximum range

    for corner in list:
        dist = distance_2_point(corner[0],corner[1], x_village, y_village)
        if dist > farest_dist:  #it's closer, so remember it
            farest_corner = corner
            farest_dist = dist
    return farest_corner[0], farest_corner[1]
    
    
def make_village(map):
    global x_village, y_village
    #list of house coordinates
    village = []
    
    #get center of village
    x_village = libtcod.random_get_int(0,5, MAP_WIDTH-5)
    y_village = libtcod.random_get_int(0,5, MAP_HEIGHT-5)
    
    x = x_village
    y = y_village
    
    #radius
    r = libtcod.random_get_int(0,2,8)
    #density
    d = libtcod.random_get_int(0,8,10) #the lower, the denser
    for xi in range(MAP_WIDTH):
        for yi in range(MAP_HEIGHT):
            if distance_2_point(xi, yi, x, y) < r and libtcod.random_get_int(0,0,d) == 1:                    
                #create house coordinate and list them
                village.append((xi,yi))
            if distance_2_point(xi, yi, x, y) < r and libtcod.random_get_int(0,0,2) == 1: #make 50% if the area grassland
                map[0][xi][yi].change_type('grass')
    
    #no houses?
    if not village:
        return map
        
    #create streets by drawing lines from one house to another
    n = libtcod.random_get_int(0,2,5)
    for i in range(n):
        random.shuffle(village)
        a,b = village[0]
        random.shuffle(village)
        s,p = village[0]
    
        libtcod.line_init(a, b, s, p)
        while True:
            (k, l) = libtcod.line_step()
            if k is None: break
            map[0][k][l].change_type('street') 
    
    for j in village:
        map[0][j[0]][j[1]].change_type('house') 
        
    
    return map
 
def make_mountains(map):
    '''make heightmap of 3 height levels and put it on map as three levels depp of lava'''
    test = libtcod.heightmap_new(MAP_WIDTH, MAP_HEIGHT)
    test2 = libtcod.heightmap_new(MAP_WIDTH, MAP_HEIGHT)
    test3 = libtcod.heightmap_new(MAP_WIDTH, MAP_HEIGHT)
    
    noise = libtcod.noise_new(2)
    
    libtcod.heightmap_add_fbm(test2, noise, 1, 1, 0.0, 0.0, 10, 0.0, 1.0)
    libtcod.heightmap_add_fbm(test3, noise, 2, 2, 0.0, 0.0,  5, 0.0, 1.0)
    
    libtcod.heightmap_multiply_hm(test2, test3, test)
    libtcod.heightmap_normalize(test, mi=0, ma=1)
    
    #assign different levels 0-4 to hightmap floats
    for x in range(MAP_WIDTH):
        for y in range(MAP_HEIGHT):
            if libtcod.heightmap_get_value(test, x, y) < 0.2:
                libtcod.heightmap_set_value(test, x, y, 0)
            elif libtcod.heightmap_get_value(test, x, y) >= 0.2 and libtcod.heightmap_get_value(test, x, y) < 0.4:
                libtcod.heightmap_set_value(test, x, y, 1)
            elif libtcod.heightmap_get_value(test, x, y) >= 0.4 and libtcod.heightmap_get_value(test, x, y) < 0.6:
                libtcod.heightmap_set_value(test, x, y, 2)
            elif libtcod.heightmap_get_value(test, x, y) >= 0.6 and libtcod.heightmap_get_value(test, x, y) < 0.8:
                libtcod.heightmap_set_value(test, x, y, 3)
            elif libtcod.heightmap_get_value(test, x, y) >= 0.8:
                libtcod.heightmap_set_value(test, x, y, 4)
    
    #create a differnet color darkness to lava levels
    for x in range(MAP_WIDTH):
        for y in range(MAP_HEIGHT):
            for z in range(int(int(libtcod.heightmap_get_value(test, x, y))-1)):
                map[0][x][y].change_type('mountain')
                if z < 1:
                    map[0][x][y].color_light = 'grey'
                elif z < 2:
                    map[0][x][y].color_light = 'darker grey'
                elif z < 3:
                    map[0][x][y].color_light = 'darkest grey'
    
    #clean up and return map
    libtcod.heightmap_delete(test)
    return map
    
def is_blocked(x, y, z):
    try:
        #first test the map tile
        if map[z][x][y].blocked:
            return True
        #now check for any blocking objects
        for object in objects[z]:
            if object.blocks and object.x == x and object.y == y:
                return True
    except: # most of the times things outside the map
        return True
    
    return False

            
def get_map_char(location_name, x, y):
    i = getattr(maps, location_name) #this is maps.temple and would give maps.temple[y][x] == '+'
    return i[y][x]
                
def make_preset_map(location_name):
    temp = []
    
    #fill map with tiles according to preset maps.py (objects kept blank)
    temp = [[ tiles.Tile(True, type = maps.char_to_type( get_map_char(location_name, x, y ) ) )
             for y in range(MAP_HEIGHT) ]
           for x in range(MAP_WIDTH) ]  
           
    return temp

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

heads = [
    
    BonusBodypart('pale skull', 'a pale skull', wit_bonus=0, strength_bonus=2, spirit_bonus=0),
    BonusBodypart('round potato', 'an old round potato head', wit_bonus=0, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('purple mass', 'a waving purple mass', wit_bonus=0, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('brown fur', 'a head of brown fur', wit_bonus=0, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('white skin', 'head of bleak white skin', wit_bonus=0, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('horsehead', 'a horse-shaped head', wit_bonus=2, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('fishhead', 'a shimmering fish-shaped head', wit_bonus=0, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('eaglehead', "an eagle's head", wit_bonus=0, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('remotely human head', 'a remotely human head', wit_bonus=0, strength_bonus=0, spirit_bonus=1),
    BonusBodypart('humanhead', 'a human head', wit_bonus=0, strength_bonus=0, spirit_bonus=2),
    BonusBodypart('hiddenhood', 'a face hidden behind a dark hood', wit_bonus=0, strength_bonus=0, spirit_bonus=5)
]

hair = [
    BonusBodypart('tentacle hair', 'with twitching tentacle hair', wit_bonus=0, strength_bonus=1, spirit_bonus=0),
    BonusBodypart('snake hair', 'with biting snake hair', wit_bonus=0, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('bald', 'which is bald', wit_bonus=0, strength_bonus=3, spirit_bonus=0),
    BonusBodypart('scales', 'which is covered with scales', wit_bonus=0, strength_bonus=2, spirit_bonus=0),
    BonusBodypart('crown', 'which is decorated with a crown', wit_bonus=3, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('horns', 'which grows horns', wit_bonus=0, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('helmet', 'covered by a helmet', wit_bonus=0, strength_bonus=1, spirit_bonus=0)
]

eyes = [
    BonusBodypart('blue eyes', 'blue eyes', wit_bonus=1, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('raven eyes', 'dark raven eyes', wit_bonus=2, strength_bonus=0, spirit_bonus=1),
    BonusBodypart('eagle eyes', 'eagle eyes', wit_bonus=5, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('mantis eyes', 'mantis eyes', wit_bonus=2, strength_bonus=1, spirit_bonus=1),
    BonusBodypart('no eyes', 'no eyes', wit_bonus=1, strength_bonus=0, spirit_bonus=10),
    BonusBodypart('blindfold', 'a blindfold on his eyes', wit_bonus=2, strength_bonus=0, spirit_bonus=12),
    BonusBodypart('dark eyes', 'dark eyes', wit_bonus=2, strength_bonus=0, spirit_bonus=0),
    BonusBodypart('antenna eyes', 'wiggling antenna eyes', wit_bonus=2, strength_bonus=2, spirit_bonus=0),
    BonusBodypart('three eyes', 'three eyes with a central one on the forehead', wit_bonus=5, strength_bonus=0, spirit_bonus=5),
    BonusBodypart("joker's eyes", 'the eyes of a joker', wit_bonus=10, strength_bonus=-1, spirit_bonus=2)
]

torso = [
    BonusBodypart('bones', 'a skeleton body', wit_bonus=0, strength_bonus=7, spirit_bonus=2),
    BonusBodypart('purple mass', 'a waving purple mass as body', wit_bonus=3, strength_bonus=1, spirit_bonus=6),
    BonusBodypart('brown fur body', 'a body of brown fur', wit_bonus=1, strength_bonus=3, spirit_bonus=0),
    BonusBodypart('white skin body', 'a body of bleak pale skin', wit_bonus=1, strength_bonus=1, spirit_bonus=1),
    BonusBodypart('horse torso', 'a horse-torso', wit_bonus=3, strength_bonus=3, spirit_bonus=0),
    BonusBodypart('bird body', 'the body of a bird', wit_bonus=3, strength_bonus=1, spirit_bonus=2),
    BonusBodypart('human body', 'the body of a human', wit_bonus=6, strength_bonus=1, spirit_bonus=2),
    BonusBodypart('undead corpse', 'an undead corpse', wit_bonus=0, strength_bonus=4, spirit_bonus=0),
    BonusBodypart('feline torso', 'a feline torso', wit_bonus=4, strength_bonus=0, spirit_bonus=3),
    BonusBodypart('dark fog', 'dark for where its body should be', wit_bonus=0, strength_bonus=0, spirit_bonus=4)
]


    #eagle wings (fly fast), bull legs (charge), bird legs (move), 
    #tongue (attack limb), 

def add_teeth(monster):
    
    teeth = ['RabbitTeeth', 'PaleTeeth', 'SnakeTeeth', 'WolfFangs', "RavenBeak", 'TentacleMouth' ] #check
    
    random.shuffle(teeth)
    choice = teeth[0]
    
    if choice == 'RabbitTeeth':    
        teeth_c = RabbitTeeth(0, speed=50)
    elif choice == 'PaleTeeth':
        teeth_c = PaleTeeth(0, speed=50)
    elif choice == 'SnakeTeeth':
        teeth_c = SnakeTeeth(0, speed=50)
    elif choice == 'WolfFangs':
        teeth_c = WolfFangs(0, speed=50)
    elif choice == 'RavenBeak':
        teeth_c = RavenBeak(0, speed=50)
    elif choice == 'TentacleMouth':
        teeth_c = TentacleMouth(0, speed=50)
    
    teeth_c.owner = monster
    monster.fighter.limbs.append(teeth_c)
    monster.desc += '\n ' + teeth_c.desc    
    return monster
    
def add_moves(monster):
    moves = ['NormalLegs', 'CautiousLegs', 'BatWings', 'FrogLegs', 'Charge', 'Charge2', 'Flee', 'Circle1', 'Circle2' ]

    random.shuffle(moves)
    choice1 = moves[0]
    choice2 = moves[1]
    
    if choice1 == 'NormalLegs':    
        move1 = NormalLegs(0, speed=70)
    if choice1 == 'CautiousLegs':    
        move1 = CautiousLegs(0, speed=70)
    if choice1 == 'BatWings':    
        move1 = BatWings(0, speed=70)
    if choice1 == 'FrogLegs':    
        move1 = FrogLegs(0, speed=70)
    if choice1 == 'Charge':    
        move1 = Charge(0, speed=70)
    if choice1 == 'Charge2':    
        move1 = Charge2(0, speed=100)
    if choice1 == 'Flee':    
        move1 = Flee(0, speed=200)
    if choice1 == 'Circle1':    
        move1 = Circle1(0, speed=250)
    if choice1 == 'Circle2':    
        move1 = Circle2(0, speed=300)
    
    if choice2 == 'NormalLegs':    
        move2 = NormalLegs(0, speed=70)
    if choice2 == 'CautiousLegs':    
        move2 = CautiousLegs(0, speed=70)
    if choice2 == 'BatWings':    
        move2 = BatWings(0, speed=70)
    if choice2 == 'FrogLegs':    
        move2 = FrogLegs(0, speed=70)
    if choice2 == 'Charge':    
        move2 = Charge(0, speed=70)
    if choice2 == 'Charge2':    
        move2 = Charge2(0, speed=100)
    if choice2 == 'Flee':    
        move2 = Flee(0, speed=200)
    if choice2 == 'Circle1':    
        move2 = Circle1(0, speed=250)
    if choice2 == 'Circle2':    
        move2 = Circle2(0, speed=300)
    
    
    move1.owner = monster
    monster.fighter.moves.append(move1)
    move2.owner = monster
    monster.fighter.moves.append(move2)
    monster.desc += '\n ' + move1.desc    
    monster.desc += '\n ' + move2.desc    
    
    return monster
    
    
def add_attacks(monster):
    
    attacks = ['IronFist', 'FatBackside', 'Tentacle', 'ClawBlade', 'SpikedClub', 'HandSlap', 'TripleStomp', 'FieryBreath']
    
    r = libtcod.random_get_int(0,0,100)
    
    if r < 60:
        n = 1
    elif r < 90:
        n = 2
    elif r >= 90:
        n = 3
    
    random.shuffle(attacks)
        
    for i in range(n):
        choice = attacks[i]
    
        if choice == 'IronFist':    
            atk = IronFist(0, speed=100)
        if choice == 'FatBackside':    
            atk = FatBackside(0, speed=100)
        if choice == 'Tentacle':    
            atk = Tentacle(0, speed=100)
        if choice == 'ClawBlade':    
            atk = ClawBlade(0, speed=150)
        if choice == 'SpikedClub':    
            atk = SpikedClub(0, speed=100)
        if choice == 'HandSlap':    
            atk = HandSlap(0, speed=100)
        if choice == 'TripleStomp':    
            atk = TripleStomp(0, speed=200)
        if choice == 'FieryBreath':    
            atk = FieryBreath(0, speed=200)
        
        atk.owner = monster
        monster.fighter.limbs.append(atk)
        monster.desc += '\n ' + atk.desc    
        
    return monster
    
def create_monster(type, x, y, z):
    # storage of data from monsters.py
    a = getattr(monsters, type)
    
    wit = libtcod.random_get_int(0,1,7)
    str = libtcod.random_get_int(0,1,7)
    spi = libtcod.random_get_int(0,1,7)
    
    # creating fighter component
    fighter_component = Monster(wit=wit, strength=str, spirit=spi, organs=[], limbs=[], moves=[], death_function=DEATH_DICT[a['death_function']])                
    
    #creating ai needs more info because of arguments
    # if a['ai'] == 'BasicMonster':
        # ai_component = NormalLegs(ticker, speed=a['speed'])
   
    #create the monster    
    monster = Object(x, y, z, a['char'], generate_name(), a['color'], blocks=True, fighter=fighter_component, ai=[])
    
    monster.desc += ', ' + generate_title() + '\n' + 'You see'
    
    #add head(s)
    random.shuffle(heads)
    monster.fighter.organs.append(heads[0])
    monster.desc += '\n ' + heads[0].desc
    
    #add hair
    random.shuffle(hair)
    if libtcod.random_get_int(0,0,3) == 1:
        random.shuffle(hair)
        monster.fighter.organs.append(hair[0])
        monster.desc +=  '\n ' + hair[0].desc
    
    #rarely a second head is found
    if libtcod.random_get_int(0,0,40) == 1:
        monster.fighter.organs.append(heads[1])
        monster.desc += '\n ' + heads[0].desc
        #it alsways has the same hair
        monster.fighter.organs.append(hair[0])
        monster.desc +=  '\n ' + hair[0].desc
    
    #add eyes
    random.shuffle(eyes)
    monster.fighter.organs.append(eyes[0])
    monster.desc += '\n ' + eyes[0].desc
    
    #add attack bite
    monster = add_teeth(monster)
    
    #add torso
    random.shuffle(torso)
    monster.fighter.organs.append(torso[0])
    monster.desc += '\n ' + torso[0].desc
    
    #add scales sometimes
    if libtcod.random_get_int(0,0,30) == 1:
        monster.fighter.organs.append(hair[3])
        monster.desc += '\n ' + hair[3].desc
    
    #add attacks
    monster = add_attacks(monster)
    
    #add moves
    monster = add_moves(monster)
    
    if libtcod.random_get_int(0,0,8) == 1:
        tail = Tail(0, speed = 100)
        monster.fighter.limbs.append(tail)
        tail.owner = monster
        monster.desc += '\n ' + tail.desc
    
    
    #add strong arms sometimes
    if libtcod.random_get_int(0,0,15) == 1:
        arm = BonusBodypart('arm', 'strong arms', wit_bonus=0, strength_bonus=7, spirit_bonus=0)
        monster.fighter.organs.append(arm)
        monster.desc += '\n ' + arm.desc
    
    
    if libtcod.random_get_int(0,0,30) == 1:
        reg = Regeneration(0, speed=2000)
        monster.fighter.limbs.append(reg)
        reg.owner = monster
        monster.desc += '\n ' + reg.desc
    
    #add horns
    value = libtcod.random_get_int(0,2,13)
    horns = BonusBodypart('horns', 'and %s' % value + ' horns', wit_bonus=0, strength_bonus=0, spirit_bonus=0)
    monster.fighter.organs.append(horns)
    monster.desc += '\n ' + horns.desc
    
    #open a new empty shelve (possibly overwriting an old one) to write the game data
    file = shelve.open('monsters\\' + monster.name, 'n')
    file['name'] = monster.name
    file['monster'] = monster
    file.close()

    return monster


def create_training_monster(type, x, y, z):
    global ticker
    # storage of data from monsters.py
    a = getattr(monsters, type)
    
    wit = libtcod.random_get_int(0,1,7)
    str = libtcod.random_get_int(0,1,7)
    spi = libtcod.random_get_int(0,1,7)
    
    # creating fighter component
    fighter_component = Monster(wit=wit, strength=str, spirit=spi, organs=[], limbs=[], moves=[], death_function=DEATH_DICT[a['death_function']])                
    
    #create the monster    
    monster = Object(x, y, z, a['char'], 'bob', a['color'], blocks=True, fighter=fighter_component, ai=[])
    
    monster.desc += ', ' + 'herzog of gehennom' + '\n' + 'You see'
    
    #add head(s)
    random.shuffle(heads)
    monster.fighter.organs.append(heads[0])
    monster.desc += '\n ' + heads[0].desc
    
    #add hair
    random.shuffle(hair)
    if libtcod.random_get_int(0,0,3) == 1:
        random.shuffle(hair)
        monster.fighter.organs.append(hair[0])
        monster.desc +=  '\n ' + hair[0].desc
    
    #rarely a second head is found
    if libtcod.random_get_int(0,0,40) == 1:
        monster.fighter.organs.append(heads[1])
        monster.desc += '\n ' + heads[0].desc
        #it alsways has the same hair
        monster.fighter.organs.append(hair[0])
        monster.desc +=  '\n ' + hair[0].desc
    
    #add eyes
    random.shuffle(eyes)
    monster.fighter.organs.append(eyes[0])
    monster.desc += '\n ' + eyes[0].desc
    
    #add torso
    random.shuffle(torso)
    monster.fighter.organs.append(torso[0])
    monster.desc += '\n ' + torso[0].desc
    
    #add scales sometimes
    if libtcod.random_get_int(0,0,30) == 1:
        monster.fighter.organs.append(hair[3])
        monster.desc += '\n ' + hair[3].desc
    
    teeth = PaleTeeth(0, speed=50)
    teeth.owner = monster
    monster.fighter.limbs.append(teeth)
    monster.desc += '\n ' + teeth.desc
    
    move = Charge2(0, speed=150)
    move.owner = monster
    monster.fighter.moves.append(move)
    monster.desc += '\n ' + move.desc
    
    #add horns
    value = libtcod.random_get_int(0,2,13)
    horns = BonusBodypart('horns', 'and %s' % value + ' horns', wit_bonus=0, strength_bonus=0, spirit_bonus=0)
    monster.fighter.organs.append(horns)
    monster.desc += '\n ' + horns.desc
    
    #tie it to reality
    for i in monster.fighter.limbs:
        i.ticker = ticker
        i.ticker.schedule_turn(i.speed, i)
    for j in monster.fighter.moves:
        j.ticker = ticker
        j.ticker.schedule_turn(j.speed, j)
    
    return monster 
    
    
def generate_name():
    length = libtcod.random_get_int(0,3,8)
    cons = ['d', 'f', 'gh', 'j', 'k', 'll', 'm', 'n', 'p', 'r', 's', 'th', 'v', 'w', 'x', 'y', 'zz']
    voc = ['as', 'e', 'i', 'oth', 'un']
    
    while True:
        name = []
        for i in range(length):
            if i%2==0:
                name.append(cons[libtcod.random_get_int(0,0,len(cons)-1)])
            else:    
                name.append(voc[libtcod.random_get_int(0,0,len(voc)-1)])
        if name[0] != "'":
            break
            
    return ''.join(name)
    
def generate_title():
    title = []
    pre = ['grand', 'high', 'arch-']
    high = ['lord', 'emperor', 'sultan', 'duke', 'earl', 'graf', 'vogt', 'king', 'prince', 'princess', 'queen', 'lady', 'dutchess', 
            'baron', 'baroness', 'freiherr', 'knight', 'infante', 'marquis', 'count', 'zar', 'emir', 'pharaoh', 'sheik', 'herzog' ]
    low = ['hell', 'gehennom', 'the fire', 'the deep', 'the depths', 'the flame', 'the bonfire', 'souls', 'the underworld', 
            'the realm of the dead', 'hades', 'niflheim', 'tartaros', 'purgatory', 'abbadon', 'the inferno', 'the river styx', 
            'dis', 'the lair', 'the 1st circle', 'the 2nd circle', 'the 3rd circle', 'the 4th circle', 'the 5th circle', 'the 6th circle']
    
    if libtcod.random_get_int(0,0,20) == 1:
        random.shuffle(pre)
        title.append(pre[0])
    random.shuffle(high)
    title.append(high[0])
    title.append('of')
    random.shuffle(low)
    title.append(low[0])
    return ' '.join(title)
        
    
def random_choice_index(chances):  #choose one option from list of chances, returning its index
    #the dice will land on some number between 1 and the sum of the chances
    dice = libtcod.random_get_int(0, 1, sum(chances))

    #go through all chances, keeping the sum so far
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w

        #see if the dice landed in the part that corresponds to this choice
        if dice <= running_sum:
            return choice
        choice += 1

def random_choice(chances_dict):
    #choose one option from dictionary of chances, returning its key
    chances = chances_dict.values()
    strings = chances_dict.keys()

    return strings[random_choice_index(chances)]

def from_dungeon_level(z, table):
    #returns a value that depends on level. the table specifies what value occurs after each level, default is 0.
    for (value, level) in reversed(table):
        if z >= level:
            return value
    return 0

            
#-----------------------------------------------------------------------------------------------------------------            
            

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color, ctrl):
    
    T.layer(0) #the bar is on the lowest layer, the only with background
    
    #render a bar (HP, experience, etc). first calculate the width of the bar
    bar_width = int(float(value) / maximum * total_width)
 
    #render the background first
    T.color(back_color)
    for i in range(total_width):
        T.print_(x + i, y, '[U+2588]')
    
    #now render the bar on top
    T.color(bar_color)
    for i in range(bar_width):
        T.print_(x + i, y, '[U+2588]')
    
    T.layer(1) #the stats are on the panel-layer
    #T.print_(x + 1, y, '[color=white]' + name)# + ': ' + str(value) + '/' + str(maximum))
   
    if value == maximum: 
        T.print_(x + BAR_WIDTH, y, '[color=white]' + name)
    
    
    #clean up
    T.color('black')
    T.layer(0)
    
def get_names_under_cursor(x,y):
    #return a string with the names of all objects under the mouse or crosshair
    T.layer(2)
    T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
    
    #create a list with the names of all objects at the mouse's coordinates and in FOV
    names = [obj.desc for obj in reversed(objects[player.z])
             if obj.x == x and obj.y == y and visible_to_player(x,y)]
    
    
    # #get terrain type unter mouse (terrain, walls, etc..)
    # if visible_to_player(x,y):
        # if not map[player.z][x][y].name == 'empty':
            # names.append(map[player.z][x][y].name)
            
    if names:
        pile = names
        # max_length = 1
        # longest_thing = None
        # for item in pile:
            # if len(item) > max_length:
                # max_length = len(item)+1
                
                # longest_thing = item
        T.composition(T.TK_ON)
        for j in range(40):
            for k in range(15):
                T.print_(x+j,y+k+1, '[color=black]' + '[U+2588]')
        
        i = 0
        #print max_length
        for thing in pile:
            T.print_(x+1, y+i+1, thing)
            
            i += 1
        
    T.layer(0)
    
#-----------------------------------------------------------------------------------------------
    
    
def render_all():
    global fov_map, fov_recompute, light_map, l_map 

    T.layer(0)
    
    #if fov_recompute:
    #recompute FOV if needed (the player moved or something)
    #fov_recompute = False
    libtcod.map_compute_fov(fov_map, player.x, player.y, 1000, FOV_LIGHT_WALLS, FOV_ALGO)
    T.clear()
    
    #go through all tiles, and set their background color according to the FOV
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            if not visible_to_player(x,y):
                #if it's not visible right now, the player can only see it if it's explored
                if map[player.z][x][y].explored:
                    T.print_(x, y, '[color=' + map[player.z][x][y].color_dark + ']' + map[player.z][x][y].char_dark)
            else:
                #it's visible
                T.print_(x, y, '[color=' + map[player.z][x][y].color_light + ']' + map[player.z][x][y].char_light)
                
                #since it's visible, explore it
                map[player.z][x][y].explored = True

    #draw all objects in the list, except the player. we want it to
    #always appear over all other objects! so it's drawn later.
    for object in objects[player.z]:
        if object != player:
            object.draw()
    player.draw()
    
#------------------------------------------------------------------------------------------ 
    # #prepare to render the GUI panel
    T.layer(1)
    T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
    
    T.color('white')
    T.print_(MLINE_X + 3, 1, '[color=yellow]&')
    T.print_(PLINE_X + 3, 1, '@')
    
    #print the game messages, one line at a time
    y = 1
    for (line, color, owner) in game_msgs:      
        if owner == 'monster':
            T.color(color)
        else:
            T.color('black')
        T.print_(MLINE_X, y + MLINE_Y, line)
        y += 1
        
    y = 1    
    for (line, color, owner) in game_msgs:      
        if owner == 'player':
            T.color(color)
        else:
            T.color('black')
        T.print_(PLINE_X, y + PLINE_Y, line)
        y += 1
    
    # y = 1    
    # for (line, color) in game_sys_msgs:      
        # T.color(color)
        # T.print_(SLINE_X, y + SLINE_Y, line)
        # y += 1
    
    T.print_(0, MAP_HEIGHT, '[color=white]Cooldown')
    #show the player's cooldowns
    if player.fighter.limbs['q']:
        render_bar(1, 1 + MAP_HEIGHT, BAR_WIDTH, 'q+dir', player.fighter.limbs['q'].cooldown, player.fighter.limbs['q'].max_cooldown, 'blue', 'white', 'q+dir')
       
    #show the player's cooldowns
    if player.fighter.limbs['a']:
        render_bar(1, 2 + MAP_HEIGHT, BAR_WIDTH, 'a+dir', player.fighter.limbs['a'].cooldown, player.fighter.limbs['a'].max_cooldown,
               'darker blue', 'white', 'a+dir')
    
    #show the player's cooldowns
    if player.fighter.limbs['w']:
        render_bar(20, 1 + MAP_HEIGHT, BAR_WIDTH, 'w+dir', player.fighter.limbs['w'].cooldown, player.fighter.limbs['w'].max_cooldown,
               'orange', 'white', 'w+dir')
        
    #show the player's cooldowns
    if player.fighter.limbs['s']:
        render_bar(20, 2 + MAP_HEIGHT, BAR_WIDTH, 's+dir', player.fighter.limbs['s'].cooldown, player.fighter.limbs['s'].max_cooldown,
               'darker orange', 'white', 's+dir')
    
    #show the player's cooldowns
    if player.fighter.limbs['e']:
        render_bar(1, 4 + MAP_HEIGHT, BAR_WIDTH, 'e', player.fighter.limbs['e'].cooldown, player.fighter.limbs['e'].max_cooldown,
               'dark green', 'white', 'e')
    
    T.print_(1 + 10, MAP_HEIGHT, '[color=white]' + chosen_weapons[0])# + ': ' + str(value) + '/' + str(maximum))
    T.print_(20 + 10, MAP_HEIGHT, '[color=white]' + chosen_weapons[1])
    T.print_(1 + 10, MAP_HEIGHT+3, '[color=white]' + 'potion')
    
    
#------------------------------------------------------------------------------------------  
#distance indicator closest monster
    # monster = closest_monster(100)
    # if monster:
        # T.print_(MAP_WIDTH + 1, 1, '[color=white]' + str(int(player.distance_to(monster))) )
        
    T.print_(MAP_WIDTH-2, MAP_HEIGHT+5, '[align=right][color=white]hp: ' + str(player.fighter.hp) )
    T.print_(1,SCREEN_HEIGHT-2, '[color=white]mouseover for desc')
    T.print_(1,SCREEN_HEIGHT-1, '[color=white]press c for controls')
#------------------------------------------------------------------------------------------
    #get info under mouse as console window attached to the mouse pointer
    T.color('white')
    (x, y) = (T.state(T.TK_MOUSE_X), T.state(T.TK_MOUSE_Y))
    get_names_under_cursor(x,y)
    T.layer(0)
    
    
def visible_to_player(x,y):
    if libtcod.map_is_in_fov(fov_map, x, y):
        return True
    return False
  
def make_GUI_frame(x, y, dx, dy, color='white'):
    #sides
    T.layer(4)
    for i in range(dx-1):
        T.print_(i+x, 0+y, '[color=' + color + ']' + '[U+2500]')
    for i in range(dx-1):
        T.print_(i+x, dy-1+y, '[color=' + color + ']' + '[U+2500]')
    for i in range(dy-1):
        T.print_(0+x, i+y, '[color=' + color + ']' + '[U+2502]')
    for i in range(dy-1):
        T.print_(dx-1+x, i+y, '[color=' + color + ']' + '[U+2502]')

    #corners
    T.print_(x, y, '[color=' + color + ']' + '[U+250C]')
    T.print_(dx-1+x, y, '[color=' + color + ']' + '[U+2510]')
    T.print_(x, dy-1+y, '[color=' + color + ']' + '[U+2514]')
    T.print_(dx-1+x, dy-1+y, '[color=' + color + ']' + '[U+2518]')
    T.layer(0)
    
#-------------------------------------------------------------------------------------------------    
def message(new_msg, color = 'white', owner = None):
    #split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
    
        #if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]

        #add the new line as a tuple, with the text and the color
        game_msgs.append( (line, color, owner) )

def message_sys(new_msg, color = 'white'):
    #split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MAP_WIDTH)

    for line in new_msg_lines:
    
        #if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == SYS_MSG_HEIGHT:
            del game_msgs[0]

        #add the new line as a tuple, with the text and the color
        game_sys_msgs.append( (line, color) )
        
def get_identity(input):
    if input == player:
        return 'player'
    else:
        return 'monster'
#--------------------------------------------------------------------------------------------------

def turn_point(x, y, alpha):
    point1 = cart2pol(x,y)    
    point1 = point1[0], point1[1] + alpha
    point1 = pol2cart(point1[0], point1[1])
    point1 = int(point1[0]), int(point1[1])
    return point1    

def cart2pol(x,y):
    r = np.sqrt(x**2 + y**2)
    phi = np.arctan2(y,x)
    return (r, phi)
        
        
def pol2cart(r,phi):
    x = r * np.cos(phi)
    y = r * np.sin(phi)
    return (x,y)
#-----------------------------------------------------------------


def player_move(dx, dy):
    global fov_recompute
    player.move(dx, dy)
    message('you move', 'white', get_identity(player))
    fov_recompute = True
        
def menu(header, options, width, back=None):
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')
    
    #calculate total height for the header (after auto-wrap) and one line per option
    header_height = libtcod.console_get_height_rect(0, 0, 0, width, SCREEN_HEIGHT, header)
    if header == '':
        header_height = 0
    height = len(options) + header_height + 2

    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2
    
    T.layer(2)
    T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
    
    #create an off-screen console that represents the menu's window
    if back:
        T.composition(T.TK_ON)
        for i in range(width):
            for j in range(height):
                T.print_(i+x,j+y, '[color=' + back + ']' + '[U+2588]')
    
    #make_GUI_frame(x, y, width, height)
    
    #cursors position
    c_pos = 0
    
    output = None
    
    while True:
        T.print_(x+1,y, '[color=white]' + header)
        
        #print all the options
        h = header_height
        letter_index = ord('a')
        run = 0
        for option_text in options:
            text = option_text
            
            if run == c_pos:
                T.print_(x+1,h+y+1, '[color=yellow]' + text.upper())
                
            else:    
                T.print_(x+1,h+y+1, '[color=white]' + text)
            h += 1
            letter_index += 1
            run += 1
            
        #present the root console to the player and wait for a key-press
        T.refresh()
        
        key = T.read()
        if key == T.TK_ESCAPE:
            break
        elif key == T.TK_UP or key == T.TK_KP_8:
            c_pos -= 1
            if c_pos < 0:
                c_pos = len(options)-1
                
        elif key == T.TK_DOWN or key == T.TK_KP_2:
            c_pos += 1
            if c_pos == len(options):
                c_pos = 0
        
        elif key == T.TK_ENTER:               
            #convert the ASCII code to an index; if it corresponds to an option, return it
            index = c_pos
            #if index >= 0 and index < len(options): 
            output = index
            break
            
    T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
    T.composition(T.TK_OFF)
    T.layer(0)
    return output
    
def inventory_menu(header):
    #show a menu with each item of the inventory as an option
    if len(player.fighter.inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = []
        for item in player.fighter.inventory:
            text = item.name
            #show additional information, in case it's equipped
            if item.equipment and item.equipment.is_equipped:
                text = text + ' (on ' + item.equipment.slot + ')'
            options.append(text)

    index = menu(header, options, INVENTORY_WIDTH, 'black')

    #if an item was chosen, return it
    if index is None or len(player.fighter.inventory) == 0: return None
    return player.fighter.inventory[index].item
    
def item_use_menu(item):
    #show a menu with each possible use of an item as an option
    
    header = 'What do you want to do with ' + item.owner.name + '?\n'
    
    options = ['cancel', 'drop', 'throw']
    if item.use_function:
        options.append('use')
    if item.owner.equipment and item.useful(): 
        if item.owner.equipment.is_equipped:
            options.append('dequip')
        else:
            options.append('equip')
    
    potion_in_inventory = False
    for i in player.fighter.inventory:
        if 'potion of oil' in i.name:
            potion_in_inventory = True
    
    if potion_in_inventory and item.owner.flammable_prob == 0:
        options.append('dip in potion')
    
    index = menu(header, options, INVENTORY_WIDTH/2)

    if index:
        #if an item was chosen, return resp option
        return options[index]

def msgbox(text, width=50):
    menu(text, [], width, 'black')  #use menu() as a sort of "message box"
    
def enter_text_menu(header, width, max_length): #many thanks to Aukustus and forums for poviding this code. 
    #clear_screen()
    # the 80 should be the width of the game window, in my game it's 80
    con = libtcod.console_new(80, 3)

    libtcod.console_set_default_foreground(con, libtcod.white)

    libtcod.console_print_rect(con, 5, 0, width, 3, header)
    libtcod.console_print_ex(con, 5, 1, libtcod.BKGND_NONE, libtcod.LEFT, 'Name:')
    timer = 0
    input = ''
    x = 11
    cx = 15
    cy = SCREEN_HEIGHT/2 - 3

    while True:
        key = libtcod.console_check_for_keypress(libtcod.KEY_PRESSED)

        timer += 1
        if timer % (LIMIT_FPS // 4) == 0:
            if timer % (LIMIT_FPS // 2) == 0:
                timer = 0
                libtcod.console_print_ex(con, x, 1, libtcod.BKGND_NONE, libtcod.LEFT, ' ')
            else:
                libtcod.console_print_ex(con, x, 1, libtcod.BKGND_NONE, libtcod.LEFT, '_')
        if key.vk == libtcod.KEY_BACKSPACE:
            if len(input) > 0:
                libtcod.console_print_ex(con, x, 1, libtcod.BKGND_NONE, libtcod.LEFT, ' ')
                input = input[:-1]
                x -= 1

        elif key.vk == libtcod.KEY_ENTER or key.vk == libtcod.KEY_KPENTER:
            break

        elif key.c > 0 and len(input) < max_length:
            letter = chr(key.c)
            if re.match("^[A-Za-z0-9-']*$", str(letter)) or str(letter) == ' ':
                libtcod.console_print_ex(con, x, 1, libtcod.BKGND_NONE, libtcod.LEFT, letter)
                input += letter
                x += 1

        libtcod.console_blit(con, 5, 0, width, 3, 0, cx, cy, 1.0, 1.0)
        libtcod.console_flush()
        
    return input

    
    
def handle_keys():
    global key, stairs, upstairs, ladder, upladder, game_state

    
    if key == T.TK_ESCAPE:
        choice = menu('Do you want to quit?', ['Yes', 'No'], 24, 'black')
        if choice == 0:                
            game_state = 'exit' #<- lead to crash WHY ??
            return 'exit' #exit game
        else:
            return 'didnt-take-turn'

    if game_state == 'playing':
        #movement keys
        
        if key == T.TK_UP and T.check(T.TK_Q):
            if player.fighter.limbs['q']:
                player.fighter.limbs['q'].do(0,-1)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_DOWN and T.check(T.TK_Q):
            if player.fighter.limbs['q']:
                player.fighter.limbs['q'].do(0,1)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_LEFT and T.check(T.TK_Q):
            if player.fighter.limbs['q']:
                player.fighter.limbs['q'].do(-1,0)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_RIGHT and T.check(T.TK_Q):
            if player.fighter.limbs['q']:
                player.fighter.limbs['q'].do(1,0)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_UP and T.check(T.TK_A):
            if player.fighter.limbs['a']:
                player.fighter.limbs['a'].do(0,-1)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_DOWN and T.check(T.TK_A):
            if player.fighter.limbs['a']:
                player.fighter.limbs['a'].do(0,1)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_LEFT and T.check(T.TK_A):
            if player.fighter.limbs['a']:
                player.fighter.limbs['a'].do(-1,0)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_RIGHT and T.check(T.TK_A):
            if player.fighter.limbs['a']:
                player.fighter.limbs['a'].do(1,0)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_UP and T.check(T.TK_W):
            if player.fighter.limbs['w']:
                player.fighter.limbs['w'].do(0,-1)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_DOWN and T.check(T.TK_W):
            if player.fighter.limbs['w']:
                player.fighter.limbs['w'].do(0,1)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_LEFT and T.check(T.TK_W):
            if player.fighter.limbs['w']:
                player.fighter.limbs['w'].do(-1,0)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_RIGHT and T.check(T.TK_W):
            if player.fighter.limbs['w']:
                player.fighter.limbs['w'].do(1,0)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_UP and T.check(T.TK_S):
            if player.fighter.limbs['s']:
                player.fighter.limbs['s'].do(0,-1)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_DOWN and T.check(T.TK_S):
            if player.fighter.limbs['s']:
                player.fighter.limbs['s'].do(0,1)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_LEFT and T.check(T.TK_S):
            if player.fighter.limbs['s']:
                player.fighter.limbs['s'].do(-1,0)
            else:
                return 'didnt-take-turn'
        elif key == T.TK_RIGHT and T.check(T.TK_S):
            if player.fighter.limbs['s']:
                player.fighter.limbs['s'].do(1,0)
            else:
                return 'didnt-take-turn'
        
        
        elif key == T.TK_UP or key == T.TK_KP_8:
            player_move(0, -1)
        elif key == T.TK_DOWN or key == T.TK_KP_2:
            player_move(0, 1)
        elif key == T.TK_LEFT or key == T.TK_KP_4:
            player_move(-1, 0)
        elif key == T.TK_RIGHT or key == T.TK_KP_6:
            player_move(1, 0)
        # elif key == T.TK_HOME or key == T.TK_KP_7:
            # player_move(-1, -1)
        # elif key == T.TK_PAGEUP or key == T.TK_KP_9:
            # player_move(1, -1)
        # elif key == T.TK_END or key == T.TK_KP_1:
            # player_move(-1, 1)
        # elif key == T.TK_PAGEDOWN or key == T.TK_KP_3:
            # player_move(1, 1)
        elif key == T.TK_X:
            message('you wait...', 'white', 'player')
            pass  #do nothing ie wait for the monster to come to you
        
        
        else:
            # #test for other keys
            # if key == T.TK_G:
                # #pick up an item
                # for object in reversed(objects[player.z]):  #look for an item in the player's tile
                    # if object.x == player.x and object.y == player.y and object.item:
                        # object.item.pick_up(player)
                        # return 0
            
            # if key == T.TK_O:
                # target_tile()
            
            # if key == T.TK_Z:
                # for crea in objects[player.z]:
                    # print crea.name, crea.fighter.wit, crea.fighter.str, crea.fighter.spirit, crea.fighter.hp
            if key == T.TK_E:
                player.fighter.limbs['e'].do(0,0)
            
            elif key == T.TK_M and T.check(T.TK_SHIFT):
                for i in objects[0]:
                    if i != player:
                        do_damage(i, 100, 0)
            
            elif key == T.TK_C:
                msgbox('\n ' + chr(24) + chr(25) + chr(26) + chr(27) + '     arrow keys to walk' +
                            '\n q+arrow  attack first weapon when bar full' +
                            '\n a+arrow  strong attack first weapon when bar full' +
                            '\n w+arrow  attack second weapon when bar full' +
                            '\n s+arrow  strong attack second weapon when bar full' +
                            '\n e        healing potion when bar full' +
                            '\n x        wait' +
                            '\n c        controls' +
                            '\n esc      quit' )
                
                    
            
            # if key == T.TK_X:
                # libtcod.line_init(player.x, player.y, 10, 10)
                # while True:
                    # (a, b) = libtcod.line_step()
                    # print a, b
                    # T.print_(a, b, '[color=white]' + 'x')
                    # #render_all()
                    # if not a:
                        # break
    

            # if key == T.TK_I:
            # #show the inventory; if an item is selected, use it
                # chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
                # if chosen_item is not None:
                    # #chosen_item.use(player)
                    # decide = item_use_menu(chosen_item)
                    
                    # if not decide:
                        # return 'didnt-take-turn'
                    
                    # if decide == 'drop':
                        # chosen_item.drop(player)
                    # elif decide == 'throw':
                        # chosen_item.throw(player)
                        # initialize_fov()
                    # elif decide == 'use':
                        # chosen_item.use(player)
                    # elif decide == 'equip' or decide == 'dequip':
                        # chosen_item.owner.equipment.toggle_equip(player)
                    # return 0

            return 'didnt-take-turn'

def give_length(thing):
    i = 0
    for part in thing:
        i += 1
    return i
            
            
def ray_effect(x1, y1, x2, y2, color):#many thanks to pat for defender of the deep providing this code!!
    render_all()
    libtcod.console_set_default_foreground(0, color)

    for frame in range(LIMIT_FPS):
        libtcod.line_init(x1, y1, x2, y2)
        while True:
            (x, y) = libtcod.line_step()
            if x is None: break

            char = libtcod.random_get_int(0, libtcod.CHAR_SUBP_NW, libtcod.CHAR_SUBP_SW)
            libtcod.console_put_char(0, x, y, char, libtcod.BKGND_NONE)

        libtcod.console_check_for_keypress()
        libtcod.console_flush()
        


# def swing_effect(x1, y1, d, color, char): #x1, y1 = position of actor; d = radius of swing;
    # render_all()
    
    # segment = d*2 + 1
    
    # for frame in range(segment):
        # libtcod.line_init(x1, y1, x2, y2)
        # T.layer(3)
        # T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
        # while True:
            # (x, y) = libtcod.line_step()
            # if x is None: break
            # T.print_(x, y, '[color=' + color +  ']' + char)
    
    # T.refresh()
    # T.layer(0)
                    
def throw_effect(x1, y1, x2, y2, color, char):
    render_all()
    libtcod.line_init(x1, y1, x2, y2)
    while True:
        (a, b) = libtcod.line_step()
        T.layer(3)
        T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
        T.print_(a, b, '[color=' + color +  ']' + char)
        if not a: 
            break
        T.refresh()
        T.layer(0)
        T.delay(50)
        #render_all()
        
def fight_effect(cx, cy, color, char):
    render_all()
    num_frames = LIMIT_FPS
    for frame in range(20):
        T.layer(1)
        T.print_(cx, cy, '[color=' + color + ']' + char)
        T.refresh()
        render_all()
    T.layer(0)
    T.clear()
    render_all()
        
def player_death(player):
    #the game ended!
    global game_state
    #in case it gets called on many events happening the same loop
    if game_state == 'dead':
        return
    
    message('--You died!', 'red', 'player')
    game_state = 'dead'

    #for added effect, transform the player into a corpse!
    player.char = '%'    
    player.color = 'dark red'
    
def monster_death(monster):
    #transform it into a nasty corpse! it doesn't block, can't be
    #attacked and doesn't move
    message(monster.name + ' is dead!', 'yellow', 'monster')
    #drop all items
    try:
        for item in monster.fighter.inventory[:]:
            item.item.drop(monster)
            item.send_to_back()
    except:
        pass
    # if libtcod.random_get_int(0,0,100) < 33:
        # return monster.delete()
    
    if not monster.name == 'bob':
        shutil.move('monsters\\' + monster.name, "defeated\\" + monster.name)
    
    monster.char = '%'
    monster.color = 'dark red'
    monster.blocks = False
    
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name

    item_component = Item(use_function=None) #use tbd
    monster.item = item_component 
    monster.item.owner = monster #monster corpse can be picked up
    
    # resulted in a bug. Player was dying by explosion of Goblin Alchemist -> list.remove(x): x not in list
    try:
        monster.send_to_back()
    except:
        pass
        
    
    
DEATH_DICT = {
    'monster_death': monster_death,
    }

def distance_2_point(x1, y1, x2, y2):
        #return the distance to another object
        dx = x2 - x1
        dy = y2 - y1
        return math.sqrt(dx ** 2 + dy ** 2)
        
def target_ball(max_range=None):
    global key, mouse
    #return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked.
    (x, y) = (player.x, player.y)
    while True:
        #render the screen. this erases the inventory and shows the names of objects under the mouse.
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
        render_all()
       
        if mouse.dx:
            (x, y) = (mouse.cx, mouse.cy)

        (x, y) = key_control_target(x, y, key)        
            
        libtcod.console_set_default_foreground(0, libtcod.red)
        i = player.fighter.firepower() + 1
        for y2 in range(MAP_HEIGHT):
            for x2 in range(MAP_WIDTH):
                if distance_2_point(x, y, x2, y2) <= i and visible_to_player(x2,y2) and visible_to_player(x,y):
                    libtcod.console_put_char(0, x2, y2, chr(7), libtcod.BKGND_NONE)
        
        
        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            message('Canceled.')
            return (None, None)  #cancel if the player right-clicked or pressed Escape

        #accept the target if the player clicked in FOV, and in case a range is specified, if it's in that range
        if ( (key.vk == libtcod.KEY_ENTER or mouse.lbutton_pressed) and visible_to_player(x,y) and
                (max_range is None or player.distance(x, y) <= max_range)):
            return (x, y)    
    
def target_line(max_range=None):
    global key, mouse
    #return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked.
    (x, y) = (player.x, player.y)
    while True:
        #render the screen. this erases the inventory and shows the names of objects under the mouse.
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
        render_all()
       
        if mouse.dx:
            (x, y) = (mouse.cx, mouse.cy)
        
        (x, y) = key_control_target(x, y, key)
        
        if not libtcod.map_is_in_fov(fov_map, x, y): continue
        
        for frame in range(LIMIT_FPS):
            libtcod.line_init(player.x, player.y, x, y)
            while True:
                (a, b) = libtcod.line_step()
                if a is None: break
                
                libtcod.console_set_default_foreground(0, libtcod.red)
              
                libtcod.console_put_char(0, a, b, chr(7), libtcod.green)
                
                if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
                    message('Canceled.')
                    return (None, None)  #cancel if the player right-clicked or pressed Escape

                #accept the target if the player clicked in FOV, and in case a range is specified, if it's in that range
                if ( (key.vk == libtcod.KEY_ENTER or mouse.lbutton_pressed) and libtcod.map_is_in_fov(fov_map, x, y) and
                        (max_range is None or player.distance(x, y) <= max_range)):
                    return (x, y)
               
def target_tile(max_range=None):
    global key
    #return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked.
    (x, y) = (player.x, player.y)
    while True:
        
        T.refresh()
        render_all()
        
        key = T.read()
        if key == T.TK_MOUSE_MOVE:
            (x, y) = (T.state(T.TK_MOUSE_X), T.state(T.TK_MOUSE_Y))
        
        T.layer(3)
        T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
        T.print_(x-1, y, '-')
        T.print_(x+1, y, '-')
        T.print_(x, y+1, '|')
        T.print_(x, y-1, '|')
        T.layer(0)    
        
        get_names_under_cursor(x,y)
            
        (x, y) = key_control_target(x, y, key)
            
        if key == T.TK_MOUSE_RIGHT or key == T.TK_ESCAPE:
            #message('Canceled.')
            T.layer(3)
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            T.layer(0)
            return (None, None)  #cancel if the player right-clicked or pressed Escape

        #accept the target if the player clicked in FOV, and in case a range is specified, if it's in that range
        if key == T.TK_MOUSE_LEFT or key == T.TK_ENTER:
            T.layer(3)
            T.clear_area(0,0,SCREEN_WIDTH,SCREEN_HEIGHT)
            T.layer(0)
            return (x, y)    
 
def key_control_target(a, b, key):
    (x, y) = 0, 0
    if key == T.TK_UP or key == T.TK_KP_8:
        y -= 1
    elif key == T.TK_DOWN or key == T.TK_KP_2:
        y += 1
    elif key == T.TK_LEFT or key == T.TK_KP_4:
        x -= 1        
    elif key == T.TK_RIGHT or key == T.TK_KP_6:
        x += 1    
    # elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7 or chr(key.c) == 'z':
        # x -= 1
        # y -= 1
    # elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9 or chr(key.c) == 'u':
        # x += 1
        # y -= 1
    # elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1 or chr(key.c) == 'b':
        # x -= 1
        # y += 1
    # elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3 or chr(key.c) == 'n':
        # x += 1
        # y += 1
    return a+x, b+y
            
def target_monster(max_range=None):
    #returns a clicked monster inside FOV up to a range, or None if right-clicked
    while True:
        (x, y) = target_tile(max_range)
        if x is None:  #player cancelled
            return None

        #return the first clicked monster, otherwise continue looping
        for obj in objects[player.z]:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj

def closest_monster(max_range):
    #find closest enemy, up to a maximum range, and in the player's FOV
    closest_enemy = None
    closest_dist = max_range + 1  #start with (slightly more than) maximum range

    for object in objects[player.z]:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            #calculate distance between this object and the player
            dist = player.distance_to(object)
            if dist < closest_dist:  #it's closer, so remember it
                closest_enemy = object
                closest_dist = dist
    return closest_enemy



def cast_heal(source=None):
    #heal the player
    
    #not if at full health
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', 'red')
        return 'cancelled'

    #check source
    if source: #player uses prayer
        f = player.fighter.firepower()+1
    else: #healing potion
        f = 1
        
    message('Your wounds start to feel better!', 'light blue')
    player.fighter.heal(HEAL_AMOUNT * f )
    
def cast_full_heal(source=None):
    #heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', 'red')
        return 'cancelled'

    message('Your wounds start to feel much better!', 'light blue')
    player.fighter.heal(200)

def cast_firebolt(creator=None):
    #ask the player for a target tile to throw a fireball at
    message('Use keys or cursor to target, left-click or Enter at a target tile for FIREBOLT, or right-click or ESC to cancel.', 'blue')
    (x, y) = target_tile()
    if x is None: return 'cancelled'
   
    throw_effect(player.x, player.y, x, y, libtcod.orange, '*')
        
    for obj in objects[player.z]:  #damage every fighter in range, including the player
        if obj.x == x and obj.y == y:
            if obj.fighter:
                do_damage(obj, 0, (player.fighter.firepower()+1)*2)
            else:
                set_on_fire(obj)
                #message(obj.name + str(obj.flammable_prob))
    
def create_player():
    #create object representing the player
    
    fighter_component = Fighter(hp=20, 
                                damage=10, 
                                armor=0, 
                                wit=5, 
                                strength=5, 
                                spirit=5,
                                death_function=player_death)
    
    
    ai_component = PlayerAI(ticker, 10)
    player = Object(x_village, y_village, 0, '@', 'Ringo', 'white', blocks=True, fighter=fighter_component, ai=ai_component)
    
    d1 = Estus(ticker, 2)
    d1.owner = player
    player.fighter.limbs['e'] = d1

    
    #player.fighter.inventory.append(create_item('blank_book'))
    
    return player
    
def new_game():
    global player, game_msgs, game_sys_msgs, game_state, objects, ticker

    ticker = timer.Ticker()

    objects = [ [] for i in range(5)] # 0 - 14: normal dungeon; 15 + 16 branch levels
    
    make_map('new')
    
    player = create_player()    
    
    objects[player.z].append(player)
    
    set_player_on_upstairs('stairs')
    
    initialize_fov()

    game_state = 'playing'

    #create the list of game messages and their colors, starts empty
    game_msgs = []
    game_sys_msgs = []

    z_consistency() #general clean-up to set all z-coordinates of all items and objects
    
    #a warm welcoming message!
    message(chr(24) + ' Unlichtwesen ' + chr(25), 'white', 'monster')

   
def training():
    global player, game_msgs, game_sys_msgs, game_state, objects, ticker

    ticker = timer.Ticker()
    
    objects = [ [] for i in range(5)] # 0 - 14: normal dungeon; 15 + 16 branch levels
    
    make_map('training')
    
    player = create_player()    
    
    objects[player.z].append(player)
    
    set_player_on_upstairs('stairs')
    
    initialize_fov()

    game_state = 'playing'

    #create the list of game messages and their colors, starts empty
    game_msgs = []
    game_sys_msgs = []

    z_consistency() #general clean-up to set all z-coordinates of all items and objects
    
    #a warm welcoming message!
    message(chr(24) + ' Unlichtwesen ' + chr(25), 'white', 'monster')
    
def z_consistency():
    global objects
    for i in range(5):
        for obj in objects[i]:
            obj.z = i
            # if obj.fighter:
                # for item in obj.fighter.inventory:
                    # item.z = i
    
def set_player_on_upstairs(stair):
    global player
    
    if stair == 'ladder':
        for i in objects[player.z]:
            if i.name == 'upladder':
                player.x = i.x
                player.y = i.y
    else:
        for i in objects[player.z]:
            if i.name == 'upstairs':
                player.x = i.x
                player.y = i.y

def set_player_on_downstairs(stair):
    global player
    
    if (player.z == 8 or player.z == 15) and stair == 'ladder':
        for i in objects[player.z]:
            if i.name == 'ladder':
                player.x = i.x
                player.y = i.y
    else:
        for i in objects[player.z]:
            if i.name == 'stairs':
                player.x = i.x
                player.y = i.y
    
def next_level(stair):
    global player
    objects[player.z].remove(player)
    
    if stair == 'stairs':    
        player.z += 1
    elif stair == 'ladder':
        if player.z == 8:
            player.z = 15
        else:
            player.z += 1
    
    objects[player.z].append(player)
    set_player_on_upstairs(stair)
    message('You descend deeper into the heart of the dungeon...', 'blue')
    z_consistency()
    initialize_fov()

def prev_level(stair):
    global player 
    # write_obj_in_bones('relics')
    objects[player.z].remove(player)
    
    if stair == 'stairs':              
        player.z -= 1  
    elif stair == 'ladder':
        if player.z == 15:
            player.z = 8
        else:
            player.z -= 1
        
    objects[player.z].append(player)    
    set_player_on_downstairs(stair)
    message('You go up the stairs cautiously.', 'blue')
    #make_map('up')  #create a fresh new level!
    z_consistency()
    initialize_fov()

def initialize_fov():
    global fov_recompute, fov_map, light_map
    fov_recompute = True

    #create the FOV map, according to the generated map
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[player.z][x][y].block_sight, not map[player.z][x][y].blocked)
    
def play_game():
    global key, mouse
    player_action = None
    
    #main loop
    while True:
        if game_state == 'exit':
            break
       
        ticker.ticks += 1
        ticker.next_turn()    
       
def generate_10_demons():
    
    for i in range(10):   
        create_monster('demon', 0, 0, 0) #monster x,y,z
        
def intro_screen():
    
    T.set("0x0084: titlescreen.png, align=top-left");
    T.color('white')
    T.print_(0,0, '[U+0084]')
    
    #present the root console to the player and wait for a key-press
    libtcod.console_flush()    
    key = libtcod.console_wait_for_keypress(True)

    # go on to main menu
    main_menu()
 
def start_menu():
    
    global monster_list
    monster_list = []
    monster_list = os.listdir('monsters')
    
    if monster_list:
        main_menu()
        return
    
    while True:
        T.layer(0)
        T.clear()
        T.color('yellow')
        
        T.print_(SCREEN_WIDTH/2, SCREEN_HEIGHT/3, '[align=center]& & &')
        
        options = ['They are coming in! (with enter)']
        # #show options and wait for the player's choice
        choice = menu('', options, SCREEN_WIDTH / 2)
        
        if choice == 0:  #new generation
            generate_10_demons()
            monster_list = os.listdir('monsters')
            main_menu()
            break
            
def main_menu():

    while True:
        #show the background image, at twice the regular console resolution
        T.layer(0)
        T.clear()
        
        #Background pic
        T.set("0x009F: titlescreen.png, align=top-left");
        T.color('white')
        T.print_(0,0, '[U+009F]')
        
        #show the game's title, and some credits!
        T.color('yellow')
        
        T.print_(SCREEN_WIDTH/2, SCREEN_HEIGHT/3-2, '[align=center]The hour of meeting')
        T.print_(SCREEN_WIDTH/2, SCREEN_HEIGHT/3, '[align=center]UNLICHTWESEN')
        T.print_(SCREEN_WIDTH/2, SCREEN_HEIGHT-2, '[align=center]Game by Jan | v 1.0')
                
        options = ['Play the game', 'Training', 'Quit']

        #show options and wait for the player's choice
        choice = menu('', options, 24)
        
        if choice == 0:  #new game
            new_game()
            monster_selection_screen()
            choose_weapon()
            
        elif choice == 1:  #load last game
            training()
            choose_weapon()

        elif choice == 2:  #quit
            break
                  
                  
def monster_selection_screen():
    global c_demon
    T.layer(0)
    T.clear()

    c_demon = None
    
    while True:
        for i in range(1):
            time.sleep(0.2)
        
        #show the game's title, and some credits!
        T.print_(SCREEN_WIDTH/2, SCREEN_HEIGHT/3-2, '[align=center]Choose your enemy!')
        
        T.print_(SCREEN_WIDTH/2, SCREEN_HEIGHT-2, '[align=center]Game by Jan | v 1.0')
        
        monster_list = os.listdir('monsters')
            
        #show options and wait for the player's choice
        choice = menu('', monster_list, 24)

        if choice or choice == 0:
            place_demon(monster_list[choice])
            break
        else:
            win()

                  
def choose_weapon():
    global chosen_weapons
    T.layer(0)
    T.clear()

    empty_hands = 2
    chosen_weapons = []
    while True:
        for i in range(1):
            time.sleep(0.2)
        
        #show the game's title, and some credits!
        T.print_(SCREEN_WIDTH/2, SCREEN_HEIGHT/3-2, '[align=center]Choose your two weapons')
        if chosen_weapons:
            T.print_(SCREEN_WIDTH/2, SCREEN_HEIGHT/3, '[align=center]' + chosen_weapons[0] + ' +')
        
        T.print_(SCREEN_WIDTH/2, SCREEN_HEIGHT-2, '[align=center]Game by Jan | v 1.0')
        
        #show options and wait for the player's choice
        
        choice = menu('', ['Dagger', 'Sword', 'Spear', 'Morningstar'], 24)

        if empty_hands == 2:
            set = 'q','a'
        else:
            set = 'w','s'
        
        if choice == 0:            
            d1 = Dagger(ticker, 2)
            d1.owner = player
            player.fighter.limbs[set[0]] = d1
            
            d2 = DaggerStrong(ticker, 2)
            d2.owner = player
            player.fighter.limbs[set[1]] = d2
            
            chosen_weapons.append('dagger')
            empty_hands -= 1
            if not empty_hands:
                break

        elif choice == 1:
            s1 = Sword(ticker, 2)
            s1.owner = player
            player.fighter.limbs[set[0]] = s1
            
            s2 = SwordStrong(ticker, 2)
            s2.owner = player
            player.fighter.limbs[set[1]] = s2
            
            chosen_weapons.append('sword')
            empty_hands -= 1
            if not empty_hands:
                break

        elif choice == 2:
            s3 = Spear(ticker, 2)
            s3.owner = player
            player.fighter.limbs[set[0]] = s3
            
            s4 = SpearStrong(ticker, 2)
            s4.owner = player
            player.fighter.limbs[set[1]] = s4
            
            chosen_weapons.append('spear')
            empty_hands -= 1
            if not empty_hands:
                break
            
        elif choice == 3:
            m1 = Morningstar(ticker, 2)
            m1.owner = player
            player.fighter.limbs[set[0]] = m1
            
            m2 = MorningstarStrong(ticker, 2)
            m2.owner = player
            player.fighter.limbs[set[1]] = m2
            
            chosen_weapons.append('morningstar')
            empty_hands -= 1
            if not empty_hands:
                break
    
    play_game()
            
            
T.open()
T.set("window: size=" + str(SCREEN_WIDTH) + "x" + str(SCREEN_HEIGHT) + ', title=Unlichtwesen v1.0')
T.set("font: courbd.ttf, size=16")

#T.set("0x00A1: tileset_16.png, size=16x16, align=top-left, spacing=2x1" )

start_menu()
#main_menu()

