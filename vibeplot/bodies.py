import numpy as np
import math
import json
from direct.showbase.ShowBase import ShowBase
from panda3d.core import Point3, Vec3, Mat3, Quat, LineSegs, TextNode, TextureStage, Shader, LVector3, Material, BitMask32
from direct.task import Task

from .utilities import create_sphere, lonlat_to_xyz, create_body_fixed_arrow

EARTH_RADIUS = 2.0  # Default radius for Earth-like bodies, can be adjusted
# ... need to avoid setting this here ...

class Body:
    """A class representing a celestial body.

    ### Heirarchy

    ```
    Body (self._body)
    └── Rotator (self._rotator)
        ├── Sphere geometry (with texture)
        ├── Axes
        ├── Grid
        └── Other visuals
    ```

    ### Notes
        * maybe add a uuid to the strings to we are sure they are unique (if bodies have the same names)
    """

    def __init__(self,
                 parent : ShowBase,
                 name: str,
                 radius : float,
                 get_position_vector = None,
                 get_rotation_matrix = None,
                 color=(1, 1, 1, 1),
                 texture : str = None,
                 day_tex : str = None,
                 night_tex : str = None,
                 sun_dir = LVector3(0, 0, 1),
                 trace_length: int = 200,
                 trace_color=(0.7, 0.7, 1, 1),
                 geojson_path : str = None,
                 lon_rotate : str = 0.0,
                 draw_grid: bool = False,
                 draw_3d_axes: bool = True,
                 orbit_markers: bool = False,
                 marker_interval: int = 10,
                 marker_size: float = 0.08,
                 marker_color=(0, 1, 1, 1),
                 show_label: bool = True,
                 label_scale: float = 0.4,
                 material: Material = None):
        """Initializes a celestial body with various visual and physical properties.

        Args:
            parent (ShowBase): The parent ShowBase instance.
            name (str): The name of the body.
            radius (float): The radius of the body.
            get_position_vector (Callable, optional): Function to calculate the body's position vector. Defaults to None.
            get_rotation_matrix (Callable, optional): Function to calculate the body's rotation matrix. Defaults to None.
            color (tuple, optional): RGBA color of the body. Defaults to (1, 1, 1, 1).
            texture (str, optional): Path to the texture file. Defaults to None.
            day_tex (str, optional): Path to the day texture file. Defaults to None.
            night_tex (str, optional): Path to the night texture file. Defaults to None.
            sun_dir (LVector3, optional): Direction of the sun for lighting. Defaults to (0, 0, 1).
            trace_length (int, optional): Length of the trace path. Defaults to 200.
            trace_color (tuple, optional): RGBA color of the trace. Defaults to (0.7, 0.7, 1, 1).
            geojson_path (str, optional): Path to the GeoJSON file for country boundaries. Defaults to None.
            lon_rotate (float, optional): Longitude rotation offset. Defaults to 0.0.
            draw_grid (bool, optional): Whether to draw latitude and longitude grid lines. Defaults to False.
            draw_3d_axes (bool, optional): Whether to draw 3D axes. Defaults to True.
            orbit_markers (bool, optional): Whether to draw orbit markers. Defaults to False.
            marker_interval (int, optional): Interval for placing orbit markers. Defaults to 10.
            marker_size (float, optional): Size of orbit markers. Defaults to 0.08.
            marker_color (tuple, optional): RGBA color of orbit markers. Defaults to (0, 1, 1, 1).
            show_label (bool, optional): Whether to show the body's label. Defaults to True.
            label_scale (float, optional): Scale of the label. Defaults to 0.4.
            material (Material, optional): Material properties for the body. Defaults to None.
        """

        self.name = name
        self.radius = radius
        self.color = color
        self.parent = parent
        if get_position_vector is not None:
            self.get_position_vector = get_position_vector
        if get_rotation_matrix is not None:
            self.get_rotation_matrix = get_rotation_matrix
        self.label_scale = label_scale
        self.trace_color = trace_color

        self.orbit_markers_np = None
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
            # Only enable automatic shaders for non-textured bodies
            # self._body.setShaderAuto()

        # # Enable shadow casting and receiving
        # # self._body.setShaderAuto()
        # # Make bodies cast shadows
        # self._body.show(BitMask32.bit(0))  # Show in shadow camera
        # # Make bodies receive shadows
        # self._body.setTag("shadow", "receiver")

        # myMaterial = Material()
        # myMaterial.setShininess(100.0)  # Increase from 5.0 to make it much shinier
        # myMaterial.setSpecular((1, 1, 1, 1))  # Add specular highlight color (white)
        # myMaterial.setAmbient((0.2, 0.2, 0.2, 1))  # Reduce ambient from blue to gray
        # myMaterial.setDiffuse((0.8, 0.8, 0.8, 1))  # Set diffuse color
        if material is not None:
            self._body.setMaterial(material)  # Apply the material!

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

        # Add body label above the z-axis
        if show_label:
            label_node = TextNode(f"{self.name}_label")
            label_node.setText(self.name)
            label_node.setTextColor(1, 1, 1, 1)
            label_node.setAlign(TextNode.ACenter)
            label_np = self._body.attachNewNode(label_node)
            label_np.setScale(self.label_scale)
            label_np.setPos(0, 0, self.radius * 2.3 + 0.01)  # Slightly above the axis
            label_np.setBillboardPointEye()
            label_np.setLightOff()
            self.body_label_np = label_np  # Store reference if you want to hide/show later

        self.reparent_to_rotator()

        #...test...
        # self._body.setLightOff()
        # self._body.setTextureOff(1)  # <--- This disables texture inheritance
        # self._body.setTransparency(True)

        # add to the list of bodies in the scene:
        self.parent.bodies.append(self)

    def update_earth_shader_sundir_task(self, task):
        """Updates the shader's sun direction for the Earth.

        Args:
            task (Task): The Panda3D task object.

        Returns:
            Task: The continuation status of the task.
        """
        self.update_shader_sundir(self.parent.dlnp)
        return Task.cont

    def update_shader_sundir(self, sun_np):
        """Updates the shader's sun direction for this body.

        Args:
            sun_np (NodePath): The NodePath of the sun.
        """
        # Get sun direction in world space
        sun_dir_world = sun_np.getQuat(self.parent.render).getForward()
        # Get sun direction in this body's local space
        sun_dir_local = self._body.getQuat(self.parent.render).conjugate().xform(sun_dir_world)
        # Optional: rotate by 180 deg around Z to match texture orientation
        rot180 = Mat3.rotateMatNormaxis(180, Vec3(0, 0, 1))
        sun_dir_local_rot = rot180.xform(sun_dir_local)
        self._body.setShaderInput("sundir", sun_dir_local_rot)

    def setup_body_fixed_camera(self, view_distance=None, follow_without_rotation=False, body_to_look_at=None):
        """Sets up the camera in this body's frame.

        Args:
            view_distance (float, optional): Distance from the body to position the camera. Defaults to None.
            follow_without_rotation (bool, optional): If True, the camera follows the body's position but does not rotate with it. Defaults to False.
        """
        self.parent.setup_body_fixed_frame(self, view_distance, follow_without_rotation, body_to_look_at)

    def create_body_fixed_axes(self):
        """Creates 3D body-fixed axes for the body.

        Returns:
            NodePath: The NodePath containing the 3D axes.
        """
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
        """Reparents the body's children to the rotator node."""
        for child in self._body.getChildren():
            if child.getName() != f"{self.name}_rotator":
                child.reparentTo(self._rotator)

    def set_orientation(self, et: float):
        """Sets the orientation of the body based on the provided time.

        Args:
            et (float): The elapsed time used to calculate the orientation.
        """
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
        """Calculates the position vector of the body.

        Args:
            et (float): The elapsed time used to calculate the position.

        Returns:
            np.ndarray: The position vector of the body.

        ### Notes:
            * there is where we would maybe call an ephemeris
              For simplicity, let's assume the orbits.
        """

        # Earth stays at the origin
        if self.name.lower() == "earth":
            return np.array([0.0, 0.0, 0.0])

        elif self.name.lower() == "sun":
            return np.array([-100.0, 0.0, 0.0])

        # Moon orbits Earth
        elif self.name.lower() == "moon":
            # Use the same parameters as before
            moon_orbit_radius = EARTH_RADIUS * 5  # Distance from Earth center
            moon_orbit_speed = 0.7  # radians per second
            angle = et * moon_orbit_speed
            x = moon_orbit_radius * math.cos(angle)
            y = moon_orbit_radius * math.sin(angle)
            z = 0
            return np.array([x, y, z])

        # Mars orbits Earth (for demo)
        elif self.name.lower() == "mars":
            mars_orbit_radius = EARTH_RADIUS * 6
            mars_orbit_speed = 0.5  # radians per second
            angle = et * mars_orbit_speed
            x = mars_orbit_radius * math.cos(angle)
            y = mars_orbit_radius * math.sin(angle)
            z = 0
            return np.array([x, y, z])

        # Venus (example, you can adjust as needed)
        elif self.name.lower() == "venus":
            venus_orbit_radius = EARTH_RADIUS * 7
            angle = et * 0.3  # example speed
            x = venus_orbit_radius * math.cos(angle)
            y = venus_orbit_radius * math.sin(angle)
            z = 0
            return np.array([x, y, z])

        # Default: stationary at origin
        return np.array([0.0, 0.0, 0.0])

    def get_rotation_matrix(self, et: float):
        """Calculates the rotation matrix of the body.

        Args:
            et (float): The elapsed time used to calculate the rotation.

        Returns:
            np.ndarray: The rotation matrix of the body.

        ### Notes
            * e.g. call spice to get the body-fixed rotation matrix
              This is a simplified example, replace with actual logic
              to get the rotation matrix
        """

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
        """Draws country boundaries on the body using a GeoJSON file.

        Args:
            geojson_path (str): Path to the GeoJSON file.
            lon_rotate (float, optional): Longitude rotation offset. Defaults to 0.0.
            radius_pad (float, optional): Padding above the surface to draw the boundaries. Defaults to 0.001.
        """

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
        """Updates the body's position, orientation, and trace during its orbit.

        Args:
            task (Task): The Panda3D task object.

        Returns:
            Task: The continuation status of the task.
        """

        if self.parent.paused:  # Check the pause flag
            return Task.cont  # Skip updates if paused

        #et = task.time
        # et = self.parent.sim_time if self.parent.use_slider_time else task.time
        et = self.parent.get_et(task)

        # Skip updates for sites    ---- this needs to be moved somewhere else....
        if self.__class__.__name__ != 'Site':
            # don't update the rotator if it's a site
            self.set_orientation(et)
            r = self.get_position_vector(et)
            # Get the new position
            new_pos = Point3(r[0], r[1], r[2])
            self._rotator.setPos(new_pos)

        if self.trace_length:
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
            if self.orbit_markers_np is None:
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
                    color = (self.trace_color[0], self.trace_color[1], self.trace_color[2], alpha)
                    segs.setColor(color)

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
                        label_np.setScale(0.2)  # Scale the label appropriately
                        label_np.setBillboardPointEye()  # Make the label always face the camera
                        # Apply same properties as marker
                        label_np.setLightOff()
                        label_np.setTransparency(True)
                        # Store for cleanup
                        self.marker_labels.append(label_np)

                # Create the trace line
                self._trace_node.attachNewNode(segs.create())
                self._trace_node.setTransparency(True)
                self._trace_node.setLightOff()  # Add this line to disable lighting
                self._trace_node.setTwoSided(True)  # Also add this for better visibility

                self._trace_node.reparentTo(self.parent.render)  # wrt to base frame

        return Task.cont

    def draw_lat_lon_grid(self, num_lat=9, num_lon=18, radius_pad=0.01, color=(1, 1, 1, 1), thickness=1.0):
        """Draws latitude and longitude grid lines on the body.

        Args:
            num_lat (int, optional): Number of latitude lines (excluding poles). Defaults to 9.
            num_lon (int, optional): Number of longitude lines. Defaults to 18.
            radius_pad (float, optional): Padding above the surface to draw the grid. Defaults to 0.01.
            color (tuple, optional): RGBA color for the grid lines. Defaults to (1, 1, 1, 1).
            thickness (float, optional): Thickness of the grid lines. Defaults to 1.0.
        """

        # --- Latitude/Longitude grid ---
        grid = LineSegs()
        grid.setThickness(thickness)
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
        self.grid_np = self._body.attachNewNode(grid.create())
        self.grid_np.setShaderOff()
        self.grid_np.setLightOff()
        self.grid_np.setTwoSided(True)
        # self.grid_np.setDepthOffset(2)