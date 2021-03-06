__all__ =  ('Clock', 'getClock')

import time

class _Event(object):

    loop = False
    callback = None
    timeout = 0.
    _last_dt = 0.
    _dt = 0.

    def __init__(self, loop, callback, timeout, starttime):
        self.loop = loop
        self.callback = callback
        self.timeout = timeout
        self._last_dt = starttime

    def do(self, dt):
        self.callback(dt)

    def tick(self, curtime):
        # timeout happen ?
        if curtime - self._last_dt < self.timeout:
            return True

        # calculate current timediff for this event
        self._dt = curtime - self._last_dt
        self._last_dt = curtime

        # call the callback
        ret = self.callback(self._dt)

        # if it's a once event, don't care about the result
        # just remove the event
        if not self.loop:
            return False

        # if user return an explicit false,
        # remove the event
        if ret == False:
            return False

        return True


class Clock(object):

    _dt = 0
    _last_tick = time.time()
    _fps = 0
    _fps_counter = 0
    _last_fps_tick = None
    _events = []

    def tick(self):
        # tick the current time
        current = time.time()
        self._dt = current - self._last_tick
        self._fps_counter += 1
        self._last_tick = current

        # calculate fps things
        if self._last_fps_tick == None:
            self._last_fps_tick = current
        elif current - self._last_fps_tick > 1:
            self._fps = self._fps_counter / float(current - self._last_fps_tick)
            self._last_fps_tick = current
            self._fps_counter = 0

        # process event
        self._process_events()

        return self._dt

    def get_fps(self):
        return self._fps

    def get_time(self):
        return self._last_tick

    def schedule_once(self, callback, timeout):
        event = _Event(False, callback, timeout, self._last_tick)
        self._events.append(event)

    def schedule_interval(self, callback, timeout):
        event = _Event(True, callback, timeout, self._last_tick)
        self._events.append(event)

    def unschedule(callback):
        self._events = [x for x in self._events if x.callback != callback]

    def _process_events(self):
        to_remove = None

        # process event
        for event in self._events:
            if event.tick(self._last_tick) == False:
                if to_remove is None:
                    to_remove = [event]
                else:
                    to_remove.append(event)

        # event to remove ?
        if to_remove is None:
            return
        for event in to_remove:
            self._events.remove(event)




# create a default clock
_default_clock = Clock()

# make it available
def getClock():
    global _default_clock
    return _default_clock

