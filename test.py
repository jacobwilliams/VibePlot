
import sys
import json
import math
import random
import psutil, os
import imageio
import numpy as np
import datetime

from direct.gui.OnscreenText import OnscreenText
from direct.particles.ParticleEffect import ParticleEffect
from direct.gui.OnscreenImage import OnscreenImage

# print('importing qt')
# # these imports are crashing! ... something is wrong here...
# # note getting installed right by pixi? in halo, it works with conda ?
# from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
# from PySide6.QtCore import Qt
# print('done importing qt')

from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenText import OnscreenText
from direct.task import Task

from panda3d.core import (GeomVertexFormat, GeomVertexData, GeomVertexWriter, Geom, GeomNode,
                          GeomTriangles, NodePath, Vec3, Vec4, Mat4,
                          Point3, TextureStage, AmbientLight, DirectionalLight, LVector3,
                          loadPrcFileData, LineSegs, TextNode,
                          GeomVertexRewriter, GeomLinestrips,
                          CardMaker, TransparencyAttrib,
                          WindowProperties, TransparencyAttrib,
                          Shader, Mat3, BitMask32,
                          Quat, CollisionTraverser, CollisionNode, CollisionRay, CollisionHandlerQueue,
                          )


loadPrcFileData('', 'framebuffer-multisample 1')
loadPrcFileData('', 'multisamples 4')
loadPrcFileData('', 'window-title VibePlot')
# loadPrcFileData('', 'window-type none')  # Prevent Panda3D from opening its own window

EARTH_RADIUS = 2.0  # Radius of Earth in Panda3D units
MOON_RADIUS = 0.5  # Radius of Moon in Panda3D units

