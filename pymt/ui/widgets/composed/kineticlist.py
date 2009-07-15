'''
Kinetic List: Custom list with kinetic interaction
'''

__all__ = ['MTKineticList', 'MTKineticObject', 'MTKineticItem', 'MTKineticImage']

from pyglet.gl import *
from pyglet.text import Label
from ....graphx import set_color, drawRectangle, GlDisplayList
from ....graphx import drawCSSRectangle
from ...factory import MTWidgetFactory
from ....vector import Vector
from ....mtpyglet import getFrameDt
from ..stencilcontainer import MTStencilContainer
from ..widget import MTWidget
from ..button import MTButton, MTToggleButton, MTImageButton
from ...animation import Animation, AnimationAlpha
from vkeyboard import MTTextInput

class MTKineticList(MTStencilContainer):
    '''This is a kinetic container widget, that allows you to make
    a kinetic list scrolling in either direction.

    :Parameters:
        `friction` : float, defaults to 10
            The Pseudo-friction of the pseudo-kinetic scrolling.
            Formula for friction is ::
                acceleration = 1 + friction * frame_delta_time
        `padding_x` : int, defaults to 4
            The spacing between scrolling items on the x axis
        `padding_y` : int, defaults to 4
            The spacing between scrolling items on the y axis
        `w_limit` : int, defaults to 1
            The limit of items that will appear horizontally.
            When this is set to a non-zero value the width(in
            terms of items in the kinetic list) will be w_limit,
            and the height will continually expand.
        `h_limit` : int, defaults to 0
            Exect opposite of w_limit.  If I didn't make either
            this or w_limit clear go bug xelapond
        `do_x` : bool, defaults to False
            Enable scrolling on the X axis
        `do_y` : bool, defaults to True
            Enable scrolling on the Y axis
        `title` : string, defaults to <Title Goes Here>
            Sets the title of the widget, which appears in 20
            point font at the top
        `deletable` : bool, defaults to True
            When enabled it allows you to delete children by
            entering delete mode(red button in upper left)
        `searchable` : bool, defaults to True
            When enabled it allows you to enter search mode
            and filter items

    :Styles:
        `bg-color` : color
             Background color of the widget

    :Events:
        `on_press` (child, callback)
            Fired when a specific item has been tapped and moved
            less then forty pixels(so we know they tapped it, didn't
            try and scroll).  It sends the item tapped, and the return
            item(if none was defined it sends None)
        `on_delete` (child, callback)
            Fired when an item gets deleted.  Passes that item and the
            return item(None if not provided).
    '''
    def __init__(self, **kwargs):
        kwargs.setdefault('friction', 10)
        kwargs.setdefault('padding_x', 4)
        kwargs.setdefault('padding_y', 4)
        kwargs.setdefault('w_limit', 1)
        kwargs.setdefault('h_limit', 0)
        kwargs.setdefault('do_x', False)
        kwargs.setdefault('do_y', True)
        kwargs.setdefault('title', '<Title Goes Here>')
        kwargs.setdefault('deletable', True)
        kwargs.setdefault('searchable', True)

        super(MTKineticList, self).__init__(**kwargs)
        self.register_event_type('on_press')
        self.register_event_type('on_delete')

        self.friction = kwargs.get('friction')
        self.padding_x = kwargs.get('padding_x')
        self.padding_y = kwargs.get('padding_y')
        self.w_limit = kwargs.get('w_limit')
        self.h_limit = kwargs.get('h_limit')
        if self.w_limit and self.h_limit:
            raise Exception('You cannot limit both axes')
        elif not(self.w_limit or self.h_limit):
            raise Exception('You must limit at least one axis')

        self.do_x = kwargs.get('do_x')
        self.do_y = kwargs.get('do_y')
        self.titletext = kwargs.get('title')
        self.deletable = kwargs.get('deletable')
        self.searchable = kwargs.get('searchable')

        #X and Y translation vectors for the kinetic movement
        self.vx = 0
        self.vy = 0

        #Hold the total size of all the kinetic items and padding
        self.total_size = [0, 0]

        #Holds widgets not a part of the scrolling(search button, etc)
        self.widgets = []

        #Title Text
        self.title = Label(font_size=18,
                           bold=True,
                           anchor_x='center',
                           anchor_y='center',
                           text=self.titletext)
        self.title.x = self.width/2 + self.x
        self.title.y = self.height - 20 + self.y

        #Delete Button
        if self.deletable:
            self.db = MTToggleButton(label='X',
                               pos=(self.x + self.width - 80, self.y + self.height - 40),
                               size=(80, 40),
                               cls='kineticlist-delete')
            self.db.on_press = self.toggle_delete
            self.widgets.append(self.db)

        #Search Button and Input Text Area
        if self.searchable:
            self.sb = MTToggleButton(label='S',  #Button
                               pos=(self.x, self.y + self.width - 40),
                               size=(80, 40),
                               cls='kineticlist-search')

            self.sb.on_press = self.toggle_search
            self.sb.parent = self
            self.widgets.append(self.sb)

            self.sinput = MTTextInput(pos=(self.x, self.y + self.height - 40), size=(80, 40))  #Text Input area
            self.sinput.parent = self
            self.sinput.on_text_change = self.apply_filter
            self.widgets.append(self.sinput)

            #Animations to hide and show the search text input box
            self.a_sinput_in = Animation(self.sinput, 'Move In', 'y', self.y + self.height - 40 - self.sinput.size[1], 1, 10)
            self.a_sinput_out = Animation(self.sinput, 'Move Out', 'y', self.y + self.height - self.sinput.size[1], 1, 10)

        #How far to offset the axes(used for scrolling/panning)
        self.xoffset = 0
        self.yoffset = 0

        self.childmap = {}  #Maps between items in the kinetic list and the item we return('callback' param in self.add, defaults to None')
        self.pchildren = []  #Holds all the current children
        #Self the children just holds the children currently being displayed

        self.touch = {} #For extra blob stats

    def on_press(self, child, callback):
        pass

    def on_delete(self, child, callback):
        pass

    def add(self, item, callback=None):
        '''Add an item to the kinetic scrolling area.
        item is the item you would like to add to the list
        callback is an optional arg that is returned when you
        tap the item(through on_press).  It is optional.
        '''
        self.children.insert(0, item)
        self.pchildren.insert(0, item)
        item.parent = self
        if callback:
            self.childmap[item] = callback
        else:
            self.childmap[item] = None

    def delete_item(self, item):
        '''Given item, that item is removed from the kinetic list
        and the on_delete event is dispatched
        '''
        self.dispatch_event('on_delete', item, self.childmap[item])
        self.children.remove(item)
        try:
            self.pchildren.remove(item)
        except:
            pass
        try:
            del self.childmap[item]
        except:
            pass

    def toggle_delete(self, touch):
        '''Toggles the delete buttons on items
        Attached to the on_press handler of the delete button(self.db)
        '''
        for child in self.children:
            if self.db.get_state() == 'down':
                child.show_delete()
            else:
                child.hide_delete()

    def toggle_search(self, touch):
        '''Toggles the search area
        Attached to the on_press handler of self.sb(the green search button)
        '''
        if self.sb.get_state() == 'down':
            self.a_sinput_in.reset()
            self.a_sinput_in.start()
        else:
            try:
                self.sinput.hide_keyboard()
            except:
                #There isn't a keyboard, so it throws a ValueError
                pass
            self.sinput.label = ''
            self.a_sinput_out.reset()
            self.a_sinput_out.start()
            self.endsearch()

    def apply_filter(self):
        '''Applies the filter in self.sinput to the current children set
        Attached to the on_text_change handler of self.sinput
        '''
        self.search(self.sinput.label, 'label')
        #Move them so you don't have to scroll up to see them
        self.yoffset = self.padding_y
        self.xoffset = self.padding_x

    def filter(self, pattern, attr):
        '''Given an attribute of the children, and a pattern, return
        a list of the children with which pattern is in attr
        '''
        return filter(lambda c: pattern in str(getattr(c, attr)), self.pchildren)

    def search(self, pattern, attr):
        '''Apply a search pattern to the current set of children'''
        self.children = self.filter(pattern, attr)

    def endsearch(self):
        '''Resets the children set to the full set'''
        self.children = self.pchildren

    def _get_total_width(self, items, axis):
        '''Given a list of items and an axis, return the space
        they take up(in pixels)
        '''
        total = 0
        if axis == 'width':
            for item in items:
                total += (item.width + self.padding_x)
        elif axis == 'height':
            for item in items:
                total+= (item.height + self.padding_y)

        return total

    def goto_head(self):
        if not self.h_limit:
            self.yoffset = -self._get_total_width(self.children, 'height')/self.w_limit + self.size[1] - 100
        else:
            self.xoffset = self._get_total_width(self.children, 'width')/self.h_limit + self.size[0] - 100

    def do_layout(self):
        '''Apply layout to all the items'''
       #Limit is on width
        if not self.h_limit:
            t = 0
            try:
                x = self.x + (self.width/2) - (self._get_total_width(
                        (self.children[z] for z in range(t, t+self.w_limit)), 'width')/2) + self.xoffset
            except:
                x = self.x + (self.width/2) - (self._get_total_width(
                        (self.children[z] for z in range(t, len(self.children)-1)), 'width')/2) + self.xoffset
            y = self.yoffset + self.y
            i = 0
            for c in self.children:
                i += 1
                c.kx = x + self.padding_x
                c.ky = y
                x += c.width + self.padding_x
                if i == self.w_limit:
                    #Take the largest height in the current row
                    y += self.padding_y + max(map(lambda x: x.height,
                                                  (self.children[x] for x in range(t, t+self.w_limit))))
                    try:
                        x = self.x + (self.width/2) - (self._get_total_width(
                                (self.children[z] for z in range(t, t+self.w_limit)), 'width')/2) + self.xoffset
                    except:
                        x = self.x + (self.width/2) - (self._get_total_width(
                                (self.children[z] for z in range(t, len(self.children)-1)), 'width')/2) + self.xoffset

                    i = 0
                    t += self.w_limit
        #Limit on height
        if not self.w_limit:
            t = 0
            try:
                y = self.y - (self._get_total_width(
                        (self.children[z] for z in range(t, t+self.w_limit)), 'height')) + self.yoffset
            except:
                y = self.y - (self._get_total_width(
                        (self.children[z] for z in range(t, len(self.children)-1)), 'height')) + self.yoffset
            x = self.xoffset + self.x
            i = 0
            for c in self.children:
                i += 1
                c.kx = x
                c.ky = y + self.padding_y
                y += c.height + self.padding_y
                if i == self.h_limit:
                    #Take the largest width in the current row
                    x += self.padding_x + max(map(lambda x: x.width,
                                                  (self.children[x] for x in range(t, t+self.h_limit))))
                    try:
                        y = self.y - (self._get_total_width(
                                (self.children[z] for z in range(t, t+self.w_limit)), 'height')) + self.yoffset
                    except:
                        y = self.y - (self._get_total_width(
                                (self.children[z] for z in range(t, len(self.children)-1)), 'height')) + self.yoffset

                    i = 0
                    t += self.h_limit

    def on_touch_down(self, touch):
        if self.collide_point(touch.x, touch.y):
            for w in self.widgets:
                if w.on_touch_down(touch):
                    return True
            self.vx = self.vy = 0 #Stop kinetic movement
            self.touch[touch.id] = {
                'ox': x,
                'oy': y,
                'xmot': 0,
                'ymot': 0,
                'travelx' : 0, #How far the blob has traveled total in the x axis
                'travely' : 0, #^
            }
            return True

    def on_touch_move(self, touch):
        if touch.id in self.touch:
            for w in self.widgets:
                if w.on_touch_move(touch):
                    return True
            t = self.touch[touch.id]
            t['xmot'] = touch.x - t['ox']
            t['ymot'] = touch.y - t['oy']
            t['ox'] = touch.x
            t['oy'] = touch.y
            t['travelx'] += abs(t['xmot'])
            t['travely'] += abs(t['ymot'])
            self.xoffset += t['xmot'] * self.do_x
            self.yoffset += t['ymot'] * self.do_y
            return True

    def on_touch_up(self, touch):
        if touch.id in self.touch:
            for w in self.widgets:
                if w.on_touch_up(touch):
                    return True
            t = self.touch[touch.id]
            self.vx = t['xmot']
            self.vy = t['ymot']
            #If any of them have been tapped, tell them
            for child in self.children:
                if child.collide_point(touch.x, touch.y):
                    if t['travelx'] <= 40 and self.do_x:
                        if not child.on_press(touch):
                            self.dispatch_event('on_press', child, self.childmap[child])
                            child.dispatch_event('on_press', touch)
                    elif t['travely'] <= 40 and self.do_y:
                        if not child.on_press(touch):
                            self.dispatch_event('on_press', child, self.childmap[child])
                            child.dispatch_event('on_press',touch)
            return True

    def process_kinetic(self):
        '''Apply kinetic movement to all the items'''
        self.xoffset += self.vx * self.do_x
        self.yoffset += self.vy * self.do_y

        dt = getFrameDt()
        self.vx /= 1 + (self.friction * dt)
        self.vy /= 1 + (self.friction * dt)

    def draw(self):
        # background
        set_color(*self.style.get('bg-color'))
        drawCSSRectangle(pos=self.pos, size=self.size, style=self.style)
        super(MTKineticList, self).on_draw()

        # title bar
        set_color(*self.style.get('title-color'))
        drawCSSRectangle(pos=(self.x, self.height + self.y - 40), size=(self.width, 40), prefix='title')
        self.title.draw()
        for w in self.widgets:
            w.on_draw()

    def on_draw(self):
        self.draw()
        self.do_layout()
        self.process_kinetic()

