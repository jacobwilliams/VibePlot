#version 120

attribute vec4 p3d_Vertex;
attribute vec4 p3d_Color;
attribute float size;
varying vec4 vertex_color;

void main() {
    gl_Position = gl_ModelViewProjectionMatrix * p3d_Vertex;
    gl_PointSize = size;
    vertex_color = p3d_Color;
}