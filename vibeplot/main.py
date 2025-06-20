
import os
import sys
import json
import math
import csv
import random
import psutil
import imageio
import numpy as np
import datetime
from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenText import OnscreenText
from direct.task import Task
from direct.gui.DirectGui import DirectButton, DirectSlider, DirectLabel, DirectFrame
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectOptionMenu import DirectOptionMenu

from .stars import Stars
from .utilities import *
from .bodies import Body
from .orbit import Orbit
from .sites import Site

from panda3d.core import (GeomVertexFormat, GeomVertexData, GeomVertexWriter, Geom, GeomNode,
                          GeomTriangles, NodePath, Vec3, Mat4,
                          Point2, Point3, TextureStage, AmbientLight, DirectionalLight, LVector3, PointLight,
                          loadPrcFileData, LineSegs,
                          CardMaker, TransparencyAttrib,
                          WindowProperties, TextNode,
                          Shader, Mat3, GeomPoints,
                          Quat, AntialiasAttrib, GeomVertexArrayFormat
                          )


loadPrcFileData('', 'framebuffer-multisample 1')
loadPrcFileData('', 'multisamples 4')
loadPrcFileData('', 'window-title VibePlot')
# loadPrcFileData('', 'window-type none')  # Prevent Panda3D from opening its own window
loadPrcFileData('', 'gl-include-points-size true')
# loadPrcFileData('', 'win-size 1920 1080')
# loadPrcFileData('', 'win-origin 0 0')

EARTH_RADIUS = 2.0  # Radius of Earth in Panda3D units
MOON_RADIUS = EARTH_RADIUS / 4.0  # Radius of Moon in Panda3D units
MARS_RADIUS = EARTH_RADIUS / 3.0  # Radius of Mars in Panda3D units
VENUS_RADIUS = EARTH_RADIUS * 0.2  # Radius of Venus in Panda3D units
SUN_RADIUS = EARTH_RADIUS * 2
MIN_LABEL_SCALE = 0  #0.05
RAD2DEG = 180.0 / math.pi
MIN_TIME = 0.0
MAX_TIME = 100.0  # temp: this represents the max time of the mission [will be user input: min/max]


