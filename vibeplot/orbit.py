import math
from direct.task import Task
from panda3d.core import Point3, LineSegs, NodePath, GeomNode, Geom, GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomTriangles, Vec3

from .bodies import Body

class Orbit:
    def __init__(self, parent, name: str, central_body: Body, radius: float = 5.0, speed: float = 1.0,
                 inclination_deg: float = 0.0, color=(1, 1, 0, 1), thickness: float = 2.0,
                 satellite_radius: float = 0.1, satellite_color=(1, 0, 0, 1),
                 visibility_cone: bool = True, cone_angle_deg: float = 5.0,
                 groundtrack: bool = True, groundtrack_length: int = 1000,
                 show_orbit_path: bool = True, num_segments: int = 100):

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

        # Visibility cone settings
        self.visibility_cone_enabled = visibility_cone
        self.visibility_cone_angle = math.radians(cone_angle_deg)
        self.visibility_cone_segments = 24

        # Groundtrack settings
        self.groundtrack_enabled = groundtrack
        self.groundtrack_length = groundtrack_length
        self.groundtrack_trace = []

        # Create the satellite
        self.satellite = self._create_satellite()

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

    def _create_satellite(self):
        """Create the satellite geometry"""
        from .utilities import create_sphere
        satellite = create_sphere(
            radius=self.satellite_radius,
            num_lat=24,
            num_lon=48,
            color=self.satellite_color
        )
        satellite.reparentTo(self.parent.render)
        satellite.setLightOff()  # Disable lighting for visibility
        return satellite

    def get_orbit_state(self, angle: float):
        """just a simple orbit model."""
        x = self.radius * math.cos(angle)
        y = self.radius * math.sin(angle)
        z = 0
        # Apply inclination
        y_incl = y * math.cos(self.inclination) - z * math.sin(self.inclination)
        z_incl = y * math.sin(self.inclination) + z * math.cos(self.inclination)
        return x, y_incl, z_incl

    def _create_orbit_path(self):
        """Create the orbital path visualization"""
        orbit_segs = LineSegs()
        orbit_segs.setThickness(self.thickness)
        orbit_segs.setColor(*self.color)

        # Create orbit path in local coordinates (relative to central body)
        for i in range(self.num_segments + 1):
            angle = 2 * math.pi * i / self.num_segments
            x, y, z = self.get_orbit_state(angle)
            if i == 0:
                orbit_segs.moveTo(x, y, z)
            else:
                orbit_segs.drawTo(x, y, z)

        orbit_np = NodePath(orbit_segs.create())
        # Parent to central body instead of render so it follows the body
        # orbit_np.reparentTo(self.central_body._body)
        orbit_np.reparentTo(self.parent.render)  # Not to the body!

        orbit_np.setLightOff()  # Turn off lighting
        #orbit_np.setColorOff()  # Don't inherit parent's color
        #orbit_np.setColor(self.color)  # Set explicit color
        orbit_np.clearColor()   # <--- This removes the parent's color override!
        orbit_np.setColor(self.color, 1)  # <--- OVERRIDE parent color!
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
        """Main orbit animation task"""
        # Calculate satellite position in LOCAL coordinates relative to central body
        angle = task.time * self.speed
        x, y, z = self.get_orbit_state(angle)

        # Set satellite position in the same local coordinate system as the orbit path
        sat_pos_local = Point3(x, y, z)

        # Convert local position to world position for satellite placement
        sat_pos_world = self.central_body._body.getPos(self.parent.render) + \
                        self.central_body._body.getQuat(self.parent.render).xform   (sat_pos_local)

        # Update satellite position in world coordinates
        self.satellite.setPos(sat_pos_world)

        # Keep the orbit path visually centered on the central body
        if self.orbit_path_np:
            body_np = self.central_body._body
            self.orbit_path_np.setPos(body_np.getPos(self.parent.render))
            self.orbit_path_np.setQuat(body_np.getQuat(self.parent.render))

        # Update visibility cone
        if self.visibility_cone_enabled:
            base_points = self._create_visibility_cone(sat_pos_world)
            self._create_cone_outline(base_points)

        # Update groundtrack
        self._update_groundtrack(sat_pos_world)

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