import math
from panda3d.core import LineSegs, NodePath, GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomTriangles, Geom, GeomNode, TransparencyAttrib

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
        fill: bool = False,
        fill_color: tuple = (1, 1, 0, 0.4),
    ):
        """
        Draws a geodesic path (open or closed) connecting given points on a sphere.
        Optionally fills the closed path with a translucent color.

        Args:
            parent_np (NodePath): Node to attach the path to (e.g., the body's _body or _rotator).
            body_radius (float): Radius of the spherical body.
            points (list): List of (altitude, lat, lon) tuples in degrees (altitude in same units as radius).
            closed (bool, optional): If True, connects last point to first. Defaults to False.
            color (tuple, optional): RGBA color for the path. Defaults to yellow.
            thickness (float, optional): Line thickness. Defaults to 2.0.
            altitude_pad (float, optional): Extra altitude above the surface. Defaults to 0.01.
            name (str, optional): Name for the NodePath. Defaults to "geodesic_path".
            lon_rotation (float, optional): Longitude rotation to apply to all points. Defaults to 0.0.
            fill (bool, optional): If True and closed, fills the path with a translucent color. Defaults to False.
            fill_color (tuple, optional): RGBA color for the fill. Defaults to (1, 1, 0, 0.2).
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
        self.fill = fill
        self.fill_color = fill_color
        self.boundary_points = None # all the points used to draw the path and fill

        self.node = self._draw_path()
        self.fill_node = None
        if self.closed and self.fill:
            self.fill_node = self._draw_fill()

    def _collect_boundary_points(self, num_subdiv: int = 64) -> None:
        """
        Collects all interpolated points along the geodesic path to use as the fill boundary.
        """
        n = len(self.points)
        self.boundary_points = []
        for i in range(n if self.closed else n - 1):
            alt1, lat1, lon1 = self.points[i]
            alt2, lat2, lon2 = self.points[(i + 1) % n]
            p1 = lonlat_to_xyz(lon1 + self.lon_rotation, lat1, self.body_radius + alt1 + self.altitude_pad)
            p2 = lonlat_to_xyz(lon2 + self.lon_rotation, lat2, self.body_radius + alt2 + self.altitude_pad)
            # Interpolate along the great circle
            r1 = math.sqrt(sum(c**2 for c in p1))
            r2 = math.sqrt(sum(c**2 for c in p2))
            v1 = [c / r1 for c in p1]
            v2 = [c / r2 for c in p2]
            dot = sum(a*b for a, b in zip(v1, v2))
            dot = max(-1.0, min(1.0, dot))
            angle = math.acos(dot)
            for j in range(num_subdiv):
                t = j / num_subdiv
                if angle == 0:
                    interp = v1
                else:
                    sin_a = math.sin(angle)
                    w1 = math.sin((1 - t) * angle) / sin_a
                    w2 = math.sin(t * angle) / sin_a
                    interp = [w1 * v1[k] + w2 * v2[k] for k in range(3)]
                avg_r = (r1 + r2) / 2
                pt = [c * avg_r for c in interp]
                self.boundary_points.append(tuple(pt))

    def _draw_path(self) -> NodePath:
        segs = LineSegs()
        segs.setThickness(self.thickness)
        segs.setColor(*self.color)

        # Use interpolated boundary points for both path and fill
        self._collect_boundary_points(num_subdiv=64)
        n = len(self.boundary_points)
        if n < 2:
            return None

        # Draw the path using the boundary points
        for i, pt in enumerate(self.boundary_points):
            if i == 0:
                segs.moveTo(*pt)
            else:
                segs.drawTo(*pt)
        # If closed, connect last to first
        if self.closed and n > 2:
            segs.drawTo(*self.boundary_points[0])

        np = self.parent_np.attachNewNode(segs.create())
        np.setTransparency(True)
        np.setLightOff()
        np.setBin('transparent', 15)
        np.setName(self.name)
        np.setTextureOff()
        np.setShaderOff()
        return np

    def _draw_fill(self) -> NodePath:
        """
        Fills the closed geodesic path with a translucent polygon using all intermediate points.
        """
        if not self.boundary_points:
            self._collect_boundary_points(num_subdiv=64)
        n = len(self.boundary_points)
        if n < 3:
            return None

        # Create a triangle fan from the centroid
        centroid = [sum(coord[i] for coord in self.boundary_points) / n for i in range(3)]

        format = GeomVertexFormat.getV3cp()
        vdata = GeomVertexData("fill", format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        color_writer = GeomVertexWriter(vdata, "color")

        # Add centroid as first vertex
        vertex.addData3(*centroid)
        color_writer.addData4f(*self.fill_color)

        # Add all boundary points
        for pt in self.boundary_points:
            vertex.addData3(*pt)
            color_writer.addData4f(*self.fill_color)

        # Close the fan by repeating the first point
        vertex.addData3(*self.boundary_points[0])
        color_writer.addData4f(*self.fill_color)

        # Build triangles
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(1, n + 1):
            tris.addVertices(0, i, i + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode(f"{self.name}_fill")
        node.addGeom(geom)
        fill_np = self.parent_np.attachNewNode(node)
        fill_np.setTransparency(TransparencyAttrib.M_alpha)
        fill_np.setLightOff()
        fill_np.setBin('transparent', 14)
        fill_np.setTextureOff()
        fill_np.setShaderOff()
        fill_np.setTwoSided(True)
        return fill_np

    def remove(self):
        """Removes the geodesic path and fill from the scene."""
        if self.node:
            self.node.removeNode()
            self.node = None
        if self.fill_node:
            self.fill_node.removeNode()
            self.fill_node = None