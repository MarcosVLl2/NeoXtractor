#version 440

layout(location = 0) in vec3 in_vert;
layout(location = 1) in float point_size;

layout(std140, binding = 0) uniform UniformBufferObject {
    mat4 mvp;
};

void main() {
    gl_Position = mvp * vec4(in_vert, 1.0);
    gl_PointSize = point_size;
}
