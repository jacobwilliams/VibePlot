
import sys
import json
import math
import random
import psutil, os
import imageio
import numpy as np
import datetime
import csv

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
                          Point2, Point3, TextureStage, AmbientLight, DirectionalLight, LVector3,
                          loadPrcFileData, LineSegs, TextNode,
                          GeomVertexRewriter, GeomLinestrips,
                          CardMaker, TransparencyAttrib,
                          WindowProperties, TransparencyAttrib,
                          Shader, Mat3, BitMask32, GeomPoints,
                          Quat, CollisionTraverser, CollisionNode, CollisionRay, CollisionHandlerQueue, AntialiasAttrib, RenderModeAttrib, GeomVertexArrayFormat
                          )


loadPrcFileData('', 'framebuffer-multisample 1')
loadPrcFileData('', 'multisamples 4')
loadPrcFileData('', 'window-title VibePlot')
# loadPrcFileData('', 'window-type none')  # Prevent Panda3D from opening its own window
loadPrcFileData('', 'gl-include-points-size true')

EARTH_RADIUS = 2.0  # Radius of Earth in Panda3D units
MOON_RADIUS = EARTH_RADIUS / 4.0  # Radius of Moon in Panda3D units
MARS_RADIUS = EARTH_RADIUS / 3.0  # Radius of Mars in Panda3D units
# STARMAP_IMAGE = 'models/epsilon_nebulae_texture_by_amras_arfeiniel.jpg'
STARMAP_IMAGE = 'models/2k_stars.jpg'
USE_STAR_IMAGE = False
VENUS_RADIUS = EARTH_RADIUS * 0.2  # Radius of Venus in Panda3D units
SUN_RADIUS = EARTH_RADIUS * 2

constellations = {
    "orion": [
        "betelgeuse", "bellatrix", "mintaka", "alnilam", "alnitak", "saiph", "rigel"
    ],
    "big_dipper": [
        "dubhe", "merak", "phecda", "megrez", "alioth", "mizar", "alkaid"
    ],
    "cassiopeia": [
        "schedar", "caph", "gamma cassiopeiae", "rho cassiopeiae", "segin"
    ],
    "cygnus": [
        "deneb", "sadr", "gienah", "delta cygni", "albireo"
    ],
    "lyra": [
        "vega", "sheliak", "sulafat"
    ],
    "taurus": [
        "aldebaran", "ain", "alnath"
    ],
    "scorpius": [
        "antareS", "shaula", "sargas", "dschubba"
    ],
    "leo": [
        "regulus", "denebola", "algieba", "zeta leonis", "adhafera"
    ],
    "gemini": [
        "castor", "pollux", "alhena", "wasat"
    ],
    "canis_major": [
        "sirius", "mirzam", "adhara", "wezen", "aludra"
    ],
    "canis_minor": [
        "procyon", "gomeisa"
    ],
    "aquila": [
        "altair", "tarazed", "alshain"
    ],
    "perseus": [
        "mirfak", "algol", "atiks"
    ],
    "crux": [
        "acrux", "mimosa", "gacrux", "delta crucis"
    ],
    "centaurus": [
        "rigil kentaurus", "hadar", "menkent"
    ],
    "aries": [
        "hamal", "sheratan", "mesarthim"
    ],
    "andromeda": [
        "almach", "mirach", "alpheratz"
    ],
    "corona_borealis": [
        "alphecca", "nusakan"
    ],
    "ursa_minor": [
        "polaris", "kochab", "pherkad"
    ],
    "pegasus": [
        "markab", "scheat", "algenib", "enif"
    ],
    "summer_triangle": [
        "vega", "deneb", "altair"
    ],
    # Add more as desired!
}

def lonlat_to_xyz(lon, lat, radius):
    lon_rad = math.radians(lon)
    lat_rad = math.radians(lat)
    x = radius * math.cos(lat_rad) * math.cos(lon_rad)
    y = radius * math.cos(lat_rad) * math.sin(lon_rad)
    z = radius * math.sin(lat_rad)
    return x, y, z

def create_body_fixed_arrow(body_radius: float, color=(1, 1, 1, 1)):
    shaft_length = body_radius * 2.0
    shaft_radius = body_radius * 0.05
    head_length = body_radius * 0.3
    head_radius = body_radius * 0.1
    return create_arrow(shaft_length, shaft_radius, head_length, head_radius, color=color)

def create_arrow(shaft_length=4.0, shaft_radius=0.1, head_length=0.6, head_radius=0.3, color=(1, 1, 1, 1)):
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

def create_sphere(radius=1.0, num_lat=16, num_lon=32, color=(1, 1, 1, 1)):
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

