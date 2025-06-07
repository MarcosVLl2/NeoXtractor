#version 440

layout(location = 0) in vec2 tex_coord;
layout(location = 0) out vec4 f_color;

layout(std140, binding = 1) uniform UniformBufferObject {
    vec3 color;
};

void main() {
    if (length(tex_coord) > 1.0) {
        discard;
    }
    
    f_color = vec4(color, 1.0);
}