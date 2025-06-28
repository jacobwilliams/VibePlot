from panda3d.core import Point3, Vec4, NodePath
from direct.particles.ParticleEffect import ParticleEffect
from direct.particles.Particles import Particles
from direct.showbase.ShowBase import ShowBase
from panda3d.physics import BaseParticleRenderer, BaseParticleEmitter

class FireEffect:
    def __init__(
        self,
        parent: ShowBase,
        target_np: NodePath,
        radius: float,
        scale: float = 1.05,
        texture: str = "models/fire.png",
        color: Vec4 = Vec4(1, 0.5, 0.1, 1),
        intensity: float = 1.0
    ):
        """
        Creates a fire particle effect around a target node.

        Args:
            parent: ShowBase instance (for taskMgr).
            target_np (NodePath): NodePath to attach the fire effect (e.g., body's _rotator).
            radius (float): Base radius of the body.
            scale (float, optional): Scale factor for the fire sphere. Defaults to 1.05.
            texture (str, optional): Path to the fire sprite texture (should have alpha). Defaults to "models/fire.png".
            color (Vec4, optional): Color for the fire. Defaults to Vec4(1, 0.5, 0.1, 1).
            intensity (float, optional): Multiplier for particle count. Defaults to 1.0.
        """
        self.parent = parent
        self.target_np = target_np
        self.radius = radius
        self.scale = scale
        self.texture = texture
        self.color = color
        self.intensity = intensity

        if self.parent.enable_particles:
            self.effect = ParticleEffect()
            self._setup_particles()
        else:
            self.effect = None
            print("Particle effects are not enabled.")

    def _setup_particles(self):
        """
        Sets up and starts the fire particle effect.
        """
        particles = Particles('fire')
        particles.setFactory("PointParticleFactory")
        particles.setRenderer("SpriteParticleRenderer")
        particles.setEmitter("SphereVolumeEmitter")
        particles.setPoolSize(int(512 * self.intensity))
        particles.setBirthRate(0.02)
        particles.setLitterSize(int(10 * self.intensity))
        particles.setLitterSpread(2)
        particles.setSystemLifespan(0.0)
        particles.setLocalVelocityFlag(True)
        particles.setSystemGrowsOlderFlag(False)

        # Factory parameters
        particles.factory.setLifespanBase(0.7)
        particles.factory.setLifespanSpread(0.3)
        particles.factory.setMassBase(1.0)
        particles.factory.setTerminalVelocityBase(400.0)

        # Renderer parameters
        particles.renderer.setAlphaMode(BaseParticleRenderer.PRALPHAOUT)
        particles.renderer.setUserAlpha(0.7)
        particles.renderer.setColor(self.color)
        particles.renderer.setXScaleFlag(True)
        particles.renderer.setYScaleFlag(True)
        particles.renderer.setInitialXScale(0.08 * self.scale)
        particles.renderer.setFinalXScale(0.18 * self.scale)
        particles.renderer.setInitialYScale(0.08 * self.scale)
        particles.renderer.setFinalYScale(0.18 * self.scale)
        particles.renderer.setTextureFromFile(self.texture)

        # Emitter parameters
        particles.emitter.setEmissionType(BaseParticleEmitter.ETRADIATE)
        particles.emitter.setAmplitude(0.2)
        particles.emitter.setAmplitudeSpread(0.1)
        particles.emitter.setRadius(self.radius * self.scale)

        self.effect.addParticles(particles)
        self.effect.start(parent=self.target_np, renderParent=self.target_np)

        self.target_np.setLightOff()

    def cleanup(self):
        """
        Cleans up the fire effect by disabling and removing the particle effect.
        """
        self.effect.disable()
        self.effect.cleanup()