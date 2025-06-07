#version 440

layout(location = 0) in float intensity;

layout(location = 0) out vec4 f_color;

layout(std140, binding = 1) uniform UniformBufferObject {
    vec3 color;
};

void main() {
    f_color = vec4(color * intensity, 1.0);
}
