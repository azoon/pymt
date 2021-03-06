'''
VideoGStreamer: implementation of VideoBase with GStreamer
'''

try:
    import pygst
    if not hasattr(pygst, '_gst_already_checked'):
        pygst.require('0.10')
        pygst._gst_already_checked = True
    import gst
except:
    raise

import threading
import gobject
import pymt
from . import VideoBase
from pymt.baseobject import BaseObject
from pymt.graphx import get_texture_target, set_texture, drawTexturedRectangle, set_color, drawRectangle
from OpenGL.GL import glTexSubImage2D, GL_UNSIGNED_BYTE, GL_RGB

# ensure that gobject have threads initialized.
gobject.threads_init()

class VideoGStreamer(VideoBase):
    '''VideoBase implementation using GStreamer (http://gstreamer.freedesktop.org/)
    '''

    __slots__ = ('_pipeline', '_decoder', '_videosink', '_colorspace',
                 '_videosize', '_buffer_lock', '_audiosink', '_volumesink')

    def __init__(self, **kwargs):
        self._pipeline      = None
        self._decoder       = None
        self._videosink     = None
        self._colorspace    = None
        self._audiosink     = None
        self._volumesink    = None
        self._buffer_lock   = threading.Lock()
        self._videosize     = (0, 0)
        super(VideoGStreamer, self).__init__(**kwargs)

    def stop(self):
        if self._pipeline is None:
            return
        self._wantplay = False
        self._pipeline.set_state(gst.STATE_PAUSED)
        self._state = ''

    def play(self):
        if self._pipeline is None:
            return
        self._wantplay = True
        self._pipeline.set_state(gst.STATE_PAUSED)
        self._state = ''

    def unload(self):
        if self._pipeline is None:
            return
        self._pipeline.set_state(gst.STATE_NULL)
        self._pipeline.get_state() # block until the null is ok
        self._pipeline = None
        self._decoder = None
        self._videosink = None
        self._texture = None
        self._audiosink = None
        self._volumesink = None
        self._state = ''

    def load(self):
        # ensure that nothing is loaded before.
        self.unload()

        # create the pipeline
        self._pipeline = gst.Pipeline()

        # hardcoded to check which decoder is better
        if self._filename.split(':')[0] in ('http', 'https', 'file'):
            # network decoder
            self._decoder = gst.element_factory_make('uridecodebin', 'decoder')
            self._decoder.set_property('uri', self._filename)
            self._decoder.connect('pad-added', self._gst_new_pad)
            self._pipeline.add(self._decoder)
        else:
            # local decoder
            filesrc = gst.element_factory_make('filesrc')
            filesrc.set_property('location', self._filename)
            self._decoder = gst.element_factory_make('decodebin', 'decoder')
            self._decoder.connect('new-decoded-pad', self._gst_new_pad)
            self._pipeline.add(filesrc, self._decoder)
            gst.element_link_many(filesrc, self._decoder)

        # create colospace information
        self._colorspace = gst.element_factory_make('ffmpegcolorspace')

        # will extract video/audio
        caps_str = 'video/x-raw-rgb,red_mask=(int)0xff0000,green_mask=(int)0x00ff00,blue_mask=(int)0x0000ff'
        caps = gst.Caps(caps_str)
        self._videosink = gst.element_factory_make('appsink', 'videosink')
        self._videosink.set_property('emit-signals', True)
        self._videosink.set_property('caps', caps)
        self._videosink.connect('new-buffer', self._gst_new_buffer)
        self._audiosink = gst.element_factory_make('autoaudiosink', 'audiosink')
        self._volumesink = gst.element_factory_make('volume', 'volume')

        # connect colorspace -> appsink
        self._pipeline.add(self._colorspace, self._videosink, self._audiosink,
                           self._volumesink)
        gst.element_link_many(self._colorspace, self._videosink)
        gst.element_link_many(self._volumesink, self._audiosink)

        # set to paused, for loading the file, and get the size information.
        self._pipeline.set_state(gst.STATE_PAUSED)

        # be sync if asked
        if self._async == False:
            self._pipeline.get_state()

    def _gst_new_pad(self, dbin, pad, *largs):
        # a new pad from decoder ?
        # if it's a video, connect decoder -> colorspace
        c = pad.get_caps().to_string()
        try:
            if c.startswith('video'):
                dbin.link(self._colorspace)
            elif c.startswith('audio'):
                dbin.link(self._volumesink)
        except:
            pass

    def _gst_new_buffer(self, appsink):
        # new buffer is comming, pull it.
        with self._buffer_lock:
            self._buffer = appsink.emit('pull-buffer')

    def _get_position(self):
        if self._videosink is None:
            return 0
        try:
            return self._videosink.query_position(gst.FORMAT_TIME)[0] / 1000000000.
        except:
            return 0

    def _get_duration(self):
        if self._videosink is None:
            return 0
        try:
            return self._videosink.query_duration(gst.FORMAT_TIME)[0] / 1000000000.
        except:
            return 0

    def _get_volume(self):
        if self._audiosink is not None:
            self._volume = self._volumesink.get_property('volume')
        else:
            self._volume = 1.
        return self._volume

    def _set_volume(self, volume):
        if self._audiosink is not None:
            self._volumesink.set_property('volume', volume)
            self._volume = volume

    def update(self):
        # no video sink ?
        if self._videosink is None:
            return

        # get size information first to create the texture
        if self._texture is None:
            for i in self._decoder.src_pads():
                cap = i.get_caps()[0]
                structure_name = cap.get_name()
                if structure_name.startswith('video') and cap.has_key('width'):
                    self._videosize = self.size = (cap['width'], cap['height'])
                    self._texture = pymt.Texture.create(
                        self._videosize[0], self._videosize[1], format=GL_RGB)
                    self._texture.flip_vertical()

        # no texture again ?
        if self._texture is None:
            return

        # ok, we got a texture, user want play ?
        if self._wantplay:
            self._pipeline.set_state(gst.STATE_PLAYING)
            self._state = 'playing'
            self._wantplay = False

        # update needed ?
        with self._buffer_lock:
            if self._buffer is not None:
                self._texture.blit_buffer(self._buffer.data,
                                          size=self._videosize,
                                          format=GL_RGB)
                self._buffer = None

    def draw(self):
        if self._texture:
            set_color(*self.color)
            drawTexturedRectangle(texture=self._texture, pos=self.pos, size=self.size)
        else:
            set_color(0, 0, 0)
            drawRectangle(pos=self.pos, size=self.size)
