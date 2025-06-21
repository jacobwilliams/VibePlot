from panda3d.core import NodePath, LineSegs, Vec3, Point3, TextNode, Mat4
import math
from .utilities import create_sphere, create_body_fixed_arrow
from direct.showbase.ShowBase import ShowBase
from .bodies import Body
import numpy as np


class Site(Body):
    """a site on the surface of a body

        Note that this is a type of body. may rethink this later.
        probably it should be an Orbit type? Or they all should inherit from a common base class.
    """

    def __init__(self, parent, name, central_body, lat_deg, lon_deg,
                 radius_offset=0.01, show_orbit: bool = True, **kwargs):

        self.central_body = central_body
        self.lat_deg = lat_deg
        self.lon_deg = lon_deg
        self.radius_offset = radius_offset

        # Compute position in central_body's local coordinates
        x, y, z = self.get_body_fixed_position()

        # Call Body's constructor
        super().__init__(parent, name=name, **kwargs)

        # a site should not inherit the lighting or texture from the parent body
        self._body.setLightOff()
        self._body.setTextureOff()
        self._body.setShaderOff()

        if not show_orbit:
            # Remove the orbit task - sites don't orbit, they're fixed to the parent body
            self.parent.remove_task(f"{self.name}OrbitTask")

        # Attach this site's _rotator to the central body's _rotator
        self._rotator.reparentTo(central_body._rotator)
        self._rotator.setPos(x, y, z)  # <-- Center the rotator on the site

        # Attach this site's _body node to the central body's _body node
        self._body.reparentTo(central_body._body)
        self._body.setPos(x, y, z)

        # Override the label position for sites
        if hasattr(self, 'body_label_np'):
            # Parent the label to the site's _rotator
            self.body_label_np.reparentTo(self._rotator)
            # Position the label exactly at the site
            self.body_label_np.setPos(0, 0, 0)  # No offset, directly at the site
            # self.body_label_np.setScale(0.5)  # Adjust this value as needed

    def set_visible(self, visible=True):
        if visible:
            self.node.show()
        else:
            self.node.hide()

    def destroy(self):
        self.node.removeNode()

    def get_body_fixed_position(self):
        # Compute position in central_body's local coordinates
        lat = math.radians(self.lat_deg)
        lon = math.radians(self.lon_deg)
        r = self.central_body.radius + self.radius_offset
        x = r * math.cos(lat) * math.cos(lon)
        y = r * math.cos(lat) * math.sin(lon)
        z = r * math.sin(lat)
        return x, y, z

    def get_position_vector(self, et: float):
        """Override to keep the site fixed relative to the central body."""
        # Sites don't orbit - they stay fixed on the surface
        # Return the site's position relative to the central body's position
        central_body_pos = self.central_body.get_position_vector(et)

        # Convert site's local position to world coordinates
        x, y, z = self.get_body_fixed_position()

        # Return site position relative to central body
        return central_body_pos + np.array([x, y, z])


