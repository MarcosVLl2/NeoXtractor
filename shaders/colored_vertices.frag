#version 440

layout(location = 0) in vec3 out_color;

layout(location = 0) out vec4 f_color;

void main() {
    f_color = vec4(out_color, 1.0);
}
