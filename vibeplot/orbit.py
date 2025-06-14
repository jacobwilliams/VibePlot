import math
from direct.task import Task
from panda3d.core import Point3, LineSegs, NodePath, GeomNode, Geom, GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomTriangles, Vec3, TextNode
import json5 as json
import bisect
from scipy.interpolate import CubicSpline
import numpy as np

from .bodies import Body
from .utilities import create_sphere, draw_path

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
                 show_orbit_path: bool = True,
                 orbit_path_linestyle: int = 0,
                 num_segments: int = 100,
                 enable_shadow: bool = False,
                 spline_mode = "linear",
                 orbit_json: str = None,
                 time_step: float = None):
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
        self.inclination = math.radians(inclination_deg)
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
        if orbit_json:
            self._load_trajectory_from_json(orbit_json)

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
        if show_orbit_path:
            self.orbit_path_np = self._create_orbit_path()
        else:
            self.orbit_path_np = None

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

    def _load_trajectory_from_json(self, filename : str | dict):

        if isinstance(filename, dict):
            # If filename is a dict, assume it's already loaded JSON data
            data = filename
        else:
            with open(filename, "r") as f:
                data = json.load(f)

        if all(k in data for k in ("x", "y", "z", "t")):
            xs, ys, zs, ts = data["x"], data["y"], data["z"], data["t"]
            assert len(xs) == len(ys) == len(zs) == len(ts), "x, y, z, t must be same length"
            self.trajectory_points = [Point3(x, y, z) for x, y, z in zip(xs, ys, zs)]
            self.trajectory_times = ts
            self.trajectory_options = data.get("options", {})
            if self.spline_mode == "cubic":
                bc_type = 'periodic' if self.trajectory_options.get("loop", False) else 'not-a-knot'
                self._splines = (
                    CubicSpline(ts, xs, bc_type=bc_type),
                    CubicSpline(ts, ys, bc_type=bc_type),
                    CubicSpline(ts, zs, bc_type=bc_type),
                )
            else:
                self._splines = None
        else:
            raise ValueError("JSON must contain 'x', 'y', 'z', 't' arrays")

    def get_orbit_state(self, angle_or_time):
        """Return position on the orbit.
        - If using JSON, angle_or_time is interpreted as time and returns interpolated position.
        - Otherwise, returns analytic orbit position for given angle.
        """
        if self.trajectory_points and self.trajectory_times:
            t = angle_or_time
            times = self.trajectory_times
            points = self.trajectory_points
            if self._splines:
                # Cubic spline interpolation
                x = float(self._splines[0](t))
                y = float(self._splines[1](t))
                z = float(self._splines[2](t))
                return Point3(x, y, z)
            else:
                # Linear interpolation
                if t <= times[0]:
                    return points[0]
                if t >= times[-1]:
                    return points[-1]
                i = bisect.bisect_right(times, t) - 1
                t0, t1 = times[i], times[i+1]
                p0, p1 = points[i], points[i+1]
                alpha = (t - t0) / (t1 - t0)
                return p0 * (1 - alpha) + p1 * alpha
        else:
            # Analytic orbit
            x = self.radius * math.cos(angle_or_time)
            y = self.radius * math.sin(angle_or_time)
            z = 0
            y_incl = y * math.cos(self.inclination) - z * math.sin(self.inclination)
            z_incl = y * math.sin(self.inclination) + z * math.cos(self.inclination)
            return Point3(x, y_incl, z_incl)

    def _create_orbit_path(self):
        """Create the orbital path visualization, using time_step if set, otherwise num_segments for interpolation modes."""

        orbit_segs = LineSegs()
        orbit_segs.setThickness(self.thickness)
        orbit_segs.setColor(*self.color)

        if self.trajectory_points and self.trajectory_times:
            t_min, t_max = self.trajectory_times[0], self.trajectory_times[-1]
            if self.time_step is not None:
                ts = np.arange(t_min, t_max + self.time_step, self.time_step)
            elif self.spline_mode in ("cubic", "linear") and (self._splines or self.spline_mode == "linear"):
                ts = np.linspace(t_min, t_max, self.num_segments + 1)
            else:
                ts = self.trajectory_times
        else:
            # Analytic orbit
            if self.time_step is not None:
                angle_max = 2 * math.pi
                ts = np.arange(0, angle_max + self.time_step, self.time_step)
            else:
                ts = [2 * math.pi * i / self.num_segments for i in range(self.num_segments + 1)]

        pts = [self.get_orbit_state(t) for t in ts]   #self.sample_orbit_path(ts)
        self._orbit_path_ts = ts
        self._orbit_path_pts = pts
        draw_path(orbit_segs, pts, linestyle = self.orbit_path_linestyle)

        orbit_np = NodePath(orbit_segs.create())
        orbit_np.reparentTo(self.parent.render)
        orbit_np.setLightOff()
        orbit_np.setTextureOff()
        orbit_np.setShaderOff()
        orbit_np.clearColor()
        orbit_np.setColor(self.color, 1)
        orbit_np.setTransparency(True)
        self._orbit_path_offset = (self.central_body._body, orbit_np)
        return orbit_np

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
            segs.setThickness(2.0)
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

    def orbit_task(self, task):
        """Main orbit animation task (satellite moves smoothly along the path)."""
        if self.parent.paused:
            return Task.cont

        ts = self._orbit_path_ts
        pts = self._orbit_path_pts
        n = len(ts)
        if n < 2:
            return Task.cont

        # Compute parameter t for current time
        t_min, t_max = ts[0], ts[-1]
        total_time = t_max - t_min
        et = self.parent.get_et(task)
        t = (et * self.speed) % total_time + t_min if getattr(self, "trajectory_options", {}).get("loop", True) else min(et * self.speed + t_min, t_max)

        # Find the segment
        for i in range(n - 1):
            if ts[i] <= t <= ts[i + 1]:
                alpha = (t - ts[i]) / (ts[i + 1] - ts[i])
                pos = pts[i] * (1 - alpha) + pts[i + 1] * alpha
                break
        else:
            # If t is exactly at the end, use the last point
            pos = pts[-1]

        sat_pos_base_frame = self.central_body._body.getPos(self.parent.render) + pos
        self.satellite.setPos(sat_pos_base_frame)

        # Update visibility cone
        if self.visibility_cone_enabled:
            base_points = self._create_visibility_cone(sat_pos_base_frame)
            self._create_cone_outline(base_points)

        # Update groundtrack
        self._update_groundtrack(sat_pos_base_frame)

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

    def set_color(self, color):
        """Change the orbit path color"""
        self.color = color
        if self.orbit_path_np:
            # Recreate the orbit path with new color
            self.orbit_path_np.removeNode()
            self.orbit_path_np = self._create_orbit_path()

    def show_orbit_path(self, show=True):
        """Show or hide the orbit path"""
        if self.orbit_path_np:
            if show:
                self.orbit_path_np.show()
            else:
                self.orbit_path_np.hide()

    def destroy(self):
        """Clean up the orbit"""
        # Remove the task
        self.parent.taskMgr.remove(f"{self.name}OrbitTask")

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

    def add_orbit_from_json(self, filename, color=(1, 0, 1, 1), thickness=2.0):
        """Load orbit points from a JSON file and draw the orbit."""
        with open(filename, "r") as f:
            data = json.load(f)
        options = data.get("options", {})
        traj = data["trajectory"]
        points = [Point3(p["x"], p["y"], p["z"]) for p in traj]
        times = [p.get("t", i) for i, p in enumerate(traj)]

        # Draw the orbit
        segs = LineSegs()
        segs.setThickness(thickness)
        segs.setColor(*color)
        for i, pt in enumerate(points):
            if i == 0:
                segs.moveTo(pt)
            else:
                segs.drawTo(pt)
        orbit_np = self.parent.render.attachNewNode(segs.create())
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
            et = self.parent.get_et(task)
            t = (et * speed) % (t_max - t_min) + t_min if loop else min(et * speed + t_min, t_max)
            # Find the segment
            for i in range(len(times) - 1):
                if times[i] <= t <= times[i+1]:
                    # Linear interpolation
                    alpha = (t - times[i]) / (times[i+1] - times[i])
                    pos = points[i] * (1 - alpha) + points[i+1] * alpha
                    self.orbit_satellite.setPos(pos)
                    break
            return task.cont if (loop or t < t_max) else task.done

        self.parent.add_task(orbit_anim_task, "OrbitAnimTask")
