

# example of item
Item = {
    'char': 'x',
    'name': 'item',
    'color': 'black',
    'equipment': False,
    'use_function': None,
    'ignite_function': None,
    'flammable_prob': 50,
    'conditions': [None, 'damaged']
    }
    
inscription = {
    'char': '=',
    'name': 'inscription',
    'color': 'sky'
    }    

bamboo_stick = {
    'char': '/',
    'name': 'bamboo stick',
    'color': 'orange',
    'equipment': True,
    'slot': 'right hand',
    'damage_bonus': 5,
    'flammable_prob': 80
    }     
    
blank_book = {
    'char': '[U+0286]',
    'name': 'blank book',
    'color': 'yellow',
    'equipment': True,
    'slot': 'left hand',
    'wis_bonus': 10,
    'flammable_prob': 30
    }    
   
campfire = {
    'char': chr(243),
    'name': 'campfire',
    'color': 'flame',
    'flammable_prob': 100,
    'light_source': 'campfire',
    'glow': 1
    }         
 
candle = {
    'char': '(',
    'name': 'candle',
    'color': 'white',
    'flammable_prob': 100,
    'light_source': 'candle',
    'conditions': [None, 'burned down']
    }  
   
chisel = {
    'char': ';',
    'name': 'chisel',
    'color': 'light_grey',
    'use_function': 'engrave'
    }   
    
crown = {
    'char': '[',
    'name': 'crown',
    'color': 'yellow',
    'equipment': True,
    'slot': 'head',
    'armor_bonus': 2
    }  
  
dagger = {
    'char': '-',
    'name': 'dagger',
    'color': 'grey',
    'equipment': True,
    'slot': 'right hand',
    'flammable_prob': 0,
    'damage_bonus': 1
    }
    
# excalibur = {
    # 'char': '/',
    # 'name': 'excalibur',
    # 'color': 'yellow',    
    # 'equipment': True,
    # 'slot': 'right hand',
    # 'damage_bonus': 100
    # }     

feather = {
    'char': '(',
    'name': 'feather',
    'color': 'grey',
    'use_function': 'write_scroll',
    'flammable_prob': 100,
    'ignite_function': 'burn_to_dust'
    }
    
    
fire_fist = {
    'char': '-',
    'name': 'fire fist',
    'color': 'orange',
    'equipment': True,
    'slot': 'right hand',
    'flammable_prob': 100,
    'damage_bonus': 1,
    'light_source': True
    }    
    
flintstone = {
    'char': '"',
    'name': 'flintstone',
    'color': 'grey',
    'use_function': 'create_spark',
    'flammable_prob': 0
    }
    
    
flute = {
    'char': '(',
    'name': 'flute',
    'color': 'amber',
    'use_function': 'play_flute',
    'flammable_prob': 0
    }
    
healing_potion = {
    'char': '!',
    'name': 'healing potion',
    'color': 'light_blue',
    'item': True,
    'use_function': 'cast_heal'
    }
    
lamp = {
    'char': '(',
    'name': 'lamp',
    'color': 'gold',
    'equipment': True,
    'slot': 'left hand',
    'flammable_prob': 100,
    'light_source': 'lamp'
    }

lantern = {
    'char': chr(24),
    'name': 'lantern',
    'color': 'gold',
    'flammable_prob': 100,
    'light_source': 'lamp'
    }       
    
lava = {
    'char': '{',
    'name': 'lava',
    'color': 'red',
    'flammable_prob': 100,
    }
    
mummy_head_wrapping = {
    'char': '[',
    'name': 'mummy head wrapping',
    'color': 'white',
    'equipment': True,
    'flammable_prob': 100,
    'slot': 'head',
    'armor_bonus': 1
    }

mummy_body_wrapping = {
    'char': '[',
    'name': 'mummy body wrapping',
    'color': 'white',
    'equipment': True,
    'flammable_prob': 100,
    'slot': 'body',
    'armor_bonus': 1
    }
    
mummy_leg_wrapping = {
    'char': '[',
    'name': 'mummy leg wrapping',
    'color': 'white',
    'equipment': True,
    'flammable_prob': 100,
    'slot': 'leg',
    'armor_bonus': 1
    }     
    
potion_of_oil = {
    'char': '!',
    'name': 'potion of oil',
    'color': 'orange',
    'item': True,
    'ignite_function': 'explode',
    'flammable_prob': 100
    }

potion_of_full_healing = {
    'char': '!',
    'name': 'potion of full healing',
    'color': 'light_blue',
    'item': True,
    'use_function': 'cast_full_heal'
    }
    
pen = {
    'char': ';',
    'name': 'pen',
    'color': 'yellow',
    'use_function': 'write_book',
    'flammable_prob': 0,
    'conditions': [None]
    }
    
ring = {
    'char': '=',
    'name': 'ring',
    'color': 'yellow',
    'equipment': True,
    'slot': 'finger',
    'armor_bonus': 2
    }  
    