class Body:

    # notes:
    # * maybe add a uuid to the strings to we are sure they are unique (if bodies have the same names)

    # Body (self._body)
    # └── Rotator (self._rotator)
    #     ├── Sphere geometry (with texture)
    #     ├── Axes
    #     ├── Grid
    #     └── Other visuals

    def __init__(self, parent : ShowBase, name: str, radius : float, color=(1, 1, 1, 1),
                 texture : str = None,
                 day_tex : str = None, night_tex : str = None, sun_dir = LVector3(0, 0, 1),
                 trace_length: int = 200,
                 geojson_path : str = None, lon_rotate : str = 0.0,
                 draw_grid: bool = False, draw_3d_axes: bool = True,
                 orbit_markers: bool = False, marker_interval: int = 10,
                 marker_size: float = 0.08, marker_color=(0, 1, 1, 1)):

        self.name = name
        self.radius = radius
        self.color = color
        self.parent = parent

        # Store orbit marker parameters
        self.orbit_markers = orbit_markers
        self.marker_interval = marker_interval
        self.marker_size = marker_size
        self.marker_color = marker_color
        self.marker_nodes = []
        self.marker_labels = []  #  initialize marker labels list

        # the rotator node is the parent of the body, so it can be rotated
        # [it's the body-fixed frame]
        #self._rotator = self._body.attachNewNode(f"{name}_rotator")
        self._rotator = self.parent.render.attachNewNode(f"{name}_rotator")
        self._rotator.setPos(0, 0, 0)

        self._body = create_sphere(radius, num_lat=24, num_lon=48, color=color)
        self._body.reparentTo(self._rotator)
        self._body.setPos(0, 0, 0)

        self._body.setLightOff()
        self._body.setLight(self.parent.dlnp)

        if texture is not None:
            tex = parent.loader.loadTexture(texture)
            self._body.setTexture(tex, 1)
        elif day_tex is not None and night_tex is not None:
            # Load and apply Earth texture
            day_tex = parent.loader.loadTexture(day_tex)
            night_tex = parent.loader.loadTexture(night_tex)
            self._body.setTexture(day_tex, 1)
            self._body.setShader(Shader.load(Shader.SL_GLSL, "models/earth_daynight.vert", "models/earth_daynight.frag"))
            self._body.setTexture(TextureStage("day"), day_tex)
            self._body.setTexture(TextureStage("night"), night_tex)
            self._body.setShaderInput("day", day_tex)
            self._body.setShaderInput("night", night_tex)
            # Set the sun direction uniform (should match your light direction)
            self._body.setShaderInput("sundir", sun_dir)

            self.parent.add_task(self.update_earth_shader_sundir_task, f"Update{self.name}ShaderSunDir")

        else:
            # no texture, just a color
            self._body.setColor(*color)

        if geojson_path:
            self.draw_country_boundaries(geojson_path=geojson_path, lon_rotate=lon_rotate)

        if draw_grid:
            self.draw_lat_lon_grid()

        self.parent.add_task(self.orbit_task, f"{self.name}OrbitTask")

        self.trace_length = trace_length  # Number of points to keep in the moon's trace
        if self.trace_length:
            self._trace = []
            self._trace_node = self.parent.render.attachNewNode(f"{self._body}_trace")

        if draw_3d_axes:
            # 3D axes for the body
            self.axis_np = self.create_body_fixed_axes()

        self.reparent_to_rotator()

    def update_earth_shader_sundir_task(self, task):
        self.update_shader_sundir(self.parent.dlnp)
        return Task.cont

    def update_shader_sundir(self, sun_np):
        """Update the sundir shader input for this body, given a sun NodePath."""
        # Get sun direction in world space
        sun_dir_world = sun_np.getQuat(self.parent.render).getForward()
        # Get sun direction in this body's local space
        sun_dir_local = self._body.getQuat(self.parent.render).conjugate().xform(sun_dir_world)
        # Optional: rotate by 180 deg around Z to match texture orientation
        rot180 = Mat3.rotateMatNormaxis(180, Vec3(0, 0, 1))
        sun_dir_local_rot = rot180.xform(sun_dir_local)
        self._body.setShaderInput("sundir", sun_dir_local_rot)

    def setup_body_fixed_camera(self, view_distance=None):
        """Set up camera in this body's frame."""
        self.parent.setup_body_fixed_frame(self, view_distance)

    def create_body_fixed_axes(self):
        # 3D body-fixed axes for a body.
        arrow_ambient_np = self.parent.render.attachNewNode(self.parent.arrow_ambient)
        axes_np = self._rotator.attachNewNode("axes")
        axes_np.setPos(0, 0, 0)
        x_arrow = create_body_fixed_arrow(self.radius)
        x_arrow.setHpr(90, 0, 0)    # +X axis
        y_arrow = create_body_fixed_arrow(self.radius)
        y_arrow.setHpr(180, 0, 0)   # +Y axis
        z_arrow = create_body_fixed_arrow(self.radius)
        z_arrow.setHpr(0, 90, 0)    # +Z axis
        for a in [x_arrow, y_arrow, z_arrow]:
            a.reparentTo(axes_np)
            a.setLightOff()
            a.setLight(self.parent.dlnp)
            a.setLight(arrow_ambient_np)
            a.setShaderOff(1)
            a.setTextureOff(1)
        axes_np.setShaderOff(1)  # Turn off shader inheritance completely
        axes_np.setTextureOff(1)  # Turn off texture inheritance
        # axes_np = self._rotator.attachNewNode("axes")
        return axes_np

    def reparent_to_rotator(self):
        # Reparent the body's children to the rotator node
        for child in self._body.getChildren():
            if child.getName() != f"{self.name}_rotator":
                child.reparentTo(self._rotator)

    def set_orientation(self, et: float):

        # Get the rotation matrix from your function
        # Assuming it returns a 3x3 numpy matrix or similar
        rotation_matrix = self.get_rotation_matrix(et)

        # Convert to Panda3D's Mat3
        mat3 = Mat3(
            rotation_matrix[0, 0], rotation_matrix[0, 1], rotation_matrix[0, 2],
            rotation_matrix[1, 0], rotation_matrix[1, 1], rotation_matrix[1, 2],
            rotation_matrix[2, 0], rotation_matrix[2, 1], rotation_matrix[2, 2]
        )
        quat = Quat()
        quat.setFromMatrix(mat3)
        self._rotator.setQuat(quat)

    def get_position_vector(self, et: float):

        # there is where we would maybe call an ephemeris
        # For simplicity, let's assume the following orbits:

        # Earth stays at the origin
        if self.name.lower() == "earth":
            return np.array([0.0, 0.0, 0.0])

        elif self.name.lower() == "sun":
            return np.array([0.0, -10.0, 0.0])

        # Moon orbits Earth
        elif self.name.lower() == "moon":
            # Use the same parameters as before
            moon_orbit_radius = EARTH_RADIUS * 3  # Distance from Earth center
            moon_orbit_speed = 0.7  # radians per second
            angle = et * moon_orbit_speed
            x = moon_orbit_radius * math.cos(angle)
            y = moon_orbit_radius * math.sin(angle)
            z = 0
            return np.array([x, y, z])

        # Mars orbits Earth (for demo)
        elif self.name.lower() == "mars":
            mars_orbit_radius = EARTH_RADIUS * 4
            mars_orbit_speed = 0.5  # radians per second
            angle = et * mars_orbit_speed
            x = mars_orbit_radius * math.cos(angle)
            y = mars_orbit_radius * math.sin(angle)
            z = 0
            return np.array([x, y, z])

        # Venus (example, you can adjust as needed)
        elif self.name.lower() == "venus":
            venus_orbit_radius = EARTH_RADIUS * 2.5
            angle = et * 0.3  # example speed
            x = venus_orbit_radius * math.cos(angle)
            y = venus_orbit_radius * math.sin(angle)
            z = 0
            return np.array([x, y, z])

        # Default: stationary at origin
        return np.array([0.0, 0.0, 0.0])

    def get_rotation_matrix(self, et: float):

        # e.g. call spice to get the body-fixed rotation matrix
        # This is a simplified example, replace with actual logic to get the rotation matrix

        if self.name.lower() == "earth":
            # Adjust this speed for your visualization (radians/sec)
            earth_rotation_speed = 2 * math.pi / 24.0  # 1 revolution per 24 "seconds" (for demo)
            angle = et * earth_rotation_speed
            # Earth's actual axial tilt is about 23.44 degrees
            tilt_deg = 23.44
            tilt_rad = math.radians(tilt_deg)
            # Rotation matrix: Rz(angle) * Rx(tilt)
            Rz = np.array([
                [math.cos(angle), -math.sin(angle), 0],
                [math.sin(angle),  math.cos(angle), 0],
                [0, 0, 1]
            ])
            Rx = np.array([
                [1, 0, 0],
                [0, math.cos(tilt_rad), -math.sin(tilt_rad)],
                [0, math.sin(tilt_rad),  math.cos(tilt_rad)]
            ])
            return Rz @ Rx

        # Moon: rotates with its orbit (tidal locking)
        elif self.name.lower() == "moon":
            moon_orbit_speed = 0.7  # radians per second
            angle = et * moon_orbit_speed
            # Tidal locking: always same face to Earth
            # Add axis tilt if desired (e.g., 6.68 degrees)
            tilt_deg = 6.68
            tilt_rad = math.radians(tilt_deg)
            # Rotation matrix: Rz(angle) * Rx(tilt)
            Rz = np.array([
                [math.cos(angle), -math.sin(angle), 0],
                [math.sin(angle),  math.cos(angle), 0],
                [0, 0, 1]
            ])
            Rx = np.array([
                [1, 0, 0],
                [0, math.cos(tilt_rad), -math.sin(tilt_rad)],
                [0, math.sin(tilt_rad),  math.cos(tilt_rad)]
            ])
            return Rz @ Rx

        # Mars: rotates as it orbits
        elif self.name.lower() == "mars":
            mars_orbit_speed = 0.5  # radians per second
            angle = et * mars_orbit_speed
            # Mars axial tilt: 25.19 degrees
            tilt_deg = 25.19
            tilt_rad = math.radians(tilt_deg)
            # Rotation matrix: Rz(angle) * Rx(tilt)
            Rz = np.array([
                [math.cos(angle), -math.sin(angle), 0],
                [math.sin(angle),  math.cos(angle), 0],
                [0, 0, 1]
            ])
            Rx = np.array([
                [1, 0, 0],
                [0, math.cos(tilt_rad), -math.sin(tilt_rad)],
                [0, math.sin(tilt_rad),  math.cos(tilt_rad)]
            ])
            return Rz @ Rx

        # Venus: slow retrograde rotation (example)
        elif self.name.lower() == "venus":
            venus_rotation_speed = -0.1  # negative for retrograde
            angle = et * venus_rotation_speed
            # Venus axial tilt: 177.4 degrees (almost upside down)
            tilt_deg = 177.4
            tilt_rad = math.radians(tilt_deg)
            Rz = np.array([
                [math.cos(angle), -math.sin(angle), 0],
                [math.sin(angle),  math.cos(angle), 0],
                [0, 0, 1]
            ])
            Rx = np.array([
                [1, 0, 0],
                [0, math.cos(tilt_rad), -math.sin(tilt_rad)],
                [0, math.sin(tilt_rad),  math.cos(tilt_rad)]
            ])
            return Rz @ Rx

        # Default: identity
        return np.eye(3)

    def draw_country_boundaries(self, geojson_path : str, lon_rotate : float = 0.0, radius_pad : float = 0.001):

        with open(geojson_path, 'r') as f:
            data = json.load(f)

        segs = LineSegs()
        segs.setThickness(1.2)
        segs.setColor(1, 1, 1, 0.5)

        for feature in data['features']:
            for coords in feature['geometry']['coordinates']:
                # Handle MultiPolygon and Polygon
                if feature['geometry']['type'] == 'Polygon':
                    rings = [coords]
                else:
                    rings = coords
                for ring in rings:
                    first = True
                    for lon, lat in ring:
                        lon = lon + lon_rotate
                        x, y, z = lonlat_to_xyz(lon, lat, self.radius + radius_pad)
                        if first:
                            segs.moveTo(x, y, z)
                            first = False
                        else:
                            segs.drawTo(x, y, z)

        self.boundaries_np = self._body.attachNewNode(segs.create())
        self.boundaries_np.setLightOff()
        self.boundaries_np.setTwoSided(True)
        self.boundaries_np.setTransparency(True)

    def orbit_task(self, task):
        et = task.time

        self.set_orientation(et)
        r = self.get_position_vector(et)

        # Get the new position
        new_pos = Point3(r[0], r[1], r[2])
        self._rotator.setPos(new_pos)

        # Update body trace
        body_pos = self._body.getPos(self.parent.render)
        self._trace.append(body_pos)

        # Trim trace if needed
        if self.trace_length and len(self._trace) > self.trace_length:
            self._trace.pop(0)

        # Draw the trace and markers
        self._trace_node.node().removeAllChildren()

        # Clear existing markers
        if hasattr(self, 'marker_nodes'):
            for marker in self.marker_nodes:
                marker.removeNode()
            self.marker_nodes = []

        # Clear existing marker labels
        if hasattr(self, 'marker_labels'):
            for label in self.marker_labels:
                label.removeNode()
        self.marker_labels = []

        # Create marker parent if needed
        if not hasattr(self, 'orbit_markers_np') or self.orbit_markers_np is None:
            self.orbit_markers_np = self.parent.render.attachNewNode(f"{self.name}_orbit_markers")
        else:
            self.orbit_markers_np.node().removeAllChildren()

        # Draw trace and add markers
        if len(self._trace) > 1:
            segs = LineSegs()
            segs.setThickness(3.0)

            # Decide how many markers to create
            marker_interval = max(1, len(self._trace) // (self.trace_length // self.marker_interval))

            marker_count = 0  # For numbering markers

            for i, pt in enumerate(self._trace):
                # Alpha increases from oldest to newest point
                alpha = i / (len(self._trace) - 1)

                # Set color for trace segment
                segs.setColor(0.7, 0.7, 1, alpha)

                # Start or continue line
                if i == 0:
                    segs.moveTo(pt)
                else:
                    segs.drawTo(pt)

                # Add marker at regular intervals
                if self.orbit_markers and i % marker_interval == 0:
                    marker_count += 1

                    marker_color = (
                        self.marker_color[0],
                        self.marker_color[1],
                        self.marker_color[2],
                        self.marker_color[3] * alpha
                    )

                    marker = create_sphere(
                        radius=self.marker_size,
                        num_lat=8,
                        num_lon=16,
                        color=marker_color
                    )
                    marker.reparentTo(self.orbit_markers_np)
                    marker.setPos(pt)
                    marker.setLightOff()
                    marker.setTransparency(True)
                    self.marker_nodes.append(marker)

                    # Create numbered label for this marker
                    label_text = TextNode(f'marker_label_{marker_count}')
                    label_text.setText(f"{marker_count}")
                    label_text.setTextColor(
                        self.marker_color[0],
                        self.marker_color[1],
                        self.marker_color[2],
                        self.marker_color[3] * alpha  # Same opacity as marker
                    )
                    label_text.setAlign(TextNode.ACenter)
                    label_np = self.orbit_markers_np.attachNewNode(label_text)

                    # Position the label next to the marker
                    label_offset = self.marker_size * 2.5
                    label_np.setPos(pt[0], pt[1], pt[2] + label_offset)

                    # Scale the label appropriately
                    label_np.setScale(0.2)

                    # Make the label always face the camera
                    label_np.setBillboardPointEye()

                    # Apply same properties as marker
                    label_np.setLightOff()
                    label_np.setTransparency(True)

                    # Store for cleanup
                    self.marker_labels.append(label_np)


            # Create the trace line
            self._trace_node.attachNewNode(segs.create())
            self._trace_node.setTransparency(True)

        return Task.cont

    def draw_lat_lon_grid(self, num_lat=9, num_lon=18, radius_pad=0.01, color=(1, 1, 1, 1)):
        """Draws latitude and longitude grid lines on the body.

        Args:
            num_lat (int, optional): Number of latitude lines (excluding poles). Defaults to 9.
            num_lon (int, optional): Number of longitude lines. Defaults to 18.
            radius_pad (float, optional): how far above surface to draw the grid. Defaults to 0.01.
            color (tuple, optional): RGBA color for the grid lines. Defaults to (1, 1, 1, 1) - white.
        """

        # --- Latitude/Longitude grid ---
        grid = LineSegs()
        grid.setThickness(1.0)
        # grid.setColor(0.7, 0.7, 0.7, 0.5)  # Light gray, semi-transparent
        grid.setColor(color)
        radius = self.radius + radius_pad
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
        # self.grid_np = self.parent.render.attachNewNode(grid.create())
        self.grid_np = self._body.attachNewNode(grid.create())
        self.grid_np.setShaderOff()
        self.grid_np.setLightOff()
        self.grid_np.setTwoSided(True)

class EarthOrbitApp(ShowBase):
    def __init__(self, parent_window=None, friction: float = 1.0, draw_plane : bool = False):
        # loadPrcFileData('', 'window-type none')  # Prevent Panda3D from opening its own window
        super().__init__()

        # Initialize tracking variables
        self.tracked_body = None
        self.tracked_distance = 0
        self.tracking_task = None
        # Task for tracking mouse during drag
        self.mouse_task = None
        # Task for inertial movement
        self.inertia_task = None
        self.mouse_dragged = False

        self.task_list = []  # list of (task, name) tuples

        # Set horizontal and vertical FOV in degrees
        self.camLens.setFov(60, 60)
        # To make the view wider (fisheye effect), increase the FOV (e.g., 90).
        # To zoom in (narrower view), decrease the FOV (e.g., 30).
        # self.camLens.setNear(0.1)
        # self.camLens.setFar(1000)

        # update aspect ratio
        width = self.win.getProperties().getXSize()
        height = self.win.getProperties().getYSize()
        if width > 0 and height > 0:
            aspect = width / height
            self.camLens.setAspectRatio(aspect)

        # Initialize in base frame at startup
        self.setup_base_frame()
        self.add_task(self.update_body_fixed_camera_task, "UpdateBodyFixedCamera")

        if parent_window is not None:
            props = WindowProperties()
            props.setParentWindow(parent_window)
            props.setOrigin(0, 0)
            props.setSize(800, 600)  # Or your desired size
            self.openDefaultWindow(props=props)

        self.process = psutil.Process(os.getpid())
        self.process.cpu_percent()  # Initialize CPU usage

        self.accept("space", self.recenter_on_earth)
        self.accept("a", self.toggle_scene_animation)  # Press 'a' to toggle all animation

        # Add key bindings for switching camera focus
        self.accept("1", self.focus_on_earth)
        self.accept("2", self.focus_on_moon)
        self.accept("3", self.focus_on_mars)
        self.accept("4", self.focus_on_venus)

        self.scene_anim_running = True

        # self.taskMgr.doMethodLater(2.0, self.debug_tasks, "DebugTasks")  # debugging
        # messenger.toggleVerbose()  # Enable verbose messenger output
        # self.accept("*", self.event_logger)  # debugging, log all events

        # inertia:
        self.last_mouse_pos = None
        self.angular_velocity = Vec3(0, 0, 0)
        self.inertia_active = False
        self.friction = min(abs(friction), 1.0) # Dampening factor for inertial rotation. should be between 0 [no inertial] and 1 [no friction]
        self.inertia_axis = Vec3(0, 0, 1)  # Default axis
        self.inertia_angular_speed = 0.0   # Angular speed in radians/sec

        # Add mouse handlers
        # self.ignore("option-mouse1")
        # self.ignore("option-mouse1-up")
        # self.ignore("alt-mouse1")
        # self.ignore("alt-mouse1-up")
        # self.ignore("shift-mouse1")
        # self.ignore("shift-mouse1-up")
        self.accept("mouse1", self.stop_inertia)
        # Add mouse handlers - use option key name for Mac compatibility
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

        self.star_sphere_np = self.render.attachNewNode("star_sphere")

        if USE_STAR_IMAGE:
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
            star_tex = self.loader.loadTexture(STARMAP_IMAGE)
            self.stars.setTexture(star_tex, 1)
        else:
            self.win.setClearColor((0, 0, 0, 1))  # black background

        # self.add_stars("models/Stars_HYGv3.txt", num_stars=500)
        self.add_stars("models/hygdata_v41.csv", num_stars=500)
        # self.add_stars_as_points("models/Stars_HYGv3.txt", num_stars=200)
        self.draw_constellations()
        self.draw_sky_grid(sphere_radius=100)

        self.add_task(self.update_star_sphere, "UpdateStarSphere")

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

        # light for the axis arrows:
        self.arrow_ambient = AmbientLight("arrow_ambient")
        self.arrow_ambient.setColor((0.4, 0.4, 0.4, 1))

        self.trackball_origin_task_ref = None

        self.earth = Body(
            self,
            name="Earth",
            radius=EARTH_RADIUS,
            day_tex="models/land_ocean_ice_cloud_2048.jpg",
            night_tex="models/2k_earth_nightmap.jpg",
            geojson_path="models/custom.geo.json",
            lon_rotate=180.0,  # Rotate to match texture orientation
            color=(1, 1, 1, 1),
            draw_grid=True,
            draw_3d_axes=True
        )

        # put a site on the Earth:
        site_lat = 0.519   # radians
        site_lon = 1.665  # radians
        earth_radius = EARTH_RADIUS + 0.001
        site_x = earth_radius * math.cos(site_lat) * math.cos(site_lon)
        site_y = earth_radius * math.cos(site_lat) * math.sin(site_lon)
        site_z = earth_radius * math.sin(site_lat)
        self.site_np = self.earth._body.attachNewNode("site")
        self.site_np.setPos(self.earth._body, site_x, site_y, site_z)
        if True:
            # Optional: add a small sphere to mark the site
            site_marker = create_sphere(radius=0.02, num_lat=24, num_lon=48, color=(1,0,0,0.5))
            site_marker.reparentTo(self.site_np)
            site_marker.setShaderOff(1)   # so it won't have the earth texture
            site_marker.setTextureOff(1)  #
            site_marker.setTransparency(True)
        self.site_lines_np = None

        #self.draw_country_boundaries("models/custom.geo.json", radius=EARTH_RADIUS + 0.001, lon_rotate = 180.0)
        # rotate because the texturemap is rotated...

        # just a test:
        #self.add_radiation_belt(inner_radius=EARTH_RADIUS*1.5, outer_radius=EARTH_RADIUS*2.5, belt_color=(0.2, 1, 0.2, 0.18), num_major=100, num_minor=24)

        # self.rings = self.add_saturn_rings(
        #                     inner_radius=EARTH_RADIUS*1.2,
        #                     outer_radius=EARTH_RADIUS*2.8,
        #                     inclination_deg=15,  # Tilt the rings
        #                     num_rings=7,         # More rings for detail
        #                     transparency=0.7     # Slightly transparent
        #                 )
        # self.add_task(self.rotate_rings_task, "RotateRingsTask")

        self.moon = Body(
            self,
            name="Moon",
            radius=MOON_RADIUS,
            texture="models/lroc_color_poles_1k.jpg",
            color=(1, 1, 1, 1),
            draw_3d_axes=True
        )

        # self.sun = Body(
        #             self,
        #             name="Sun",
        #             radius=SUN_RADIUS,
        #             texture="models/2k_sun.jpg",
        #             color=(1, 1, 0, 1),
        #             draw_3d_axes=False
        #         )
        # self.sun._body.setLightOff()  # no shadowing on the sun!

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
                 trace_length=50,
                 color=(1, 0.8, 0.6, 1),
                 orbit_markers=True,
                 marker_size=0.06,
                 marker_interval=5,
                 marker_color=(1, 1, 1, 0.5))

        # --- Add a satellite orbiting the Moon ---
        self.moon_satellite_orbit_radius = 2 * MOON_RADIUS  # Distance from Moon center
        self.moon_satellite_orbit_speed = 2.0  # radians per second (relative to Moon)
        self.moon_satellite = create_sphere(radius=0.1, num_lat=16, num_lon=32, color=(1, 1, 0, 1))
        self.moon_satellite.reparentTo(self.moon._body)  # Parent to the Moon so it follows Moon's orbit
        self.add_task(self.moon_satellite_orbit_task, "MoonSatelliteOrbitTask")
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
        self.moon_satellite_orbit_np = self.moon._body.attachNewNode(moon_orbit_segs.create())
        # self.moon_satellite_orbit_np.setTransparency(True)
        self.moon_satellite_orbit_np.setLightOff()
        self.moon_satellite.setTextureOff(1)  # so it doesn't use the moon texture
        self.moon_satellite.setShaderOff(1)

        if draw_plane:
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
        self.orbit_radius = EARTH_RADIUS * 2.0
        self.orbit_speed = 1.0 #0.5  # radians per second
        #self.add_task(self.orbit_task, "OrbitTask")

        # Add a small sphere as the satellite
        self.satellite = create_sphere(radius=0.1, num_lat=24, num_lon=48, color=(1,0,0,1))
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

        self.add_task(self.orbit_task, "OrbitTask")

        # to pulsate the orbit line:
        # self.add_task(self.pulsate_orbit_line_task, "PulsateOrbitLineTask")

        # self.orbit_tube_np = self.add_orbit_tube(radius=5.0, inclination_deg=20, tube_radius=0.03, num_segments=100, num_sides=16, eccentricity=0.2)
        # self.orbit_tube_np2 = self.add_orbit_tube(radius=4.0, inclination_deg=45, tube_radius=0.03, num_segments=100, num_sides=16, eccentricity=0.3)

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
            # particle = self.loader.loadModel("models/planet_sphere")
            #particle.setScale(particle_radius)
            #particle.setColor(random.random(), random.random(), random.random(), 1)
            particle = create_sphere(radius=particle_radius, num_lat=10, num_lon=20, color=(random.random(), random.random(), random.random(), 1))
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

        self.add_task(self.particles_orbit_task, "ParticlesOrbitTask")

        self.manifold_np = None

        # self.setup_mouse_picker()

        self.record_movie = False
        self.movie_writer = None
        self.movie_filename = "output.mp4"
        self.movie_fps = 60 #30  # or your desired framerate
        self.accept("r", self.toggle_movie_recording)

        self.draw_axis_grid()

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
            #self.trackball.reparentTo(self.initial_trackball_parent)
            self.trackball.setPos(self.render, self.initial_trackball_pos)
            self.trackball.setHpr(self.render, self.initial_trackball_hpr)

            # self.trackball.node().resetMat()
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

            # print(f'{self.initial_camera_parent=}')
            # print(f'{self.initial_camera_pos=}')
            # print(f'{self.initial_camera_hpr=}')
            # print(f'{self.initial_trackball_parent=}')
            # print(f'{self.initial_trackball_pos=}')
            # print(f'{self.initial_trackball_hpr=}')

        # Restore trackball node settings
        # print('restore')
        # self.trackball.node().setPos(0, view_distance, 0)
        # self.trackball.node().setOrigin(Point3(0, 0, 0))
        # self.trackball.node().setForwardScale(1.0)
        # self.trackball.node().setRelTo(self.render)
        # # self.camera.setPos(0, view_distance, 0)  # why not this ??
        # # self.camera.lookAt(0, 0, 0)

        # print(f'  {self.camera.getParent()=}')
        # print(f'  {self.camera.getPos(self.render)=}')
        # print(f'  {self.camera.getHpr(self.render)=}')
        # print(f'  {self.trackball.getParent()=}')
        # print(f'  {self.trackball.getPos(self.render)=}')
        # print(f'  {self.trackball.getHpr(self.render)=}')


        self.trackball.node().setPos(0, view_distance, 0)
        self.trackball.node().setOrigin(Point3(0, 0, 0))

        self.current_focus = "base_frame"

    # def setup_base_frame(self):
    #     """Restore camera and trackball to their original working setup."""
    #     self.stop_inertia()

    #     # Remove camera_pivot if it exists
    #     if hasattr(self, 'camera_pivot'):
    #         self.camera_pivot.removeNode()
    #         del self.camera_pivot

    #     # Restore parents first (critical step for proper hierarchy)
    #     self.camera.reparentTo(self.render)
    #     self.trackball.reparentTo(self.render)

    #     # ALWAYS set these values exactly as they were in the first call
    #     self.trackball.node().setPos(0, EARTH_RADIUS * 10, 0)
    #     self.trackball.node().setOrigin(Point3(0, 0, 0))
    #     self.trackball.node().setForwardScale(1.0)
    #     self.trackball.node().setRelTo(self.render)
    #     self.trackball.node().setMat(Mat4())  # Reset matrix to identity

    #     # Position camera ALWAYS at the same distance
    #     self.camera.setPos(0, EARTH_RADIUS * 10, 0)
    #     self.camera.lookAt(0, 0, 0)  # Make sure camera looks at origin

    #     # Only store initial values on first call
    #     if not hasattr(self, 'initial_camera_parent'):
    #         print('first call - storing initial values')
    #         # Store the initial WORKING camera setup:
    #         self.initial_camera_parent = self.camera.getParent()
    #         self.initial_camera_pos = self.camera.getPos(self.render)
    #         self.initial_camera_hpr = self.camera.getHpr(self.render)
    #         self.initial_trackball_parent = self.trackball.getParent()
    #         self.initial_trackball_pos = self.trackball.getPos(self.render)
    #         self.initial_trackball_hpr = self.trackball.getHpr(self.render)

    #     self.current_focus = "base_frame"

    def update_body_fixed_camera_task(self, task):
        """When in body-fixed mode, adjust the view parameters if needed."""
        # We don't need to constantly reposition since the camera is parented
        # Just update view parameters if they change
        return Task.cont

    # def setup_body_fixed_frame(self, body, view_distance=None):
    #     """Set up camera in a body-fixed frame."""
    #     if not view_distance:
    #         view_distance = body.radius * 10.0

    #     # The Scene Graph Hierarchy
    #     #
    #     # body._rotator
    #     # └── camera_pivot (rotated 180°)
    #     #     └── trackball (at 0, view_distance, 0)
    #     #         └── camera (we need to position this correctly)

    #     # Create a new node that will follow the body but maintain camera orientation
    #     if not hasattr(self, 'camera_pivot'):
    #         self.camera_pivot = self.render.attachNewNode("camera_pivot")

    #     # Attach the camera pivot to the body's rotator
    #     self.camera_pivot.reparentTo(body._rotator)

    #     # Crucial fix: Rotate the pivot 180 degrees so cameras look TOWARD the body
    #     self.camera_pivot.setHpr(180, 0, 0)

    #     # Position the trackball relative to the pivot
    #     self.trackball.reparentTo(self.camera_pivot)
    #     self.trackball.node().setPos(0, view_distance, 0)
    #     self.trackball.node().setOrigin(Point3(0, 0, 0))
    #     self.trackball.node().setForwardScale(1.0)
    #     self.trackball.node().setRelTo(self.camera_pivot)

    #     # Position camera at same spot
    #     self.camera.reparentTo(self.trackball)
    #     self.camera.setPos(0, -view_distance, 0)
    #     self.camera.lookAt(0, 0, 0)

    #     self.current_focus = body.name.lower()

    def setup_body_fixed_frame(self, body, view_distance=None):
        """Set up camera in a body-fixed frame."""
        if not view_distance:
            view_distance = body.radius * 10.0

        # Create a pivot that follows the body
        if not hasattr(self, 'camera_pivot'):
            self.camera_pivot = self.render.attachNewNode("camera_pivot")

        self.stop_inertia()  # Stop any existing inertia
        self.trackball.node().setMat(Mat4())  # Reset matrix to identity

        # Attach pivot to body
        self.camera_pivot.reparentTo(body._rotator)
        self.camera_pivot.setHpr(180, 0, 0)

        # Parent camera directly to pivot (skip trackball)
        self.camera.reparentTo(self.camera_pivot)
        # Position camera AWAY from body center
        self.camera.setPos(0, -view_distance, 0)
        # Make camera look at the body center
        self.camera.lookAt(0, 0, 0)

        # update trackball also:
        self.trackball.node().setPos(0, view_distance, 0)
        self.trackball.node().setOrigin(Point3(0, 0, 0))

        self.current_focus = body.name.lower()

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

        # Critical fix: Use the same position for camera as provided to trackball
        self.camera.setPos(view_pos)
        self.camera.lookAt(*focus_point)

    def recenter_on_earth(self):
        """Reset to base render frame."""
        self.setup_base_frame()

    def focus_on_earth(self):
        self.earth.setup_body_fixed_camera()

    def focus_on_moon(self):
        self.moon.setup_body_fixed_camera()

    def focus_on_mars(self):
        self.mars.setup_body_fixed_camera()

    def focus_on_venus(self):
        self.venus.setup_body_fixed_camera()

    def event_logger(self, *args, **kwargs):
        """Log all events for debugging"""
        print(f"EVENT: {args}, {kwargs}")

    def on_alt_mouse_up(self, *args):
        """Stop tracking mouse and apply inertia if moving fast enough"""
        if self.mouse_task:
            self.taskMgr.remove(self.mouse_task)
            self.mouse_task = None

        # Only start inertia if the mouse was dragged
        if self.mouse_dragged and self.angular_velocity.length() > 0.01:
            self.inertia_active = True
            self.inertia_task = self.taskMgr.add(self.apply_inertia_task, "InertiaTask")
        self.mouse_dragged = False  # Reset for next interaction

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

    def debug_tasks(self, task):
        print(f"Active tasks: {[t.getName() for t in self.taskMgr.getTasks()]}")
        print(f"Moon position: {self.moon.getPos()}")
        print(f"Mars position: {self.mars.getPos()}")
        return Task.again

    def toggle_particle_labels(self):
        self.labels_visible = not self.labels_visible
        for label in self.particle_labels:
            if self.labels_visible:
                label.show()
            else:
                label.hide()

    def draw_axis_grid(self, thickness=3.0, show_grid=False, tick_interval=1.0, tick_size=0.2):
        """
        Draw coordinate axes with hash marks at specified intervals.

        Args:
            thickness: Line thickness for the main axes
            show_grid: Whether to show the background grid
            tick_interval: Distance between hash marks on axes
            tick_size: Size of the hash marks
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

        # Store references to the labels (optional)
        self.axis_labels = [x_label_np, y_label_np, z_label_np]

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
            # self.movie_writer = imageio.get_writer(self.movie_filename, fps=self.movie_fps)
            self.movie_writer = imageio.get_writer(self.movie_filename, fps=self.movie_fps, codec='libx264', format='ffmpeg')
        else:
            print("Recording stopped.")
            if self.movie_writer:
                self.movie_writer.close()
                self.movie_writer = None

    def on_mouse_click(self):
        if self.mouseWatcherNode.hasMouse():
            mpos = self.mouseWatcherNode.getMouse()
            self.pickerRay.setFromLens(self.camNode, mpos.getX(), mpos.getY())
            self.picker.traverse(self.render)
            if self.pq.getNumEntries() > 0:
                self.pq.sortEntries()
                pickedObj = self.pq.getEntry(0).getIntoNodePath()
                pos = pickedObj.getPos(self.render)
                distance = (self.camera.getPos() - pos).length()
                self.setup_camera_view(pos, distance)

    def add_task(self, task_func, name):
        """Add a task to the task manager with a unique name."""
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

    def pause_scene_animation(self):
        if self.scene_anim_running:
            for func, name in self.task_list:
                self.taskMgr.remove(name)
            # keep the task list intact, so we can resume later
            self.scene_anim_running = False

    def resume_scene_animation(self):
        if not self.scene_anim_running:
            # Re-add all tasks (with correct function references)
            for func, name in self.task_list:
                self.add_task(func, name)
            self.scene_anim_running = True

    def toggle_scene_animation(self):
        if self.scene_anim_running:
            self.pause_scene_animation()
        else:
            self.resume_scene_animation()

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
            ground_point_local = self.earth._body.getRelativePoint(self.render, ground_point)
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

        #...fixed axis:
        # angle = task.time * self.moon_orbit_speed
        # x = self.moon_orbit_radius * math.cos(angle)
        # y = self.moon_orbit_radius * math.sin(angle)
        # z = 0
        # self.moon.setPos(x, y, z)
        # self.moon.setHpr(math.degrees(angle), 0, 0)  # Rotates X axis toward Earth

        angle = task.time * self.moon_orbit_speed
        x = self.moon_orbit_radius * math.cos(angle)
        y = self.moon_orbit_radius * math.sin(angle)
        z = 0
        self.moon.setPos(x, y, z)

        # Set orientation for tidal locking (always same face to Earth)
        # self.moon.setH(math.degrees(angle))

        # add some rotation:
        self.moon_rotation += self.moon_rotation_speed
        self.moon.setH(math.degrees(angle) + self.moon_rotation)

        # Apply axis tilt
        self.moon.setP(self.moon_axis_tilt)

        # Apply rotation around its own axis
        rotation_angle = task.time * self.moon_rotation_speed

        # Create a separate node for the moon's own rotation
        if not hasattr(self, 'moon_rotator'):
            self.moon_rotator = self.moon.attachNewNode("moon_rotator")
            # Reparent the moon's children to this node
            for child in self.moon.getChildren():
                if child.getName() != "moon_rotator":
                    child.reparentTo(self.moon_rotator)

        # Rotate the moon around its own axis
        self.moon_rotator.setR(rotation_angle)


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

        return Task.cont

    def mars_orbit_task(self, task):

        angle = task.time * self.mars_orbit_speed
        x = self.mars_orbit_radius * math.cos(angle)
        y = self.mars_orbit_radius * math.sin(angle)
        z = 0
        self.mars.setPos(x, y, z)
        self.mars.setHpr(math.degrees(angle), 0, 0)  # Rotates X axis toward Earth

        # Update mars trace
        mars_pos = self.mars.getPos(self.render)
        self.mars_trace.append(mars_pos)
        if len(self.mars_trace) > self.mars_trace_length:
            self.mars_trace.pop(0)
        # Draw the trace
        self.mars_trace_node.node().removeAllChildren()
        segs = LineSegs()
        segs.setThickness(3.0)
        for i, pt in enumerate(self.mars_trace):
            alpha = i / len(self.mars_trace)
            segs.setColor(1.0, 0.1, 0, alpha)
            if i == 0:
                segs.moveTo(pt)
            else:
                segs.drawTo(pt)
        self.mars_trace_node.attachNewNode(segs.create())
        self.mars_trace_node.setTransparency(True)

        # # Draw the moon's orbit as a translucent manifold
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
        # self.earth_to_moon_arrow = create_arrow(
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

        self.add_task(orbit_anim_task, "OrbitAnimTask")

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

    def add_stars(self, filename="models/Stars_HYGv3.txt", num_stars=100):
        """this one draws stars as spheres. this is not as efficient, but
        seems to work."""
        # Read the star data
        stars = []
        if os.path.splitext(filename)[1] == '.txt':
            delimiter = '\t'
        else:
            delimiter = ','
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            for row in reader:
                try:
                    ra = float(row['ra'])
                    dec = float(row['dec'])
                    mag = float(row['mag'])
                    ci = float(row.get('ci', 0.0))  # Color index, default to 0.0 if missing
                    name = row.get('proper', '')
                    if name.lower().strip() == 'sol':  # skip the Sun
                        continue
                    stars.append({'ra': ra, 'dec': dec, 'mag': mag, 'ci': ci, 'name': name})
                except Exception:
                    continue  # skip malformed lines

        # Sort by magnitude (lower is brighter)
        stars = sorted(stars, key=lambda s: s['mag'])
        stars = stars[:num_stars]

        # Place each star on a celestial sphere of large radius
        STAR_SPHERE_RADIUS = 100
        self.star_positions = {}
        for star in stars:
            ra = star['ra'] * 15  # convert hours to degrees
            dec = star['dec']
            mag = star['mag']
            ci = star['ci']
            # Color mapping by color index (ci)
            if ci <= 0.0:
                color = (0.6, 0.8, 1.0, 1)  # blue-white
            elif ci <= 0.3:
                color = (0.7, 0.85, 1.0, 1)  # white-blue
            elif ci <= 0.6:
                color = (1.0, 1.0, 1.0, 1)   # white
            elif ci <= 1.0:
                color = (1.0, 1.0, 0.7, 1)   # yellow-white
            elif ci <= 1.5:
                color = (1.0, 0.8, 0.6, 1)   # orange
            else:
                color = (1.0, 0.6, 0.6, 1)   # red
            # Convert to radians
            ra_rad = math.radians(ra)
            dec_rad = math.radians(dec)
            # Spherical to Cartesian
            x = STAR_SPHERE_RADIUS * math.cos(dec_rad) * math.cos(ra_rad)
            y = STAR_SPHERE_RADIUS * math.cos(dec_rad) * math.sin(ra_rad)
            z = STAR_SPHERE_RADIUS * math.sin(dec_rad)
            self.star_positions[star['name'].strip().lower()] = (x, y, z)
            # Scale star size by magnitude (smaller mag = bigger)
            size = max(0.05, 0.25 - 0.04 * (mag + 1.5))
            #color = (1, 0, 0, 1)  # white, or use color index if desired
            star_np = create_sphere(radius=size, num_lat=6, num_lon=12, color=color)
            star_np.setPos(x, y, z)
            # star_np.reparentTo(self.render)
            star_np.reparentTo(self.star_sphere_np)
            star_np.setLightOff()
            star_np.setTransparency(True)
            if mag < 100.0 and star['name']:
                text_node = TextNode('star_label')
                text_node.setText(star['name'])
                text_node.setTextColor(color)
                text_node.setAlign(TextNode.ACenter)
                text_np = star_np.attachNewNode(text_node)
                text_np.setScale(0.9)  # Adjust size as needed
                text_np.setPos(0, 0, size * 2.5)  # Offset above the star
                text_np.setBillboardAxis()  # Make label always face the camera

    def draw_constellations(self):
        for name, star_list in constellations.items():
            segs = LineSegs()
            segs.setThickness(1.0)
            segs.setColor(1, 1, 0.5, 0.3)  # Light yellow
            for i in range(len(star_list) - 1):
                s1 = star_list[i].strip().lower()
                s2 = star_list[i + 1].strip().lower()
                if s1 in self.star_positions and s2 in self.star_positions:
                    segs.moveTo(*self.star_positions[s1])
                    segs.drawTo(*self.star_positions[s2])
            constellation_np = self.star_sphere_np.attachNewNode(segs.create())
            constellation_np.setLightOff()
            constellation_np.setTransparency(True)

    def update_star_sphere(self, task):
        """so the stars will rotate when you rotate the camera"""
        self.star_sphere_np.setPos(self.camera.getPos())
        return Task.cont

    def add_stars_as_points(self, filename : str = "models/Stars_HYGv3.txt", num_stars : int = 100):
        """this one draws stars as points, but they are squares on mac since
        i can't get the shader thing to work right."""
        # --- Custom vertex format with per-point size ---
        array = GeomVertexArrayFormat()
        array.addColumn("vertex", 3, Geom.NTFloat32, Geom.CPoint)
        array.addColumn("color", 4, Geom.NTFloat32, Geom.CColor)
        array.addColumn("size", 1, Geom.NTFloat32, Geom.COther)
        format = GeomVertexFormat()
        format.addArray(array)
        format = GeomVertexFormat.registerFormat(format)
        vdata = GeomVertexData('stars', format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        color_writer = GeomVertexWriter(vdata, 'color')
        size_writer = GeomVertexWriter(vdata, 'size')

        # --- Read and sort stars ---
        stars = []
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter='\t')
            for row in reader:
                try:
                    ra = float(row['ra'])
                    dec = float(row['dec'])
                    mag = float(row['mag'])
                    ci = float(row['ci'])
                    stars.append({'ra': ra, 'dec': dec, 'mag': mag, 'ci': ci})
                except Exception:
                    continue
        stars = sorted(stars, key=lambda s: s['mag'])[:num_stars]

        # --- Write star data ---
        STAR_SPHERE_RADIUS = 1000
        for star in stars:
            ra = star['ra'] * 15
            dec = star['dec']
            mag = star['mag']
            ci = star['ci']
            size = max(4.0, 16.0 - 2.5 * (mag + 1.5)) / 4.0
            if ci <= 0.0:
                color = (0.6, 0.8, 1.0, 1)
            elif ci <= 0.3:
                color = (0.7, 0.85, 1.0, 1)
            elif ci <= 0.6:
                color = (1.0, 1.0, 1.0, 1)
            elif ci <= 1.0:
                color = (1.0, 1.0, 0.7, 1)
            elif ci <= 1.5:
                color = (1.0, 0.8, 0.6, 1)
            else:
                color = (1.0, 0.6, 0.6, 1)
            ra_rad = math.radians(ra)
            dec_rad = math.radians(dec)
            x = STAR_SPHERE_RADIUS * math.cos(dec_rad) * math.cos(ra_rad)
            y = STAR_SPHERE_RADIUS * math.cos(dec_rad) * math.sin(ra_rad)
            z = STAR_SPHERE_RADIUS * math.sin(dec_rad)
            vertex.addData3(x, y, z)
            color_writer.addData4f(*color)
            size_writer.addData1f(size)

        points = GeomPoints(Geom.UHStatic)
        for i in range(len(stars)):
            points.addVertex(i)
        points.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(points)
        node = GeomNode('star_points')
        node.addGeom(geom)

        stars_np = self.camera.attachNewNode(node)
        stars_np.setBin('background', 0)
        stars_np.setDepthWrite(False)
        stars_np.setLightOff()
        stars_np.setCompass()
        stars_np.setTransparency(True)

        # this doesn't work on the mac:
        #stars_np.setShader(Shader.load(Shader.SL_GLSL, "models/star_point.vert", "models/star_point.frag"))

    def draw_sky_grid(self, sphere_radius=100, ra_lines=24, dec_lines=12):
        """Draws a right ascension/declination grid on the celestial sphere."""
        grid = LineSegs()
        grid.setThickness(1.0)
        grid.setColor(0.4, 0.7, 1, 0.3)  # Light blue, semi-transparent

        # Declination lines (horizontal circles)
        for i in range(1, dec_lines):
            dec = -90 + 180 * i / dec_lines  # from -90 to +90
            dec_rad = math.radians(dec)
            z = sphere_radius * math.sin(dec_rad)
            r_xy = sphere_radius * math.cos(dec_rad)
            segments = 120
            for j in range(segments + 1):
                ra = 360 * j / segments
                ra_rad = math.radians(ra)
                x = r_xy * math.cos(ra_rad)
                y = r_xy * math.sin(ra_rad)
                if j == 0:
                    grid.moveTo(x, y, z)
                else:
                    grid.drawTo(x, y, z)

        # Right Ascension lines (vertical half-circles)
        for i in range(ra_lines):
            ra = 360 * i / ra_lines
            ra_rad = math.radians(ra)
            segments = 120
            for j in range(segments + 1):
                dec = -90 + 180 * j / segments
                dec_rad = math.radians(dec)
                x = sphere_radius * math.cos(dec_rad) * math.cos(ra_rad)
                y = sphere_radius * math.cos(dec_rad) * math.sin(ra_rad)
                z = sphere_radius * math.sin(dec_rad)
                if j == 0:
                    grid.moveTo(x, y, z)
                else:
                    grid.drawTo(x, y, z)

        sky_grid_np = self.star_sphere_np.attachNewNode(grid.create())
        sky_grid_np.setLightOff()
        sky_grid_np.setTransparency(True)
        sky_grid_np.setTwoSided(True)

    def add_saturn_rings(self, inner_radius=EARTH_RADIUS*1.2,
                         outer_radius=EARTH_RADIUS*3.0,
                         inclination_deg=10, num_rings=5,
                         transparency=0.6):
        """Create Saturn-like ring system around Earth"""

        # Create parent node for all rings
        ring_system = self.render.attachNewNode("ring_system")

        # Apply inclination to the entire ring system
        ring_system.setP(inclination_deg)

        # Create multiple rings with gaps
        ring_width = (outer_radius - inner_radius) / (num_rings * 2 - 1)

        for i in range(num_rings):
            # Calculate this ring's inner and outer radius
            ring_inner = inner_radius + i * ring_width * 2
            ring_outer = ring_inner + ring_width

            # Vary color slightly for each ring
            base_color = (0.8, 0.75, 0.6, transparency)  # Sandy color
            color_variation = 0.1 * (i / num_rings)
            ring_color = (
                base_color[0] - color_variation,
                base_color[1] - color_variation,
                base_color[2] - color_variation,
                base_color[3]
            )

            # Create the ring
            ring = self.create_flat_ring(
                inner_radius=ring_inner,
                outer_radius=ring_outer,
                color=ring_color,
                segments=120,
                num_subdivisions=8
            )

            ring.reparentTo(ring_system)
            ring.setTwoSided(True)
            ring.setTransparency(True)
            ring.setBin('transparent', 30)

        # Parent to Earth so it follows Earth's rotation
        ring_system.reparentTo(self.earth)
        # Also set these on the parent node to be extra sure
        ring_system.setTextureOff(1)
        ring_system.setShaderOff(1)

        return ring_system

    def create_flat_ring(self, inner_radius, outer_radius, color, segments=64, num_subdivisions=4):
        """Create a flat ring with triangles for better texture mapping"""

        format = GeomVertexFormat.getV3n3c4t2()
        vdata = GeomVertexData('ring', format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        normal = GeomVertexWriter(vdata, 'normal')
        color_writer = GeomVertexWriter(vdata, 'color')
        texcoord = GeomVertexWriter(vdata, 'texcoord')

        tris = GeomTriangles(Geom.UHStatic)

        # Create vertices for the ring
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            cos_angle = math.cos(angle)
            sin_angle = math.sin(angle)

            # Create multiple subdivisions from inner to outer radius
            for j in range(num_subdivisions + 1):
                # Calculate radius for this subdivision
                r = inner_radius + (outer_radius - inner_radius) * j / num_subdivisions

                x = r * cos_angle
                y = r * sin_angle
                z = 0  # Flat ring

                # Add vertex
                vertex.addData3(x, y, z)
                normal.addData3(0, 0, 1)  # Normal points up
                color_writer.addData4(*color)
                texcoord.addData2(i / segments, j / num_subdivisions)

        # Create triangles
        for i in range(segments):
            for j in range(num_subdivisions):
                # First triangle
                v1 = i * (num_subdivisions + 1) + j
                v2 = (i + 1) * (num_subdivisions + 1) + j
                v3 = i * (num_subdivisions + 1) + (j + 1)
                tris.addVertices(v1, v2, v3)

                # Second triangle
                v1 = (i + 1) * (num_subdivisions + 1) + j
                v2 = (i + 1) * (num_subdivisions + 1) + (j + 1)
                v3 = i * (num_subdivisions + 1) + (j + 1)
                tris.addVertices(v1, v2, v3)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode('ring')
        node.addGeom(geom)

        return NodePath(node)

    def rotate_rings_task(self, task):
        self.rings.setH(self.rings.getH() + 0.01)  # Slow rotation
        return Task.cont

###############################################

app = EarthOrbitApp()

# example reading trajectory from JSON file;
# app.orbit_from_json_np = app.add_orbit_from_json("traj.json", color=(1, 0, 1, 1), thickness=2.0)

# https://docs.panda3d.org/1.10/python/programming/render-attributes/antialiasing
app.render.setAntialias(AntialiasAttrib.MAuto)  # antialiasing


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