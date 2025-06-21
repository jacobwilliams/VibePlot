
import math
from direct.task import Task
from panda3d.core import (Point3, LineSegs, NodePath, GeomNode, Geom, GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomTriangles, Vec3, TextNode, TransparencyAttrib)
import json5 as json
import bisect
from scipy.interpolate import CubicSpline
import numpy as np

from .utilities import create_sphere, draw_path, simple_propagator, create_arrow_with_endpoints


class Path():
    """The path of an Orbit or Body."""

    def __init__(self,
                 parent,
                 spline_mode = "linear",
                 orbit_json: str | dict = None,
                 orbit_path_linestyle: int = 0,
                 color = (1, 1, 0, 1),
                 thickness: float = 2.0,
                 num_segments: int = 100,
                 time_step: float = None,
                 radius: float = None,
                 inclination_deg: float = 0.0,
                 speed: float = 1.0,
                 show_orbit_path: bool = True,  # test
                 trace_mode=False, # test
                 trace_dt=2.0,    # test
                 ):
        """
        Initialize the Path object by loading trajectory data from a JSON file or dictionary.

        :param filename: Path to the JSON file or a dictionary containing trajectory data.
        """

        self.parent = parent
        self.num_segments = num_segments
        self.time_step = time_step
        self.inclination_deg = inclination_deg
        self.speed = speed
        self.radius = radius
        self.thickness = thickness
        self.color = color
        self.orbit_path_linestyle = orbit_path_linestyle  # 0: solid, 1: dashed
        self.spline_mode = spline_mode
        self.orbit_json = orbit_json
        self.show_orbit_path = show_orbit_path
        self.trace_mode = trace_mode
        self.trace_dt = trace_dt
        self.trace_np = None  # NodePath for the trace

        # Initialize trajectory data
        self.trajectory_points = None
        self.trajectory_times = None
        self.trajectory_colors = None
        self.trajectory_options = {}
        self._splines = None
        self.dv_vectors = None
        self.dv0 = None
        self.dvf = None
        self.dv_arrows = []

        if orbit_json:
            self._load_trajectory_from_json(orbit_json)

        # Create the path
        self.orbit_path_np = self._create_orbit_path()

    def update_trace(self, current_time: float):
        """Update the trace segment for the current time."""
        if not self.trace_mode or self.trajectory_points is None or self.trajectory_times is None:
            return

        t0 = max(self.trajectory_times[0], current_time - self.trace_dt)
        t1 = min(self.trajectory_times[-1], current_time)
        # Sample points between t0 and t1
        num_trace_pts = 50
        ts = np.linspace(t0, t1, num_trace_pts)
        pts = [self.get_orbit_state(t) for t in ts]

        # Alpha fades from 0 (oldest) to 1 (newest)
        colors = [(self.color[0], self.color[1], self.color[2], float(i) / (num_trace_pts - 1)) for i in range(num_trace_pts)]

        # Remove previous trace
        if self.trace_np:
            self.trace_np.removeNode()
        self.trace_np = draw_path(self.parent.render, pts, linestyle=0, colors=colors)
        self.trace_np.setRenderModeThickness(self.thickness)
        self.trace_np.setLightOff()
        self.trace_np.setTransparency(True)

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
        elif 'segs' in data:
            # halo format - read all the segs into one trajectory
            print('reading trajectory from halo format')
            xs = []
            ys = []
            zs = []
            ts = []
            for seg in data['segs']:
                # sort since some are backwards propagated:
                zipped_lists = zip(seg['et'], seg['x_inertial'], seg['y_inertial'], seg['z_inertial'])
                sorted_zipped_lists = sorted(zipped_lists) # sort based on et
                et, x, y, z = zip(*sorted_zipped_lists)
                ts.extend(et[0:-2])  # skip the last point since it's the same as the first point in the next seg
                xs.extend(x[0:-2])
                ys.extend(y[0:-2])
                zs.extend(z[0:-2])
            #.. for now, just scale the data...
            ts = [100.0*(t-ts[0])/ts[-1] for t in ts]  # 0 - 100  --> TODO fix this
            xs = [x / 1000.0 for x in xs]
            ys = [y / 1000.0 for y in ys]
            zs = [z / 1000.0 for z in zs]
        else:
            raise ValueError("JSON must contain 'x', 'y', 'z', 't' or 'seg' arrays")

        self.trajectory_points = [Point3(x, y, z) for x, y, z in zip(xs, ys, zs)]
        self.trajectory_times = ts
        self.trajectory_options = data.get("options", {})

        # --- Delta-v vectors support ---
        if all(k in data for k in ("dvx", "dvy", "dvz")):
            dvx, dvy, dvz = data["dvx"], data["dvy"], data["dvz"]
            assert len(dvx) == len(xs), "dvx must be same length as x"
            assert len(dvy) == len(xs), "dvy must be same length as x"
            assert len(dvz) == len(xs), "dvz must be same length as x"
            self.dv_vectors = [Vec3(dx, dy, dz) for dx, dy, dz in zip(dvx, dvy, dvz)]
            self._plot_dv_vectors()
        if 'dv0' in data:
            dv0 = data['dv0']
            if isinstance(dv0, (list, tuple)) and len(dv0) == 3:
                self.dv0 = Vec3(*dv0)
                self._add_arrow(self.trajectory_points[0], self.dv0, scale=1.0, color=(0,1,0,1), thickness = 0.05)
            else:
                raise ValueError("dv0 must be a list or tuple of 3 values")
        if 'dvf' in data:
            dvf = data['dvf']
            if isinstance(dvf, (list, tuple)) and len(dvf) == 3:
                self.dvf = Vec3(*dvf)
                self._add_arrow(self.trajectory_points[0], self.dvf, scale=1.0, color=(1,0,0,1), thickness = 0.05)
            else:
                raise ValueError("dvf must be a list or tuple of 3 values")

        if "colors" in data and len(data["colors"]) == len(xs):
            self.trajectory_colors = [tuple(c) for c in data["colors"]]
        else:
            self.trajectory_colors = None

        if self.spline_mode == "cubic":
            bc_type = 'periodic' if self.trajectory_options.get("loop", False) else 'not-a-knot'
            self._splines = (
                CubicSpline(ts, xs, bc_type=bc_type),
                CubicSpline(ts, ys, bc_type=bc_type),
                CubicSpline(ts, zs, bc_type=bc_type),
            )
        else:
            self._splines = None

    def _add_arrow(self, p, vec, scale, color, thickness):
        """add an arrow to a point on the trajectory"""
        if scale==0.0 or p.length()==0.0:
            return
        arrow = create_arrow_with_endpoints(
            start=p,
            end=p + vec * scale,
            color=color,
            thickness=thickness,
            head_size=thickness * 2
        )
        arrow.reparentTo(self.parent.render)
        arrow.setLightOff()
        arrow.setTransparency(True)
        self.dv_arrows.append(arrow)

    def _plot_dv_vectors(self,
                         scale: float = 1.0,
                         color: tuple = (1,0,0,1),
                         thickness: float = 0.05):
        """Plot delta-v vectors as arrows at each trajectory point."""

        if not self.dv_vectors or not self.trajectory_points:
            return
        for p, dv in zip(self.trajectory_points, self.dv_vectors):
            if dv.length() == 0:
                continue
            self._add_arrow(p, dv, scale, color, thickness)

    def get_orbit_state(self, et: float):
        """Return position on the orbit.
        - If using JSON, angle_or_time is interpreted as time and returns interpolated position.
        - Otherwise, returns analytic orbit position for given angle.
        """
        if self.trajectory_points and self.trajectory_times:
            t = et
            times = self.trajectory_times
            points = self.trajectory_points
            if self._splines:
                # Cubic spline interpolation
                x = float(self._splines[0](t))
                y = float(self._splines[1](t))
                z = float(self._splines[2](t))
                return Point3(x, y, z)
            else:
                # Linear interpolation    --> TODO: need to cache the last t to avoid bisecting every time
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

            #TODO need to consolidate this with _get_position_vector
            # and move it out of here.
            r = simple_propagator(self.radius, self.inclination_deg, et, self.speed)
            return Point3(r[0], r[1], r[2])

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
                print('use times as is')
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

        # --- Prepare per-point colors, resampled if needed ---
        if self.trajectory_colors and self.trajectory_times:
            # Interpolate colors at the new ts
            orig_times = np.array(self.trajectory_times)
            orig_colors = np.array(self.trajectory_colors)  # shape: (N, 4)
            ts_arr = np.array(ts)

            # Interpolate each channel separately
            resampled_colors = []
            for k in range(4):  # RGBA channels
                channel = orig_colors[:, k]
                interp = np.interp(ts_arr, orig_times, channel)
                resampled_colors.append(interp)
            # Stack back into (len(ts), 4)
            colors = np.stack(resampled_colors, axis=1)
            colors = [tuple(c) for c in colors]
        else:
            colors = [self.color] * len(pts)

        orbit_np = draw_path(self.parent.render, pts, linestyle=self.orbit_path_linestyle, colors=colors)
        orbit_np.setRenderModeThickness(self.thickness)
        orbit_np.setLightOff()
        orbit_np.setTextureOff()
        orbit_np.setShaderOff()
        orbit_np.clearColor()
        orbit_np.setTransparency(True)
        if not self.show_orbit_path:
            orbit_np.hide()
        return orbit_np

    def destroy(self):
        """Clean up all NodePaths and references created by this Path."""

        # Remove the main orbit path
        if hasattr(self, 'orbit_path_np') and self.orbit_path_np:
            self.orbit_path_np.removeNode()
        # Remove the trace, if present
        if hasattr(self, 'trace_np') and self.trace_np:
            self.trace_np.removeNode()
        # Remove delta-v arrows, if present
        if hasattr(self, 'dv_arrows') and self.dv_arrows:
            for arrow in self.dv_arrows:
                if arrow:
                    arrow.removeNode()

        self.trace_np = None
        self.orbit_path_np = None
        self.trajectory_points = None
        self.trajectory_times = None
        self.trajectory_colors = None
        self.dv_vectors = None
        self.dv0 = None
        self.dvf = None
        self.dv_arrows = []
        self._splines = None