ring_mail = {
    'char': '[',
    'name': 'ring mail',
    'color': 'light_grey',
    'equipment': True,
    'slot': 'body',
    'armor_bonus': 6
    }  

    
    
robe_of_flames = {
    'char': '[',
    'name': 'robe of flames',
    'color': 'red',
    'equipment': True,
    'slot': 'body',
    'armor_bonus': 6,
    'flammable_prob': 100,
    'light_source': 'torch',
    'glow': 1
    }     
    
robe = {
    'char': '[',
    'name': 'robe',
    'color': 'green',
    'equipment': True,
    'slot': 'body',
    'armor_bonus': 1,
    'flammable_prob': 100
    } 

rubble = {
    'char': ',',
    'name': 'rubble',
    'color': 'darkest_grey',
    'flammable_prob': 0
    }    
    
scepter = {
    'char': '/',
    'name': 'scepter',
    'color': 'yellow',
    'equipment': True,
    'slot': 'right hand',
    'damage_bonus': 2,
    'flammable_prob': 0
    }   
    
scroll_of_cooking = {
    'char': '?',
    'name': 'scroll of cooking',
    'color': 'darkest_green',
    'ignite_function': 'burn_to_dust',
    'flammable_prob': 100,
    'use_function': 'read_scroll'
    }    
    
shield = {
    'char': '[',
    'name': 'shield',
    'color': 'light_grey',
    'equipment': True,
    'slot': 'left hand',
    'armor_bonus': 3
    }  
 
shovel = {
    'char': '(',
    'name': 'shovel',
    'color': 'light_grey',
    'use_function': 'use_shovel'
    }  
 
sky = {
    'char': '{',
    'name': 'lava',
    'color': 'red'
    } 

stone = {
    'char': '*',
    'name': 'stone',
    'color': 'grey',
    'use_function': 'stone',
    'flammable_prob': 0
    }

short_sword = {
    'char': '/',
    'name': 'short sword',
    'color': 'light_grey',
    'equipment': True,
    'slot': 'right hand',
    'damage_bonus': 4
    }    

long_sword = {
    'char': '/',
    'name': 'longsword',
    'color': 'lighter_grey',
    'equipment': True,
    'slot': 'right hand',
    'damage_bonus': 7
    }    

    
torch = {
    'char': '(',
    'name': 'torch',
    'color': 'darkest_orange',
    'equipment': True,
    'slot': 'right hand',
    'damage_bonus': 2,
    'flammable_prob': 100,
    'light_source': 'torch'
    } 

tree = {
    'char': chr(5),
    'name': 'tree',
    'color': 'dark_green',
    'flammable_prob': 100,
    'ignite_function': 'burn_tree',
    'light_source': 'tree'
    }  

wild_fur = {
    'char': '[',
    'name': 'wild fur',
    'color': 'dark_yellow',
    'equipment': True,
    'slot': 'body',
    'armor_bonus': 4,
    'flammable_prob': 60
    } 
    
wooden_sword = {
    'char': '/',
    'name': 'wooden sword',
    'color': 'orange',
    'equipment': True,
    'flammable_prob': 100,
    'slot': 'right hand',
    'damage_bonus': 3
    }
    
wooden_block = {
    'char': chr(5),
    'name': 'wooden block',
    'blocks': True,
    'color': 'orange',
    'flammable_prob': 100,
    'ignite_function': 'burn_to_dust'
    }      

grass = {
    'char': '"',
    'name': 'grass',
    'color': 'darkest_green',
    'flammable_prob': 100,
    'ignite_function': 'burn_to_dust'
    }
    
wood = {
    'char': '(',
    'name': 'wood',
    'color': 'orange',
    'conditions': [None, 'dried', 'smoked', 'blackened', 'burned', 'charred'],
    'flammable_prob': 100
    }

    
####################################################
   
testspark = {
    'char': "'",
    'name': 'ts',
    'color': 'yellow',
    }  
    
testr = {
    'char': 'r',
    'name': 'R',
    'color': 'lighter_sepia',
    } 

testn = {
    'char': 'n',
    'name': 'N',
    'color': 'flame',
    }     
   
testg = {
    'char': 'g',
    'name': 'G',
    'color': 'darker_green',
    }  
    
testc = {
    'char': 'c',
    'name': 'C',
    'color': 'green',
    }  
    
testl = {
    'char': 'L',
    'name': 'L',
    'color': 'dark_yellow',
    }  
    
 
    
##############################################################
   
    
    # equipment_component = Equipment(slot='left hand', wis_bonus=10, prayer_number=4)
    # obj = Object(0, 0, '+', 'book of holy water', libtcod.orange, equipment=equipment_component)
    # player.fighter.inventory.append(obj)
    
    # equipment_component = Equipment(slot='left hand', wis_bonus=10, prayer_number=2)
    # obj = Object(0, 0, '+', 'book of lightning', libtcod.orange, equipment=equipment_component)
    # player.fighter.inventory.append(obj)
    