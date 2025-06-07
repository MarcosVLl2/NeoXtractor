#version 440

layout(location = 0) in vec3 in_vert;
layout(location = 1) in vec3 in_color;

layout(location = 0) out vec3 out_color;

layout(std140, binding = 0) uniform UniformBufferObject {
    mat4 mvp;
};

void main() {
    gl_Position = mvp * vec4(in_vert, 1.0);
    out_color = in_color;
}