class EarthOrbitApp(ShowBase):
    """A simple Panda3D application to visualize Earth and other celestial bodies."""

    def __init__(self, parent_window=None, friction: float = 1.0, draw_plane : bool = False):
        super().__init__()

        self.task_list = []  # list of (task, name) tuples

        # to keep track of sim time:
        self.use_slider_time = False
        self.pause_scene_animation()
        self.sim_time = MIN_TIME  # This will be your time variable
        self.sim_time_task = self.add_task(self.sim_time_update_task, "SimTimeTask")

        # Task for tracking mouse during drag
        self.mouse_task = None
        # Task for inertial movement
        self.inertia_task = None
        self.mouse_dragged = False
        self.last_mouse_move_time = 0
        self.prev_quat = None
        self.curr_quat = None

        # Set horizontal and vertical FOV in degrees
        self.camLens.setFov(60, 60)
        # To make the view wider (fisheye effect), increase the FOV (e.g., 90).
        # To zoom in (narrower view), decrease the FOV (e.g., 30).
        # self.camLens.setNear(0.1)
        # self.camLens.setFar(1000)
        # self.render.setScale(1)
        # self.camLens.setNear(1000)
        # self.camLens.setFar(1e8)

        # update aspect ratio
        width = self.win.getProperties().getXSize()
        height = self.win.getProperties().getYSize()
        if width > 0 and height > 0:
            aspect = width / height
            self.camLens.setAspectRatio(aspect)

        # self.star_sphere_np = self.render.attachNewNode("star_sphere")
        self.stars = Stars(self, star_database="models/hygdata_v41.csv")

        # Initialize in base frame at startup
        self.setup_base_frame()

        if parent_window is not None:
            props = WindowProperties()
            props.setParentWindow(parent_window)
            props.setOrigin(0, 0)
            props.setSize(800, 600)  # Or your desired size
            self.openDefaultWindow(props=props)

        self.process = psutil.Process(os.getpid())

        # Add key bindings:
        self.accept("space", self.recenter_on_earth)
        self.accept("a", self.toggle_scene_animation)  # Press 'a' to toggle all animation
        self.accept("1", self.focus_on_earth)
        self.accept("shift-1", self.focus_on_earth, extraArgs=[True])
        self.accept("2", self.focus_on_moon)
        self.accept("shift-2", self.focus_on_moon, extraArgs=[True])
        self.accept("3", self.focus_on_mars)
        self.accept("shift-3", self.focus_on_mars, extraArgs=[True])
        self.accept("4", self.focus_on_venus)
        self.accept("shift-4", self.focus_on_venus, extraArgs=[True])
        self.accept("5", self.focus_on_site)
        self.accept("shift-5", self.focus_on_site, extraArgs=[True])
        self.accept("6", self.venus_mars_frame)  # test. center on venus but look at mars

        # messenger.toggleVerbose()  # Enable verbose messenger output
        # self.accept("*", self.event_logger)  # debugging, log all events
        # messenger.toggleVerbose()

        # inertia:
        self.last_mouse_pos = None
        self.angular_velocity = Vec3(0, 0, 0)
        self.inertia_active = False
        self.friction = min(abs(friction), 1.0) # Dampening factor for inertial rotation. should be between 0 [no inertial] and 1 [no friction]
        self.inertia_axis = Vec3(0, 0, 1)  # Default axis
        self.inertia_angular_speed = 0.0   # Angular speed in radians/sec

        # Add mouse handlers
        self.accept("mouse1", self.stop_inertia)
        self.accept("alt-mouse1", self.on_alt_mouse_down)  # Option/Alt key + mouse button
        self.accept("option-mouse1", self.on_alt_mouse_down)  # Mac-specific
        # self.accept("alt-mouse1-up", self.on_alt_mouse_up)
        # self.accept("option-mouse1-up", self.on_alt_mouse_up) # Mac-specific
        self.accept("time-mouse1-up", self.on_alt_mouse_up)

        self.hud_text = OnscreenText(
            text="Frame: 0",
            pos=(-1.3, 0.95),  # (x, y) in screen space, top-left
            scale=0.07,
            fg=(1, 1, 1, 1),   # White color
            align=TextNode.ALeft,
            mayChange=True
        )
        self.frame_count = 0

        # Lighting

        # Sunlight (directional)
        # so it isn't really a point light. i don't think we can get shadows with a point light?
        # so we update it to point to the center of the scene using a task.
        dlight = DirectionalLight("dlight")
        dlight.setColor((1, 1, 1, 1))
        dlnp = self.render.attachNewNode(dlight)
        # dlnp.setHpr(0, -60, 0)  # Or your desired sun direction
        # dlnp.setHpr(-10, 0, 0)  # Or your desired sun direction
        # dlnp.setHpr(-10, -45, 0)  # Adjust direction as needed
        self.render.setLight(dlnp)

        # sun_dir = dlnp.getQuat(self.render).getForward()
        self.dlnp = dlnp  # Store a reference for later use

        # Enable shadow mapping
        self.render.setShaderAuto()
        self.render.setAntialias(AntialiasAttrib.MAuto)
        # Set up shadow mapping for your directional light
        self.dlnp.node().setShadowCaster(True, 2048, 2048)  # Enable shadows with 2048x2048 shadow map
        self.dlnp.node().getLens().setNearFar(1, 100)  # Adjust based on your scene scale
        self.dlnp.node().setShadowBufferSize(2048)  # Shadow buffer resolution (single value)
        # Enable shadows globally
        self.render.setShaderAuto()

        # Neutral ambient for the rest
        neutral_ambient = AmbientLight("neutral_ambient")
        # neutral_ambient.setColor((0.3, 0.3, 0.4, 1))
        # neutral_ambient.setColor((0.5, 0.5, 0.6, 1))  # Brighter, cooler
        # neutral_ambient.setColor((0.85, 0.85, 0.85, 1))  # Brighter, cooler
        neutral_ambient.setColor((0.3, 0.3, 0.4, 1))  # Increase from 0.2 to 0.3
        neutral_ambient_np = self.render.attachNewNode(neutral_ambient)
        self.render.setLight(neutral_ambient_np)

        # light for the axis arrows:
        self.arrow_ambient = AmbientLight("arrow_ambient")
        self.arrow_ambient.setColor((0.4, 0.4, 0.4, 1))

        # list of the attributes in the scene:
        # [note a site is a kind of body]
        self.bodies: list[Body] = []
        self.orbits: list[Orbit] = []

        ############################################
        # add items to the scene:

        self.earth = Body(
            self,
            name="Earth",
            radius=EARTH_RADIUS,
            day_tex="models/land_ocean_ice_cloud_2048.jpg",
            night_tex="models/2k_earth_nightmap.jpg",
            geojson_path="models/custom.geo.json",
            # geojson_path="models/combined-with-oceans-1970.json",
            lon_rotate=180.0,  # Rotate to match texture orientation
            color=(1, 1, 1, 1),
            draw_grid=True,
            draw_3d_axes=True
        )

        self.iss = Orbit(
            parent=self,
            central_body=self.earth,
            name="ISS",
            radius=EARTH_RADIUS * 1.3,
            speed=3.0,
            inclination_deg=51.6,  # ISS inclination
            color=(1, 0, 0, 1),
            satellite_color=(0.8, 0.8, 1, 1),
            visibility_cone=True,
            groundtrack=True,
            add_tube=True
        )

        self.equatorial_satellite = Orbit(
            parent=self,
            central_body=self.earth,
            name="equatorial_satellite",
            radius=EARTH_RADIUS * 5.0,
            speed=1.0,
            inclination_deg=1.0,
            color=(0, 1, 0, 1),
            satellite_color=(0, 1, 0, 1),
            visibility_cone=True,
            groundtrack=True
        )
        self.polar_satellite = Orbit(
            parent=self,
            central_body=self.earth,
            name="polar",
            radius=EARTH_RADIUS * 5.0,
            speed=1.0,
            inclination_deg=90.0,
            color=(0, 1, 0, 1),
            satellite_color=(0, 1, 0, 1),
            visibility_cone=False,
            groundtrack=False
        )
        self.json_orbit = Orbit(
            parent=self,
            central_body=self.earth,
            name="json_orbit",
            radius=EARTH_RADIUS * 5.0,
            speed=4.0,
            orbit_json='models/test_orbit.json',
            spline_mode="cubic",  # linear or cubic
            time_step = 0.1,       # can specify time step for resplining
            #num_segments=5,
            color=(1, 0, 1, 1),
            satellite_color=(1, 0, 1, 1),
            thickness=5,
            satellite_radius=0.2,
            visibility_cone=False,
            groundtrack=False,
            orbit_path_linestyle = 2  # short dash
        )
        self.json_orbit_2 = Orbit(
            parent=self,
            central_body=self.earth,
            name="json_orbit_polar",
            #radius=EARTH_RADIUS * 5.0,  # not used for json orbit
            speed=8.0,
            orbit_json='models/test_orbit_2.json',
            spline_mode="cubic",  # linear or cubic
            time_step = 0.1,       # can specify time step for resplining
            color=(1, 1, 1, 1),
            groundtrack=False,
            orbit_path_linestyle = 0  # short dash
        )
        # self.json_orbit_2.destroy()  # test - remove it

        # test reading a trajectory in the halo output format:
        # self.nrho_orbit = Orbit(
        #     parent=self,
        #     central_body=self.earth,
        #     name="nrho_orbit",
        #     label_text='NRHO',
        #     radius=EARTH_RADIUS * 5.0,  # not used for json orbit
        #     speed=8.0,
        #     orbit_json='models/traj_20251229220000_L2_S_NREVS=20.json',
        #     spline_mode = None,   # use the input times as is
        #     num_segments = None,
        #     color=(1, 0, 1, 1),
        #     satellite_color=(1, 1, 1, 1),
        #     thickness=1,
        #     satellite_radius=0.1,
        #     visibility_cone=False,
        #     groundtrack=False,
        #     orbit_path_linestyle = 0  # solid line
        # )

        self.orbits = []
        for i in range(2):
            c = random_rgba()
            name = f"S{i}"
            s = Orbit(parent=self,
                      central_body=self.earth,
                      name=name,
                      radius=EARTH_RADIUS * 10.0,
                      speed=2.0,
                      inclination_deg=40 + i*10,
                      spline_mode="cubic",  # linear or cubic
                      time_step = 0.1,  # can specify time step for resplining
                      label_text=name,
                      label_size=0.8,
                      label_color=c,
                      color=c,
                      satellite_color=c,
                      thickness=2,
                      enable_shadow=False,
                      satellite_radius=0.3,
                      visibility_cone=False,
                      groundtrack=False)
            self.orbits.append(s)

        # put a site on the Earth:
        site_lat = 0.519 * RAD2DEG  # deg
        site_lon = 1.665 * RAD2DEG  # radians
        self.site = Site(parent=self,
                         name = 'site',
                         central_body=self.earth,
                         lat_deg=site_lat,
                         lon_deg=site_lon,
                         radius_offset=0.001,
                         radius=0.01,
                         color=(1,0,0,0.5))
        self.site_lines_np = None

        self.moon = Body(
            self,
            name="Moon",
            radius=MOON_RADIUS,
            texture="models/lroc_color_poles_1k.jpg",
            color=(1, 1, 1, 1),
            draw_3d_axes=True
        )

        # note: we need a way to disable body shadows if
        # the sun is not in the scene.
        self.sun = Body(
                    self,
                    name="Sun",
                    radius=SUN_RADIUS,
                    texture="models/2k_sun.jpg",
                    color=(1, 1, 0, 1),
                    draw_3d_axes=False,
                    is_sun=True,  # use this as the light source
                )

        self.mars = Body(
            self,
            name="Mars",
            radius=MARS_RADIUS,
            texture="models/2k_mars.jpg",
            color=(1, 1, 1, 1),
            draw_grid=True,
            draw_3d_axes=True
        )

        self.venus = Body(self,
                          name="Venus",
                          texture='models/2k_venus_surface.jpg',
                          radius=VENUS_RADIUS,
                          color=(1, 0.8, 0.6, 1),
                          trace_length=50,
                          orbit_markers=True,
                          marker_size=0.06,
                          marker_interval=5,
                          marker_color=(1, 1, 1, 0.5),
                          trajectory_mode=0, #trace
                          )

        venus_site = Site(parent=self, name='P1', label_scale=0.1, central_body=self.venus, lat_deg=40, radius = 0.01, radius_offset = 0.02, lon_deg=-105, color = (0, 0, 1, 1), trajectory_mode = 0, trace_color = (1, 0, 0, 1)) #, show_axes=True)

        self.venus_orbiter = Orbit(parent=self,
                                   central_body=self.venus,
                                   name="venus_orbiter",
                                   radius=VENUS_RADIUS * 1.5,
                                   satellite_radius=0.02,
                                   speed=3.0,
                                   inclination_deg=90,
                                   color=(1, 1, 1, 1),
                                   satellite_color=(1, 1, 1, 1),
                                   visibility_cone=True,
                                   groundtrack=True,
                                   groundtrack_length = 400,
                                   show_orbit_path=False, # don't show the orbit path
                                )

        self.moon_site = Site(parent=self, name = 'copernicus', central_body=self.moon, radius = 0.01, lat_deg=40, lon_deg=-105, label_scale = 0.1, color = (1, 1, 0, 1), draw_3d_axes=True, trace_color = (1, 1, 1, 1))

        # Add Apollo landing sites to the Moon
        apollo_sites = [
            {"name": "Apollo 11", "lat_deg": 0.67408, "lon_deg": 23.47297},
            {"name": "Apollo 12", "lat_deg": -3.01239, "lon_deg": -23.42157},
            {"name": "Apollo 14", "lat_deg": -3.64530, "lon_deg": -17.47136},
            {"name": "Apollo 15", "lat_deg": 26.13222, "lon_deg": 3.63386},
            {"name": "Apollo 16", "lat_deg": -8.97301, "lon_deg": 15.50019},
            {"name": "Apollo 17", "lat_deg": 20.19080, "lon_deg": 30.77168},
        ]

        for site in apollo_sites:
            apollo_site = Site(
                parent=self,
                name=site["name"],
                central_body=self.moon,
                radius=0.005,  # Adjust the size of the site marker
                lat_deg=site["lat_deg"],
                lon_deg=site["lon_deg"],
                trace_length=0,
                color=(1, 0, 0, 1),  # Red color for visibility
                label_scale=0.05,  # Adjust label size
                draw_3d_axes=False  # Disable axes for simplicity
            )

        for inc in range(0, 360, 20):
            self.moon_satellite_2 = Orbit(parent=self,
                                          central_body=self.moon,
                                          name=f"moon_satellite_{inc}",
                                          radius=MOON_RADIUS * 1.2,
                                          satellite_radius = 0.03,
                                          thickness=2,
                                          speed=2*inc/260,
                                          inclination_deg=inc,
                                          color=(inc/360, inc/360, 0, 1),
                                          satellite_color=(inc/360, inc/360, 0, 1),
                                          visibility_cone=False,
                                          groundtrack=False,
                                          enable_shadow=False,
                                          show_orbit_path=False  # don't show the orbit
                                        )

        if draw_plane:
            # --- Equatorial plane (square, translucent) ---
            plane_size = EARTH_RADIUS * 4.0  # Half-width of the square plane
            plane_color = (0.2, 0.6, 1.0, 0.3)  # RGBA, mostly transparent blue
            # Create the plane
            cm = CardMaker("equatorial_plane")
            cm.setFrame(-plane_size, plane_size, -plane_size, plane_size)
            plane_np = self.render.attachNewNode(cm.generate())
            plane_np.setPos(0, 0, 0)
            plane_np.setHpr(0, -90, 0)  # Rotate from XZ to XY plane
            plane_np.setTransparency(TransparencyAttrib.MAlpha)
            plane_np.setColor(*plane_color)
            # --- Gridlines on the plane ---
            gridlines = LineSegs()
            gridlines.setThickness(1.0)
            grid_color = (1, 1, 1.0, 0.6)  # Slightly more visible
            num_lines = 9  # Number of gridlines per axis
            step = (2 * plane_size) / (num_lines - 1)
            z = 0  # Equatorial plane at z=0
            # Vertical lines (constant x)
            for i in range(num_lines):
                x = -plane_size + i * step
                gridlines.setColor(*grid_color)
                gridlines.moveTo(x, -plane_size, z)
                gridlines.drawTo(x, plane_size, z)
            # Horizontal lines (constant y)
            for i in range(num_lines):
                y = -plane_size + i * step
                gridlines.setColor(*grid_color)
                gridlines.moveTo(-plane_size, y, z)
                gridlines.drawTo(plane_size, y, z)
            grid_np = self.render.attachNewNode(gridlines.create())
            grid_np.setTransparency(TransparencyAttrib.MAlpha)

        # Add a small sphere as the satellite
        self.satellite = create_sphere(radius=0.1, num_lat=24, num_lon=48, color=(1,0,0,1))
        self.satellite.reparentTo(self.render)

        # --- Example particles ---
        self.particles = []
        self.particle_params = []
        self.particle_labels = []
        num_particles = 50
        particle_radius = 0.03
        for idx in range(num_particles):
            # Random orbital parameters
            #r = random.uniform(2.2, 4.0)
            r = random.uniform(EARTH_RADIUS * 1.2, EARTH_RADIUS * 2.0)
            inclination = random.uniform(0, math.pi)
            angle0 = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.05, 0.2)
            particle = create_sphere(radius=particle_radius, num_lat=10, num_lon=20, color=(random.random(), random.random(), random.random(), 1))
            particle.reparentTo(self.render)
            self.particles.append(particle)
            self.particle_params.append((r, inclination, angle0, speed))

            label = TextNode(f"S{idx+1}_label")
            label.setText(f"S{idx+1}")
            label.setTextColor(1, 1, 1, 1)
            label.setAlign(TextNode.ACenter)
            label_np = self.render.attachNewNode(label)
            particle_pos = particle.getPos()
            label_np.setPos(particle_pos[0] + 0.1, particle_pos[1] + 0.1, particle_pos[2] + 0.1)  # Offset above particle
            label_np.setScale(0.2)
            label_np.setBillboardPointEye()  # Always face camera
            label_np.setLightOff()
            self.particle_labels.append(label_np)

        self.labels_visible = True
        self.accept("s", self.toggle_particle_labels)

        # --- Connect some particles with lines ---
        self.connect_count = 5  # Number of particles to connect
        self.particle_lines = LineSegs()
        self.particle_lines.setThickness(1.5)
        self.particle_lines.setColor(1, 0, 1, 1)  # Magenta

        # Initial draw (positions will be updated each frame)
        for i in range(self.connect_count):
            for j in range(i + 1, self.connect_count):
                pos_i = self.particles[i].getPos()
                pos_j = self.particles[j].getPos()
                self.particle_lines.moveTo(pos_i)
                self.particle_lines.drawTo(pos_j)
        self.lines_np = NodePath(self.particle_lines.create())
        self.lines_np.reparentTo(self.render)
        self.lines_np.setLightOff()  # Turn off lighting completely

        # Trace settings
        self.use_particle_traces = True
        if self.use_particle_traces:
            self.trace_length = 100  # Number of points in the trace
            self.particle_traces = [[particle.getPos()] * self.trace_length for particle in self.particles]
            self.trace_nodes = [self.render.attachNewNode("trace") for _ in self.particles]
        self.add_task(self.particles_orbit_task, "ParticlesOrbitTask")

        # movie recording:
        self.record_movie = False
        self.movie_writer = None
        self.movie_filename = "output.mp4"
        self.movie_fps = 60 #30  # or your desired framerate
        self.accept("r", self.toggle_movie_recording)

        self.draw_axis_grid()
        self.recenter_on_earth()  # start the animation centered on Earth
        self.setup_gui()  # set up the GUI buttons/slider/etc

        # test: turn off shadowing on the bodies:
        # self.toggle_sunlight_on_bodies(False)

    def toggle_sunlight_on_bodies(self, enable: bool = None):
        """
        Toggle whether all bodies are lit by the main sunlight (directional light).
        If enable is None, toggles the current state.
        """
        for body in self.bodies:
            body.set_shadowed(enable, sunlight_np=self.dlnp)

    def _on_slider_drag_start(self, event):
        self.use_slider_time = True
        self.resume_scene_animation()

    def _on_slider_drag_end(self, event):
        self.pause_scene_animation()
        self.use_slider_time = False

    def on_slider_change(self):
        """Handle slider change event to update simulation time."""
        self.sim_time = float(self.time_slider['value'])
        self.time_label["text"] = f"Time: {self.sim_time:.2f}"

    def sim_time_update_task(self, task):
        """Update the simulation time and GUI elements."""
        if not self.use_slider_time:
            if not self.paused:
                self.sim_time += globalClock.getDt()
                self.sim_time = max(MIN_TIME, self.sim_time % MAX_TIME)
                if hasattr(self, "time_slider"):
                    self.time_slider['value'] = self.sim_time
                if hasattr(self, "time_label"):
                    self.time_label["text"] = f"Time: {self.sim_time:.2f}"
        return Task.cont

    def pause_scene_animation(self):
        """Pause the scene animation."""
        self.paused = True  # Set the pause flag to True
        if hasattr(self, 'pause_button'):
            self.pause_button['text'] = "Resume"

    def resume_scene_animation(self):
        """Resume the scene animation."""
        self.paused = False  # Set the pause flag to False
        if hasattr(self, 'pause_button'):
            self.pause_button['text'] = "Pause"

    def setup_gui(self):
        """Add some GUI elements for interaction."""

        aspect = self.getAspectRatio()

        self.gui_frame = DirectFrame(
            frameColor=(0, 0, 0, 0.4),
            frameSize=(-aspect, aspect, -0.15, 0.15),  # full width, adjust height as needed
            pos=(0, 0, 0.85),  # Centered at top of window
        )

        # Build options list and a mapping from label to function/args
        self.menu_options = []
        self.menu_callbacks = {}
        for b in self.bodies:
            label_fixed = f"{b.name} (body-fixed)"
            label_inertial = f"{b.name} (inertial)"
            self.menu_options.append(label_inertial)
            self.menu_options.append(label_fixed)
            self.menu_callbacks[label_fixed] = (self.setup_body_fixed_frame, (b, None, False, None))
            self.menu_callbacks[label_inertial] = (self.setup_body_fixed_frame, (b, None, True, None))
        label_fixed = 'Venus-Mars frame'
        self.menu_options.append(label_fixed)
        self.menu_callbacks[label_fixed] = (self.venus_mars_frame, (True,))

        # Create the DirectOptionMenu
        self.view_menu = DirectOptionMenu(
            text="View",
            scale=0.05,
            items=self.menu_options,
            initialitem=0,
            highlightColor=(0.65, 0.65, 0.65, 1),
            pos=(0.9, 0, 0.1),  # Adjust position as needed
            parent=self.gui_frame,
            command=self._on_menu_select
        )
        self.pause_button = DirectButton(
            text="Pause",
            scale=0.07,
            pos=(1.21, 0, 0),
            command=self.toggle_scene_animation,
            parent=self.gui_frame,
            frameSize=(-1.8, 1.8, -0.6, 0.6)
        )
        self.my_button = DirectButton(
            text="Reset",
            scale=0.07,
            pos=(1.5, 0, 0),
            command=self.recenter_on_earth,
            parent=self.gui_frame,
            frameSize=(-1.8, 1.8, -0.6, 0.6)
        )

        self.time_slider = DirectSlider(
            range=(MIN_TIME, MAX_TIME),  # Set min/max time as needed
            value=self.sim_time,
            pageSize=1,      # How much to move per click
            scale=0.6,
            pos=(0, 0, 0),  # Center of the frame
            command=self.on_slider_change,
            parent=self.gui_frame
        )
        # Bind to the thumb for drag start/end
        self.time_slider.thumb.bind(DGG.B1PRESS, self._on_slider_drag_start)
        self.time_slider.thumb.bind(DGG.B1RELEASE, self._on_slider_drag_end)

        self.time_label = DirectLabel(
            text="Time",
            scale=0.07,
            pos=(0.67, 0, 0),  # X, Y, Z
            text_fg=(1, 1, 1, 1),  # White text
            text_bg=(0, 0, 0, 1),
            parent=self.gui_frame,
            text_align=TextNode.ALeft
        )

    def _on_menu_select(self, selected_label):
        func, args = self.menu_callbacks.get(selected_label, (None, ()))
        if func:
            func(*args)

    def setup_base_frame(self):
        """Restore camera and trackball to their original working setup."""

        view_distance = EARTH_RADIUS * 10

        self.stop_inertia()

        # Remove camera_pivot if it exists
        if hasattr(self, 'camera_pivot'):
            self.camera_pivot.removeNode()
            del self.camera_pivot

        # Check if this is the first call (during initialization)
        if hasattr(self, 'initial_camera_parent'):
            # Regular restoration of state
            self.camera.reparentTo(self.initial_camera_parent)
            self.camera.setPos(self.render, self.initial_camera_pos)
            self.camera.setHpr(self.render, self.initial_camera_hpr)
            self.trackball.setPos(self.render, self.initial_trackball_pos)
            self.trackball.setHpr(self.render, self.initial_trackball_hpr)
            self.trackball.node().setMat(Mat4())  # Reset matrix to identity
            self.camera.lookAt(0, 0, 0)
        else:
            # First call - just use default setup
            self.trackball.node().setPos(0, view_distance, 0)
            self.trackball.node().setOrigin(Point3(0, 0, 0))
            self.trackball.node().setForwardScale(1.0)
            self.trackball.node().setRelTo(self.render)
            self.camera.setPos(0, view_distance, 0)
            # Store the initial WORKING camera setup:
            self.initial_camera_parent = self.camera.getParent()
            self.initial_camera_pos = self.camera.getPos(self.render)
            self.initial_camera_hpr = self.camera.getHpr(self.render)
            self.initial_trackball_parent = self.trackball.getParent()
            self.initial_trackball_pos = self.trackball.getPos(self.render)
            self.initial_trackball_hpr = self.trackball.getHpr(self.render)

        self.trackball.node().setPos(0, view_distance, 0)
        self.trackball.node().setOrigin(Point3(0, 0, 0))

        # Change star sphere parent to render
        if self.stars:
            self.stars.star_sphere_np.reparentTo(self.render)

    def setup_body_fixed_frame(self, body: Body, view_distance: float = None, follow_without_rotation: bool = False, body_to_look_at: Body = None):
        """Sets up the camera in a body-fixed frame.

        The camera can either follow the body's position and rotation or follow its position without rotation.
        Additionally, the camera can look at another body while being centered on the given body.

        Args:
            body (Body): The celestial body to focus on.
            view_distance (float, optional): Distance from the body to position the camera. Defaults to 10 times the body's radius.
            follow_without_rotation (bool, optional): If True, the camera follows the body's position but does not rotate with it. Defaults to False.
            body_to_look_at (Body, optional): The celestial body for the camera to look at. Defaults to None (camera looks at `body`).

        ### The Scene Graph Hierarchy

        ```
        body._rotator
        └── camera_pivot (rotated 180°)
            └── trackball (at 0, view_distance, 0)
                └── camera (we need to position this correctly)
        ```
        """

        if not view_distance:
            if isinstance(body, Site):
                # a little closer for sites
                view_distance = body.radius * 1.5   #body.central_body.radius * 5.0
            else:
                view_distance = body.radius * 10.0

        # Remove any existing follow node or look-at tasks
        if self.taskMgr.hasTaskNamed("UpdateFollowNodeTask"):
            self.taskMgr.remove("UpdateFollowNodeTask")
        if self.taskMgr.hasTaskNamed("UpdateCameraLookAtTask"):
            self.taskMgr.remove("UpdateCameraLookAtTask")

        self.stop_inertia()  # Stop any existing inertia
        self.trackball.node().setMat(Mat4())  # Reset matrix to identity

        # Clean up any existing camera pivot
        if hasattr(self, 'camera_pivot'):
            self.camera_pivot.removeNode()
            del self.camera_pivot

        if follow_without_rotation:
            # Create or reuse a node to follow the body without rotation
            if not hasattr(self, 'camera_follow_node'):
                self.camera_follow_node = self.render.attachNewNode("camera_follow_node")

            # Parent the camera to the follow node
            self.camera.reparentTo(self.camera_follow_node)

            def update_follow_node_task(task):
                if body_to_look_at:
                    current_body_pos = body._body.getPos(self.render)
                    current_target_pos = body_to_look_at._body.getPos(self.render)
                    self.camera_follow_node.setPos(current_body_pos)
                    self.trackball.node().setOrigin(current_body_pos)
                    self.camera.lookAt(current_target_pos - current_body_pos)
                else:
                    current_body_pos = body._body.getPos(self.render)
                    self.camera_follow_node.setPos(current_body_pos)  # ← Only follow node
                return Task.cont
            self.add_task(update_follow_node_task, "UpdateFollowNodeTask")

        else:
            # Create a pivot that follows the body and rotates with it
            self.camera_pivot = self.render.attachNewNode("camera_pivot")

            # Attach pivot to body's rotator
            self.camera_pivot.reparentTo(body._rotator)
            #self.camera_pivot.setHpr(180, 0, 0)

            # Parent camera to pivot
            self.camera.reparentTo(self.camera_pivot)

            if body_to_look_at:
                # Position camera at distance and add task to look at target
                def update_camera_look_at_task(task):
                    # Get target position relative to the body's rotator
                    target_world_pos = body_to_look_at._body.getPos(self.render)
                    body_world_pos = body._body.getPos(self.render)

                    # Calculate direction from target to body (opposite direction)
                    direction = (body_world_pos - target_world_pos).normalized()

                    # Position camera slightly past the body, away from the target
                    camera_offset = direction * view_distance
                    local_offset = self.camera_pivot.getRelativeVector(self.render, camera_offset)
                    self.camera.setPos(local_offset)

                    # Convert target to local coordinate system and look at it
                    target_local_pos = self.camera_pivot.getRelativePoint(self.render, target_world_pos)
                    self.camera.lookAt(target_local_pos)
                    return Task.cont

                self.add_task(update_camera_look_at_task, "UpdateCameraLookAtTask")
            else:
                # Default behavior: position camera and look at body center
                #self.camera.setPos(0, -view_distance, 0) # unnecesary?
                self.camera.lookAt(0, 0, 0)

        # Update trackball position to match camera
        self.trackball.node().setPos(0, view_distance, 0)
        self.trackball.node().setOrigin(Point3(0, 0, 0))

    def setup_camera_view(self, focus_point, view_distance):
        """Set up camera to look at a point while preserving mouse control."""
        # Always ensure consistent parenting
        #self.trackball.reparentTo(self.render)
        self.camera.reparentTo(self.render)

        # Calculate the position that's view_distance away from focus point
        view_pos = Point3(focus_point[0], focus_point[1] + view_distance, focus_point[2])

        # Set the same position on both trackball and camera
        self.trackball.node().setPos(view_pos)
        self.trackball.node().setOrigin(Point3(*focus_point))
        self.trackball.node().setForwardScale(1.0)
        self.trackball.node().setRelTo(self.render)

        # Use the same position for camera as provided to trackball
        self.camera.setPos(view_pos)
        self.camera.lookAt(*focus_point)

    def recenter_on_earth(self):
        """Reset to base render frame."""

        print("Reset")
        self.use_slider_time = False  # Enter manual time mode
        self.resume_scene_animation()
        self.sim_time = MIN_TIME  # reset clock

        # Clean up tasks created by setup_body_fixed_frame
        if self.taskMgr.hasTaskNamed("UpdateFollowNodeTask"):
            self.taskMgr.remove("UpdateFollowNodeTask")
        if self.taskMgr.hasTaskNamed("UpdateCameraLookAtTask"):
            self.taskMgr.remove("UpdateCameraLookAtTask")

        # Clean up camera follow node
        if hasattr(self, 'camera_follow_node'):
            self.camera_follow_node.removeNode()
            del self.camera_follow_node

        # Clean up camera pivot
        if hasattr(self, 'camera_pivot'):
            self.camera_pivot.removeNode()
            del self.camera_pivot

        self.resume_scene_animation()
        self.setup_base_frame()

        # --- Reset the menu selection to Earth (inertial) ---
        if hasattr(self, "view_menu"):
            self.view_menu.set(self.menu_options[0])

    def focus_on_earth(self, follow_without_rotation: bool = False):
        self.earth.setup_body_fixed_camera(follow_without_rotation=follow_without_rotation)

    def focus_on_moon(self, follow_without_rotation: bool = False):
        self.moon.setup_body_fixed_camera(follow_without_rotation=follow_without_rotation)

    def focus_on_mars(self, follow_without_rotation: bool = False):
        self.mars.setup_body_fixed_camera(follow_without_rotation=follow_without_rotation)

    def focus_on_venus(self, follow_without_rotation: bool = False):
        self.venus.setup_body_fixed_camera(follow_without_rotation=follow_without_rotation)

    def venus_mars_frame(self, follow_without_rotation: bool = False):
        view_distance = self.venus.radius # just at the body surface
        self.venus.setup_body_fixed_camera(follow_without_rotation=True, body_to_look_at=self.mars, view_distance=view_distance)

    def focus_on_site(self, follow_without_rotation: bool = False):
        min_safe_distance = EARTH_RADIUS * 1.2  # 20% beyond Earth's radius
        self.site.setup_body_fixed_camera(view_distance=min_safe_distance, follow_without_rotation=follow_without_rotation)

    def event_logger(self, *args, **kwargs):
        """Log all events for debugging"""
        print(f"EVENT: {args}, {kwargs}")

    def on_alt_mouse_up(self, *args):

        if self.mouse_task:
            self.taskMgr.remove(self.mouse_task)
            self.mouse_task = None

        if self.prev_quat and self.curr_quat:
            # Compute the delta rotation between the last two frames
            delta_quat = self.curr_quat * self.prev_quat.conjugate()
            axis = delta_quat.getAxis()
            angle = delta_quat.getAngle()
            if angle > 0:
                self.inertia_axis = axis.normalized()
                self.inertia_angular_speed = angle / globalClock.getDt()

        now = globalClock.getFrameTime()
        time_since_move = now - getattr(self, "last_mouse_move_time", 0)

        # Only start inertia if the mouse was dragged, moving recently, and velocity is high enough
        if (
            self.mouse_dragged
            and self.angular_velocity.length() > 0.5
            and time_since_move < 0.12  # 120 ms, adjust as needed
        ):
            self.inertia_active = True
            self.inertia_task = self.taskMgr.add(self.apply_inertia_task, "InertiaTask")
        else:
            self.inertia_active = False

        self.mouse_dragged = False

    def stop_inertia(self, *args):
        self.inertia_active = False
        if self.inertia_task:
            self.taskMgr.remove(self.inertia_task)
            self.inertia_task = None

    def on_alt_mouse_down(self):
        """Start tracking mouse for inertial rotation"""
        if self.mouseWatcherNode.hasMouse():

            self.stop_inertia()  # Stop any existing inertia

            # Store current mouse position
            self.last_mouse_pos = self.mouseWatcherNode.getMouse()
            # Store current orientation as quaternion
            mat = self.trackball.node().getMat()
            self.start_quat = Quat()
            self.start_quat.setFromMatrix(mat.getUpper3())

            # Start tracking mouse movement
            if self.mouse_task:
                self.taskMgr.remove(self.mouse_task)
            self.mouse_task = self.taskMgr.add(self.track_mouse_task, "TrackMouseTask")

            # Stop any existing inertia
            if self.inertia_task:
                self.taskMgr.remove(self.inertia_task)
                self.inertia_task = None

            # Angular velocity is now a 3D vector in camera's local coordinates
            self.angular_velocity = Vec3(0, 0, 0)
            self.inertia_active = False

    def track_mouse_task(self, task):
        if self.mouseWatcherNode.hasMouse():
            current_pos = self.mouseWatcherNode.getMouse()
            if self.last_mouse_pos:
                delta_x = current_pos.getX() - self.last_mouse_pos.getX()
                delta_y = current_pos.getY() - self.last_mouse_pos.getY()

                # If the mouse moved more than a small threshold, consider it a drag
                if abs(delta_x) > 0.002 or abs(delta_y) > 0.002:
                    self.mouse_dragged = True
                    self.last_mouse_move_time = globalClock.getFrameTime()

                # Sensitivity
                angle_heading = delta_x * 30      # Horizontal drag = heading (around up)
                angle_pitch   = -delta_y * 30     # Vertical drag = pitch (around right)

                mat = self.trackball.node().getMat()
                cam_quat = Quat()
                cam_quat.setFromMatrix(mat.getUpper3())

                # FIXED: Get local axes directly from matrix rows
                right = Vec3(mat.getCell(0, 0), mat.getCell(0, 1), mat.getCell(0, 2)).normalized()
                up = Vec3(mat.getCell(2, 0), mat.getCell(2, 1), mat.getCell(2, 2)).normalized()

                # Compose axis and angle for this frame
                axis = (right * angle_pitch) + (up * angle_heading)
                angle = axis.length()
                if angle > 0:
                    axis = axis.normalized()
                    quat = Quat()
                    quat.setFromAxisAngle(angle, axis)
                    new_quat = quat * cam_quat
                else:
                    new_quat = cam_quat

                rot_mat3 = Mat3()
                new_quat.extractToMatrix(rot_mat3)
                new_mat = Mat4(rot_mat3)
                new_mat.setRow(3, self.trackball.node().getMat().getRow3(3))
                self.trackball.node().setMat(new_mat)

                # Now update prev_quat and curr_quat
                self.prev_quat = getattr(self, 'curr_quat', None)
                self.curr_quat = Quat()
                self.curr_quat.setFromMatrix(new_mat.getUpper3())

                # Calculate angular velocity for inertia
                dt = globalClock.getDt()
                if dt > 0.001 and angle > 0:
                    self.inertia_axis = axis
                    self.inertia_angular_speed = angle / dt
                    self.angular_velocity = Vec3(angle_pitch / dt, angle_heading / dt, 0)

            self.last_mouse_pos = Point2(current_pos.getX(), current_pos.getY())
        return Task.cont

    def apply_inertia_task(self, task):
        if not self.inertia_active:
            return Task.done

        dt = globalClock.getDt()

        # Use the SAME rotation method as manual dragging
        if hasattr(self, 'inertia_axis') and hasattr(self, 'inertia_angular_speed'):
            # Get current camera matrix
            mat = self.trackball.node().getMat()
            cam_quat = Quat()
            cam_quat.setFromMatrix(mat.getUpper3())

            # Apply rotation using the stored axis and current angular speed
            angle_this_frame = self.inertia_angular_speed * dt

            if angle_this_frame > 0:
                quat = Quat()
                quat.setFromAxisAngle(angle_this_frame, self.inertia_axis)
                new_quat = quat * cam_quat

                rot_mat3 = Mat3()
                new_quat.extractToMatrix(rot_mat3)
                new_mat = Mat4(rot_mat3)
                new_mat.setRow(3, mat.getRow3(3))
                self.trackball.node().setMat(new_mat)

            # Apply friction to angular speed
            self.inertia_angular_speed *= self.friction

            # Stop when speed gets too small
            if self.inertia_angular_speed < 1.0:
                self.inertia_active = False
                return Task.done
        else:
            # Fallback to old method if axis not available
            self.inertia_active = False
            return Task.done

        return Task.cont

    def toggle_particle_labels(self):
        self.labels_visible = not self.labels_visible
        for label in self.particle_labels:
            if self.labels_visible:
                label.show()
            else:
                label.hide()
        for b in self.bodies:
            b.show_hide_label(self.labels_visible)
        for b in self.orbits:
            b.show_hide_label(self.labels_visible)

    def draw_axis_grid(self, thickness=2.0, show_grid=False, tick_interval=1.0, tick_size=0.2):
        """Draws coordinate axes with hash marks at specified intervals.

        Args:
            thickness (float, optional): Line thickness for the main axes. Defaults to 2.0.
            show_grid (bool, optional): Whether to show the background grid. Defaults to False.
            tick_interval (float, optional): Distance between hash marks on axes. Defaults to 1.0.
            tick_size (float, optional): Size of the hash marks. Defaults to 0.2.
        """

        axes = LineSegs()
        axes.setThickness(thickness)
        length = 8.0  # Adjust as needed

        # X axis (red)
        axes.setColor(1, 0, 0, 1)
        axes.moveTo(0, 0, 0)
        axes.drawTo(length, 0, 0)

        if tick_interval:
            # Hash marks for X axis (in YZ plane)
            for i in range(1, int(length/tick_interval) + 1):
                pos = i * tick_interval
                # Vertical tick (in Z direction)
                axes.moveTo(pos, 0, -tick_size/2)
                axes.drawTo(pos, 0, tick_size/2)
                # Horizontal tick (in Y direction)
                axes.moveTo(pos, -tick_size/2, 0)
                axes.drawTo(pos, tick_size/2, 0)

        # Y axis (green)
        axes.setColor(0, 1, 0, 1)
        axes.moveTo(0, 0, 0)
        axes.drawTo(0, length, 0)

        if tick_interval:
            # Hash marks for Y axis (in XZ plane)
            for i in range(1, int(length/tick_interval) + 1):
                pos = i * tick_interval
                # Vertical tick (in Z direction)
                axes.moveTo(0, pos, -tick_size/2)
                axes.drawTo(0, pos, tick_size/2)
                # Horizontal tick (in X direction)
                axes.moveTo(-tick_size/2, pos, 0)
                axes.drawTo(tick_size/2, pos, 0)

        # Z axis (blue)
        axes.setColor(0, 0, 1, 1)
        axes.moveTo(0, 0, 0)
        axes.drawTo(0, 0, length)

        if tick_interval:
            # Hash marks for Z axis (in XY plane)
            for i in range(1, int(length/tick_interval) + 1):
                pos = i * tick_interval
                # Tick in X direction
                axes.moveTo(-tick_size/2, 0, pos)
                axes.drawTo(tick_size/2, 0, pos)
                # Tick in Y direction
                axes.moveTo(0, -tick_size/2, pos)
                axes.drawTo(0, tick_size/2, pos)

        axes_np = self.render.attachNewNode(axes.create())
        axes_np.setLightOff()
        axes_np.setTwoSided(True)

        # Create axis labels
        label_scale = 0.5
        label_offset = 0.3  # Distance beyond the end of the axis

        # X axis label
        x_label = TextNode('x_label')
        x_label.setText("X")
        x_label.setTextColor(1, 0, 0, 1)  # Red
        x_label.setAlign(TextNode.ACenter)
        x_label_np = self.render.attachNewNode(x_label)
        x_label_np.setPos(length + label_offset, 0, 0)
        x_label_np.setScale(label_scale)
        x_label_np.setBillboardPointEye()  # Always face camera
        x_label_np.setLightOff()

        # Y axis label
        y_label = TextNode('y_label')
        y_label.setText("Y")
        y_label.setTextColor(0, 1, 0, 1)  # Green
        y_label.setAlign(TextNode.ACenter)
        y_label_np = self.render.attachNewNode(y_label)
        y_label_np.setPos(0, length + label_offset, 0)
        y_label_np.setScale(label_scale)
        y_label_np.setBillboardPointEye()
        y_label_np.setLightOff()

        # Z axis label
        z_label = TextNode('z_label')
        z_label.setText("Z")
        z_label.setTextColor(0, 0, 1, 1)  # Blue
        z_label.setAlign(TextNode.ACenter)
        z_label_np = self.render.attachNewNode(z_label)
        z_label_np.setPos(0, 0, length + label_offset)
        z_label_np.setScale(label_scale)
        z_label_np.setBillboardPointEye()
        z_label_np.setLightOff()

        if show_grid:
            grid = LineSegs()
            grid.setThickness(1.0)
            grid.setColor(0.7, 0.7, 0.7, 0.5)  # Light gray, semi-transparent

            grid_size = 8.0  # Half-width of the grid cube
            num_lines = 4    # Number of lines per axis
            step = (2 * grid_size) / (num_lines - 1)

            # Draw grid lines along X
            for i in range(num_lines):
                y = -grid_size + i * step
                for j in range(num_lines):
                    z = -grid_size + j * step
                    grid.moveTo(-grid_size, y, z)
                    grid.drawTo(grid_size, y, z)

            # Draw grid lines along Y
            for i in range(num_lines):
                x = -grid_size + i * step
                for j in range(num_lines):
                    z = -grid_size + j * step
                    grid.moveTo(x, -grid_size, z)
                    grid.drawTo(x, grid_size, z)

            # Draw grid lines along Z
            for i in range(num_lines):
                x = -grid_size + i * step
                for j in range(num_lines):
                    y = -grid_size + j * step
                    grid.moveTo(x, y, -grid_size)
                    grid.drawTo(x, y, grid_size)

            grid_np = self.render.attachNewNode(grid.create())
            grid_np.setLightOff()
            grid_np.setTwoSided(True)
            grid_np.setTransparency(True)

    def toggle_movie_recording(self):
        self.record_movie = not self.record_movie
        if self.record_movie:
            print("Recording started.")
            self.movie_writer = imageio.get_writer(self.movie_filename, fps=self.movie_fps, codec='libx264', format='ffmpeg')
            self.add_task(self.movie_writer_task, "MovieWriterTask")
        else:
            print("Recording stopped.")
            if self.movie_writer:
                self.movie_writer.close()
                self.movie_writer = None
            if self.taskMgr.hasTaskNamed("MovieWriterTask"):
                self.taskMgr.remove("MovieWriterTask")

    def add_task(self, task_func, name):
        """Adds a task to the task manager with a unique name.

        Args:
            task_func (Callable): The function to be added as a task.
            name (str): The unique name of the task.

        Returns:
            bool: True if the task was added successfully, False if the task already exists.
        """
        if not self.taskMgr.hasTaskNamed(name):
            self.taskMgr.add(task_func, name)
            for _func, _name in self.task_list:
                if name == _name:
                    return True # we already have this one
            self.task_list.append((task_func, name))  # keep a list
            return True
        else:
            print(f"Task '{name}' already exists.")
            return False

    def toggle_scene_animation(self):
        """Toggles the animation state of the scene.

        Pauses the animation if it is running, and resumes it if it is paused.
        """
        self.use_slider_time = False  # Enter animation time mode
        if self.paused:
            self.resume_scene_animation()
        else:
            self.pause_scene_animation()

    def line_intersects_sphere(self, p1, p2, sphere_center, sphere_radius):
        # p1, p2: endpoints of the line (Point3)
        # sphere_center: center of the sphere (Point3)
        # sphere_radius: radius of the sphere (float)
        # Returns True if the segment intersects the sphere
        d = p2 - p1
        f = p1 - sphere_center

        a = d.dot(d)
        b = 2 * f.dot(d)
        c = f.dot(f) - sphere_radius * sphere_radius

        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return False  # No intersection
        discriminant = math.sqrt(discriminant)
        t1 = (-b - discriminant) / (2 * a)
        t2 = (-b + discriminant) / (2 * a)
        # Check if intersection is within the segment
        return (0 <= t1 <= 1) or (0 <= t2 <= 1)

    def movie_writer_task(self, task):
        """Task to capture frames for movie recording."""
        if not self.record_movie or not self.movie_writer:
            return Task.done  # Stop the task if not recording

        tex = self.win.getScreenshot()
        img = np.array(tex.getRamImageAs("RGB"))
        img = img.reshape((tex.getYSize(), tex.getXSize(), 3))
        img = np.flipud(img)  # Flip vertically
        self.movie_writer.append_data(img)
        return Task.cont

    def get_et(self, task=None) -> float:
        """Returns the global simulation time."""
        return self.sim_time

    def particles_orbit_task(self, task):

        if self.paused:  # Check the pause flag
            return Task.cont  # Skip updates if paused

        self.frame_count += 1
        # self.hud_text.setText(f"Frame: {self.frame_count}")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fps = globalClock.getAverageFrameRate()
        mem_mb = self.process.memory_info().rss / (1024 * 1024)
        cpu = self.process.cpu_percent()
        # elapsed_time = self.get_et(task)
        text_to_display = [f"FPS: {fps:.1f}",   # f"{now}",
                           f"Frame: {self.frame_count}",
                           f"Mem: {mem_mb:.1f} MB",
                           f"CPU: {cpu:.1f}%"]
        self.hud_text.setText('\n'.join(text_to_display))
        # self.hud_text.setText(f"{now}\nFPS: {fps:.1f}")
        for i, particle in enumerate(self.particles):
            r, inclination, angle0, speed = self.particle_params[i]
            angle = angle0 + self.get_et(task) * speed
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            z = 0
            y_incl = y * math.cos(inclination) - z * math.sin(inclination)
            z_incl = y * math.sin(inclination) + z * math.cos(inclination)
            pos = Point3(x, y_incl, z_incl)
            particle.setPos(pos)

            if self.use_particle_traces:
                # Update trace positions
                trace = self.particle_traces[i]
                trace.append(pos)
                if len(trace) > self.trace_length:
                    trace.pop(0)

                # Draw fading trace
                self.trace_nodes[i].removeNode()
                segs = LineSegs()
                for j in range(1, len(trace)):
                    alpha = j / self.trace_length  # Fades from 0 to 1
                    segs.setColor(alpha, alpha, 0, alpha)
                    segs.moveTo(trace[j-1])
                    segs.drawTo(trace[j])
                self.trace_nodes[i] = self.render.attachNewNode(segs.create())
                self.trace_nodes[i].setTransparency(True)
                self.trace_nodes[i].setLightOff()

            pos_3d = particle.getPos(self.render)
            pos_cam = self.camera.getRelativePoint(self.render, pos_3d)
            p3 = Point3()
            label_np = self.particle_labels[i]
            if self.labels_visible and self.camLens.project(pos_cam, p3):
                x = p3.x * base.getAspectRatio()
                y = p3.y
                label_np.setPos(pos_3d[0] + 0.01, pos_3d[1] + 0.01, pos_3d[2] + 0.01)
                label_np.show()
            else:
                label_np.hide()
            # Update label color for connected particles
            if i < self.connect_count:
                # ... old version with onscreentext:
                #label_np['fg'] = (1, 0, 0, 1)  # Red for connected
                #label_np['bg'] = (0, 0, 0, 0.5)
                label_np.node().setTextColor(1, 0, 0, 1)  # Red for connected
            else:
                #label_np['fg'] = (0, 0, 0, 1)  # Black for others
                #label_np['bg'] = (1, 1, 1, 0.5)
                label_np.node().setTextColor(1, 1, 1, 1)  # White for others

            if MIN_LABEL_SCALE:
                # Calculate distance from camera to label
                label_pos = label_np.getPos(self.render)
                cam_pos = self.camera.getPos(self.render)
                distance = (label_pos - cam_pos).length()
                # Optionally, set a base scale that grows with distance, but clamp to a minimum
                scale = max(MIN_LABEL_SCALE, 0.15 * (distance / 7.0))  # Adjust 0.2 and 10.0 as needed
                label_np.setScale(scale)

        # hide the ones that intersect the earth:
        self.particle_lines = LineSegs()
        self.particle_lines.setThickness(1.5)
        self.particle_lines.setColor(1, 0, 1, 1)
        earth_center = Point3(0, 0, 0)
        earth_radius = EARTH_RADIUS
        for i in range(self.connect_count):
            for j in range(i + 1, self.connect_count):
                pos_i = self.particles[i].getPos()
                pos_j = self.particles[j].getPos()
                if not self.line_intersects_sphere(pos_i, pos_j, earth_center, earth_radius):
                    self.particle_lines.moveTo(pos_i)
                    self.particle_lines.drawTo(pos_j)
        self.lines_np.removeNode()
        self.lines_np = NodePath(self.particle_lines.create())
        self.lines_np.reparentTo(self.render)
        self.lines_np.setLightOff()  # Turn off lighting completely

        # lines that connect to a site:
        # Remove previous site lines
        if self.site_lines_np:
            self.site_lines_np.removeNode()

        site_lines = LineSegs()
        site_lines.setThickness(2.0)
        site_lines.setColor(0, 1, 0, 1)  # Green
        site_pos = self.site._body.getPos(self.render)
        earth_center = Point3(0, 0, 0)
        earth_radius = EARTH_RADIUS
        for particle in self.particles:
            particle_pos = particle.getPos(self.render)
            # Only draw if line does not intersect the Earth
            if not self.line_intersects_sphere(site_pos, particle_pos, earth_center, earth_radius):
                site_lines.moveTo(site_pos)
                site_lines.drawTo(particle_pos)

        self.site_lines_np = self.render.attachNewNode(site_lines.create())
        self.site_lines_np.setTransparency(True)
        self.site_lines_np.setLightOff()  # Add this line

        return Task.cont

