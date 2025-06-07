#version 440

layout(location = 0) in vec3 in_vert;
layout(location = 1) in vec3 in_norm;

layout(location = 0) out float intensity;

layout(std140, binding = 0) uniform UniformBufferObject {
    mat4 mv;
    mat4 mvp;
};

void main() {
    vec3 norm = normalize(transpose(inverse(mat3(mv))) * in_norm);
    intensity = abs(dot(norm, vec3(0.0, 0.0, 1.0))) * 0.6 + 0.4;
    gl_Position = mvp * vec4(in_vert, 1.0);
}