class MTKineticObject(MTWidget):
    def __init__(self, **kwargs):
        kwargs.setdefault('deletable', True)

        super(MTKineticObject, self).__init__(**kwargs)

        #List of attributes that can be searched
        self.attr_search = ['label']

        self.deletable = kwargs.get('deletable')

        #Delete Button
        self.db = MTButton(label='',
                                      size=(40, 40),
                                      pos=(self.x + self.width-40, self.y + self.height-40),
                                      style={'bg-color':(1, 0, 0, 0)})
        self.db.hide()
        self.db.on_press = self.delete
        self.add_widget(self.db)

        self.xoffset = self.yoffset = 0  #In case the widget has to move itself while still having kinetic movement applied
        self.kx = self.ky = 0  #The position values that the kinetic container edits.  We do this so we can break free and move ourself it necessary

        self.db_alpha = 0
        self.a_show = Animation(self, 'Show Button Alpha', 'db_alpha', .5, 1, 5)
        self.a_hide = Animation(self, 'Hide Button Alpha', 'db_alpha', 0, 1, 5)
        self.a_delete_w = Animation(self, 'Deleting Self W', 'width', 0, 1, 10)
        self.a_delete_h = Animation(self, 'Deleting Self H', 'height', 0, 1, 10)
        self.a_delete_x = Animation(self, 'Deleting Self X', 'xoffset', self.kx + self.width/2, 1, 10)
        self.a_delete_y = Animation(self, 'Deleting Self Y', 'yoffset', self.ky + self.height/2, 1, 10)

        self.free = False #Set to true if you want to break free from the grasp of a kinetic widget

    def show_delete(self):
        self.db.show()
        self.a_show.reset()
        self.a_show.start()

    def hide_delete(self):
        self.a_hide.reset()
        self.a_hide.start()

    def on_animation_complete(self, anim):
        if anim == self.a_hide:
            self.db.hide()
        elif anim == self.a_delete_w:
            '''We don't check Y because then it gets called
            twice and throws an exception because its already
            been deleted, and a try...except... isn't really worth it
            '''
            self.parent.delete_item(self)

    def on_draw(self):
        if not self.free:
            self.x, self.y = self.kx + self.xoffset, self.ky + self.yoffset
        self.db.pos = (self.x + self.width-40, self.y + self.height-40)
        self.db.style['bg-color'] = (1, 0, 0, self.db_alpha)
        super(MTKineticObject, self).on_draw()

    def delete(self, touch):
        self.db.hide()  #So it doesn't poke out at the end(we aren't scaling it)
        self.a_delete_x.reset()
        self.a_delete_y.reset()
        self.a_delete_w.reset()
        self.a_delete_h.reset()
        self.a_delete_x.start()
        self.a_delete_y.start()
        self.a_delete_w.start()
        self.a_delete_h.start()

    def on_press(self, touch):
        if self.db.visible and self.db.on_touch_down(touch):
            return True

class MTKineticItem(MTButton, MTKineticObject):
    def on_press(self, touch):
        if self.db.visible and self.db.on_touch_down(touch):
            return True

class MTKineticImage(MTImageButton, MTKineticObject):
    def on_press(self, touch):
        if self.db.visible and self.db.on_touch_down(touch):
            return True

MTWidgetFactory.register('MTKineticObject', MTKineticObject)
MTWidgetFactory.register('MTKineticList', MTKineticList)
MTWidgetFactory.register('MTKineticItem', MTKineticItem)
MTWidgetFactory.register('MTKineticImage', MTKineticImage)