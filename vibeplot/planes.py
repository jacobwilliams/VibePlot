from panda3d.core import (LineSegs,
                          CardMaker,
                          TransparencyAttrib)


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
                 thickness: float = 1.0):
        """Equatorial plane (square, translucent)

        Args:
            parent (NodePath): NodePath to attach the plane to (e.g., a body's _rotator or _body).
            radius (float): Half-width of the square plane
            color (tuple, optional): RGBA color of the plane. Defaults to a translucent blue.
            grid_color (tuple, optional): RGBA color of the gridlines. Defaults to white.
            num_lines (int, optional): Number of gridlines per axis. Defaults to 9
            thickness (float, optional): Thickness of the gridlines. Defaults to 1.0.
        """
        self.parent = parent
        plane_size = radius
        plane_color = color

        # Create the plane
        cm = CardMaker("equatorial_plane")
        cm.setFrame(-plane_size, plane_size, -plane_size, plane_size)
        plane_np = parent.attachNewNode(cm.generate())
        plane_np.setPos(0, 0, 0)
        plane_np.setHpr(0, -90, 0)  # Rotate from XZ to XY plane
        plane_np.setTransparency(TransparencyAttrib.MAlpha)
        plane_np.setColor(*plane_color)
        plane_np.setTextureOff()
        plane_np.setShaderOff()
        plane_np.setLightOff()
        plane_np.setTwoSided(True)
        plane_np.setBin('fixed', 10)  # or 'transparent', 20

        # --- Gridlines on the plane ---
        gridlines = LineSegs()
        gridlines.setThickness(thickness)
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
        grid_np = parent.attachNewNode(gridlines.create())
        grid_np.setTextureOff()
        grid_np.setShaderOff()
        grid_np.setLightOff()
        grid_np.setTwoSided(True)
        grid_np.setTransparency(TransparencyAttrib.MAlpha)
        grid_np.setBin('fixed', 11)  # or 'transparent', 21