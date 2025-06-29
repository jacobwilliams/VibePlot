import math
from panda3d.core import LineSegs, NodePath

from .utilities import lonlat_to_xyz

class GeodesicPath:
    def __init__(
        self,
        parent_np: NodePath,
        body_radius: float,
        points: list,
        closed: bool = False,
        color: tuple = (1, 1, 0, 1),
        thickness: float = 2.0,
        altitude_pad: float = 0.01,
        name: str = "geodesic_path",
        lon_rotation: float = 0.0,
    ):
        """
        Draws a geodesic path (open or closed) connecting given points on a sphere.

        Args:
            parent_np (NodePath): Node to attach the path to (e.g., the body's _body or _rotator).
            body_radius (float): Radius of the spherical body.
            points (list): List of (altitude, lat, lon) tuples in degrees (altitude in same units as radius).
            closed (bool, optional): If True, connects last point to first. Defaults to False.
            color (tuple, optional): RGBA color for the path. Defaults to yellow.
            thickness (float, optional): Line thickness. Defaults to 2.0.
            altitude_pad (float, optional): Extra altitude above the surface. Defaults to 0.01.
            name (str, optional): Name for the NodePath. Defaults to "geodesic_path".
        """
        self.parent_np = parent_np
        self.body_radius = body_radius
        self.points = points
        self.closed = closed
        self.color = color
        self.thickness = thickness
        self.altitude_pad = altitude_pad
        self.name = name
        self.lon_rotation = lon_rotation

        self.node = self._draw_path()

    def _draw_path(self) -> NodePath:
        segs = LineSegs()
        segs.setThickness(self.thickness)
        segs.setColor(*self.color)

        n = len(self.points)
        if n < 2:
            return None

        # Convert all points to xyz
        xyz_points = []
        for alt, lat, lon in self.points:
            x, y, z = lonlat_to_xyz(lon + self.lon_rotation, lat, self.body_radius + alt + self.altitude_pad)
            xyz_points.append((x, y, z))

        # Draw geodesic segments between points
        for i in range(n if self.closed else n - 1):
            p1 = xyz_points[i]
            p2 = xyz_points[(i + 1) % n]
            self._draw_geodesic_segment(segs, p1, p2)

        np = self.parent_np.attachNewNode(segs.create())
        np.setTransparency(True)
        np.setLightOff()
        np.setBin('transparent', 15)
        np.setName(self.name)
        np.setTextureOff()
        np.setShaderOff()
        return np

    def _draw_geodesic_segment(self, segs: LineSegs, p1, p2, num_subdiv: int = 64):
        """
        Draws a geodesic (great circle) segment between two 3D points on the sphere.
        """
        # Normalize to sphere
        r1 = math.sqrt(p1[0]**2 + p1[1]**2 + p1[2]**2)
        r2 = math.sqrt(p2[0]**2 + p2[1]**2 + p2[2]**2)
        v1 = [c / r1 for c in p1]
        v2 = [c / r2 for c in p2]

        # Angle between points
        dot = sum(a*b for a, b in zip(v1, v2))
        dot = max(-1.0, min(1.0, dot))
        angle = math.acos(dot)

        # Interpolate along the great circle
        for i in range(num_subdiv + 1):
            t = i / num_subdiv
            if angle == 0:
                interp = v1
            else:
                sin_a = math.sin(angle)
                w1 = math.sin((1 - t) * angle) / sin_a
                w2 = math.sin(t * angle) / sin_a
                interp = [w1 * v1[j] + w2 * v2[j] for j in range(3)]
            # Scale to average radius
            avg_r = (r1 + r2) / 2
            pt = [c * avg_r for c in interp]
            if i == 0:
                segs.moveTo(*pt)
            else:
                segs.drawTo(*pt)

    def remove(self):
        """Removes the geodesic path from the scene."""
        if self.node:
            self.node.removeNode()
            self.node = None