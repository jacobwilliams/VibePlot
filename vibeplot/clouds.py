from panda3d.core import LVector3, ColorBlendAttrib, TransparencyAttrib, NodePath
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from .utilities import create_sphere

class CloudLayer:
    def __init__(
        self,
        parent: ShowBase,
        body_np: NodePath,
        radius: float,
        texture: str,
        opacity: float = 0.5,
        scale: float = 1.02,
        rotate_rate: float = 1.0,
        name: str = "CloudLayer",
        setLightOff: bool = False
    ):
        """
        Creates a semi-transparent, rotating cloud layer around a body.

        Args:
            parent: ShowBase instance (for loader and taskMgr).
            body_np: NodePath to parent (typically the body's _rotator).
            radius (float): Base radius of the body.
            texture (str): Path to the cloud texture image.
            opacity (float, optional): Opacity of the cloud layer (0-1). Defaults to 0.5.
            scale (float, optional): Scale factor for the cloud sphere (should be >1). Defaults to 1.02.
            rotate_rate (float, optional): Relative rotation rate (1.0 = same as body, 2.0 = twice as fast, etc.). Defaults to 1.0.
            name (str, optional): Node name. Defaults to "CloudLayer".
        """
        self.parent = parent
        self.body_np = body_np
        self.radius = radius
        self.texture = texture
        self.opacity = opacity
        self.scale = scale
        self.rotate_rate = rotate_rate
        self.name = name

        self.cloud_np = create_sphere(self.radius * self.scale, num_lat=24, num_lon=48, color=(1,1,1,self.opacity))
        if self.texture:
            tex = self.parent.loader.loadTexture(self.texture)
            # self.cloud_np.setTexture(tex, 1)
            # Make all black pixels (0,0,0) fully transparent
            # tex.setFormat(tex.F_srgb_alpha)  # Ensure alpha channel is present
            self.cloud_np.setTexture(tex, 1)
            self.cloud_np.setTransparency(True)
            self.cloud_np.setAlphaScale(self.opacity)
            self.cloud_np.setColor(1, 1, 1, 1)
            # Use a color mask: black (0,0,0) becomes transparent
            self.cloud_np.setColorScale(1, 1, 1, 1)
            self.cloud_np.setAttrib(
                ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha, ColorBlendAttrib.O_one)
            )
            self.cloud_np.setAttrib(
                TransparencyAttrib.make(TransparencyAttrib.M_binary)
            )
            self.cloud_np.setAlphaScale(self.opacity)
            self.cloud_np.setColor(1, 1, 1, 1)
            self.cloud_np.setTransparency(TransparencyAttrib.M_alpha)
            self.cloud_np.setAttrib(TransparencyAttrib.make(TransparencyAttrib.M_alpha))
        self.cloud_np.setName(self.name)
        self.cloud_np.reparentTo(self.body_np)
        self.cloud_np.setTransparency(True)
        # self.cloud_np.setTwoSided(True)
        if setLightOff:
            self.cloud_np.setLightOff()
        self.cloud_np.setShaderOff()
        self.cloud_np.setBin('transparent', 0)
        self.cloud_np.setDepthWrite(False)

        self._angle = 0.0
        self._task_name = f"{self.name}_CloudRotateTask"
        self.parent.add_task(self._cloud_rotate_task, self._task_name)

    def _cloud_rotate_task(self, task: Task):
        """
        Task to rotate the cloud layer at the specified rate.

        Args:
            task (Task): The Panda3D task object.

        Returns:
            Task.cont: To continue the task in the task manager.
        """
        # Rotate the cloud layer at the specified rate
        dt = globalClock.getDt()
        self._angle = (self._angle + dt * self.rotate_rate * 360.0 / 24.0) % 360.0
        self.cloud_np.setH(self._angle)
        return Task.cont

    def cleanup(self) -> None:
        """
        Cleans up the cloud layer by removing the rotation task and the node.
        """
        self.parent.taskMgr.remove(self._task_name)
        self.cloud_np.removeNode()