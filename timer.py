'''contains Ticker class for scheduling system
http://www.roguebasin.com/index.php?title=A_simple_turn_scheduling_system_--_Python_implementation
'''

class Ticker(object):
    '''Simple timer for roguelike games.'''
    def __init__(self):
        self.ticks = 0  # current ticks--sys.maxint is 2147483647
        self.schedule = {}  # this is the dict of things to do {ticks: [obj1, obj2, ...], ticks+1: [...], ...}

    def schedule_turn(self, interval, obj):
        self.schedule.setdefault(self.ticks + interval, []).append(obj)

    def next_turn(self):
        things_to_do = self.schedule.pop(self.ticks, [])
        for obj in things_to_do:
            obj.take_turn()
