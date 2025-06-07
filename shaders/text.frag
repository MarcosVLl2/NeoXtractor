#version 440

layout(location = 0) in vec2 v_texcoord;
layout(location = 1) in vec4 v_textcolor;

layout(location = 0) out vec4 fragColor;

layout(binding = 0) uniform UniformBufferObject {
    mat4 projection;
};

layout(binding = 1) uniform sampler2D atlas_texture;

void main() {
    float alpha = texture(atlas_texture, v_texcoord).r;
    fragColor = vec4(v_textcolor.rgb, alpha * v_textcolor.a);
}
