#version 120
varying vec2 texcoord;
varying vec3 normal;
uniform sampler2D day;
uniform sampler2D night;
uniform vec3 sundir;
void main() {
    float NdotL = dot(normalize(normal), normalize(sundir));
    // Use smoothstep for a soft but sharper edge
    //float blend = smoothstep(-0.02, 0.02, NdotL);
    float blend = smoothstep(-0.05, 0.05, NdotL);
    vec4 dayColor = texture2D(day, texcoord);
    vec4 nightColor = texture2D(night, texcoord);
    gl_FragColor = mix(nightColor, dayColor, blend);
}