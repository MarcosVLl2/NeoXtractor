import os
import numpy as np
from PyQt5 import QtCore, QtOpenGL
from PyQt5.QtWidgets import *
import moderngl
from converter import parse_mesh_helper, parse_mesh_original, parse_mesh_adaptive

class QModernGLWidget(QtOpenGL.QGLWidget):
    def __init__(self, parent=None):
        fmt = QtOpenGL.QGLFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QtOpenGL.QGLFormat.CoreProfile)
        fmt.setSampleBuffers(True)
        self.timer = QtCore.QElapsedTimer()
        super().__init__(fmt, parent=parent)

    def initializeGL(self):
        pass

    def paintGL(self):
        self.ctx = moderngl.create_context()
        self.screen = self.ctx.detect_framebuffer()
        self.init()
        self.render()
        self.paintGL = self.render

    def init(self):
        pass

    def render(self):
        pass

def data_from_path(path):
    data = None
    with open(path, 'rb') as f:
        data = f.read()
    return data

def text_from_path(path):
    text = None
    with open(path) as f:
        text = f.read()
    return text

def shader_from_path(path):
    return text_from_path('shader/' + path)

def compile_shader_program(ctx, vertex_path, fragment_path):
    # Read vertex and fragment shader sources
    vertex_shader_source = text_from_path(vertex_path)
    fragment_shader_source = text_from_path(fragment_path)

    try:
        program = ctx.program(
            vertex_shader=vertex_shader_source,
            fragment_shader=fragment_shader_source,
        )
        print("Shader program compiled and linked successfully.")
        return program
    except Exception as e:
        print(f"Error compiling and linking shader program: {e}")
        return None

def res_from_path(path):
    return data_from_path('res/' + path)

def mesh_from_path(path):
    try:
            print(f"Parsing mesh using original parser")
            mesh = parse_mesh_original(path)
            if mesh is None or 'position' not in mesh:
                raise ValueError("original parser failed.")
    except Exception as e:
        print(f"original parser failed: {e}. Attempting to use helper instead.")
        try:
            mesh = parse_mesh_helper(path) # Atempting second parser
            if mesh is None or 'position' not in mesh:
                raise ValueError("helper parser failed.")
        except Exception as e2:
            print(f"helper parser also failed: {e2}. Attempting to use adaptive instead.")
            try:
                mesh = parse_mesh_adaptive(path)  # Atempting third parser
                if mesh is None or 'position' not in mesh:
                    raise ValueError("adaptive parser failed.")
            except Exception as e3:
                QMessageBox.critical(None, "Error", f"Failed to parse mesh file: {e}")
                raise None

    # Proceed if we have a valid mesh
    pos = np.array(mesh['position'])
    pos[:, 0] = -pos[:, 0]  # Flip X-axis
    norm = np.array(mesh['normal'])
    norm[:, 0] = -norm[:, 0]  # Flip X-axis for normals as well

    # Combine position and normals into a single array
    dat = np.hstack((pos, norm))
    mesh['gldat'] = dat

    # Reorder indices for OpenGL
    index = np.array(mesh['face'])
    index = index[:, [1, 0, 2]]
    mesh['glindex'] = index

    print(f"Successfully parsed and processed mesh")
    return mesh

def log(*args, **kwargs):
    print('log: ', *args, **kwargs)

def grid(size, steps):
    u = np.repeat(np.linspace(-size, size, steps), 2)
    v = np.tile([-size, size], steps)
    w = np.zeros(steps * 2)
    return np.concatenate([np.dstack([u, w, v]), np.dstack([v, w, u])])

def file_names_from_dir(path):
    file_names = os.listdir(path)
    file_names = list(filter(lambda s: s.endswith('.mesh'), file_names))
    return file_names

def file_paths_from_dir(path):
    file_names = file_names_from_dir(path)
    file_paths = list(map(lambda s: path + '/' + s, file_names))
    return file_paths