class EarthOrbitApp(ShowBase):
    def __init__(self, parent_window=None):
        # loadPrcFileData('', 'window-type none')  # Prevent Panda3D from opening its own window
        super().__init__()

        self.process = psutil.Process(os.getpid())
        self.process.cpu_percent()  # Initialize CPU usage

        if parent_window is not None:
            props = WindowProperties()
            props.setParentWindow(parent_window)
            props.setOrigin(0, 0)
            props.setSize(800, 600)  # Or your desired size
            self.openDefaultWindow(props=props)

        # self.accept("mouse1-double", self.recenter_on_earth)  # doesn't work?
        self.accept("space", self.recenter_on_earth)

        self.accept("a", self.toggle_scene_animation)  # Press 'a' to toggle all animation
        # self.accept("window-event", self.on_window_event)  # for moving HUD

        self.scene_anim_running = True
        self.scene_anim_task_names = [
            "OrbitTask",
            "MoonOrbitTask",
            "RotateEarthTask",
            "ParticlesOrbitTask",
            # "OrbitAnimTask",
            # "HyperbolicOrbitTask",
            # Add any other task names you want to pause/resume
]
        # inertia:
        # self.last_mouse_pos = None
        # self.angular_velocity = 0.0
        # self.inertia_axis = LVector3(0, 0, 1)
        # self.accept("mouse1", self.on_mouse_down)
        # self.accept("mouse1-up", self.on_mouse_up)
        # self.inertia_task = None

        self.hud_text = OnscreenText(
            text="Frame: 0",
            pos=(-1.3, 0.95),  # (x, y) in screen space, top-left
            scale=0.07,
            fg=(1, 1, 1, 1),   # White color
            align=TextNode.ALeft,
            mayChange=True
        )
        self.frame_count = 0

        self.trackball.node().setPos(0, 20, 0)
        self.trackball.node().setOrigin(Point3(0, 0, 0))
        self.trackball.node().setForwardScale(1.0)
        self.trackball.node().setRelTo(self.render)

        # Set initial camera position
        self.camera.setPos(0, 20, 0)
        self.camera.lookAt(0, 0, 0)
        # self.camera.reparentTo(self.trackball)  #

        # Star background (sky sphere)
        self.stars = self.loader.loadModel("models/planet_sphere")
        # self.stars.reparentTo(self.render)
        self.stars.reparentTo(self.camera)
        self.stars.setPos(0, 0, 0)
        self.stars.setScale(1000, 1000, 1000)
        self.stars.setTwoSided(True)  # Render inside of sphere
        self.stars.setCompass()
        self.stars.setBin('background', 0)
        self.stars.setDepthWrite(False)
        self.stars.setLightOff()
        self.stars.setCompass()  # Keep stars stationary relative to camera

        # star_tex = self.loader.loadTexture("models/epsilon_nebulae_texture_by_amras_arfeiniel.jpg")
        star_tex = self.loader.loadTexture("models/2k_stars.jpg")
        self.stars.setTexture(star_tex, 1)

        # Lighting
        # ambient = AmbientLight("ambient")
        # ambient.setColor((0.02, 0.02, 0.02, 1))
        # self.render.setLight(self.render.attachNewNode(ambient))

        # dlight = DirectionalLight("dlight")
        # dlight.setColor((1, 1, 1, 1))
        # dlnp = self.render.attachNewNode(dlight)
        # dlnp.setHpr(0, -60, 0)
        # # dlnp.setHpr(0, 60, 60)
        # self.render.setLight(dlnp)

        # Sunlight (directional)
        dlight = DirectionalLight("dlight")
        dlight.setColor((1, 1, 1, 1))
        dlnp = self.render.attachNewNode(dlight)
        # dlnp.setHpr(0, -60, 0)  # Or your desired sun direction
        dlnp.setHpr(-10, 0, 0)  # Or your desired sun direction
        sun_dir = dlnp.getQuat(self.render).getForward()
        self.dlnp = dlnp  # Store a reference for later use

        # Neutral ambient for the rest
        neutral_ambient = AmbientLight("neutral_ambient")
        # neutral_ambient.setColor((0.3, 0.3, 0.4, 1))
        # neutral_ambient.setColor((0.5, 0.5, 0.6, 1))  # Brighter, cooler
        neutral_ambient.setColor((0.85, 0.85, 0.85, 1))  # Brighter, cooler
        # neutral_ambient.setColor((0.2, 0.2, 0.2, 1))  # Dimmer, more neutral
        neutral_ambient_np = self.render.attachNewNode(neutral_ambient)
        self.render.setLight(neutral_ambient_np)

        # Load the Earth sphere
        self.earth = self.create_sphere(radius=EARTH_RADIUS, num_lat=24, num_lon=48, color=(1,1,1,1))
        self.earth.reparentTo(self.render)
        self.earth.setPos(0, 0, 0)
        # Load and apply Earth texture
        day_tex = self.loader.loadTexture("models/land_ocean_ice_cloud_2048.jpg")
        night_tex = self.loader.loadTexture("models/2k_earth_nightmap.jpg")
        self.earth.setTexture(day_tex, 1)
        self.earth.setShader(Shader.load(Shader.SL_GLSL, "models/earth_daynight.vert", "models/earth_daynight.frag"))
        self.earth.setTexture(TextureStage("day"), day_tex)
        self.earth.setTexture(TextureStage("night"), night_tex)
        self.earth.setShaderInput("day", day_tex)
        self.earth.setShaderInput("night", night_tex)
        # Set the sun direction uniform (should match your light direction)
        self.earth.setShaderInput("sundir", sun_dir)

        # put a site on the Earth:
        site_lat = 0.519   # radians
        site_lon = 1.665  # radians
        earth_radius = EARTH_RADIUS + 0.001
        site_x = earth_radius * math.cos(site_lat) * math.cos(site_lon)
        site_y = earth_radius * math.cos(site_lat) * math.sin(site_lon)
        site_z = earth_radius * math.sin(site_lat)
        self.site_np = self.earth.attachNewNode("site")
        self.site_np.setPos(self.earth, site_x, site_y, site_z)
        if True:
            # Optional: add a small sphere to mark the site
            site_marker = self.create_sphere(radius=0.02, num_lat=24, num_lon=48, color=(1,0,0,0.5))
            site_marker.reparentTo(self.site_np)
            site_marker.setShaderOff(1)   # so it won't have the earth texture
            site_marker.setTextureOff(1)  #
            site_marker.setTransparency(True)
        self.site_lines_np = None

        # Add the Moon
        # self.moon = self.loader.loadModel("models/planet_sphere")
        self.moon = self.create_sphere(radius=MOON_RADIUS, num_lat=24, num_lon=48, color=(1,1,1,1))
        self.moon.reparentTo(self.render)
        #self.moon.setScale(0.5)  # Relative to Earth (Earth=1, Moon~0.27)
        # self.moon.setScale(0.5, 0.5, 0.3)  # X, Y, Z scale - ellipsoidal shape
        self.moon.setPos(0, 0, 0)
        tex = self.loader.loadTexture("models/lroc_color_poles_1k.jpg")
        self.moon.setTexture(tex, 1)
        self.moon_orbit_radius = 6.0  # Distance from Earth center (tweak as desired)
        self.moon_orbit_speed = 0.7  # radians per second (tweak for desired speed)
        self.taskMgr.add(self.moon_orbit_task, "MoonOrbitTask")
        self.moon_trace = []
        self.moon_trace_length = 200  # Number of points to keep in the moon's trace
        self.moon_trace_node = self.render.attachNewNode("moon_trace")
        self.moon.setLightOff()
        self.moon.setLight(dlnp)
        self.moon.setShaderInput("sundir", sun_dir)
        self.moon_axes_np = self.create_axes(self.moon, length = 2 * MOON_RADIUS)  # coordinate axes for the Moon

        # --- Add a satellite orbiting the Moon ---
        self.moon_satellite_orbit_radius = 2 * MOON_RADIUS  # Distance from Moon center
        self.moon_satellite_orbit_speed = 2.0  # radians per second (relative to Moon)
        self.moon_satellite = self.create_sphere(radius=0.1, num_lat=16, num_lon=32, color=(1, 1, 0, 1))
        self.moon_satellite.reparentTo(self.moon)  # Parent to the Moon so it follows Moon's orbit
        self.taskMgr.add(self.moon_satellite_orbit_task, "MoonSatelliteOrbitTask")
        # --- Visualize the satellite's orbit path around the Moon ---
        moon_orbit_segs = LineSegs()
        moon_orbit_segs.setThickness(2)
        moon_orbit_segs.setColor(1, 0.5, 0, 1)  # Orange
        segments = 100
        self.moon_satellite_inclination = math.radians(30)  # 30 degree inclination
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            x = self.moon_satellite_orbit_radius * math.cos(angle)
            y = self.moon_satellite_orbit_radius * math.sin(angle)
            z = 0
            # Apply inclination (rotation around X axis)
            y_incl = y * math.cos(self.moon_satellite_inclination) - z * math.sin(self.moon_satellite_inclination)
            z_incl = y * math.sin(self.moon_satellite_inclination) + z * math.cos(self.moon_satellite_inclination)
            if i == 0:
                moon_orbit_segs.moveTo(x, y_incl, z_incl)
            else:
                moon_orbit_segs.drawTo(x, y_incl, z_incl)
        self.moon_satellite_orbit_np = self.moon.attachNewNode(moon_orbit_segs.create())
        # self.moon_satellite_orbit_np.setTransparency(True)
        self.moon_satellite_orbit_np.setLightOff()
        self.moon_satellite.setTextureOff(1)  # so it doesn't use the moon texture
        self.moon_satellite.setShaderOff(1)

        # --- Latitude/Longitude grid ---
        grid = LineSegs()
        grid.setThickness(1.0)
        # grid.setColor(0.7, 0.7, 0.7, 0.5)  # Light gray, semi-transparent
        grid.setColor(1, 1, 1, 1)  # White, fully opaque
        radius = EARTH_RADIUS + 0.001
        num_lat = 9   # Number of latitude lines (excluding poles)
        num_lon = 18  # Number of longitude lines
        # Latitude lines (horizontal circles)
        for i in range(1, num_lat):
            lat = math.pi * i / num_lat  # from 0 (north pole) to pi (south pole)
            z = radius * math.cos(lat)
            r_xy = radius * math.sin(lat)
            segments = 72
            for j in range(segments + 1):
                lon = 2 * math.pi * j / segments
                x = r_xy * math.cos(lon)
                y = r_xy * math.sin(lon)
                if j == 0:
                    grid.moveTo(x, y, z)
                else:
                    grid.drawTo(x, y, z)
        # Longitude lines (vertical half-circles)
        for i in range(num_lon):
            lon = 2 * math.pi * i / num_lon
            segments = 72
            for j in range(segments + 1):
                lat = math.pi * j / segments
                x = radius * math.sin(lat) * math.cos(lon)
                y = radius * math.sin(lat) * math.sin(lon)
                z = radius * math.cos(lat)
                if j == 0:
                    grid.moveTo(x, y, z)
                else:
                    grid.drawTo(x, y, z)
        # the shader is effecting the grid lines, so do this:
        self.grid_np = self.render.attachNewNode(grid.create())
        self.grid_np.setShaderOff()
        self.grid_np.setLightOff()
        self.grid_np.setTwoSided(True)

        if False:
            # --- Equatorial plane (square, translucent) ---
            plane_size = 4.0  # Half-width of the square plane
            plane_color = (0.2, 0.6, 1.0, 0.18)  # RGBA, mostly transparent blue
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
            grid_color = (0.5, 0.8, 1.0, 0.35)  # Slightly more visible
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

        # Add orbit task
        self.orbit_radius = 4
        self.orbit_speed = 1.0 #0.5  # radians per second
        self.taskMgr.add(self.orbit_task, "OrbitTask")


        # Add a small sphere as the satellite
        # self.satellite = self.loader.loadModel("models/planet_sphere")
        # self.satellite.setScale(0.1, 0.1, 0.1)
        # self.satellite.setColor(1, 0, 0, 1)
        # self.satellite.reparentTo(self.render)
        # self.satellite = self.loader.loadModel("models/planet_sphere")
        # self.satellite = self.loader.loadModel("models/teapot")
        self.satellite = self.create_sphere(radius=0.1, num_lat=24, num_lon=48, color=(1,0,0,1))
        #self.satellite.setScale(0.1, 0.1, 0.1)
        #self.satellite.setColor(1, 0, 0, 1)
        self.satellite.reparentTo(self.render)

        self.groundtrack_trace = []
        self.groundtrack_length = 1000  # Number of points to keep in the groundtrack
        #self.groundtrack_node = self.earth.attachNewNode("groundtrack")
        self.groundtrack_node = self.render.attachNewNode("groundtrack")
        self.groundtrack_node.setShaderOff()
        self.groundtrack_node.setLightOff()
        self.groundtrack_node.setTwoSided(True)

        # --- Visibility cone setup ---
        self.visibility_cone_np = self.render.attachNewNode("visibility_cone")
        self.visibility_cone_angle = math.radians(5)  # cone half-angle in radians
        self.visibility_cone_segments = 24  # smoothness of the cone

        # Draw the orbit path
        self.orbit_segs = LineSegs()
        self.orbit_segs.setThickness(2.0)
        self.orbit_segs.setColor(1, 1, 0, 1)  # Yellow
        num_segments = 100
        inclination = math.radians(45)
        for i in range(num_segments + 1):
            angle = 2 * math.pi * i / num_segments
            x = self.orbit_radius * math.cos(angle)
            y = self.orbit_radius * math.sin(angle)
            z = 0
            y_incl = y * math.cos(inclination) - z * math.sin(inclination)
            z_incl = y * math.sin(inclination) + z * math.cos(inclination)
            self.orbit_segs.drawTo(x, y_incl, z_incl)
        self.orbit_np = NodePath(self.orbit_segs.create())
        self.orbit_np.reparentTo(self.render)
        self.taskMgr.add(self.orbit_task, "OrbitTask")

        self.taskMgr.add(self.rotate_earth_task, "RotateEarthTask")

        # to pulsate the orbit line:
        # self.taskMgr.add(self.pulsate_orbit_line_task, "PulsateOrbitLineTask")

        # self.orbit_tube_np = self.add_orbit_tube(radius=5.0, inclination_deg=20, tube_radius=0.03, num_segments=100, num_sides=16, eccentricity=0.2)
        # self.orbit_tube_np2 = self.add_orbit_tube(radius=4.0, inclination_deg=45, tube_radius=0.03, num_segments=100, num_sides=16, eccentricity=0.3)

        #--------------------------------------------
        # Draw Earth-fixed coordinate axes (origin at Earth's center)

        # lighting for the arrows only:
        arrow_ambient = AmbientLight("arrow_ambient")
        arrow_ambient.setColor((0.4, 0.4, 0.4, 1))  # Brighter ambient just for arrow
        arrow_ambient_np = self.render.attachNewNode(arrow_ambient)
        self.axes_np = self.render.attachNewNode("axes")
        self.axes_np.setPos(0, 0, 0)
        self.x_arrow = self.create_arrow()
        self.x_arrow.setHpr(90, 0, 0)    # +X axis
        self.y_arrow = self.create_arrow()
        self.y_arrow.setHpr(180, 0, 0)   # +Y axis
        self.z_arrow = self.create_arrow()
        self.z_arrow.setHpr(0, 90, 0)    # +Z axis
        for a in [self.x_arrow, self.y_arrow, self.z_arrow]:
            a.reparentTo(self.axes_np)
            a.setLightOff()               # Remove all inherited lights
            a.setLight(self.dlnp)         # Sunlight (directional)
            a.setLight(arrow_ambient_np)  # Apply only this ambient light
        # self.earth_to_moon_arrow.setLight(arrow_ambient_np)

        # --- Example particles ---
        self.particles = []
        self.particle_params = []
        self.particle_labels = []
        num_particles = 50
        particle_radius = 0.03
        for idx in range(num_particles):
            # Random orbital parameters
            r = random.uniform(2.2, 4.0)
            inclination = random.uniform(0, math.pi)
            angle0 = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.05, 0.2)
            # particle = self.loader.loadModel("models/planet_sphere")
            #particle.setScale(particle_radius)
            #particle.setColor(random.random(), random.random(), random.random(), 1)
            particle = self.create_sphere(radius=particle_radius, num_lat=10, num_lon=20, color=(random.random(), random.random(), random.random(), 1))
            particle.reparentTo(self.render)
            self.particles.append(particle)
            self.particle_params.append((r, inclination, angle0, speed))

            label = OnscreenText(
                text=f"S{idx+1}",
                pos=(0, 0),  # Will be updated each frame
                scale=0.05,
                fg=(0, 0, 0, 1),
                bg=(1, 1, 1, 0.5),
                mayChange=True,
                align=TextNode.ACenter
            )
            self.particle_labels.append(label)

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

        # Trace settings
        self.trace_length = 100  # Number of points in the trace
        self.particle_traces = [[particle.getPos()] * self.trace_length for particle in self.particles]
        self.trace_nodes = [self.render.attachNewNode("trace") for _ in self.particles]

        self.taskMgr.add(self.particles_orbit_task, "ParticlesOrbitTask")

        self.manifold_np = None

        # self.setup_mouse_picker()

        self.record_movie = False
        self.movie_writer = None
        self.movie_filename = "output.mp4"
        self.movie_fps = 60 #30  # or your desired framerate
        self.accept("r", self.toggle_movie_recording)

        self.draw_axis_grid()

    # def on_window_event(self, window):
    #     self.update_hud_position()

    def toggle_particle_labels(self):
        self.labels_visible = not self.labels_visible
        for label in self.particle_labels:
            if self.labels_visible:
                label.show()
            else:
                label.hide()

    def draw_axis_grid(self):

        axes = LineSegs()
        axes.setThickness(3.0)
        length = 8.0  # Adjust as needed

        # X axis (red)
        axes.setColor(1, 0, 0, 1)
        axes.moveTo(0, 0, 0)
        axes.drawTo(length, 0, 0)
        # Y axis (green)
        axes.setColor(0, 1, 0, 1)
        axes.moveTo(0, 0, 0)
        axes.drawTo(0, length, 0)
        # Z axis (blue)
        axes.setColor(0, 0, 1, 1)
        axes.moveTo(0, 0, 0)
        axes.drawTo(0, 0, length)

        axes_np = self.render.attachNewNode(axes.create())
        axes_np.setLightOff()
        axes_np.setTwoSided(True)

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

    def create_sphere(self, radius=1.0, num_lat=16, num_lon=32, color=(1, 1, 1, 1)):
        format = GeomVertexFormat.getV3n3c4t2()
        vdata = GeomVertexData('sphere', format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        normal = GeomVertexWriter(vdata, 'normal')
        color_writer = GeomVertexWriter(vdata, 'color')
        texcoord = GeomVertexWriter(vdata, 'texcoord')
        tris = GeomTriangles(Geom.UHStatic)

        for i in range(num_lat + 1):
            theta = math.pi * i / num_lat
            sin_theta = math.sin(theta)
            cos_theta = math.cos(theta)
            v = i / num_lat  # V coordinate
            for j in range(num_lon + 1):
                phi = 2 * math.pi * j / num_lon
                sin_phi = math.sin(phi)
                cos_phi = math.cos(phi)
                x = radius * sin_theta * cos_phi
                y = radius * sin_theta * sin_phi
                z = radius * cos_theta
                u = j / num_lon  # U coordinate
                vertex.addData3(x, y, z)
                normal.addData3(Vec3(x, y, z).normalized())
                color_writer.addData4(*color)
                texcoord.addData2(u, 1 - v)

        for i in range(num_lat):
            for j in range(num_lon):
                first = i * (num_lon + 1) + j
                second = first + num_lon + 1
                tris.addVertices(first, second, first + 1)
                tris.addVertices(second, second + 1, first + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode('sphere')
        node.addGeom(geom)
        sphere_np = NodePath(node)
        return sphere_np

    def create_axes(self, body, length: int = 1.0, thickness: int = 3):
        """coordinate axes"""
        axes = LineSegs()
        axes.setThickness(thickness)
        # X axis (red)
        axes.setColor(1, 0, 0, 1)
        axes.moveTo(0, 0, 0)
        axes.drawTo(length, 0, 0)
        # Y axis (green)
        axes.setColor(0, 1, 0, 1)
        axes.moveTo(0, 0, 0)
        axes.drawTo(0, length, 0)
        # Z axis (blue)
        axes.setColor(0, 0, 1, 1)
        axes.moveTo(0, 0, 0)
        axes.drawTo(0, 0, length)
        axes_np = body.attachNewNode(axes.create())
        axes_np.setLightOff()
        return axes_np

    def toggle_movie_recording(self):
        self.record_movie = not self.record_movie
        if self.record_movie:
            print("Recording started.")
            # self.movie_writer = imageio.get_writer(self.movie_filename, fps=self.movie_fps)
            self.movie_writer = imageio.get_writer(self.movie_filename, fps=self.movie_fps, codec='libx264', format='ffmpeg')
        else:
            print("Recording stopped.")
            if self.movie_writer:
                self.movie_writer.close()
                self.movie_writer = None

    # def update_hud_position(self):
    #     aspect = base.getAspectRatio()
    #     # Multiply by aspect to keep text at the left edge
    #     self.hud_text.setPos(-1.3 * (1 / aspect), 0.95)
    #     if hasattr(self, "fps_text"):
    #         self.fps_text.setPos(-1.3 * (1 / aspect), 0.90)

    ####################
    #---- try to have inertia spin on mouse drag.... not quite what i want but a start ....
    # def on_mouse_down(self):
    #     self.last_mouse_pos = self.win.getPointer(0).getX(), self.win.getPointer(0).getY()
    #     self.angular_velocity = 0.0
    #     if self.inertia_task:
    #         self.taskMgr.remove(self.inertia_task)
    #         self.inertia_task = None

    # def on_mouse_up(self):
    #     # Calculate velocity based on last drag
    #     if self.last_mouse_pos is not None:
    #         x, y = self.win.getPointer(0).getX(), self.win.getPointer(0).getY()
    #         dx = x - self.last_mouse_pos[0]
    #         dy = y - self.last_mouse_pos[1]
    #         self.angular_velocity = math.sqrt(dx*dx + dy*dy) * 0.01  # Tune this factor
    #         if self.angular_velocity > 0.01:
    #             self.inertia_axis = LVector3(-dy, dx, 0)
    #             self.inertia_axis.normalize()
    #             self.inertia_task = self.taskMgr.add(self.inertia_spin_task, "InertiaSpinTask")

    # def inertia_spin_task(self, task):
    #     if self.angular_velocity > 0.001:
    #         # Rotate the camera or trackball
    #         self.trackball.node().setHpr(
    #             self.trackball.node().getH() + self.angular_velocity * self.inertia_axis.getX(),
    #             self.trackball.node().getP() + self.angular_velocity * self.inertia_axis.getY(),
    #             self.trackball.node().getR()
    #         )
    #         self.angular_velocity *= 0.96  # Damping factor
    #         return Task.cont
    #     else:
    #         self.angular_velocity = 0.0
    #         return Task.done
    ####################

    # def setup_mouse_picker(self):
    #     self.picker = CollisionTraverser()
    #     self.pq = CollisionHandlerQueue()
    #     self.pickerNode = CollisionNode('mouseRay')
    #     self.pickerNP = self.camera.attachNewNode(self.pickerNode)
    #     self.pickerNode.setFromCollideMask(BitMask32.bit(1))
    #     self.pickerRay = CollisionRay()
    #     self.pickerNode.addSolid(self.pickerRay)
    #     self.picker.addCollider(self.pickerNP, self.pq)
    #     self.accept('mouse1', self.on_mouse_click)

    # def on_mouse_click(self):
    #     if self.mouseWatcherNode.hasMouse():
    #         mpos = self.mouseWatcherNode.getMouse()
    #         self.pickerRay.setFromLens(self.camNode, mpos.getX(), mpos.getY())
    #         self.picker.traverse(self.render)
    #         if self.pq.getNumEntries() > 0:
    #             self.pq.sortEntries()
    #             pickedObj = self.pq.getEntry(0).getIntoNodePath()
    #             # Move camera to look at the picked object's position
    #             pos = pickedObj.getPos(self.render)
    #             self.camera.lookAt(pos)
    #             # Optionally, move the camera closer/farther as needed
    # def on_mouse_click(self):
    #     if self.mouseWatcherNode.hasMouse():
    #         mpos = self.mouseWatcherNode.getMouse()
    #         self.pickerRay.setFromLens(self.camNode, mpos.getX(), mpos.getY())
    #         self.picker.traverse(self.render)
    #         if self.pq.getNumEntries() > 0:
    #             self.pq.sortEntries()
    #             pickedObj = self.pq.getEntry(0).getIntoNodePath()
    #             pos = pickedObj.getPos(self.render)

    #             # Move camera to a fixed distance from the object, along the current camera direction
    #             cam_vec = self.camera.getQuat(self.render).getForward()
    #             distance = (self.camera.getPos(self.render) - pos).length()
    #             if distance < 1.0:
    #                 distance = 10.0  # fallback if too close
    #             new_cam_pos = pos - cam_vec * distance
    #             self.camera.setPos(new_cam_pos)
    #             self.camera.lookAt(pos)

    #             # Recenter the trackball's origin to the picked object
    #             self.trackball.node().setOrigin(pos)

    def on_mouse_click(self):
        if self.mouseWatcherNode.hasMouse():
            mpos = self.mouseWatcherNode.getMouse()
            self.pickerRay.setFromLens(self.camNode, mpos.getX(), mpos.getY())
            self.picker.traverse(self.render)
            if self.pq.getNumEntries() > 0:
                self.pq.sortEntries()
                pickedObj = self.pq.getEntry(0).getIntoNodePath()
                pos = pickedObj.getPos(self.render)

                # Move the trackball node to keep the same distance from the object
                distance = (self.camera.getPos(self.render) - pos).length()
                if distance < 1.0:
                    distance = 10.0  # fallback if too close

                # Set the new origin (center of rotation)
                self.trackball.node().setOrigin(pos)
                # Move the trackball node's position so the camera stays at the same distance
                cam_vec = self.camera.getQuat(self.render).getForward()
                self.trackball.node().setPos(pos - cam_vec * distance)
                # Optionally reset HPR if you want to face the object directly
                self.trackball.node().setHpr(0, 0, 0)

    def create_arrow(self, shaft_length=4.0, shaft_radius=0.1, head_length=0.6, head_radius=0.3, color=(1, 1, 1, 1)):
        """Create an arrow NodePath pointing along +Y."""
        # Shaft (cylinder)
        format = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData('arrow', format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        normal = GeomVertexWriter(vdata, 'normal')
        color_writer = GeomVertexWriter(vdata, 'color')
        tris = GeomTriangles(Geom.UHStatic)
        segments = 24

        # Cylinder shaft
        for i in range(segments + 1):
            theta = 2 * math.pi * i / segments
            x = shaft_radius * math.cos(theta)
            z = shaft_radius * math.sin(theta)
            # Bottom
            vertex.addData3(x, 0, z)
            normal.addData3(x, 0, z)
            color_writer.addData4(*color)
            # Top
            vertex.addData3(x, shaft_length, z)
            normal.addData3(x, 0, z)
            color_writer.addData4(*color)
        for i in range(segments):
            a = i * 2
            b = a + 1
            c = ((i + 1) % segments) * 2
            d = c + 1
            tris.addVertices(a, b, d)
            tris.addVertices(a, d, c)

        # Cone head
        base_idx = (segments + 1) * 2
        tip = Vec3(0, shaft_length + head_length, 0)
        for i in range(segments + 1):
            theta = 2 * math.pi * i / segments
            x = head_radius * math.cos(theta)
            z = head_radius * math.sin(theta)
            vertex.addData3(x, shaft_length, z)
            normal_vec = Vec3(x, head_length * 0.5, z).normalized()
            normal.addData3(normal_vec)
            color_writer.addData4(*color)
        vertex.addData3(tip)
        normal.addData3(0, 1, 0)
        color_writer.addData4(*color)
        tip_idx = vertex.getWriteRow() - 1
        for i in range(segments):
            a = base_idx + i
            b = base_idx + (i + 1) % segments
            tris.addVertices(a, b, tip_idx)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode('arrow')
        node.addGeom(geom)
        arrow_np = NodePath(node)
        arrow_np.setTwoSided(True)
        # arrow_np.setBin('opaque', 10)
        arrow_np.setPos(0, 0, 0)  # by default, center at origin

        return arrow_np

    def pause_scene_animation(self):
        if self.scene_anim_running:
            for name in self.scene_anim_task_names:
                self.taskMgr.remove(name)
            self.scene_anim_running = False

    def resume_scene_animation(self):
        if not self.scene_anim_running:
            # Re-add all tasks (with correct function references)
            self.taskMgr.add(self.orbit_task, "OrbitTask")
            self.taskMgr.add(self.moon_orbit_task, "MoonOrbitTask")
            self.taskMgr.add(self.rotate_earth_task, "RotateEarthTask")
            self.taskMgr.add(self.particles_orbit_task, "ParticlesOrbitTask")
            # Only add if the relevant objects exist:
            if hasattr(self, "animate_orbit_satellite") and hasattr(self, "orbit_satellite"):
                self.taskMgr.add(self.animate_orbit_satellite, "OrbitAnimTask")
            # if hasattr(self, "hyperbolic_orbit_task"):
            #     self.taskMgr.add(self.hyperbolic_orbit_task, "HyperbolicOrbitTask")
            self.scene_anim_running = True

    def toggle_scene_animation(self):
        if self.scene_anim_running:
            self.pause_scene_animation()
        else:
            self.resume_scene_animation()

    def recenter_on_earth(self):
        # Reset camera and trackball to look at Earth's center
        self.trackball.node().setHpr(0, 0, 0)
        self.trackball.node().setPos(0, 20, 0)
        self.trackball.node().setOrigin(Point3(0, 0, 0))
        self.camera.setPos(0, -20, 0)
        self.camera.lookAt(0, 0, 0)

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

    def draw_translucent_manifold(self, points, tube_radius=0.15, num_sides=16, color=(0.2, 0.8, 1, 0.25)):
        """Draw a translucent tube (manifold) around a list of 3D points."""
        if len(points) < 2:
            return None

        format = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData('manifold', format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        normal = GeomVertexWriter(vdata, 'normal')
        color_writer = GeomVertexWriter(vdata, 'color')

        rings = []
        for i in range(len(points)):
            p = points[i]
            # Compute tangent
            if i == 0:
                tangent = (points[i+1] - p).normalized()
            elif i == len(points) - 1:
                tangent = (p - points[i-1]).normalized()
            else:
                tangent = (points[i+1] - points[i-1]).normalized()
            # Find a vector perpendicular to tangent
            up = Vec3(0, 0, 1)
            if abs(tangent.dot(up)) > 0.99:
                up = Vec3(1, 0, 0)
            side = tangent.cross(up).normalized()
            up = side.cross(tangent).normalized()

            # ring = []
            # for j in range(num_sides):
            #     theta = 2 * math.pi * j / num_sides
            #     offset = side * math.cos(theta) * tube_radius + up * math.sin(theta) * tube_radius
            #     pos = p + offset
            #     vertex.addData3(pos)
            #     normal.addData3(offset.normalized())
            #     color_writer.addData4(*color)
            #     ring.append(i * num_sides + j)
            fade_alpha = (i + 1) / len(points)  # 0 (oldest) to 1 (newest)
            ring = []
            for j in range(num_sides):
                theta = 2 * math.pi * j / num_sides
                offset = side * math.cos(theta) * tube_radius + up * math.sin(theta) * tube_radius
                pos = p + offset
                vertex.addData3(pos)
                normal.addData3(offset.normalized())
                color_writer.addData4(color[0], color[1], color[2], color[3] * fade_alpha)
                ring.append(i * num_sides + j)
            rings.append(ring)

        # Build triangles
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(len(points) - 1):
            for j in range(num_sides):
                a = i * num_sides + j
                b = i * num_sides + (j + 1) % num_sides
                c = (i + 1) * num_sides + j
                d = (i + 1) * num_sides + (j + 1) % num_sides
                tris.addVertices(a, b, c)
                tris.addVertices(b, d, c)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode('manifold')
        node.addGeom(geom)
        manifold_np = self.render.attachNewNode(node)
        manifold_np.setTransparency(True)
        manifold_np.setTwoSided(True)
        manifold_np.setBin('transparent', 10)
        return manifold_np

    def orbit_task(self, task):
        angle = task.time * self.orbit_speed
        inclination = math.radians(45)  # 45 degree inclination
        x = self.orbit_radius * math.cos(angle)
        y = self.orbit_radius * math.sin(angle)
        z = 0
        # Rotate around X axis for inclination
        y_incl = y * math.cos(inclination) - z * math.sin(inclination)
        z_incl = y * math.sin(inclination) + z * math.cos(inclination)
        sat_pos = Point3(x, y_incl, z_incl)
        self.satellite.setPos(sat_pos)

        # --- Visibility cone ---
        # Earth center
        earth_center = Point3(0, 0, 0)
        v = sat_pos - earth_center
        v_len = v.length()
        if v_len != 0:
            surface_point = earth_center + v * (EARTH_RADIUS / v_len)
        else:
            surface_point = earth_center

        # Cone geometry
        self.visibility_cone_np.node().removeAllChildren()

        # Calculate cone base radius
        cone_height = (sat_pos - surface_point).length()
        base_radius = cone_height * math.tan(self.visibility_cone_angle)

        # Find orthonormal basis for the cone base
        axis = (surface_point - sat_pos).normalized()
        # Find a vector not parallel to axis
        up = Vec3(0, 0, 1) if abs(axis.dot(Vec3(0, 0, 1))) < 0.99 else Vec3(0, 1, 0)
        right = axis.cross(up).normalized()
        up = right.cross(axis).normalized()

        # Build cone geometry
        format = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData('cone', format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        color = GeomVertexWriter(vdata, 'color')

        # Apex
        vertex.addData3(sat_pos)
        color.addData4(1, 1, 0, 0.3)  # semi-transparent yellow

        # Base circle
        base_points = []
        for i in range(self.visibility_cone_segments + 1):
            theta = 2 * math.pi * i / self.visibility_cone_segments
            dir_vec = (right * math.cos(theta)  + up * math.sin(theta)) * base_radius
            pt = surface_point + dir_vec
            base_points.append(pt)
            vertex.addData3(pt)
            color.addData4(1, 1, 0, 0.15)  # more transparent

        # Triangles
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(self.visibility_cone_segments):
            tris.addVertices(0, i + 1, i + 2)
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode('cone')
        node.addGeom(geom)
        cone_np = self.visibility_cone_np.attachNewNode(node)
        cone_np.setTransparency(True)


        # Draw the intersection outline
        if hasattr(self, "cone_outline_np"):
            self.cone_outline_np.removeNode()
        outline = LineSegs()
        outline.setThickness(2.0)
        outline.setColor(1, 1, 0, 1)  # Bright yellow
        for i, pt in enumerate(base_points):
            if i == 0:
                outline.moveTo(pt)
            else:
                outline.drawTo(pt)
        # Close the loop
        if base_points:
            outline.drawTo(base_points[0])
        self.cone_outline_np = self.render.attachNewNode(outline.create())
        self.cone_outline_np.setTransparency(True)


        # Project satellite position onto Earth's surface
        sat_vec = sat_pos - Point3(0, 0, 0)
        if sat_vec.length() != 0:
            ground_point = sat_vec.normalized() * (EARTH_RADIUS + .001)
            # Convert to Earth's local coordinates
            ground_point_local = self.earth.getRelativePoint(self.render, ground_point)
            self.groundtrack_trace.append(ground_point_local)

            # uncomment to make it a trace:
            if len(self.groundtrack_trace) > self.groundtrack_length:
               self.groundtrack_trace.pop(0)
            # Draw the groundtrack
            self.groundtrack_node.node().removeAllChildren()
            segs = LineSegs()
            segs.setThickness(2.0)
            segs.setColor(1, 0.5, 0, 1)  # Orange
            for i, pt in enumerate(self.groundtrack_trace):
                alpha = i / self.groundtrack_length  # Fades from 0 to 1
                segs.setColor(1, 0.5, 0, alpha)
                if i == 0:
                    segs.moveTo(pt)
                else:
                    segs.drawTo(pt)
            self.groundtrack_node.attachNewNode(segs.create())
            self.groundtrack_node.setTransparency(True)

        if self.record_movie and self.movie_writer:
            tex = self.win.getScreenshot()
            img = np.array(tex.getRamImageAs("RGB"))
            img = img.reshape((tex.getYSize(), tex.getXSize(), 3))
            img = np.flipud(img)  # Flip vertically
            self.movie_writer.append_data(img)

        return Task.cont

    def rotate_earth_task(self, task):
        self.earth.setH(self.earth.getH() + 0.4)  # Adjust speed as desired

        # we have to do all this because the earth uses a custom shader,
        # which messes up all the child objects.
        self.grid_np.setH(self.earth.getH())  # <-- rotate the lat/lon grid with the earth
        self.groundtrack_node.setH(self.earth.getH())
        self.axes_np.setH(self.earth.getH())

        # Update sun direction in Earth's local space
        sun_dir_world = self.dlnp.getQuat(self.render).getForward()
        sun_dir_local = self.earth.getQuat(self.render).conjugate().xform(sun_dir_world)
        # self.earth.setShaderInput("sundir", sun_dir_local)
        # Rotate sun_dir_local by -90 degrees around Z to match texture orientation
        rot90 = Mat3.rotateMatNormaxis(180, Vec3(0, 0, 1))
        sun_dir_local_rot = rot90.xform(sun_dir_local)
        self.earth.setShaderInput("sundir", sun_dir_local_rot)

        return Task.cont

    def hyperbolic_orbit_task(self, task):
        # Move along the hyperbolic path with focus at Earth's center
        t_range = self.hyperbolic_t_max - self.hyperbolic_t_min
        t = self.hyperbolic_t_min + (task.time * self.hyperbolic_speed) % t_range
        x = self.hyperbolic_a * math.cosh(t) - self.hyperbolic_c  # Shift so focus is at x=0
        y = self.hyperbolic_b * math.sinh(t)
        z = 0
        y_incl = y * math.cos(self.hyperbolic_incl) - z * math.sin(self.hyperbolic_incl)
        z_incl = y * math.sin(self.hyperbolic_incl) + z * math.cos(self.hyperbolic_incl)
        self.hyper_sat.setPos(x, y_incl, z_incl)
        return Task.cont

    def particles_orbit_task(self, task):
        self.frame_count += 1
        # self.hud_text.setText(f"Frame: {self.frame_count}")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fps = globalClock.getAverageFrameRate()
        mem_mb = self.process.memory_info().rss / (1024 * 1024)
        cpu = self.process.cpu_percent()
        text_to_display = [f"{now}",
                           f"FPS: {fps:.1f}",
                           f"Frame: {self.frame_count}",
                           f"Mem: {mem_mb:.1f} MB",
                           f"CPU: {cpu:.1f}%"]
        self.hud_text.setText('\n'.join(text_to_display))
        # self.hud_text.setText(f"{now}\nFPS: {fps:.1f}")
        for i, particle in enumerate(self.particles):
            r, inclination, angle0, speed = self.particle_params[i]
            angle = angle0 + task.time * speed
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            z = 0
            y_incl = y * math.cos(inclination) - z * math.sin(inclination)
            z_incl = y * math.sin(inclination) + z * math.cos(inclination)
            pos = Point3(x, y_incl, z_incl)
            particle.setPos(pos)

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

            pos_3d = particle.getPos(self.render)
            pos_cam = self.camera.getRelativePoint(self.render, pos_3d)
            p3 = Point3()
            if self.labels_visible and self.camLens.project(pos_cam, p3):
                x = p3.x * base.getAspectRatio()
                y = p3.y
                self.particle_labels[i].setPos(x, y + 0.04)
                self.particle_labels[i].show()
            else:
                self.particle_labels[i].hide()
            # Update label color for connected particles
            if i < self.connect_count:
                self.particle_labels[i]['fg'] = (1, 0, 0, 1)  # Red for connected
                self.particle_labels[i]['bg'] = (0, 0, 0, 0.5)
            else:
                self.particle_labels[i]['fg'] = (0, 0, 0, 1)  # Black for others
                self.particle_labels[i]['bg'] = (1, 1, 1, 0.5)

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

        # lines that connect to a site:
        # Remove previous site lines
        if self.site_lines_np:
            self.site_lines_np.removeNode()

        site_lines = LineSegs()
        site_lines.setThickness(2.0)
        site_lines.setColor(0, 1, 0, 1)  # Green
        site_pos = self.site_np.getPos(self.render)
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

        return Task.cont

    def pulsate_orbit_line_task(self, task):
        # Pulsate between 2.0 and 8.0 thickness, and brightness 0.5 to 1.0
        t = task.time
        thickness = 2.0 + 6.0 * (0.5 + 0.5 * math.sin(t * 2.0))  # Pulsate every ~3 seconds
        brightness = 1.0 #0.5 + 0.5 * math.sin(t * 2.0)
        color = (brightness, brightness, 0, 1)

        # Re-create the orbit line with new thickness/color
        self.orbit_segs = LineSegs()
        self.orbit_segs.setThickness(thickness)
        self.orbit_segs.setColor(*color)

        num_segments = 100
        inclination = math.radians(45)
        for i in range(num_segments + 1):
            angle = 2 * math.pi * i / num_segments
            x = self.orbit_radius * math.cos(angle)
            y = self.orbit_radius * math.sin(angle)
            z = 0
            y_incl = y * math.cos(inclination) - z * math.sin(inclination)
            z_incl = y * math.sin(inclination) + z * math.cos(inclination)
            if i == 0:
                self.orbit_segs.moveTo(x, y_incl, z_incl)
            else:
                self.orbit_segs.drawTo(x, y_incl, z_incl)

        self.orbit_np.removeNode()
        self.orbit_np = NodePath(self.orbit_segs.create())
        self.orbit_np.reparentTo(self.render)
        return Task.cont

    def add_orbit_tube(self, radius=3.0, inclination_deg=20, tube_radius=0.07, num_segments=100, num_sides=12, eccentricity=0.0):
        inclination = math.radians(inclination_deg)
        a = radius
        e = eccentricity
        b = a * math.sqrt(1 - e * e)
        # Prepare vertex data
        format = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData('tube', format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        normal = GeomVertexWriter(vdata, 'normal')
        color = GeomVertexWriter(vdata, 'color')

        verts = []
        for i in range(num_segments + 1):
            angle = 2 * math.pi * i / num_segments
            # Elliptical orbit, centered at focus
            x = a * math.cos(angle) - a * e
            y = b * math.sin(angle)
            z = 0
            # Incline orbit
            y_incl = y * math.cos(inclination) - z * math.sin(inclination)
            z_incl = y * math.sin(inclination) + z * math.cos(inclination)
            center = Vec3(x, y_incl, z_incl)

            # Tangent vector (direction of orbit)
            next_angle = 2 * math.pi * ((i+1)%num_segments) / num_segments
            x2 = a * math.cos(next_angle) - a * e
            y2 = b * math.sin(next_angle)
            z2 = 0
            y2_incl = y2 * math.cos(inclination) - z2 * math.sin(inclination)
            z2_incl = y2 * math.sin(inclination) + z2 * math.cos(inclination)
            next_center = Vec3(x2, y2_incl, z2_incl)
            tangent = (next_center - center).normalized()

            # Find a vector perpendicular to tangent
            up = Vec3(0, 0, 1)
            if abs(tangent.dot(up)) > 0.99:
                up = Vec3(1, 0, 0)
            side = tangent.cross(up).normalized()
            up = side.cross(tangent).normalized()

            ring = []
            for j in range(num_sides):
                theta = 2 * math.pi * j / num_sides
                offset = side * math.cos(theta) * tube_radius + up * math.sin(theta) * tube_radius
                pos = center + offset
                vertex.addData3(pos)
                normal.addData3(offset.normalized())
                color.addData4(0, 1, 1, 0.5)  # Cyan tube
                ring.append(i * num_sides + j)
            verts.append(ring)

        # Build triangles
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(num_segments):
            for j in range(num_sides):
                a_idx = i * num_sides + j
                b_idx = i * num_sides + (j + 1) % num_sides
                c_idx = (i + 1) * num_sides + j
                d_idx = (i + 1) * num_sides + (j + 1) % num_sides
                tris.addVertices(a_idx, b_idx, c_idx)
                tris.addVertices(b_idx, d_idx, c_idx)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode('orbit_tube')
        node.addGeom(geom)
        tube_np = self.render.attachNewNode(node)
        tube_np.setTransparency(True)
        tube_np.setTwoSided(True)
        tube_np.setBin('opaque', 10)
        return tube_np

    def moon_orbit_task(self, task):

        angle = task.time * self.moon_orbit_speed
        x = self.moon_orbit_radius * math.cos(angle)
        y = self.moon_orbit_radius * math.sin(angle)
        z = 0
        self.moon.setPos(x, y, z)
        self.moon.setHpr(math.degrees(angle), 0, 0)  # Rotates X axis toward Earth

        # Update moon trace
        moon_pos = self.moon.getPos(self.render)
        self.moon_trace.append(moon_pos)
        if len(self.moon_trace) > self.moon_trace_length:
            self.moon_trace.pop(0)
        # Draw the trace
        self.moon_trace_node.node().removeAllChildren()
        segs = LineSegs()
        segs.setThickness(3.0)
        for i, pt in enumerate(self.moon_trace):
            alpha = i / len(self.moon_trace)
            segs.setColor(0.7, 0.7, 1, alpha)
            if i == 0:
                segs.moveTo(pt)
            else:
                segs.drawTo(pt)
        self.moon_trace_node.attachNewNode(segs.create())
        self.moon_trace_node.setTransparency(True)

        # if self.manifold_np:
        #     self.manifold_np.removeNode()
        # self.manifold_np = self.draw_translucent_manifold(self.moon_trace, tube_radius=0.3, color=(1.0, 0.8, 1, 0.18))

        # moon_orbit = LineSegs()
        # moon_orbit.setThickness(1.2)
        # moon_orbit.setColor(0.7, 0.7, 1, 0.7)
        # segments = 100
        # for i in range(segments + 1):
        #     angle = 2 * math.pi * i / segments
        #     x = self.moon_orbit_radius * math.cos(angle)
        #     y = self.moon_orbit_radius * math.sin(angle)
        #     z = 0
        #     if i == 0:
        #         moon_orbit.moveTo(x, y, z)
        #     else:
        #         moon_orbit.drawTo(x, y, z)
        # moon_orbit_np = self.render.attachNewNode(moon_orbit.create())

        # # Update sun direction in Moon's local space
        # sun_dir_world = self.dlnp.getQuat(self.render).getForward()
        # sun_dir_local = self.moon.getQuat(self.render).conjugate().xform(sun_dir_world)
        # self.moon.setShaderInput("sundir", sun_dir_local)

        # Update the Earth-to-Moon arrow
        # moon_pos = self.moon.getPos(self.render)
        # # Remove old geometry
        # self.earth_to_moon_arrow.removeNode()
        # # Create a new arrow with updated end point
        # self.earth_to_moon_arrow = self.create_arrow(
        #     start=Vec3(0, 0, 0),
        #     end=moon_pos,
        #     shaft_radius=0.05,
        #     head_length=0.4,
        #     head_radius=0.18,
        #     color=(1, 1, 1, 0.5)
        # )
        # self.earth_to_moon_arrow.reparentTo(self.render)
        # self.earth_to_moon_arrow.setLightOff()
        # self.earth_to_moon_arrow.setLight(self.dlnp)
        # self.earth_to_moon_arrow.setLight(self.render.find("**/arrow_ambient"))

        return Task.cont

    def add_radiation_belt(self, inner_radius=2.5, outer_radius=3.5, belt_color=(0.2, 1, 0.2, 0.18), num_major=100, num_minor=24):
        """Draw a translucent torus (belt) around the Earth."""

        format = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData('belt', format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        normal = GeomVertexWriter(vdata, 'normal')
        color = GeomVertexWriter(vdata, 'color')

        verts = []
        major_radius = (inner_radius + outer_radius) / 2
        minor_radius = (outer_radius - inner_radius) / 2

        for i in range(num_major + 1):
            phi = 2 * math.pi * i / num_major
            center = Vec3(major_radius * math.cos(phi), major_radius * math.sin(phi), 0)
            for j in range(num_minor + 1):
                theta = 2 * math.pi * j / num_minor
                # Local circle in XZ plane
                x = (major_radius + minor_radius * math.cos(theta)) * math.cos(phi)
                y = (major_radius + minor_radius * math.cos(theta)) * math.sin(phi)
                z = minor_radius * math.sin(theta)
                pos = Vec3(x, y, z)
                n = (pos - center).normalized()
                vertex.addData3(pos)
                normal.addData3(n)
                color.addData4(*belt_color)
                verts.append((i, j))

        # Build triangles
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(num_major):
            for j in range(num_minor):
                a = i * (num_minor + 1) + j
                b = ((i + 1) % (num_major + 1)) * (num_minor + 1) + j
                c = ((i + 1) % (num_major + 1)) * (num_minor + 1) + (j + 1)
                d = i * (num_minor + 1) + (j + 1)
                tris.addVertices(a, b, d)
                tris.addVertices(b, c, d)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode('radiation_belt')
        node.addGeom(geom)
        belt_np = self.render.attachNewNode(node)
        belt_np.setTransparency(True)
        belt_np.setTwoSided(True)
        belt_np.setBin('transparent', 20)
        return belt_np

    def load_orbit_from_json(self, filename):
        with open(filename, "r") as f:
            data = json.load(f)
        options = data.get("options", {})
        traj = data["trajectory"]
        points = [Point3(p["x"], p["y"], p["z"]) for p in traj]
        times = [p.get("t", i) for i, p in enumerate(traj)]
        return points, times, options

    def add_orbit_from_json(self, filename, color=(1, 0, 1, 1), thickness=2.0):
        points, times, options = self.load_orbit_from_json(filename)
        # Draw the orbit
        segs = LineSegs()
        segs.setThickness(thickness)
        segs.setColor(*color)
        for i, pt in enumerate(points):
            if i == 0:
                segs.moveTo(pt)
            else:
                segs.drawTo(pt)
        orbit_np = self.render.attachNewNode(segs.create())
        orbit_np.setTransparency(True)
        orbit_np.setBin('opaque', 20)

        # Animate if requested
        if options.get("animate", False):
            self.animate_orbit_satellite(points, times, options)
        return orbit_np

    def animate_orbit_satellite(self, points, times, options):
        # Create a satellite model if not already present
        if not hasattr(self, "orbit_satellite"):
            self.orbit_satellite = self.loader.loadModel("models/planet_sphere")
            self.orbit_satellite.setScale(0.12)
            self.orbit_satellite.setColor(1, 0, 1, 1)
            self.orbit_satellite.reparentTo(self.render)

        speed = options.get("speed", 1.0)
        loop = options.get("loop", True)
        t_min, t_max = times[0], times[-1]

        def orbit_anim_task(task):
            t = (task.time * speed) % (t_max - t_min) + t_min if loop else min(task.time * speed + t_min, t_max)
            # Find the segment
            for i in range(len(times) - 1):
                if times[i] <= t <= times[i+1]:
                    # Linear interpolation
                    alpha = (t - times[i]) / (times[i+1] - times[i])
                    pos = points[i] * (1 - alpha) + points[i+1] * alpha
                    self.orbit_satellite.setPos(pos)
                    break
            return task.cont if (loop or t < t_max) else task.done

        self.taskMgr.add(orbit_anim_task, "OrbitAnimTask")

    def moon_satellite_orbit_task(self, task):
        angle = task.time * self.moon_satellite_orbit_speed
        x = self.moon_satellite_orbit_radius * math.cos(angle)
        y = self.moon_satellite_orbit_radius * math.sin(angle)
        z = 0
        # Apply inclination (rotation around X axis)
        y_incl = y * math.cos(self.moon_satellite_inclination) - z * math.sin(self.moon_satellite_inclination)
        z_incl = y * math.sin(self.moon_satellite_inclination) + z * math.cos(self.moon_satellite_inclination)
        self.moon_satellite.setPos(x, y_incl, z_incl)
        return Task.cont

app = EarthOrbitApp()

# example reading trajectory from JSON file;
# app.orbit_from_json_np = app.add_orbit_from_json("traj.json", color=(1, 0, 1, 1), thickness=2.0)

app.run()

# ---- attempt to use pyside6 ... isn't working yet ----
# class PandaWidget(QWidget):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setAttribute(Qt.WA_PaintOnScreen, True)
#         self.setAttribute(Qt.WA_NativeWindow, True)
#         self.setMinimumSize(800, 600)
#         self.panda_app = None
#         self.timer = QTimer(self)
#         self.timer.timeout.connect(self.step_panda)

#     def showEvent(self, event):
#         if self.panda_app is None:
#             window_handle = int(self.winId())
#             self.panda_app = EarthOrbitApp(parent_window=window_handle)
#             self.timer.start(16)  # ~60 FPS

#     def step_panda(self):
#         if self.panda_app is not None:
#             self.panda_app.taskMgr.step()

# if __name__ == "__main__":
#     print('start')
#     app = QApplication(sys.argv)
#     main_window = QMainWindow()
#     panda_widget = PandaWidget()
#     main_window.setCentralWidget(panda_widget)
#     main_window.resize(800, 600)
#     main_window.show()
#     sys.exit(app.exec())