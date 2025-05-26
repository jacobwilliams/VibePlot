from direct.showbase.ShowBase import ShowBase
from panda3d.core import Point3, TextureStage, AmbientLight, DirectionalLight, LVector3
from direct.task import Task
import math
from panda3d.core import Point3
import random
from panda3d.core import loadPrcFileData
from panda3d.core import LineSegs, NodePath
from panda3d.core import TextNode
from panda3d.core import GeomVertexFormat, GeomVertexData, Geom, GeomNode, GeomTriangles, GeomVertexWriter, GeomVertexRewriter, GeomLinestrips, Vec3, Vec4

from direct.gui.OnscreenText import OnscreenText
import datetime

loadPrcFileData('', 'framebuffer-multisample 1')
loadPrcFileData('', 'multisamples 4')
loadPrcFileData('', 'window-title VibePlot')

class EarthOrbitApp(ShowBase):
    def __init__(self):
        super().__init__()

        # self.accept("mouse1-double", self.recenter_on_earth)  # doesn't work?

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
        self.camera.setPos(0, -20, 0)
        self.camera.lookAt(0, 0, 0)

        # Star background (sky sphere)
        self.stars = self.loader.loadModel("models/planet_sphere")
        self.stars.reparentTo(self.render)
        self.stars.setScale(100, 100, 100)
        self.stars.setTwoSided(True)  # Render inside of sphere
        self.stars.setBin('background', 0)
        self.stars.setDepthWrite(False)
        self.stars.setLightOff()
        self.stars.setCompass()  # Keep stars stationary relative to camera

        star_tex = self.loader.loadTexture("models/epsilon_nebulae_texture_by_amras_arfeiniel.jpg")
        self.stars.setTexture(star_tex, 1)

        # Load the Earth sphere
        self.earth = self.loader.loadModel("models/planet_sphere")
        self.earth.reparentTo(self.render)
        self.earth.setScale(2, 2, 2)
        self.earth.setPos(0, 0, 0)

        # Load and apply Earth texture
        tex = self.loader.loadTexture("models/land_ocean_ice_cloud_2048.jpg")
        self.earth.setTexture(tex, 1)

        # # Add a small sphere as the satellite
        # self.satellite = self.loader.loadModel("models/planet_sphere")
        # self.satellite.setScale(0.2, 0.2, 0.2)
        # self.satellite.setColor(1, 0, 0, 1)
        # self.satellite.reparentTo(self.render)


        # --- Latitude/Longitude grid ---
        grid = LineSegs()
        grid.setThickness(1.0)
        grid.setColor(0.7, 0.7, 0.7, 0.5)  # Light gray, semi-transparent

        radius = 1 #self.earth.getScale().x  # Earth radius
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

        grid_np = self.earth.attachNewNode(grid.create())

        # Lighting
        ambient = AmbientLight("ambient")
        ambient.setColor((0.2, 0.2, 0.2, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        dlight = DirectionalLight("dlight")
        dlight.setColor((1, 1, 1, 1))
        dlnp = self.render.attachNewNode(dlight)
        dlnp.setHpr(0, -60, 0)
        self.render.setLight(dlnp)

        # Add orbit task
        self.orbit_radius = 4
        self.orbit_speed = 1  # radians per second
        self.taskMgr.add(self.orbit_task, "OrbitTask")


        # Add a small sphere as the satellite
        self.satellite = self.loader.loadModel("models/planet_sphere")
        self.satellite.setScale(0.2, 0.2, 0.2)
        self.satellite.setColor(1, 0, 0, 1)
        self.satellite.reparentTo(self.render)

        # --- Visibility cone setup ---
        self.visibility_cone_np = self.render.attachNewNode("visibility_cone")
        self.visibility_cone_angle = math.radians(20)  # cone half-angle in radians
        self.visibility_cone_segments = 24  # smoothness of the cone

        # Draw the orbit path
        orbit_segs = LineSegs()
        orbit_segs.setThickness(2.0)
        orbit_segs.setColor(1, 1, 0, 1)  # Yellow

        num_segments = 100
        inclination = math.radians(45)  # 45 degree inclination
        for i in range(num_segments + 1):
            angle = 2 * math.pi * i / num_segments
            x = self.orbit_radius * math.cos(angle)
            y = self.orbit_radius * math.sin(angle)
            z = 0
            # Rotate around X axis for inclination
            y_incl = y * math.cos(inclination) - z * math.sin(inclination)
            z_incl = y * math.sin(inclination) + z * math.cos(inclination)
            orbit_segs.drawTo(x, y_incl, z_incl)

        orbit_np = NodePath(orbit_segs.create())
        orbit_np.reparentTo(self.render)

        self.taskMgr.add(self.orbit_task, "OrbitTask")
        self.taskMgr.add(self.rotate_earth_task, "RotateEarthTask")

        # #--------------------------------------------
        # # Draw Earth-fixed coordinate axes (origin at Earth's center)
        # axes = LineSegs()
        # axes.setThickness(3.0)
        axis_length = self.earth.getScale().x * 1  # Earth radius * 2

        # # X axis (red)
        # axes.setColor(1, 1, 1, 0.6)
        # axes.moveTo(0, 0, 0)
        # axes.drawTo(axis_length, 0, 0)

        # # Y axis (green)
        # axes.setColor(1, 1, 1, 0.6)
        # axes.moveTo(0, 0, 0)
        # axes.drawTo(0, axis_length, 0)

        # # Z axis (blue)
        # axes.setColor(1, 1, 1, 0.6)
        # axes.moveTo(0, 0, 0)
        # axes.drawTo(0, 0, axis_length)

        # # axes_np = self.render.attachNewNode(axes.create())
        # axes_np = self.earth.attachNewNode(axes.create())

        # --- Arrowheads ---
        arrow_scale = 0.2 * axis_length  # Adjust size as needed

        # Y arrowhead
        x_arrow = self.loader.loadModel("models/arrow")
        x_arrow.reparentTo(self.earth)
        x_arrow.setPos(0, 0, 0)
        x_arrow.setHpr(270, 0, 90)  # Points along +Y
        x_arrow.setScale(arrow_scale)
        x_arrow.setColor(0, 1, 0, 1)

        # X arrowhead
        y_arrow = self.loader.loadModel("models/arrow")
        y_arrow.reparentTo(self.earth)
        y_arrow.setPos(0, 0, 0)
        y_arrow.setHpr(180, 0, 90)  # Points along +X
        y_arrow.setScale(arrow_scale)
        y_arrow.setColor(0, 1, 0, 1)

        # Z arrowhead
        z_arrow = self.loader.loadModel("models/arrow")
        z_arrow.reparentTo(self.earth)
        z_arrow.setPos(0, 0, 0)
        z_arrow.setHpr(180, 0, 0)  # Points along +Z
        z_arrow.setScale(arrow_scale)
        z_arrow.setColor(0, 0, 1, 1)

        # #--------------------------------------------

        # # --- Hyperbolic orbit path ---
        # hyperbolic_segs = LineSegs()
        # hyperbolic_segs.setThickness(1.0)
        # hyperbolic_segs.setColor(0, 1, 1, 1)  # Cyan

        # a = 12 # semi-transverse axis
        # b = 8  # semi-conjugate axis
        # h_inclination = math.radians(30)  # inclination for hyperbolic orbit
        # num_segments = 200
        # t_min = -2
        # t_max = 2
        # c = math.sqrt(a * a + b * b)  # Distance from center to focus

        # dash_length = 3  # Number of segments per dash
        # gap_length = 2   # Number of segments per gap

        # drawing = True
        # for i in range(num_segments + 1):
        #     t = t_min + (t_max - t_min) * i / num_segments
        #     x = a * math.cosh(t) - c  # Shift so focus is at x=0
        #     y = b * math.sinh(t)
        #     z = 0
        #     # Rotate around X axis for inclination
        #     y_incl = y * math.cos(h_inclination) - z * math.sin(h_inclination)
        #     z_incl = y * math.sin(h_inclination) + z * math.cos(h_inclination)

        #     # Dashed line logic
        #     pattern_length = dash_length + gap_length
        #     if (i % pattern_length) == 0:
        #         drawing = True
        #         hyperbolic_segs.moveTo(x, y_incl, z_incl)
        #     elif (i % pattern_length) == dash_length:
        #         drawing = False
        #     if drawing:
        #         hyperbolic_segs.drawTo(x, y_incl, z_incl)

        # hyperbolic_np = NodePath(hyperbolic_segs.create())
        # hyperbolic_np.reparentTo(self.render)
        # # Hyperbolic satellite
        # self.hyper_sat = self.loader.loadModel("models/planet_sphere")
        # self.hyper_sat.setScale(0.15, 0.15, 0.15)
        # self.hyper_sat.setColor(0, 1, 1, 1)
        # self.hyper_sat.reparentTo(self.render)

        # self.hyperbolic_a = a
        # self.hyperbolic_b = b
        # self.hyperbolic_c = c
        # self.hyperbolic_incl = h_inclination
        # self.hyperbolic_t_min = t_min
        # self.hyperbolic_t_max = t_max
        # self.hyperbolic_speed = 0.5  # Adjust for faster/slower

        # self.taskMgr.add(self.hyperbolic_orbit_task, "HyperbolicOrbitTask")

        # --- Example particles ---
        self.particles = []
        self.particle_params = []
        num_particles = 100
        particle_radius = 0.03
        for _ in range(num_particles):
            # Random orbital parameters
            r = random.uniform(2.2, 4.0)
            inclination = random.uniform(0, math.pi)
            angle0 = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.3, 1.2)
            particle = self.loader.loadModel("models/planet_sphere")
            particle.setScale(particle_radius)
            particle.setColor(random.random(), random.random(), random.random(), 1)
            particle.reparentTo(self.render)
            self.particles.append(particle)
            self.particle_params.append((r, inclination, angle0, speed))

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
        self.trace_length = 20  # Number of points in the trace
        self.particle_traces = [[particle.getPos()] * self.trace_length for particle in self.particles]
        self.trace_nodes = [self.render.attachNewNode("trace") for _ in self.particles]

        self.taskMgr.add(self.particles_orbit_task, "ParticlesOrbitTask")

    # def recenter_on_earth(self):
    #     # Reset camera and trackball to look at Earth's center
    #     self.trackball.node().setHpr(0, 0, 0)
    #     self.trackball.node().setPos(0, 20, 0)
    #     self.trackball.node().setOrigin(Point3(0, 20, 0))
    #     self.camera.setPos(0, 0, 0)
    #     self.camera.lookAt(0, 20, 0)

    # def orbit_task(self, task):
    #     angle = task.time * self.orbit_speed
    #     inclination = math.radians(45)  # 45 degree inclination
    #     x = self.orbit_radius * math.cos(angle)
    #     y = self.orbit_radius * math.sin(angle)
    #     z = 0
    #     # Rotate around X axis for inclination
    #     y_incl = y * math.cos(inclination) - z * math.sin(inclination)
    #     z_incl = y * math.sin(inclination) + z * math.cos(inclination)
    #     self.satellite.setPos(x, 20 + y_incl, z_incl)
    #     return Task.cont


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
        earth_radius = self.earth.getScale().x
        if v_len != 0:
            surface_point = earth_center + v * (earth_radius / v_len)
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

        return Task.cont

    def rotate_earth_task(self, task):
        self.earth.setH(self.earth.getH() + 0.2)  # Adjust speed as desired
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
        self.hud_text.setText(f"{now}")
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

        # (existing code for connecting lines...)
        self.particle_lines = LineSegs()
        self.particle_lines.setThickness(1.5)
        self.particle_lines.setColor(1, 0, 1, 1)
        for i in range(self.connect_count):
            for j in range(i + 1, self.connect_count):
                pos_i = self.particles[i].getPos()
                pos_j = self.particles[j].getPos()
                self.particle_lines.moveTo(pos_i)
                self.particle_lines.drawTo(pos_j)
        self.lines_np.removeNode()
        self.lines_np = NodePath(self.particle_lines.create())
        self.lines_np.reparentTo(self.render)

        return Task.cont

app = EarthOrbitApp()
app.run()