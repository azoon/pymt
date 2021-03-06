'''
Base: Main event loop, provider creation, window management...
'''

__all__ = [
    'TouchEventLoop',
    'pymt_usage', 'runTouchApp', 'stopTouchApp',
    'getFrameDt', 'getAvailableTouchs', 'getCurrentTouches',
    'getEventLoop',
    'touch_event_listeners',
    'pymt_providers',
    'getWindow', 'setWindow'
]

import pymt
import sys
import os
from logger import pymt_logger
from exceptions import pymt_exception_manager, ExceptionManager
from clock import getClock
from input import *

# All event listeners will add themselves to this
# list upon creation
touch_event_listeners   = []
touch_list              = []
pymt_window             = None
pymt_providers          = []
pymt_evloop             = None
frame_dt                = 0.01 # init to a non-zero value, to prevent user zero division

def getFrameDt():
    '''Return the last delta between old and new frame.'''
    global frame_dt
    return frame_dt

def getCurrentTouches():
    global touch_list
    return touch_list

@pymt.deprecated
def getAvailableTouchs():
    return getCurrentTouches()

def getWindow():
    global pymt_window
    return pymt_window

def setWindow(win):
    global pymt_window
    pymt_window = win

def getEventLoop():
    global pymt_evloop
    return pymt_evloop

class TouchEventLoop(object):
    '''Main event loop. This loop handle update of input + dispatch event
    '''
    def __init__(self):
        super(TouchEventLoop, self).__init__()
        self.quit = False
        self.input_events = []
        self.postproc_modules = []

    def start(self):
        global pymt_providers
        for provider in pymt_providers:
            provider.start()

    def close(self):
        global pymt_providers
        for provider in pymt_providers:
            provider.stop()

    def add_postproc_module(self, mod):
        self.postproc_modules.append(mod)

    def remove_postproc_module(self, mod):
        if mod in self.postproc_modules:
            self.postproc_modules.remove(mod)

    def post_dispatch_input(self, type, touch):
        # update available list
        global touch_list
        if type == 'down':
            touch_list.append(touch)
        elif type == 'up':
            touch_list.remove(touch)

        # dispatch to listeners
        if not touch.grab_exclusive_class:
            for listener in touch_event_listeners:
                if type == 'down':
                    listener.dispatch_event('on_touch_down', touch)
                elif type == 'move':
                    listener.dispatch_event('on_touch_move', touch)
                elif type == 'up':
                    listener.dispatch_event('on_touch_up', touch)

        # dispatch grabbed touch
        touch.grab_state = True
        for wid in touch.grab_list:
            root_window = wid.get_root_window()
            if wid != root_window and root_window is not None:
                touch.push()
                touch.scale_for_screen(*root_window.size)
                # and do to_local until the widget
                if wid.parent:
                    touch.x, touch.y = wid.parent.to_widget(touch.x, touch.y)
                else:
                    touch.x, touch.y = wid.to_parent(wid.to_widget(touch.x, touch.y))

            touch.grab_current = wid

            if type == 'down':
                # don't dispatch again touch in on_touch_down
                # a down event are nearly uniq here.
                # wid.dispatch_event('on_touch_down', touch)
                pass
            elif type == 'move':
                wid.dispatch_event('on_touch_move', touch)
            elif type == 'up':
                wid.dispatch_event('on_touch_up', touch)

            touch.grab_current = None

            if wid != root_window and root_window is not None:
                touch.pop()
        touch.grab_state = False

    def _dispatch_input(self, type, touch):
        ev = (type, touch)
        # remove the save event for the touch if exist
        if ev in self.input_events:
            self.input_events.remove(ev)
        self.input_events.append(ev)

    def dispatch_input(self):
        global pymt_providers

        # first, aquire input events
        for provider in pymt_providers:
            provider.update(dispatch_fn=self._dispatch_input)

        # execute post-processing modules
        for mod in self.postproc_modules:
            self.input_events = mod.process(events=self.input_events)

        # real dispatch input
        for type, touch in self.input_events:
            self.post_dispatch_input(type=type, touch=touch)

        self.input_events = []

    def idle(self):
        # update dt
        global frame_dt
        frame_dt = getClock().tick()

        # read and dispatch input from providers
        self.dispatch_input()

        if pymt_window:
            pymt_window.dispatch_events()
            pymt_window.dispatch_event('on_update')
            pymt_window.dispatch_event('on_draw')
            pymt_window.flip()

        # don't loop if we don't have listeners !
        if len(touch_event_listeners) == 0:
            self.exit()
            return False

        return self.quit

    def run(self):
        while not self.quit:
            self.idle()
        self.exit()

    def close(self):
        self.quit = True

    def exit(self):
        self.close()
        if pymt_window:
            pymt_window.close()


