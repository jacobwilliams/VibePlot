from panda3d.core import NodePath, GeomNode, CollisionNode, CollisionRay, CollisionHandlerQueue, Geom, GeomVertexFormat, GeomVertexData, GeomVertexWriter, GeomLines, LVector3, Quat, CollisionSegment, CollisionTube, LPoint2f, Point3, Plane, CollisionPolygon

from direct.showbase.DirectObject import DirectObject
import math
import numpy as np

from .utilities import create_arrow_with_endpoints, create_circle, random_rgba

LENGTH_FACTOR = 0.7  # size of the gizmo relative to the vector length

class DraggableVector(DirectObject):
    """
    A 3D vector (arrow) that can be clicked and rotated interactively.

    This is a common UI element in 3D editors and is often
    called a "gizmo" or "rotation manipulator."
    see also: https://discourse.panda3d.org/t/manipulators-gizmos/10086
    https://github.com/Derfies/panda3d-editor
    """

    def __init__(self, parent,
                 pos: tuple = (0, 0, 0),
                 direction: tuple = (1, 1, 1),
                 length: float = 2.0,
                 color: tuple = (1, 0, 0, 1),
                 thickness: float = 0.2,
                 head_size: float = 0.4,
                 name: str = "DraggableVector"):

        self.parent = parent
        self.root = parent.render.attachNewNode(name)
        self.root.setPos(*pos)
        self.length = length
        self.color = color
        self.name = name
        self.root_quat = Quat()  # For the main vector

        self.root.setTag("draggable_vector", self.name)

        self.gizmo_circle_styles = {
            "ra": {"color": (0.2, 0.2, 1, 1), "thickness": 5},
            "dec": {"color": (0.2, 1, 0.2, 1), "thickness": 5},
        }

        self.arrow_start = (0, 0, 0)
        # Normalize the direction vector and scale it by length
        direction_vector = LVector3(*direction)
        if direction_vector.length() > 0:
            direction_vector.normalize()
        self.arrow_end = direction_vector * self.length

        self.arrow_np = self._create_arrow(thickness=thickness, head_size=head_size)
        self.arrow_np.reparentTo(self.root)

        # Show the rotation gizmo at all times
        self.show_rotation_gizmo(pos)

        self.accept("mouse3", self.on_mouse_click)
        self.dragging = False
        self.last_mouse = None

    def highlight_gizmo_circle(self, axis, highlight=True):
        idx = 0 if axis == "ra" else 1
        circle = self.gizmo_nodes[idx]
        style = self.gizmo_circle_styles[axis]
        if highlight:
            circle.setRenderModeThickness(style["thickness"]*2)  # increate thickness
        else:
            circle.setRenderModeThickness(style["thickness"])

    def show_rotation_gizmo(self, pos):
        self.hide_rotation_gizmo()

        # Create a single node to serve as the rigid gizmo.
        self.gizmo_node = self.parent.render.attachNewNode("gizmo_node")
        self.gizmo_node.setPos(pos)

        # Create the two circles as children of the gizmo node.
        # RA circle: intended normal (in its own local space) is along local Z.
        c1 = create_circle(radius=self.length*LENGTH_FACTOR,
                           color=self.gizmo_circle_styles['ra']['color'],
                           axis='z',
                           thickness=self.gizmo_circle_styles['ra']['thickness'])
        c1.setTag("gizmo_axis", "ra")
        c1.reparentTo(self.gizmo_node)

        # Dec circle: intended normal is along local X.
        c2 = create_circle(radius=self.length*LENGTH_FACTOR,
                           color=self.gizmo_circle_styles['dec']['color'],
                           axis='x',
                           thickness=self.gizmo_circle_styles['dec']['thickness'])
        c2.setTag("gizmo_axis", "dec")
        c2.reparentTo(self.gizmo_node)

        self.gizmo_nodes = [c1, c2]

        # Add precise collision shapes using CollisionPolygon
        for c, axis, radius in zip(self.gizmo_nodes, ['z', 'x'],
                                   [self.length * LENGTH_FACTOR,
                                    self.length * LENGTH_FACTOR]):
            col_node = CollisionNode(f"gizmo_{axis}_col")
            num_segments = 32  # Number of segments to approximate the circle
            for i in range(num_segments):
                angle1 = (i / num_segments) * 2 * math.pi
                angle2 = ((i + 1) / num_segments) * 2 * math.pi
                if axis == 'z':
                    # RA circle lies in the XY plane
                    p1 = Point3(radius * math.cos(angle1), radius * math.sin(angle1), 0)
                    p2 = Point3(radius * math.cos(angle2), radius * math.sin(angle2), 0)
                elif axis == 'x':
                    # Dec circle lies in the XZ plane
                    # [but because of how it was drawn, it works here as x-y plane for some reason]
                    p1 = Point3(radius * math.cos(angle1), radius * math.sin(angle1), 0)
                    p2 = Point3(radius * math.cos(angle2), radius * math.sin(angle2), 0)
                else:
                    continue
                col_node.addSolid(CollisionPolygon(Point3(0, 0, 0), p1, p2))

            col_node.setIntoCollideMask(GeomNode.getDefaultCollideMask())
            col_np = c.attachNewNode(col_node)
            # col_np.show()  # For debugging; remove if desired
            col_np.setColor(1, 0, 1, 1)

    def hide_rotation_gizmo(self):
        if hasattr(self, "gizmo_nodes"):
            for n in self.gizmo_nodes:
                n.removeNode()
            self.gizmo_nodes = []

    def _create_arrow(self, thickness: float = 0.2, head_size: float = 0.4):
        arrow_np = create_arrow_with_endpoints(
            self.arrow_start,
            self.arrow_end,
            color=self.color,
            thickness=thickness,
            head_size=head_size
        )
        arrow_np.setLightOff()
        return arrow_np

    def on_mouse_click(self):
        if not self.parent.mouseWatcherNode.hasMouse():
            return
        mpos = self.parent.mouseWatcherNode.getMouse()
        self.parent.pickerRay.setFromLens(self.parent.camNode, mpos.getX(), mpos.getY())
        self.parent.picker.traverse(self.parent.render)
        if self.parent.pq.getNumEntries() > 0:
            self.parent.pq.sortEntries()
            pickedObj = self.parent.pq.getEntry(0).getIntoNodePath()
            axis = pickedObj.findNetTag("gizmo_axis")
            if not axis.isEmpty():
                # print("Picked axis:", axis.getTag("gizmo_axis"))
                self.active_axis = axis.getTag("gizmo_axis")
                self.start_gizmo_drag()
                return

    def start_gizmo_drag(self):

        # Determine rotation axis from the picked circle.
        if self.active_axis == "ra":
            self.drag_axis = LVector3(0, 0, 1)  # World-space Z-axis
        elif self.active_axis == "dec":
            self.drag_axis = LVector3(0, 1, 0)  # World-space y-axis

        self.highlight_gizmo_circle(self.active_axis, highlight=True)
        self.parent.block_camera_events = True
        self.dragging = True
        self.last_mouse = self.parent.mouseWatcherNode.getMouse()
        self.accept("mouse1-up", self.stop_gizmo_drag)
        self.parent.taskMgr.add(self.drag_task, f"{self.name}_drag_task")
        for event, _ in self.parent._camera_events:
            self.parent.ignore(event)

    def stop_gizmo_drag(self):
        if self.active_axis:
            self.highlight_gizmo_circle(self.active_axis, highlight=False)

        self.parent.block_camera_events = False
        self.dragging = False
        self.ignore("mouse1-up")
        self.parent.taskMgr.remove(f"{self.name}_drag_task")
        for event, handler in self.parent._camera_events:
            self.parent.accept(event, handler)
        self.active_axis = None

    def mouse_to_world(self, mouse, axis):
        # Get the camera and lens
        cam = self.parent.cam
        lens = self.parent.camLens
        origin = self.root.getPos(self.parent.render)

        # Get the mouse ray in world coordinates
        near_point = Point3()
        far_point = Point3()
        if not lens.extrude(mouse, near_point, far_point):
            return origin
        near_point = self.parent.render.getRelativePoint(cam, near_point)
        far_point = self.parent.render.getRelativePoint(cam, far_point)

        # The plane is through the origin, perpendicular to the axis
        plane = Plane(axis, origin)
        intersection = Point3()
        if plane.intersectsLine(intersection, near_point, far_point):
            return intersection
        else:
            return origin

    def drag_task(self, task):
        if not self.dragging or not self.parent.mouseWatcherNode.hasMouse():
            return task.cont

        mpos = self.parent.mouseWatcherNode.getMouse()
        origin = self.root.getPos(self.parent.render)

        # Use the stored drag_axis directly (in world space)
        axis = self.drag_axis

        if axis is not None:
            prev_world = self.mouse_to_world(self.last_mouse, axis)
            curr_world = self.mouse_to_world(mpos, axis)
            v_prev = prev_world - origin
            v_curr = curr_world - origin
            if v_prev.length() > 0.001 and v_curr.length() > 0.001:
                v_prev.normalize()
                v_curr.normalize()
                angle_rad = math.atan2(axis.dot(v_prev.cross(v_curr)), v_prev.dot(v_curr))
                rotation = Quat()
                rotation.setFromAxisAngleRad(angle_rad, axis)
                # Rotate the vector using computed quaternion.
                self.root_quat = self.root_quat * rotation
                self.root.setQuat(self.root_quat)

                # just a test to do something with the rotation
                # in this case, change the color of the manifold
                #hpr = self.root_quat.getHpr()
                #ra = hpr[0] % 360
                #dec = hpr[1] % 180 - 90
                #self.parent.manifold.set_color((abs(ra/180), abs(dec/90), 0, 1))

        self.last_mouse = LPoint2f(mpos.getX(), mpos.getY())
        return task.cont

    def destroy(self):
        self.ignoreAll()
        self.arrow_np.removeNode()
        self.root.removeNode()