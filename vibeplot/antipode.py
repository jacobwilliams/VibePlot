from panda3d.core import TextNode
from direct.task import Task
from .utilities import create_arrow_with_endpoints


class BodyToBodyArrow:

    def __init__(self, app, body_a, body_b, extension=1.5, color=(1, 0.5, 0, 1), thickness=0.05, head_size=0.15, name="BodyToBodyArrow", label_text=None, label_color=(1,1,1,1), label_scale=0.3, always_on_top: bool = False):
        """
        Draws an arrow from body_a to body_b, extending beyond body_b by extension * body_b.radius.
        - app: your main app (for taskMgr and render)
        - body_a, body_b: Body instances
        - extension: multiplier for how far beyond body_b to extend (1.1 = 10% beyond radius)
        """
        self.app = app
        self.body_a = body_a
        self.body_b = body_b
        self.extension = extension
        self.color = color
        self.thickness = thickness
        self.head_size = head_size
        self.arrow_np = None
        self.name = name
        self.label_text = label_text
        self.label_color = label_color
        self.label_scale = label_scale
        self.label_np = None
        self.always_on_top = always_on_top

        # Start the update task
        self.app.add_task(self.update_task, f"Update_{self.name}")

    def update_task(self, task):
        # Get positions in render coordinates
        pos_a = self.body_a._body.getPos(self.app.render)
        pos_b = self.body_b._body.getPos(self.app.render)

        # Direction and length
        direction = (pos_b - pos_a).normalized()
        length = (pos_b - pos_a).length() + self.body_b.radius * self.extension
        end_pos = pos_a + direction * length

        # Remove previous arrow
        if self.arrow_np:
            self.arrow_np.removeNode()

        # Draw new arrow
        self.arrow_np = create_arrow_with_endpoints(
            start=pos_a,
            end=end_pos,
            color=self.color,
            thickness=self.thickness,
            head_size=self.head_size
        )
        self.arrow_np.reparentTo(self.app.render)
        self.arrow_np.setLightOff()
        self.arrow_np.setTransparency(True)

        # Draw label if requested
        if self.label_text:
            if self.label_np is None:
                label_node = TextNode(f"{self.name}_label")
                label_node.setText(self.label_text)
                label_node.setTextColor(*self.label_color)
                label_node.setAlign(TextNode.ACenter)
                self.label_np = self.app.render.attachNewNode(label_node)
                self.label_np.setScale(self.label_scale)
                self.label_np.setBillboardPointEye()
                self.label_np.setLightOff()
                if self.always_on_top:
                    self.label_np.setBin('fixed', 100)
                    self.label_np.setDepthTest(False)
                    self.label_np.setDepthWrite(False)
            # move the label to the end of the arrow
            self.label_np.setPos(end_pos)

        return Task.cont

    def destroy(self):
        if self.arrow_np:
            self.arrow_np.removeNode()
            self.arrow_np = None
        if self.label_np:
            self.label_np.removeNode()
            self.label_np = None
        if self.app.taskMgr.hasTaskNamed(f"Update_{self.name}"):
            self.app.taskMgr.remove(f"Update_{self.name}")