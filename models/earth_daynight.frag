#version 120
varying vec2 texcoord;
varying vec3 normal;
uniform sampler2D day;
uniform sampler2D night;
uniform vec3 sundir;
void main() {
    float NdotL = max(dot(normalize(normal), normalize(sundir)), 0.0);
    vec4 dayColor = texture2D(day, texcoord);
    vec4 nightColor = texture2D(night, texcoord);
    gl_FragColor = mix(nightColor, dayColor, NdotL);
}