def pymt_usage():
    '''PyMT Usage: %s [OPTION...] ::

        -h, --help                  prints this mesage
        -f, --fullscreen            force run in fullscreen
        -w, --windowed              force run in window
        -p, --provider id:provider[,options] add a provider (eg: ccvtable1:tuio,192.168.0.1:3333)
        -F, --fps                   show fps in window
        -m mod, --module=mod        activate a module (use "list" to get available module)
        -s, --save                  save current PyMT configuration
        --size=640x480              size of window
        --dump-frame                dump each frame in file
        --dump-prefix               specify a prefix for each frame file
        --dump-format               specify a format for dump

    '''
    print pymt_usage.__doc__ % (os.path.basename(sys.argv[0]))


def _run_mainloop():
    '''Main loop is done by us.'''
    while True:
        try:
            pymt_evloop.run()
            stopTouchApp()
            break
        except BaseException, inst:
            # use exception manager first
            r = pymt_exception_manager.handle_exception(inst)
            if r == ExceptionManager.RAISE:
                stopTouchApp()
                raise
            else:
                pass


def runTouchApp(widget=None, slave=False):
    '''Static main function that starts the application loop.
    You got some magic things, if you are using argument like this ::

        `<empty>`
            To make dispatching work, you need at least one
            input listener. If not, application will leave.
            (MTWindow act as an input listener)

        `widget`
            If you pass only a widget, a MTWindow will be created,
            and your widget will be added on the window as the root
            widget.

        `slave`
            No event dispatching are done. This will be your job.

        `widget + slave`
            No event dispatching are done. This will be your job, but
            we are trying to get the window (must be created by you before),
            and add the widget on it. Very usefull for embedding PyMT
            in another toolkit. (like Qt, check pymt-designed)
    
    '''

    global pymt_evloop
    global pymt_providers

    # Ok, we got one widget, and we are not in slave mode
    # so, user don't create the window, let's create it for him !
    ### Not needed, since we always create window ?!
    #if not slave and widget:
    #    global pymt_window
    #    from ui.window import MTWindow
    #    pymt_window = MTWindow()

    # Check if we show event stats
    if pymt.pymt_config.getboolean('pymt', 'show_eventstats'):
        pymt.widget.event_stats_activate()

    # Instance all configured input
    for key, value in pymt.pymt_config.items('input'):
        pymt_logger.debug('Create provider from %s' % (str(value)))

        # split value
        args = str(value).split(',', 1)
        if len(args) == 1:
            args.append('')
        provider_id, args = args
        provider = TouchFactory.get(provider_id)
        if provider is None:
            pymt_logger.warning('Unknown <%s> provider' % str(provider_id))
            continue

        # create provider
        p = provider(key, args)
        if p:
            pymt_providers.append(p)

    pymt_evloop = TouchEventLoop()

    # add postproc modules
    for mod in pymt_postproc_modules:
        pymt_evloop.add_postproc_module(mod)

    # add main widget
    if widget and getWindow():
        getWindow().add_widget(widget)

    # start event loop
    pymt_logger.info('Start application main loop')
    pymt_evloop.start()

    # we are in a slave mode, don't do dispatching.
    if slave:
        return

    # in non-slave mode, they are 2 issues
    #
    # 1. if user created a window, call the mainloop from window.
    #    This is due to glut, it need to be called with
    #    glutMainLoop(). Only FreeGLUT got a gluMainLoopEvent().
    #    So, we are executing the dispatching function inside
    #    a redisplay event.
    #
    # 2. if no window is created, we are dispatching event lopp
    #    ourself (previous behavior.)
    #
    if pymt_window is None:
        _run_mainloop()
    else:
        pymt_window.mainloop()

    # Show event stats
    if pymt.pymt_config.getboolean('pymt', 'show_eventstats'):
        pymt.widget.event_stats_print()

def stopTouchApp():
    global pymt_evloop
    if pymt_evloop is None:
        return
    pymt_logger.info('Leaving application in progress...')
    pymt_evloop.close()
