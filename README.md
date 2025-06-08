Vibe coding 3D spacecraft trajectory graphics.

### Example:

![example](media/example.gif)


### To run (using pixi):

```
pixi shell --manifest-path ./env/pixi.toml
python test.py
```

Keys:
 * 'a' -- pause/reset the animation
 * space -- recenter the camera view
 * 'r' -- start/stop `.mp4` movie capture
 * 's' -- toggle display of the labels
 * '1' -- center on Earth-fixed frame
 * '2' -- center on Moon-fixed frame
 * '3' -- center on Mars-fixed frame
 * '4' -- center on Venus-fixed frame
 * '5' -- center on Site-fixed frame
 * 'shift-1' -- center on Earth, in the base frame
 * 'shift-2' -- center on Moon, in the base frame
 * 'shift-3' -- center on Mars, in the base frame
 * 'shift-4' -- center on Venus, in the base frame
 * 'shift-5' -- center on Site, in the base frame
 * '6' -- look at Mars from the surface of Venus

### See also

* [Panda3D](https://www.panda3d.org)
* [Solar Textures](https://www.solarsystemscope.com/textures/)