import numpy as np
import json5 as json
from panda3d.core import (GeomVertexFormat,
                          GeomVertexData,
                          GeomVertexWriter,
                          GeomTriangles,
                          Geom,
                          GeomNode,
                          GeomLines)


class Manifold:
    def __init__(self, parent,
                 mesh : str | list | np.ndarray,
                 color: tuple = (0.2, 0.7, 1, 0.5),
                 name : str = "Manifold",
                 draw_edges: bool = True,
                 edge_color: tuple = (1, 1, 1, 0.7),
                 edge_thickness: float = 1.0) -> None:
        """
        Create and draw a 3D manifold mesh as a tube connecting rings of points over time.

        Args:
            parent: The parent object (typically your ShowBase app) with a .render NodePath.
            mesh (str | list | np.ndarray): The mesh data.
                Can be a filename (JSON or .npy), a list, or a numpy array
                of shape (num_times, num_points, 3), where each time step is
                a ring of 3D points.
            color (tuple, optional): RGBA color for the mesh surface.
                Defaults to (0.2, 0.7, 1, 0.5).
            name (str, optional): Name for the mesh node.
                Defaults to "Manifold".
            draw_edges (bool, optional): Whether to draw edge lines on the mesh.
                Defaults to True.
            edge_color (tuple, optional): RGBA color for the edge lines.
                Defaults to (1,1,1,1).
            edge_thickness (float, optional): Thickness of the edge lines.
                Defaults to 1.0.

        Raises:
            ValueError: If the mesh array does not have shape (num_times, num_points, 3).
            TypeError: If mesh is not a filename, list, or numpy array.
        """

        self.parent = parent

        if isinstance(mesh, str):
            # Load from file
            self.mesh_history = self.load_mesh_history_from_file(mesh)
        elif isinstance(mesh, np.ndarray):
            # Ensure it's a numpy array
            if mesh.ndim != 3 or mesh.shape[2] != 3:
                raise ValueError("mesh_history must be a 3D array with shape (num_times, num_points, 3)")
            self.mesh_history = mesh
        elif isinstance(mesh, list):
            # Convert list to numpy array
            self.mesh_history = np.array(mesh)
        else:
            raise TypeError("mesh_history must be a filename (str), numpy array, or list of points")

        self.color = color
        self.name = name
        self.mesh_np = None
        self.draw_edges = draw_edges
        self.edge_color = edge_color
        self.edge_thickness = edge_thickness
        self.edge_np = None

        self.draw_tube_mesh()

    def load_mesh_history_from_file(self, filename : str) -> np.ndarray:
        """
        Reads mesh_history from a file (JSON or .npy).
        The file should contain:
            [
                [[x, y, z], ...],  # t0
                [[x, y, z], ...],  # t1
                ...
            ]
        Returns:
            mesh_history (np.ndarray)
        """
        if filename.endswith('.npy'):
            mesh_history = np.load(filename)
        else:
            with open(filename, "r") as f:
                mesh_history = json.load(f)
            mesh_history = np.array(mesh_history)
        return mesh_history

    def draw_tube_mesh(self):
        """Draw a tube mesh connecting corresponding points between time steps, with closed rings."""
        if self.mesh_np:
            self.mesh_np.removeNode()

        mesh = self.mesh_history
        num_times, num_points, _ = mesh.shape

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData('manifold', fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, 'vertex')
        color_writer = GeomVertexWriter(vdata, 'color')

        # Write all vertices for all time steps
        for t in range(num_times):
            for p in range(num_points):
                vertex.addData3(*mesh[t, p])
                color_writer.addData4(*self.color)

        # Build tube faces (quads as two triangles), with closed rings
        tris = GeomTriangles(Geom.UHStatic)
        for t in range(num_times - 1):
            for p in range(num_points):
                p_next = (p + 1) % num_points  # Wrap around for closed ring
                # Indices of the quad's corners
                i0 = t * num_points + p
                i1 = t * num_points + p_next
                i2 = (t + 1) * num_points + p_next
                i3 = (t + 1) * num_points + p
                # Two triangles per quad
                tris.addVertices(i0, i1, i2)
                tris.addVertices(i0, i2, i3)

        # Add end cap at the start (t=0)
        if mesh[0].shape[0] == 1:
            # Single point start (cone)
            center0_idx = num_times * num_points
            vertex.addData3(*mesh[0][0])
            color_writer.addData4(*self.color)
            for p in range(num_points):
                p_next = (p + 1) % num_points
                tris.addVertices(center0_idx, p_next, p)
        else:
            # Ring start (average center)
            center0 = np.mean(mesh[0], axis=0)
            center0_idx = num_times * num_points
            vertex.addData3(*center0)
            color_writer.addData4(*self.color)
            for p in range(num_points):
                p_next = (p + 1) % num_points
                tris.addVertices(center0_idx, p_next, p)

        # Add end cap at the end (t=num_times-1)
        center1 = np.mean(mesh[-1], axis=0)
        center1_idx = num_times * num_points + 1
        vertex.addData3(*center1)
        color_writer.addData4(*self.color)
        offset = (num_times - 1) * num_points
        for p in range(num_points):
            p_next = (p + 1) % num_points
            tris.addVertices(center1_idx, offset + p, offset + p_next)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode('manifold')
        node.addGeom(geom)
        self.mesh_np = self.parent.render.attachNewNode(node)
        self.mesh_np.setTransparency(True)
        self.mesh_np.setLightOff()
        # self.mesh_np.setTwoSided(True)

        # Draw edges if requested
        if self.edge_np:
            self.edge_np.removeNode()
            self.edge_np = None

        if self.draw_edges:
            edge_vdata = GeomVertexData('manifold_edges', GeomVertexFormat.getV3c4(), Geom.UHStatic)
            edge_vertex = GeomVertexWriter(edge_vdata, 'vertex')
            edge_color_writer = GeomVertexWriter(edge_vdata, 'color')

            # Write all vertices again for edges
            for t in range(num_times):
                for p in range(num_points):
                    edge_vertex.addData3(*mesh[t, p])
                    edge_color_writer.addData4(*self.edge_color)

            edges = GeomLines(Geom.UHStatic)
            # Connect each ring (closed)
            for t in range(num_times):
                for p in range(num_points):
                    i0 = t * num_points + p
                    i1 = t * num_points + (p + 1) % num_points
                    edges.addVertices(i0, i1)
            # Connect along the tube
            for t in range(num_times - 1):
                for p in range(num_points):
                    i0 = t * num_points + p
                    i1 = (t + 1) * num_points + p
                    edges.addVertices(i0, i1)

            edge_geom = Geom(edge_vdata)
            edge_geom.addPrimitive(edges)
            edge_node = GeomNode('manifold_edges')
            edge_node.addGeom(edge_geom)
            self.edge_np = self.parent.render.attachNewNode(edge_node)
            self.edge_np.setTransparency(True)
            self.edge_np.setLightOff()
            self.edge_np.setRenderModeThickness(self.edge_thickness)
            self.edge_np.setTwoSided(True)
            # try to fix depth fighting for the edge lines
            #self.edge_np.setDepthOffset(1)
            # Optionally, for always-on-top edges:
            self.edge_np.setBin('fixed', 100)
            self.edge_np.setDepthWrite(False)

    def destroy(self):
        if self.mesh_np:
            self.mesh_np.removeNode()
            self.mesh_np = None
        if self.edge_np:
            self.edge_np.removeNode()
            self.edge_np = None
