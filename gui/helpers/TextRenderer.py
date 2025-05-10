import moderngl
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyrr import Matrix44

class TextRenderer:
    def __init__(self, ctx: moderngl.Context, font_size=14):
        self.ctx = ctx

        # Enable blending for transparency
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        # Define shaders
        vertex_shader = """
        #version 330 core
        in vec2 in_position;
        in vec2 in_texcoord;
        out vec2 v_texcoord;
        uniform mat4 projection;
        
        void main() {
            gl_Position = projection * vec4(in_position, 0.0, 1.0);
            v_texcoord = in_texcoord;
        }
        """

        fragment_shader = """
        #version 330 core
        in vec2 v_texcoord;
        out vec4 fragColor;
        uniform sampler2D atlas_texture;
        uniform vec3 text_color;
        
        void main() {
            float alpha = texture(atlas_texture, v_texcoord).r;
            fragColor = vec4(text_color, alpha);
        }
        """

        self._create_texture_atlas(font_size)

        # Initialize shader program
        self.program = self.ctx.program(
            vertex_shader=vertex_shader,
            fragment_shader=fragment_shader
        )

        # Initialize vertex buffer and vertex array
        self.vertex_buffer = self.ctx.buffer(reserve=4096 * 4 * 6)
        self.vao = self.ctx.vertex_array(
            self.program,
            [(self.vertex_buffer, "2f 2f", "in_position", "in_texcoord")]
        )

    def _create_texture_atlas(self, font_size):
        # Create texture atlas using PIL
        atlas_size = 512
        atlas = Image.new('L', (atlas_size, atlas_size), 0)
        atlas_draw = ImageDraw.Draw(atlas)
        
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont
        try:
            font = ImageFont.truetype("./fonts/Roboto-Regular.ttf", font_size)
        except OSError:
            print("Failed to load font, falling back to default")
            font = ImageFont.load_default()
            
        # Create character map
        self.char_data: dict[str, Character] = {}
        cursor_x, cursor_y = 0, 0
        max_height = 0
        
        ascent, descent = font.getmetrics()
        total_height = ascent + descent
        
        for char_code in range(32, 128):
            char = chr(char_code)
            bbox = font.getbbox(char)
            char_width = bbox[2] - bbox[0]
            char_height = bbox[3] - bbox[1]
            
            if cursor_x + char_width >= atlas_size:
                cursor_x = 0
                cursor_y += total_height + 2
                max_height = 0
                
            if char_height > max_height:
                max_height = char_height
                
            # Draw character aligned to the baseline
            atlas_draw.text((cursor_x, cursor_y + ascent), char, font=font, fill=255, anchor="ls")
            
            self.char_data[char] = Character(
                (
                    cursor_x / atlas_size,
                    cursor_y / atlas_size,
                    (cursor_x + char_width) / atlas_size,
                    (cursor_y + total_height) / atlas_size
                ),
                (char_width, total_height),
                ascent
            )
            
            cursor_x += char_width + 2
            
        # Create ModernGL texture from atlas
        self.texture = self.ctx.texture(
            atlas.size, 1,
            atlas.tobytes(),
            dtype='f1'
        )
        self.texture.swizzle = 'RRRR'

    def render_text(self, text, x, y, scale, color=(1.0, 1.0, 1.0)):
        previous_wireframe_state = self.ctx.wireframe  # Save current wireframe state
        self.ctx.wireframe = False  # Disable wireframe for text rendering

        self.program['text_color'].value = color
        self.program['atlas_texture'].value = 0
        self.texture.use(location=0)

        # Set up orthographic projection
        projection = Matrix44.orthogonal_projection(0, self.ctx.viewport[2], 0, self.ctx.viewport[3], -1, 1)
        self.program['projection'].write(projection.astype('f4').tobytes())

        self.vertex_buffer.clear()

        vertices = []
        cursor_x = x

        for char in text:
            if char not in self.char_data:
                continue
                
            char_info = self.char_data[char]
            w, h = char_info.size
            w, h = w * scale, h * scale
            tex_coords = char_info.tex_coords
        
            # Position character relative to baseline
            char_y = y - (char_info.ascent * scale)
            
            quad = [
                cursor_x, char_y + h, tex_coords[0], tex_coords[1],
                cursor_x, char_y, tex_coords[0], tex_coords[3],
                cursor_x + w, char_y, tex_coords[2], tex_coords[3],
                cursor_x, char_y + h, tex_coords[0], tex_coords[1],
                cursor_x + w, char_y, tex_coords[2], tex_coords[3],
                cursor_x + w, char_y + h, tex_coords[2], tex_coords[1]
            ]
            vertices.extend(quad)
            cursor_x += w
            
        self.vertex_buffer.write(np.array(vertices, dtype='f4').tobytes())
        self.vao.render(moderngl.TRIANGLES)

        self.ctx.wireframe = previous_wireframe_state  # Restore original wireframe state


class Character:
    def __init__(self, tex_coords: tuple[int, int, int, int], size: tuple[int, int], ascent: int):
        self.tex_coords = tex_coords
        self.size = size
        self.ascent = ascent
