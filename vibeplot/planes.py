from panda3d.core import (LineSegs,
                          CardMaker,
                          TransparencyAttrib,
                          GeomVertexFormat,
                          GeomVertexData,
                          GeomVertexWriter,
                          GeomTriangles,
                          Geom,
                          GeomNode,
                          NodePath)
import math

class Plane:
    """Base class for drawing planes in 3D space.

    This class provides a method to draw an equatorial plane with gridlines.
    """

    def __init__(self,
                 parent,
                 radius: float,
                 color: tuple = (0.2, 0.6, 1.0, 0.3),
                 grid_color: tuple = (1.0, 1.0, 1.0, 0.6),
                 num_lines: int = 9,
                 thickness: float = 1.0,
                 circular: bool = False,
                 num_circle_segments: int = 64):
        """Equatorial plane (square or circular, translucent)

        Args:
            parent (NodePath): NodePath to attach the plane to (e.g., a body's _rotator or _body).
            radius (float): Half-width of the square plane or radius of the circular plane.
            color (tuple, optional): RGBA color of the plane. Defaults to a translucent blue.
            grid_color (tuple, optional): RGBA color of the gridlines. Defaults to white.
            num_lines (int, optional): Number of gridlines per axis. Defaults to 9.
            thickness (float, optional): Thickness of the gridlines. Defaults to 1.0.
            circular (bool, optional): If True, draw a circular plane; otherwise, square. Defaults to False.
            num_circle_segments (int, optional): Number of segments for the circle. Defaults to 64.
        """
        self.parent = parent
        plane_color = color

        if not circular:
            # --- Square plane ---
            plane_size = radius
            cm = CardMaker("equatorial_plane")
            cm.setFrame(-plane_size, plane_size, -plane_size, plane_size)
            plane_np = parent.attachNewNode(cm.generate())
            plane_np.setPos(0, 0, 0)
            plane_np.setHpr(0, -90, 0)  # Rotate from XZ to XY plane
        else:
            # --- Circular plane ---
            format = GeomVertexFormat.getV3()
            vdata = GeomVertexData("circle", format, Geom.UHStatic)
            vertex = GeomVertexWriter(vdata, "vertex")
            # Center vertex
            vertex.addData3(0, 0, 0)
            # Perimeter vertices
            for i in range(num_circle_segments + 1):
                angle = 2 * math.pi * i / num_circle_segments
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                vertex.addData3(x, y, 0)
            # Triangles
            tris = GeomTriangles(Geom.UHStatic)
            for i in range(1, num_circle_segments):
                tris.addVertices(0, i, i + 1)
            # Close the fan by connecting the last perimeter vertex to the first
            tris.addVertices(0, num_circle_segments, 1)
            geom = Geom(vdata)
            geom.addPrimitive(tris)
            node = GeomNode("equatorial_circle")
            node.addGeom(geom)
            plane_np = parent.attachNewNode(node)
            plane_np.setHpr(0, 0, 0)

        plane_np.setTransparency(TransparencyAttrib.MAlpha)
        plane_np.setColor(*plane_color)
        plane_np.setTextureOff()
        plane_np.setShaderOff()
        plane_np.setLightOff()
        plane_np.setTwoSided(True)
        plane_np.setBin('fixed', 10)  # or 'transparent', 20
        self.plane_np = plane_np

        # --- Gridlines on the plane ---
        gridlines = LineSegs()
        gridlines.setThickness(thickness)
        z = 0  # Equatorial plane at z=0

        if not circular:
            plane_size = radius
            step = (2 * plane_size) / (num_lines - 1)
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
        else:
            # Radial lines
            for i in range(num_lines):
                angle = 2 * math.pi * i / num_lines
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                gridlines.setColor(*grid_color)
                gridlines.moveTo(0, 0, z)
                gridlines.drawTo(x, y, z)
            # Concentric circles
            num_rings = max(2, num_lines // 2)
            for j in range(1, num_rings + 1):
                r = radius * j / num_rings
                prev_x, prev_y = None, None
                for i in range(num_circle_segments + 1):
                    angle = 2 * math.pi * i / num_circle_segments
                    x = r * math.cos(angle)
                    y = r * math.sin(angle)
                    if i == 0:
                        gridlines.moveTo(x, y, z)
                    else:
                        gridlines.drawTo(x, y, z)

        grid_np = parent.attachNewNode(gridlines.create())
        grid_np.setTextureOff()
        grid_np.setShaderOff()
        grid_np.setLightOff()
        grid_np.setTwoSided(True)
        grid_np.setTransparency(TransparencyAttrib.MAlpha)
        grid_np.setBin('fixed', 11)  # or 'transparent', 21
        self.grid_np = grid_np