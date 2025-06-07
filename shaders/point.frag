#version 440

layout(location = 0) out vec4 f_color;

layout(std140, binding = 1) uniform UniformBufferObject {
    vec3 color;
};

void main() {
    if (length(gl_PointCoord - vec2(0.5)) > 0.5) {
        discard;
    }
    f_color = vec4(color, 1.0);
}
