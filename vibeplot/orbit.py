import math
from direct.task import Task
from panda3d.core import Point3, LineSegs, NodePath, GeomNode, Geom, GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomTriangles, Vec3, TextNode, TransparencyAttrib
import json5 as json
import bisect
from scipy.interpolate import CubicSpline
import numpy as np

from .bodies import Body
from .utilities import create_sphere, draw_path
from .path import Path

class Orbit:
    def __init__(self, parent,
                 name: str,
                 central_body: Body,
                 label_text: str = None,
                 label_color=(1,1,1,1),
                 label_size=0.5,
                 radius: float = 5.0,
                 speed: float = 1.0,
                 inclination_deg: float = 0.0,
                 color=(1, 1, 0, 1),
                 thickness: float = 2.0,
                 satellite_radius: float = 0.1,
                 satellite_color = (1, 0, 0, 1),
                 visibility_cone: bool = True,
                 cone_angle_deg: float = 5.0,
                 groundtrack: bool = True,
                 groundtrack_length: int = 1000,
                 groundtrack_thickness: float = 2.0,
                 show_orbit_path: bool = True,
                 trace_mode: bool = False,
                 trace_dt: float = 2.0,
                 orbit_path_linestyle: int = 0,
                 num_segments: int = 100,
                 enable_shadow: bool = False,
                 spline_mode = "linear",
                 orbit_json: str = None,
                 time_step: float = None,
                 add_tube: bool = False):

        """
        Initialize an Orbit object representing a satellite or object orbiting a central body.

        Args:
            parent: The parent application or scene object (must provide .render and .add_task).
            name (str): Name of the orbit instance.
            central_body (Body): The central body that this orbit is around.
            radius (float, optional): Orbit radius for analytic orbits (ignored if orbit_json is provided).
            speed (float, optional): Orbital angular speed or time scaling factor.
            inclination_deg (float, optional): Inclination angle in degrees for analytic orbits.
            color (tuple, optional): RGBA color for the orbit path.
            thickness (float, optional): Thickness of the orbit path line.
            satellite_radius (float, optional): Radius of the satellite sphere.
            satellite_color (tuple, optional): RGBA color for the satellite.
            visibility_cone (bool, optional): Whether to show the visibility cone from the satellite.
            cone_angle_deg (float, optional): Half-angle of the visibility cone in degrees.
            groundtrack (bool, optional): Whether to show the groundtrack on the central body.
            groundtrack_length (int, optional): Number of points to keep in the groundtrack trace.
            show_orbit_path (bool, optional): Whether to display the orbit path.
            num_segments (int, optional): Number of segments to use for drawing the orbit path (ignored if time_step is set).
            time_step (float, optional): If set, sample the orbit path at this time interval (overrides num_segments for JSON orbits).
            enable_shadow (bool, optional): If True, enable lighting/shadow on the satellite.
            spline_mode (str, optional): Interpolation mode for JSON orbits ("linear" or "cubic").
            orbit_json (str, optional): Path to a JSON file specifying a custom orbit trajectory.

        Notes:
            - If orbit_json is provided, the orbit will follow the trajectory defined in the JSON file.
            - If not, an analytic circular orbit is used.
            - The orbit path, satellite, visibility cone, and groundtrack are all created and managed by this class.
        """

        self.parent = parent
        self.central_body = central_body  # Store the central body
        self.name = name
        self.radius = radius
        self.speed = speed
        self.inclination_deg = inclination_deg
        self.color = color
        self.thickness = thickness
        self.satellite_radius = satellite_radius
        self.satellite_color = satellite_color
        self.num_segments = num_segments
        self.time_step = time_step
        self.enable_shadow = enable_shadow
        self.label_text = label_text
        self.label_color = label_color
        self.label_size = label_size
        self.label_np = None
        self.orbit_path_linestyle = orbit_path_linestyle  # 0: solid, 1: dashed
        self.groundtrack_thickness = groundtrack_thickness
        self.show_orbit_path = show_orbit_path
        self.trace_mode = trace_mode
        self.trace_dt = trace_dt

        # Visibility cone settings
        self.visibility_cone_enabled = visibility_cone
        self.visibility_cone_angle = math.radians(cone_angle_deg)
        self.visibility_cone_segments = 24

        # Groundtrack settings
        self.groundtrack_enabled = groundtrack
        self.groundtrack_length = groundtrack_length
        self.groundtrack_trace = []

        # JSON trajectory attributes
        self.spline_mode = spline_mode
        self._splines = None
        self.orbit_json = orbit_json
        self.trajectory_points = None
        self.trajectory_times = None
        self.trajectory_colors = None
        # if orbit_json:
        #     self._load_trajectory_from_json(orbit_json)

        # Create the satellite
        self.satellite = self._create_satellite()

        if self.label_text:
            tn = TextNode(f"{self.name}_label")
            tn.setText(self.label_text)
            tn.setTextColor(*self.label_color)
            tn.setAlign(TextNode.ACenter)
            self.label_np = self.parent.render.attachNewNode(tn)
            self.label_np.setScale(self.label_size)
            self.label_np.setBillboardPointEye()
            self.label_np.setLightOff()
            self.label_np.setTransparency(True)
        else:
            self.label_np = None

        # Create orbit path
        # if show_orbit_path:
        #     self.orbit_path_np = self._create_orbit_path()
        # else:
        #     self.orbit_path_np = None

        # Create orbit path
        self.path = Path(parent = self.parent,
                         orbit_json = self.orbit_json,
                         spline_mode = self.spline_mode,
                         orbit_path_linestyle = self.orbit_path_linestyle,
                         color = self.color,
                         thickness = self.thickness,
                         num_segments = self.num_segments,
                         time_step = self.time_step,
                         inclination_deg = self.inclination_deg,
                         radius = self.radius,
                         show_orbit_path = self.show_orbit_path,
                         trace_mode = self.trace_mode,
                         trace_dt = self.trace_dt
                        )
        self.orbit_path_np = self.path.orbit_path_np   # for now do this to match old way
        self._orbit_path_pts = self.path._orbit_path_pts
        self._orbit_path_ts = self.path._orbit_path_ts

        # to pulsate the orbit line:
        # self.add_task(self.pulsate_orbit_line_task, "PulsateOrbitLineTask")

        # Setup visibility cone
        if self.visibility_cone_enabled:
            self.visibility_cone_np = self.parent.render.attachNewNode("visibility_cone")
            self.cone_outline_np = None

        # Setup groundtrack
        if self.groundtrack_enabled:
            self.groundtrack_node = self.central_body._rotator.attachNewNode("groundtrack")
            self.groundtrack_node.setShaderOff()
            self.groundtrack_node.setLightOff()
            self.groundtrack_node.setTwoSided(True)

        # Start the orbit task
        self.parent.add_task(self.orbit_task, f"{self.name}OrbitTask")

        if add_tube:
            self.orbit_tube_np = self.add_orbit_tube(tube_radius=0.1 * self.thickness)

        # add to the list of bodies in the scene:
        self.parent.orbits.append(self)

    def _create_satellite(self):
        """Create the satellite geometry"""
        satellite = create_sphere(
            radius=self.satellite_radius,
            num_lat=24,
            num_lon=48,
            color=self.satellite_color
        )
        satellite.reparentTo(self.parent.render)

        if not self.enable_shadow:
            satellite.setLightOff()  # Disable lighting for visibility
        return satellite

    # def _load_trajectory_from_json(self, filename : str | dict):

    #     if isinstance(filename, dict):
    #         # If filename is a dict, assume it's already loaded JSON data
    #         data = filename
    #     else:
    #         with open(filename, "r") as f:
    #             data = json.load(f)
    #             #...just a test...
    #             # data['t'] = [t-data['t'][0] for t in data['t']]
    #             # data['x'] = [x / 1000.0 for x in data['x']]
    #             # data['y'] = [y / 1000.0 for y in data['y']]
    #             # data['z'] = [z / 1000.0 for z in data['z']]

    #     if all(k in data for k in ("x", "y", "z", "t")):
    #         xs, ys, zs, ts = data["x"], data["y"], data["z"], data["t"]
    #         assert len(xs) == len(ys) == len(zs) == len(ts), "x, y, z, t must be same length"
    #     elif 'segs' in data:
    #         # halo format - read all the segs into one trajectory
    #         print('reading trajectory from halo format')
    #         xs = []
    #         ys = []
    #         zs = []
    #         ts = []
    #         for seg in data['segs']:
    #             # sort since some are backwards propagated:
    #             zipped_lists = zip(seg['et'], seg['x_inertial'], seg['y_inertial'], seg['z_inertial'])
    #             sorted_zipped_lists = sorted(zipped_lists) # sort based on et
    #             et, x, y, z = zip(*sorted_zipped_lists)
    #             ts.extend(et[0:-2])  # skip the last point since it's the same as the first point in the next seg
    #             xs.extend(x[0:-2])
    #             ys.extend(y[0:-2])
    #             zs.extend(z[0:-2])
    #         #.. for now, just scale the data...
    #         ts = [100.0*(t-ts[0])/ts[-1] for t in ts]  # 0 - 100
    #         xs = [x / 1000.0 for x in xs]
    #         ys = [y / 1000.0 for y in ys]
    #         zs = [z / 1000.0 for z in zs]
    #     else:
    #         raise ValueError("JSON must contain 'x', 'y', 'z', 't' or 'seg' arrays")

    #     self.trajectory_points = [Point3(x, y, z) for x, y, z in zip(xs, ys, zs)]
    #     self.trajectory_times = ts
    #     self.trajectory_options = data.get("options", {})

    #     if "colors" in data and len(data["colors"]) == len(xs):
    #         self.trajectory_colors = [tuple(c) for c in data["colors"]]
    #     else:
    #         self.trajectory_colors = None

    #     if self.spline_mode == "cubic":
    #         bc_type = 'periodic' if self.trajectory_options.get("loop", False) else 'not-a-knot'
    #         self._splines = (
    #             CubicSpline(ts, xs, bc_type=bc_type),
    #             CubicSpline(ts, ys, bc_type=bc_type),
    #             CubicSpline(ts, zs, bc_type=bc_type),
    #         )
    #     else:
    #         self._splines = None

    # def get_orbit_state(self, angle_or_time):
    #     """Return position on the orbit.
    #     - If using JSON, angle_or_time is interpreted as time and returns interpolated position.
    #     - Otherwise, returns analytic orbit position for given angle.
    #     """
    #     if self.trajectory_points and self.trajectory_times:
    #         t = angle_or_time
    #         times = self.trajectory_times
    #         points = self.trajectory_points
    #         if self._splines:
    #             # Cubic spline interpolation
    #             x = float(self._splines[0](t))
    #             y = float(self._splines[1](t))
    #             z = float(self._splines[2](t))
    #             return Point3(x, y, z)
    #         else:
    #             # Linear interpolation
    #             if t <= times[0]:
    #                 return points[0]
    #             if t >= times[-1]:
    #                 return points[-1]
    #             i = bisect.bisect_right(times, t) - 1
    #             t0, t1 = times[i], times[i+1]
    #             p0, p1 = points[i], points[i+1]
    #             alpha = (t - t0) / (t1 - t0)
    #             return p0 * (1 - alpha) + p1 * alpha
    #     else:
    #         # Analytic orbit
    #         x = self.radius * math.cos(angle_or_time)
    #         y = self.radius * math.sin(angle_or_time)
    #         z = 0
    #         y_incl = y * math.cos(self.inclination) - z * math.sin(self.inclination)
    #         z_incl = y * math.sin(self.inclination) + z * math.cos(self.inclination)
    #         return Point3(x, y_incl, z_incl)

    # def _create_orbit_path(self):
    #     """Create the orbital path visualization, using time_step if set, otherwise num_segments for interpolation modes."""

    #     orbit_segs = LineSegs()
    #     orbit_segs.setThickness(self.thickness)
    #     orbit_segs.setColor(*self.color)

    #     if self.trajectory_points and self.trajectory_times:
    #         t_min, t_max = self.trajectory_times[0], self.trajectory_times[-1]
    #         if self.time_step is not None:
    #             ts = np.arange(t_min, t_max + self.time_step, self.time_step)
    #         elif self.spline_mode in ("cubic", "linear") and (self._splines or self.spline_mode == "linear"):
    #             ts = np.linspace(t_min, t_max, self.num_segments + 1)
    #         else:
    #             print('use times as is')
    #             ts = self.trajectory_times
    #     else:
    #         # Analytic orbit
    #         if self.time_step is not None:
    #             angle_max = 2 * math.pi
    #             ts = np.arange(0, angle_max + self.time_step, self.time_step)
    #         else:
    #             ts = [2 * math.pi * i / self.num_segments for i in range(self.num_segments + 1)]

    #     pts = [self.get_orbit_state(t) for t in ts]   #self.sample_orbit_path(ts)
    #     self._orbit_path_ts = ts
    #     self._orbit_path_pts = pts

    #     # --- Prepare per-point colors, resampled if needed ---
    #     if self.trajectory_colors and self.trajectory_times:
    #         # Interpolate colors at the new ts
    #         orig_times = np.array(self.trajectory_times)
    #         orig_colors = np.array(self.trajectory_colors)  # shape: (N, 4)
    #         ts_arr = np.array(ts)

    #         # Interpolate each channel separately
    #         resampled_colors = []
    #         for k in range(4):  # RGBA channels
    #             channel = orig_colors[:, k]
    #             interp = np.interp(ts_arr, orig_times, channel)
    #             resampled_colors.append(interp)
    #         # Stack back into (len(ts), 4)
    #         colors = np.stack(resampled_colors, axis=1)
    #         colors = [tuple(c) for c in colors]
    #     else:
    #         colors = [self.color] * len(pts)

    #     orbit_np = draw_path(self.parent.render, pts, linestyle=self.orbit_path_linestyle, colors=colors)
    #     orbit_np.setRenderModeThickness(self.thickness)
    #     orbit_np.setLightOff()
    #     orbit_np.setTextureOff()
    #     orbit_np.setShaderOff()
    #     orbit_np.clearColor()
    #     orbit_np.setTransparency(True)
    #     return orbit_np

    def show_hide_label(self, show: bool):
        """Show or hide the orbits's label.

        Args:
            show (bool): If True, show the label; if False, hide it.
        """
        if hasattr(self, 'label_np') and self.label_np:
            if show:
                self.label_np.show()
            else:
                self.label_np.hide()

    def _create_visibility_cone(self, sat_pos):
        """Create visibility cone geometry"""

        # Clear previous cone
        self.visibility_cone_np.node().removeAllChildren()

        # Get central body center and radius
        central_body_center = self.central_body._body.getPos(self.parent.render)
        central_body_radius = self.central_body.radius
        v = sat_pos - central_body_center
        v_len = v.length()
        if v_len != 0:
            surface_point = central_body_center + v * (central_body_radius / v_len)
        else:
            surface_point = central_body_center

        # Calculate cone geometry
        cone_height = (sat_pos - surface_point).length()
        base_radius = cone_height * math.tan(self.visibility_cone_angle)

        # Find orthonormal basis for the cone base
        axis = (surface_point - sat_pos).normalized()
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
            dir_vec = (right * math.cos(theta) + up * math.sin(theta)) * base_radius
            pt = surface_point + dir_vec
            base_points.append(pt)
            vertex.addData3(pt)
            color.addData4(1, 1, 0, 0.15)  # more transparent

        # Create triangles
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(self.visibility_cone_segments):
            tris.addVertices(0, i + 1, i + 2)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode('cone')
        node.addGeom(geom)
        cone_np = self.visibility_cone_np.attachNewNode(node)
        cone_np.setTransparency(True)
        cone_np.setLightOff()

        return base_points

    def _create_cone_outline(self, base_points):
        """Create the outline of the visibility cone"""
        if hasattr(self, "cone_outline_np") and self.cone_outline_np:
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

        self.cone_outline_np = self.parent.render.attachNewNode(outline.create())
        self.cone_outline_np.setTransparency(True)
        self.cone_outline_np.setLightOff()

    def _update_groundtrack(self, sat_pos):
        """Update the groundtrack on central body's surface"""
        if not self.groundtrack_enabled:
            return

        # Get central body center and project satellite position onto its surface
        central_body_center = self.central_body._body.getPos(self.parent.render)
        sat_vec = sat_pos - central_body_center

        if sat_vec.length() != 0:
            ground_point = central_body_center + sat_vec.normalized() * (self.central_body.radius + 0.001)
            # Convert to central body's local coordinates
            ground_point_local = self.central_body._body.getRelativePoint(self.parent.render, ground_point)
            self.groundtrack_trace.append(ground_point_local)

            # Limit trace length
            if len(self.groundtrack_trace) > self.groundtrack_length:
                self.groundtrack_trace.pop(0)

            # Draw the groundtrack
            self.groundtrack_node.node().removeAllChildren()
            segs = LineSegs()
            segs.setThickness(self.groundtrack_thickness)
            segs.setColor(self.color)

            for i, pt in enumerate(self.groundtrack_trace):
                alpha = i / self.groundtrack_length  # Fades from 0 to 1
                color = (self.color[0], self.color[1], self.color[2], alpha)
                segs.setColor(color)
                if i == 0:
                    segs.moveTo(pt)
                else:
                    segs.drawTo(pt)

            self.groundtrack_node.attachNewNode(segs.create())
            self.groundtrack_node.setTransparency(True)
            self.groundtrack_node.setLightOff()

    def add_orbit_tube(self, tube_radius=0.2, num_sides=12, color=(1, 1, 1, 0.2)):
        """
        Draw a tube along the given path_points.
        """
        path_points = self._orbit_path_pts
        num_segments = len(path_points) - 1
        format = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData('tube', format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        normal = GeomVertexWriter(vdata, 'normal')
        color_writer = GeomVertexWriter(vdata, 'color')

        verts = []
        for i,center in enumerate(path_points):
            # Tangent vector (direction of orbit)
            if i < len(path_points) - 1:
                tangent = (path_points[i+1] - center).normalized()
            else:
                tangent = (center - path_points[i-1]).normalized()
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
                color_writer.addData4(*color)
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
        tube_np = self.parent.render.attachNewNode(node)

        tube_np.setTransparency(True)
        # tube_np.setTwoSided(True)
        # tube_np.setBin('opaque', 20)
        tube_np.setLightOff()
        tube_np.setShaderOff()

        tube_np.setTransparency(TransparencyAttrib.M_alpha)

        return tube_np

    def orbit_task(self, et):
        """Main orbit animation task (satellite moves smoothly along the path)."""

        # if self.parent.paused:
        #     return Task.cont

        # et = self.parent.get_et(task)

        if self.path:
            self.path.update_trace(et)

        ts = self._orbit_path_ts
        pts = self._orbit_path_pts
        n = len(ts)
        if n < 2:
            return Task.cont

        # Compute parameter t for current time
        t_min, t_max = ts[0], ts[-1]
        total_time = t_max - t_min
        t = (et * self.speed) % total_time + t_min if getattr(self, "trajectory_options", {}).get("loop", True) else min(et * self.speed + t_min, t_max)

        #TODO: shouldn't this be in Path? ...

        # Find the segment
        for i in range(n - 1):
            if ts[i] <= t <= ts[i + 1]:
                alpha = (t - ts[i]) / (ts[i + 1] - ts[i])
                pos = pts[i] * (1 - alpha) + pts[i + 1] * alpha
                break
        else:
            # If t is exactly at the end, use the last point
            pos = pts[-1]

        # TODO: i think this should be the origin of the base frame?
        # don't assuming there's a body at the center?

        sat_pos_base_frame = self.central_body._body.getPos(self.parent.render) + pos
        self.satellite.setPos(sat_pos_base_frame)

        # Update visibility cone
        if self.visibility_cone_enabled:
            base_points = self._create_visibility_cone(sat_pos_base_frame)
            self._create_cone_outline(base_points)

        # Update groundtrack
        self._update_groundtrack(sat_pos_base_frame)

        # note: need to move the label resizing into a separate task
        # so it will still work when zooming when the scene is paused.
        if self.label_np:
            # Offset label above the satellite
            label_pos = sat_pos_base_frame + Point3(0, 0, self.satellite_radius * 2)
            self.label_np.setPos(label_pos)

            # Keep label a constant size on screen
            cam = self.parent.cam if hasattr(self.parent, "cam") else None
            if cam:
                cam_pos = cam.getPos(self.parent.render)
                dist = (label_pos - cam_pos).length()
                # Adjust 0.5 to your preferred on-screen size
                desired_screen_size = self.label_size
                scale = desired_screen_size * dist / 30.0  # 30.0 is a tuning constant
                self.label_np.setScale(scale)

        return Task.cont

    def set_speed(self, speed):
        """Change the orbital speed"""
        self.speed = speed

    # def set_color(self, color):
    #     """Change the orbit path color"""
    #     self.color = color
    #     if self.orbit_path_np:
    #         # Recreate the orbit path with new color
    #         self.orbit_path_np.removeNode()
    #         self.orbit_path_np = self._create_orbit_path()

    # def show_orbit_path(self, show=True):
    #     """Show or hide the orbit path"""
    #     if self.orbit_path_np:
    #         if show:
    #             self.orbit_path_np.show()
    #         else:
    #             self.orbit_path_np.hide()

    def destroy(self):
        """Clean up the orbit"""

        # Remove the tasks
        self.parent.remove_task(f"{self.name}OrbitTask")
        self.parent.remove_task(f"{self.name}PulsateOrbitLineTask")

        # Remove nodes
        if self.satellite:
            self.satellite.removeNode()
        if self.orbit_path_np:
            self.orbit_path_np.removeNode()
        if hasattr(self, 'visibility_cone_np'):
            self.visibility_cone_np.removeNode()
        if hasattr(self, 'cone_outline_np') and self.cone_outline_np:
            self.cone_outline_np.removeNode()
        if hasattr(self, 'groundtrack_node'):
            self.groundtrack_node.removeNode()
        if self.label_np:
            self.label_np.removeNode()
        if hasattr(self, 'orbit_tube_np') and self.orbit_tube_np:
            self.orbit_tube_np.removeNode()

        # remove from parent orbits list:
        if hasattr(self.parent, 'orbits') and self in self.parent.orbits:
            self.parent.orbits.remove(self)


    # def pulsate_orbit_line_task(self, task):
    #     # Pulsate between 2.0 and 8.0 thickness, and brightness 0.5 to 1.0
    #     t = task.time
    #     thickness = 2.0 + 6.0 * (0.5 + 0.5 * math.sin(t * 2.0))  # Pulsate every ~3 seconds
    #     brightness = 1.0 #0.5 + 0.5 * math.sin(t * 2.0)
    #     color = (brightness, brightness, 0, 1)

    #     # Re-create the orbit line with new thickness/color
    #     self.orbit_segs = LineSegs()
    #     self.orbit_segs.setThickness(thickness)
    #     self.orbit_segs.setColor(*color)

    #     num_segments = 100
    #     inclination = math.radians(45)
    #     for i in range(num_segments + 1):
    #         angle = 2 * math.pi * i / num_segments
    #         x = self.orbit_radius * math.cos(angle)
    #         y = self.orbit_radius * math.sin(angle)
    #         z = 0
    #         y_incl = y * math.cos(inclination) - z * math.sin(inclination)
    #         z_incl = y * math.sin(inclination) + z * math.cos(inclination)
    #         if i == 0:
    #             self.orbit_segs.moveTo(x, y_incl, z_incl)
    #         else:
    #             self.orbit_segs.drawTo(x, y_incl, z_incl)

    #     self.orbit_np.removeNode()
    #     self.orbit_np = NodePath(self.orbit_segs.create())
    #     self.orbit_np.reparentTo(self.render)
    #     return Task.cont
