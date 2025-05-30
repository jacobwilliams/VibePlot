#version 120

varying vec4 vertex_color;

void main() {
    vec2 c = gl_PointCoord - vec2(0.5);
    float dist = length(c);
    if (dist > 0.5) discard;
    gl_FragColor = vertex_color;
}
