from pyrr import Matrix44, Vector3
import numpy as np
import transformations as tf
import moderngl as mgl
from gui.camera import *
from utils.util import *
from gui.viewer_3d import *

class Scene:
    def __init__(self, ctx, viewer):
        self.ctx = ctx
        self.viewer = viewer
        self.normals_vao = None

        # Enable depth testing and disable blending for opaque rendering
        self.ctx.enable(mgl.DEPTH_TEST)
        self.ctx.disable(mgl.BLEND)

        # Initialize camera, shaders, and resources
        self.camera = Camera()
        self._init_shader()
        self.load_grid()
        self.load_point()

        # Initialize matrices and scaling
        self.mesh_center = Vector3([0, 1, 0])
        self.model_scale = 1.0
        self.base_model_matrix = Matrix44.identity()
        self.model_matrix = Matrix44.identity()
        self.show_bones = True
        self.show_normals = False
        self.show_wireframe = False
        self.bone_lines = []
        
        # Initialize mesh data placeholders
        self.vbo = None
        self.ibo = None
        self.vao = None

        self.armature_loaded = False

    def _init_shader(self):
        self._init_mesh_shader()
        self._init_grid_shader()
        self._init_point_shader()
        self._init_line_shader()  # Initialize line shader for armature

    def _init_grid_shader(self):
        grid_vertex_shader = shader_from_path('basic.vert')
        grid_fragment_shader = shader_from_path('basic.frag')

        self.grid_prog = self.ctx.program(
            vertex_shader=grid_vertex_shader,
            fragment_shader=grid_fragment_shader,
        )
        self.grid_mvp = self.grid_prog['mvp']
        self.grid_const_color = self.grid_prog['const_color']

    def _init_point_shader(self):
        point_vertex_shader = shader_from_path('point.vert')
        point_fragment_shader = shader_from_path('point.frag')

        self.point_prog = self.ctx.program(
            vertex_shader=point_vertex_shader,
            fragment_shader=point_fragment_shader,
        )
        self.point_mvp = self.point_prog['mvp']
        self.point_const_color = self.point_prog['const_color']

    def _init_line_shader(self):
        line_vertex_shader = shader_from_path('line.vert')
        line_fragment_shader = shader_from_path('line.frag')

        self.line_shader = self.ctx.program(
            vertex_shader=line_vertex_shader,
            fragment_shader=line_fragment_shader,
        )

    def _init_mesh_shader(self):
        vertex_shader = shader_from_path('basic_w_norm.vert')
        fragment_shader = shader_from_path('basic_w_norm.frag')
        self.prog = self.ctx.program(
            vertex_shader=vertex_shader,
            fragment_shader=fragment_shader,
        )
        self.mv = self.prog['mv']
        self.mvp = self.prog['mvp']
        self.const_color = self.prog['const_color']

    def scale_mesh(self, scale_factor):
        """Scale both mesh and armature uniformly, keeping them aligned."""
        relative_scale = scale_factor / 10.0

        self.model_matrix = self.base_model_matrix * Matrix44.from_scale([relative_scale] * 3)
        self.armature_matrix = self.base_armature_matrix * Matrix44.from_scale([relative_scale] * 3)

    def load_mesh(self, mesh):
        self.release_mesh()
        self.release_armature()
        self.mesh = mesh

        print("Attempting to load mesh with basic shader.")

        # Set up vertex and index buffers
        self.vbo = self.ctx.buffer(mesh['gldat'].astype('f4').tobytes())
        self.ibo = self.ctx.buffer(mesh['glindex'].astype('i4').tobytes())
        vao_content = [(self.vbo, '3f 3f', 'in_vert', 'in_norm')]
        self.vao = self.ctx.vertex_array(self.prog, vao_content, self.ibo)

        # Initialize model matrix
        self.model = Matrix44.identity()

        # Load armature data if it exists
        if 'bone_name' in mesh and 'bone_parent' in mesh:
            self.load_armature(mesh)
            print("Armature loaded successfully.")
        else:
            print("No armature data found; skipping armature load.")
        
        self.viewer.update_aspect_ratio()
        self.viewer.update()
        print("Model loaded successfully.")
        
        # Initialize normals VAO for visualization
        self.setup_normals_vao()
        print("Mesh loaded successfully with basic shader.")

    def setup_normals_vao(self):
        if hasattr(self, 'mesh') and 'gldat' in self.mesh:
            # Proceed with setting up the normals VAO as before
            positions = self.mesh['gldat'][:, 0:3]
            normals = self.mesh['gldat'][:, 3:6]
            line_vertices = np.empty((positions.shape[0] * 2, 3), dtype='f4')
            line_vertices[0::2] = positions
            line_vertices[1::2] = positions + normals * 0.008

            self.normals_vbo = self.ctx.buffer(line_vertices.tobytes())
            self.normals_vao = self.ctx.simple_vertex_array(self.line_shader, self.normals_vbo, 'in_vert')
            print("Normals VAO initialized successfully.")
        else:
            print("Mesh data is missing or improperly initialized; skipping normals VAO setup.")

    def load_armature(self, mesh):
        # Extract armature data from mesh
        bone_positions = []
        bone_lines = []
        
        # Calculate each bone's position and connections
        for i, parent in enumerate(mesh['bone_parent']):
            matrix = mesh['bone_original_matrix'][i]
            pos = Vector3(tf.translation_from_matrix(matrix.T))
            bone_positions.append(pos)
            
            # Only create a line if the bone has a parent
            if parent != -1:
                parent_pos = Vector3(tf.translation_from_matrix(mesh['bone_original_matrix'][parent].T))
                bone_lines.extend([pos, parent_pos])
        
        # Store and setup the bone VAO
        self.bone_vbo = self.ctx.buffer(np.array(bone_lines, dtype='f4').tobytes())
        self.bone_vao = self.ctx.simple_vertex_array(self.line_shader, self.bone_vbo, 'in_vert')
        print("Armature loaded successfully.")

    def load_grid(self):
        self.grid_vbo = self.ctx.buffer(grid(5, 10).astype('f4').tobytes())
        self.grid_vao = self.ctx.simple_vertex_array(self.grid_prog, self.grid_vbo, 'in_vert')
        self.grid_model = Matrix44.from_translation((0, 0, 0))

    def load_point(self):
        self.point_vbo = self.ctx.buffer(np.array([0.0, 0.0, 0.0]).astype('f4').tobytes())
        self.point_vao = self.ctx.simple_vertex_array(self.point_prog, self.point_vbo, 'in_vert')
        self.point_model = Matrix44.from_translation((0, 0, 0))

    def clear(self, color=(0.23, 0.23, 0.23)):
        self.ctx.clear(*color, depth=1.0)

    def draw(self):
        self.clear()
        self.draw_grid()
        self.draw_point()
        self.draw_mesh()
        self.draw_armature()
        self.draw_normals()

    def draw_grid(self):
        mvp = self.camera.view_proj() * self.grid_model
        self.grid_mvp.write(mvp.astype('f4').tobytes())
        self.grid_const_color.value = (0.3, 0.3, 0.3)
        self.grid_vao.render(mgl.LINES)

    def draw_point(self):
        mvp = self.camera.view_proj() * self.point_model
        self.point_mvp.write(mvp.astype('f4').tobytes())
        self.point_const_color.value = (1.0, 0.0, 0.0)
        self.point_vao.render(mgl.POINTS)

    def draw_mesh(self):
        if self.vao:
            # Set up the transformation matrices
            mv = self.camera.view() * self.model
            mvp = self.camera.proj() * mv
            self.mv.write(mv.astype('f4').tobytes())
            self.mvp.write(mvp.astype('f4').tobytes())

            # Set the mesh color
            self.const_color.value = (0.8, 0.8, 0.8)  # Light gray color

            self.ctx.enable (mgl.DEPTH_TEST)

            # Render the mesh
            self.vao.render(mgl.TRIANGLES)

    def draw_normals(self):
        if self.normals_vao is not None and self.show_normals:
            mvp = self.camera.view_proj() * self.model_matrix
            self.line_shader['mvp'].write(mvp.astype('f4').tobytes())
            self.normals_vao.render(mgl.LINES)

            # Set color for the lines
            if 'color' in self.line_shader:
                self.line_shader['color'].value = (0.8, 0.1, 0.3)

            # Render vertices as points in `draw` function (or similar)
            self.ctx.point_size = 0.08  # Set point size
            self.vao.render(mgl.POINTS)

    def draw_armature(self):
        """Draws the armature if loaded."""
        if self.show_bones and hasattr(self, 'bone_vao') and self.bone_vao:
            mvp = self.camera.view_proj() * Matrix44.identity()
            self.line_shader['mvp'].write(mvp.astype('f4').tobytes())
            
            # Set color for the armature lines
            if 'color' in self.line_shader:
                self.line_shader['color'].value = (1.0, 0.8, 0.3)

            self.ctx.disable (mgl.DEPTH_TEST)

            # Render armature lines
            self.bone_vao.render(mgl.LINES)

            self.ctx.point_size = 4.0
            self.bone_vao.render(mgl.POINTS)

    def release_mesh(self):
        if hasattr(self, 'vao') and self.vao:
            self.vao.release()
            self.vbo.release()
            self.ibo.release()
            del self.vao, self.vbo, self.ibo

    def release_armature(self):
        if hasattr(self, 'bone_vao'):
            self.bone_vao.release()
            self.bone_vbo.release()
            del self.bone_vao, self.bone_vbo
        self.bone_lines = []
        self.armature_loaded = False

    def get_selected_object_center(self):
        return self.mesh_center

