import numpy as np
import math
import json
from direct.showbase.ShowBase import ShowBase
from panda3d.core import Point3, Vec3, Mat3, Quat, LineSegs, TextNode, TextureStage, Shader, LVector3, Material, BitMask32
from direct.task import Task

from .utilities import (create_sphere,
                        lonlat_to_xyz,
                        create_body_fixed_arrow,
                        draw_path,
                        simple_propagator)
from .path import Path
from .clouds import CloudLayer

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
                 et0: float = 0.0,
                 etf: float = 100.0,
                 et_step: float = 1.0,
                 num_segments: int = 500,
                 time_step: float = None,
                 spline_mode: str = "cubic",  # "linear" or "cubic"
                 get_position_vector = None,
                 get_rotation_matrix = None,
                 color=(1, 1, 1, 1),
                 texture : str = None,
                 day_tex : str = None,
                 night_tex : str = None,
                 sun_dir = LVector3(0, 0, 1),
                 thickness: float = 2.0,
                 trajectory_mode: int = 1,  # 0: trace, 1: full trajectory
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
                 label_on_top: bool = False,
                 label_scale: float = 0.4,
                 material: Material = None,
                 is_sun: bool = False,
                 show_orbit_path: bool = True,
                 trace_mode: bool = False,
                 trace_dt: float = 2.0,
                 cloud_tex: str = None,
                 cloud_opacity: float = 0.5,
                 cloud_scale: float = 1.02,
                 cloud_rotate_rate: float = 1.0):
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
            thickness (float, optional): Thickness of the orbit path line. Defaults to 2.0.
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
            label_on_top (bool, optional): Label is always visible even when behind other objects. Defaults to False.
            label_scale (float, optional): Scale of the label. Defaults to 0.4.
            material (Material, optional): Material properties for the body. Defaults to None.
            is_sun (bool, optional): Whether the body is the sun. Defaults to False.
        """

        self.name = name
        self.radius = radius
        self.color = color
        self.parent = parent
        if get_position_vector is not None:
            self.get_position_vector = get_position_vector
        else:
            self.get_position_vector = self._get_position_vector
        if get_rotation_matrix is not None:
            self.get_rotation_matrix = get_rotation_matrix
        else:
            self.get_rotation_matrix = self._get_rotation_matrix
        self.label_scale = label_scale
        self.trace_color = trace_color
        self.spline_mode = spline_mode  # "linear" or "cubic"

        self.show_orbit_path = show_orbit_path
        self.trace_mode = trace_mode
        self.trace_dt = trace_dt

        self.num_segments = num_segments
        self.time_step = time_step
        self.et0 = et0
        self.etf = etf
        self.et_step = et_step

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
            self.day_tex = day_tex  # save it
            night_tex = parent.loader.loadTexture(night_tex)
            self.night_tex = night_tex  # save it
            self._body.setTexture(day_tex, 1)
            self._apply_daynight_shader(sun_dir)
        else:
            # no texture, just a color
            self._body.setColor(*color)

        # # Enable shadow casting and receiving
        # # self._body.setShaderAuto()
        # # Make bodies cast shadows
        # self._body.show(BitMask32.bit(0))  # Show in shadow camera
        # # Make bodies receive shadows
        # self._body.setTag("shadow", "receiver")

        self.cloud_layer = None
        if cloud_tex is not None:
            self.cloud_layer = CloudLayer(
                parent=self.parent,
                body_np=self._rotator,
                radius=self.radius,
                texture=cloud_tex,
                opacity=cloud_opacity,
                scale=cloud_scale,
                rotate_rate=cloud_rotate_rate,
                name=f"{self.name}_CloudLayer"
            )

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

        self.trajectory_mode = trajectory_mode
        self.thickness = thickness
        if self.trajectory_mode == 1:
            # draw the full trajectory
            self.trace_length = 0 # do not draw the trace
            #self.draw_trajectory(None, color=self.color)
            #TODO add the trace code to this class as an option ...
            #pts = []
            orbit_json = {'t': [], 'x': [], 'y': [], 'z': []}
            for et in np.arange(self.et0, self.etf, self.et_step):
                r = self.get_position_vector(et)
                orbit_json['t'].append(et)
                orbit_json['x'].append(r[0])
                orbit_json['y'].append(r[1])
                orbit_json['z'].append(r[2])
            self.path = Path(parent = self.parent,
                             spline_mode = self.spline_mode,
                             color = self.color,
                             thickness = self.thickness,
                             orbit_json = orbit_json,
                             num_segments = self.num_segments,
                             time_step = self.time_step,
                             show_orbit_path = self.show_orbit_path,
                             trace_mode = self.trace_mode,
                             trace_dt = self.trace_dt)
        else:
            self.path = None
            # draw trajectory using the fading trace
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
            if draw_3d_axes:
                label_np.setPos(0, 0, self.radius * 2.3 + 0.01)  # Slightly above the axis
            else:
                label_np.setPos(0, 0, self.radius + 0.31)  # Slightly above the body
            label_np.setBillboardPointEye()
            label_np.setLightOff()
            self.body_label_np = label_np  # Store reference if you want to hide/show later

            if label_on_top:
                self.body_label_np.setBin('fixed', 100)  # Draw in a high-priority bin
                self.body_label_np.setDepthTest(False)   # Don't test against the depth buffer
                self.body_label_np.setDepthWrite(False)  # Don't write to the depth buffer

        self.is_sun = is_sun
        if self.is_sun:
            self._body.setLightOff()  # no shadowing on the sun!
            # trying to get the light to follow the sun.
            # [it's a directionaly light, not a point light (which i couldn't get to work)]
            # self.parent.dlnp.reparentTo(self.sun._body)  # move light to the sun
            # self.parent.dlnp.setPos(0, 0, 0)
            self.parent.add_task(self.update_sunlight_direction, "UpdateSunlightDirection")

        self.reparent_to_rotator()

        # add to the list of bodies in the scene:
        self.parent.bodies.append(self)

    # def draw_trajectory(self, pts = None, color=(1,1,1,1), linestyle: int = 0):

    #     # PROBLEM: the body calls get_position_vector separately, so it
    #     # doesn't follow this path. we need to replace with what is done
    #     # in Orbit. should commonize that code so we can call it here (also for the task).
    #     # TODO

    #     if not pts:
    #         # if no points, generate them here
    #         pts = []
    #         for et in range(0, 100, 10):    # et0, etf, delta should be inputs !
    #             r = self.get_position_vector(et)
    #             pts.append(Point3(r[0], r[1], r[2]))

    #     orbit_np = draw_path(self.parent.render, pts, linestyle=linestyle, colors=[color]*len(pts))
    #     orbit_np.setRenderModeThickness(self.thickness)
    #     orbit_np.setLightOff()
    #     orbit_np.setTextureOff()
    #     orbit_np.setShaderOff()
    #     orbit_np.clearColor()
    #     orbit_np.setTwoSided(True)
    #     orbit_np.setTransparency(True)
    #     return orbit_np

    def show_hide_label(self, show: bool):
        """Show or hide the body's label.

        Args:
            show (bool): If True, show the label; if False, hide it.
        """
        if hasattr(self, 'body_label_np'):
            if show:
                self.body_label_np.show()
            else:
                self.body_label_np.hide()

    def _apply_daynight_shader(self, sun_dir=None):
        """Apply the day/night shader and textures to this body."""
        if hasattr(self, "day_tex") and hasattr(self, "night_tex"):
            self._body.setShader(Shader.load(Shader.SL_GLSL, "models/earth_daynight.vert", "models/earth_daynight.frag"))
            self._body.setTexture(TextureStage("day"), self.day_tex)
            self._body.setTexture(TextureStage("night"), self.night_tex)
            self._body.setShaderInput("day", self.day_tex)
            self._body.setShaderInput("night", self.night_tex)
            # Set the sun direction uniform (should match your light direction)
            if sun_dir is not None:
                self._body.setShaderInput("sundir", sun_dir)
            else:
                self._body.setShaderInput("sundir", LVector3(0, 0, 1))
            # Add/update the sun direction update task
            self.parent.add_task(self.update_earth_shader_sundir_task, f"Update{self.name}ShaderSunDir")

    def set_shadowed(self, enable: bool, sunlight_np=None):
        """
        Enable or disable sunlight/shadowing on this body.
        If the body uses a day/night shader, disables the shader and sets the day texture when shadowing is off.
        """
        if enable:
            if sunlight_np:
                self._body.setLight(sunlight_np)
            self._body.setShaderAuto()
            self._apply_daynight_shader()
        else:
            if sunlight_np:
                self._body.setLightOff(sunlight_np)
            self._body.setShaderOff()
            # If using a day/night shader, switch to day texture only
            if hasattr(self, "day_tex"):
                self._body.clearTexture()
                self._body.setTexture(self.day_tex, 1)
            # Remove the sundir update task if present
            self.parent.remove_task(f"Update{self.name}ShaderSunDir")

    def update_earth_shader_sundir_task(self, et):
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

    def _get_position_vector(self, et: float):
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

            # .... doesn't work since some of the code is assuming earth is a 0,0,0 ?
            # earth_orbit_radius = EARTH_RADIUS * 0.5  # Distance from Earth center
            # earth_orbit_speed = 0.7  # radians per second
            # return simple_propagator(earth_orbit_radius, 0.0, et, earth_orbit_speed)

        elif self.name.lower() == "sun":
            sun_orbit_radius = EARTH_RADIUS * 10  # Distance from Earth center
            sun_orbit_speed = 0.7  # radians per second
            return simple_propagator(sun_orbit_radius, 10.0, et, sun_orbit_speed)

        # Moon orbits Earth
        elif self.name.lower() == "moon":
            # Use the same parameters as before
            moon_orbit_radius = EARTH_RADIUS * 5  # Distance from Earth center
            moon_orbit_speed = 0.7  # radians per second
            return simple_propagator(moon_orbit_radius, 5.0, et, moon_orbit_speed)

        # Mars orbits Earth (for demo)
        elif self.name.lower() == "mars":
            mars_orbit_radius = EARTH_RADIUS * 6
            mars_orbit_speed = 0.5  # radians per second
            return simple_propagator(mars_orbit_radius, 2.0, et, mars_orbit_speed)

        # Venus (example, you can adjust as needed)
        elif self.name.lower() == "venus":
            venus_orbit_radius = EARTH_RADIUS * 7
            venus_orbit_speed = 0.3
            return simple_propagator(venus_orbit_radius, 1.0, et, venus_orbit_speed)

        # Default: stationary at origin
        return np.array([0.0, 0.0, 0.0])

    def _get_rotation_matrix(self, et: float):
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

    def draw_country_boundaries(self, geojson_path : str, lon_rotate : float = 0.0, radius_pad : float = 0.02, thickness: float = 1.2, color = (1, 1, 1, 0.5)):
        """Draws country boundaries on the body using a GeoJSON file.

        Args:
            geojson_path (str): Path to the GeoJSON file.
            lon_rotate (float, optional): Longitude rotation offset. Defaults to 0.0.
            radius_pad (float, optional): Padding above the surface to draw the boundaries. Defaults to 0.001.
        """

        with open(geojson_path, 'r') as f:
            data = json.load(f)

        segs = LineSegs()
        segs.setThickness(thickness)
        segs.setColor(color)

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
        self.boundaries_np.setBin('transparent', 10)

    def orbit_task(self, et):
        """Updates the body's position, orientation, and trace during its orbit.

        Args:
            task (Task): The Panda3D task object.

        Returns:
            Task: The continuation status of the task.
        """

        # if self.parent.paused:  # Check the pause flag
        #     return Task.cont  # Skip updates if paused

        #et = task.time
        # et = self.parent.sim_time if self.parent.use_slider_time else task.time
        # et = self.parent.get_et(task)

        if self.path:
            self.path.update_trace(et)

        # Skip updates for sites    ---- this needs to be moved somewhere else....
        if self.__class__.__name__ != 'Site':
            # don't update the rotator if it's a site
            self.set_orientation(et)
            if self.path:
                r = self.path.get_orbit_state(et)    # use the path class
            else:
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
                segs.setThickness(self.thickness)

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

    def draw_lat_lon_grid(self, num_lat=10, num_lon=16, radius_pad=0.015, color=(1, 1, 1, 1), thickness=2.0):
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
        self.grid_np.setDepthOffset(3)
        self.grid_np.setBin('transparent', 20)

    def update_sunlight_direction(self, et):
        sun_pos = self._body.getPos(self.parent.render)
        self.parent.dlnp.setPos(sun_pos)  # Move the light to the Sun's position (optional for DirectionalLight)
        self.parent.dlnp.lookAt(0, 0, 0)  # Point at the scene center
        return Task.cont

    # def add_saturn_rings(self, inner_radius=EARTH_RADIUS*1.2,
    #                      outer_radius=EARTH_RADIUS*3.0,
    #                      inclination_deg=10, num_rings=5,
    #                      transparency=0.6):
    #     """Create Saturn-like ring system around Earth"""

    #     # Create parent node for all rings
    #     ring_system = self.render.attachNewNode("ring_system")

    #     # Apply inclination to the entire ring system
    #     ring_system.setP(inclination_deg)

    #     # Create multiple rings with gaps
    #     ring_width = (outer_radius - inner_radius) / (num_rings * 2 - 1)

    #     for i in range(num_rings):
    #         # Calculate this ring's inner and outer radius
    #         ring_inner = inner_radius + i * ring_width * 2
    #         ring_outer = ring_inner + ring_width

    #         # Vary color slightly for each ring
    #         base_color = (0.8, 0.75, 0.6, transparency)  # Sandy color
    #         color_variation = 0.1 * (i / num_rings)
    #         ring_color = (
    #             base_color[0] - color_variation,
    #             base_color[1] - color_variation,
    #             base_color[2] - color_variation,
    #             base_color[3]
    #         )

    #         # Create the ring
    #         ring = self.create_flat_ring(
    #             inner_radius=ring_inner,
    #             outer_radius=ring_outer,
    #             color=ring_color,
    #             segments=120,
    #             num_subdivisions=8
    #         )

    #         ring.reparentTo(ring_system)
    #         ring.setTwoSided(True)
    #         ring.setTransparency(True)
    #         ring.setBin('transparent', 30)

    #     # Parent to Earth so it follows Earth's rotation
    #     ring_system.reparentTo(self.earth)
    #     # Also set these on the parent node to be extra sure
    #     ring_system.setTextureOff(1)
    #     ring_system.setShaderOff(1)

    #     return ring_system

    # def create_flat_ring(self, inner_radius, outer_radius, color, segments=64, num_subdivisions=4):
    #     """Create a flat ring with triangles for better texture mapping"""

    #     format = GeomVertexFormat.getV3n3c4t2()
    #     vdata = GeomVertexData('ring', format, Geom.UHStatic)
    #     vertex = GeomVertexWriter(vdata, 'vertex')
    #     normal = GeomVertexWriter(vdata, 'normal')
    #     color_writer = GeomVertexWriter(vdata, 'color')
    #     texcoord = GeomVertexWriter(vdata, 'texcoord')

    #     tris = GeomTriangles(Geom.UHStatic)

    #     # Create vertices for the ring
    #     for i in range(segments + 1):
    #         angle = 2 * math.pi * i / segments
    #         cos_angle = math.cos(angle)
    #         sin_angle = math.sin(angle)

    #         # Create multiple subdivisions from inner to outer radius
    #         for j in range(num_subdivisions + 1):
    #             # Calculate radius for this subdivision
    #             r = inner_radius + (outer_radius - inner_radius) * j / num_subdivisions

    #             x = r * cos_angle
    #             y = r * sin_angle
    #             z = 0  # Flat ring

    #             # Add vertex
    #             vertex.addData3(x, y, z)
    #             normal.addData3(0, 0, 1)  # Normal points up
    #             color_writer.addData4(*color)
    #             texcoord.addData2(i / segments, j / num_subdivisions)

    #     # Create triangles
    #     for i in range(segments):
    #         for j in range(num_subdivisions):
    #             # First triangle
    #             v1 = i * (num_subdivisions + 1) + j
    #             v2 = (i + 1) * (num_subdivisions + 1) + j
    #             v3 = i * (num_subdivisions + 1) + (j + 1)
    #             tris.addVertices(v1, v2, v3)

    #             # Second triangle
    #             v1 = (i + 1) * (num_subdivisions + 1) + j
    #             v2 = (i + 1) * (num_subdivisions + 1) + (j + 1)
    #             v3 = i * (num_subdivisions + 1) + (j + 1)
    #             tris.addVertices(v1, v2, v3)

    #     geom = Geom(vdata)
    #     geom.addPrimitive(tris)
    #     node = GeomNode('ring')
    #     node.addGeom(geom)

    #     return NodePath(node)

    # def rotate_rings_task(self, task):
    #     self.rings.setH(self.rings.getH() + 0.01)  # Slow rotation
    #     return Task.cont

    # def add_radiation_belt(self, inner_radius=2.5, outer_radius=3.5, belt_color=(0.2, 1, 0.2, 0.18), num_major=100, num_minor=24):
    #     """Draw a translucent torus (belt) around the Earth."""

    #     format = GeomVertexFormat.getV3n3c4()
    #     vdata = GeomVertexData('belt', format, Geom.UHStatic)
    #     vertex = GeomVertexWriter(vdata, 'vertex')
    #     normal = GeomVertexWriter(vdata, 'normal')
    #     color = GeomVertexWriter(vdata, 'color')

    #     verts = []
    #     major_radius = (inner_radius + outer_radius) / 2
    #     minor_radius = (outer_radius - inner_radius) / 2

    #     for i in range(num_major + 1):
    #         phi = 2 * math.pi * i / num_major
    #         center = Vec3(major_radius * math.cos(phi), major_radius * math.sin(phi), 0)
    #         for j in range(num_minor + 1):
    #             theta = 2 * math.pi * j / num_minor
    #             # Local circle in XZ plane
    #             x = (major_radius + minor_radius * math.cos(theta)) * math.cos(phi)
    #             y = (major_radius + minor_radius * math.cos(theta)) * math.sin(phi)
    #             z = minor_radius * math.sin(theta)
    #             pos = Vec3(x, y, z)
    #             n = (pos - center).normalized()
    #             vertex.addData3(pos)
    #             normal.addData3(n)
    #             color.addData4(*belt_color)
    #             verts.append((i, j))

    #     # Build triangles
    #     tris = GeomTriangles(Geom.UHStatic)
    #     for i in range(num_major):
    #         for j in range(num_minor):
    #             a = i * (num_minor + 1) + j
    #             b = ((i + 1) % (num_major + 1)) * (num_minor + 1) + j
    #             c = ((i + 1) % (num_major + 1)) * (num_minor + 1) + (j + 1)
    #             d = i * (num_minor + 1) + (j + 1)
    #             tris.addVertices(a, b, d)
    #             tris.addVertices(b, c, d)

    #     geom = Geom(vdata)
    #     geom.addPrimitive(tris)
    #     node = GeomNode('radiation_belt')
    #     node.addGeom(geom)
    #     belt_np = self.render.attachNewNode(node)
    #     belt_np.setTransparency(True)
    #     belt_np.setTwoSided(True)
    #     belt_np.setBin('transparent', 20)
    #     return belt_np


