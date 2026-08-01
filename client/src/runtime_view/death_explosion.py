"""Death explosion: the Delver's skeleton parts detach and fly around.

Any death cause (hazard, fall, ...) triggers the same scattering. Gameplay
death is decided by the Rust engine (which freezes the world); this effect is
visual-only sugar for viewing mode. It detaches every skeleton slot via
pyglet_dragonbones and drives the freed sprites with a client-side pymunk
simulation, so it never runs in headless/training runtimes.
"""

import math
import random

import pymunk
import pyglet
from pyglet_dragonbones import DetachedPart
from pytiling.pyglet_support.utils import set_pixelated_scaling

from runtime.config import GRAVITY
from src.config import config


class DeathExplosionEffect:
    """Watches for the Delver's death and replaces the corpse with flying parts."""

    def __init__(self, runtime):
        self._runtime = runtime
        self._space: pymunk.Space | None = None
        self._batch: pyglet.graphics.Batch | None = None
        self._parts: list[tuple[DetachedPart, pymunk.Body]] = []
        self._rng = random.Random()
        self._despawn_y = 0.0
        self._gif_sprite: pyglet.sprite.Sprite | None = None

    @property
    def active(self) -> bool:
        return self._space is not None

    def update(self, dt: float):
        if not self.active:
            self._maybe_trigger()
            return

        if not self._parts:
            return

        cfg = config.DEATH_EXPLOSION
        self._space.step(min(dt, cfg.MAX_DT))

        kept: list[tuple[DetachedPart, pymunk.Body]] = []
        for part, body in self._parts:
            if body.position.y < self._despawn_y:
                self._space.remove(body, *body.shapes)
                part.delete()
                continue
            # pymunk rotates counterclockwise; pyglet sprites clockwise.
            part.set_pose(body.position.x, body.position.y, -math.degrees(body.angle))
            kept.append((part, body))
        self._parts = kept

    def draw(self):
        if self._batch is not None:
            self._batch.draw()

    def _maybe_trigger(self):
        delver = self._runtime.delver
        if not self._runtime.physics or delver.in_replay or delver.skeleton is None:
            return
        state = self._runtime.physics_engine.get_delver()
        if state.is_dead:
            self._trigger(state)

    def _trigger(self, state):
        self._batch = pyglet.graphics.Batch()
        self._apply_part_displays()
        parts = self._runtime.delver.skeleton.detach_all_slots(batch=self._batch)
        if not parts:
            return
        self._spawn_death_animation(parts)

        self._space = pymunk.Space()
        self._space.gravity = (0.0, float(GRAVITY))
        self._space.damping = config.DEATH_EXPLOSION.AIR_DAMPING
        # Screen-space world bottom edge sits one tile above y=0.
        tile_h = self._runtime.level.map.tile_size[1]
        self._despawn_y = tile_h - config.DEATH_EXPLOSION.DESPAWN_DEPTH
        self._add_static_geometry()

        for part in parts:
            body = self._spawn_part_body(part, (state.x, state.y))
            self._parts.append((part, body))

    def _apply_part_displays(self):
        """Switch configured slots to their death-frame displays before detach."""
        displays = getattr(config.DEATH_EXPLOSION.PART_DISPLAYS, "_data", {})
        if not displays:
            return
        skeleton = self._runtime.delver.skeleton
        for slot_name, display_name in displays.items():
            slot = (skeleton.slots or {}).get(slot_name)
            if slot is None:
                continue
            for index, subtexture in enumerate(slot.subtextures):
                if subtexture["name"] == display_name:
                    slot.change_display(index)
                    break

    def _spawn_death_animation(self, parts: list[DetachedPart]):
        """Play the death GIF once, centered on the body's visual center."""
        cfg = config.DEATH_EXPLOSION
        path = config.ASSETS_PATH / cfg.GIF_PATH
        if not path.exists():
            return

        animation = pyglet.image.load_animation(str(path))
        for frame in animation.frames:
            # Anchor first: get_texture() caches, and the anchor is only copied
            # into the texture at creation time.
            frame.image.anchor_x = frame.image.width // 2
            frame.image.anchor_y = frame.image.height // 2
            # GL_NEAREST: keep the pixel art crisp like every other sprite.
            set_pixelated_scaling(frame.image)

        center_x = sum(part.center[0] for part in parts) / len(parts)
        center_y = sum(part.center[1] for part in parts) / len(parts)
        sprite = pyglet.sprite.Sprite(
            animation, x=center_x, y=center_y, batch=self._batch
        )
        sprite.scale = cfg.GIF_SCALE
        self._gif_sprite = sprite
        # The GIF is not loopable: pyglet would wrap to frame 0, so delete on end.
        sprite.push_handlers(
            on_animation_end=lambda: self._on_death_animation_end(sprite)
        )

    def _on_death_animation_end(self, sprite: pyglet.sprite.Sprite):
        sprite.delete()
        if self._gif_sprite is sprite:
            self._gif_sprite = None

    def _add_static_geometry(self):
        """Static boxes for platform tiles, in screen (sprite) coordinates.

        Parts live in screen space, which pytiling renders one tile above
        physics space (grid_pos_to_actual_pos inverts Y as
        map_height - ty*tile_h), so the colliders must use that same mapping.

        Contiguous horizontal runs merge into one box: per-tile boxes share
        edges, and fast small parts slip through those seams.
        """
        tilemap = self._runtime.level.map.tilemap
        platforms = tilemap.get_layer("platforms")
        height, _ = platforms.grid.shape
        tile_w, tile_h = self._runtime.level.map.tile_size

        rows: dict[int, list[int]] = {}
        for tile in platforms.tiles:
            tx, ty = tile.position
            rows.setdefault(ty, []).append(tx)

        cfg = config.DEATH_EXPLOSION
        static = self._space.static_body
        for ty, xs in rows.items():
            xs.sort()
            run_start = previous = xs[0]
            for tx in xs[1:] + [None]:
                if tx is not None and tx == previous + 1:
                    previous = tx
                    continue
                x0 = run_start * tile_w
                x1 = (previous + 1) * tile_w
                y0 = (height - ty) * tile_h
                y1 = y0 + tile_h
                shape = pymunk.Poly(
                    static,
                    [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                )
                shape.friction = cfg.TILE_FRICTION
                shape.elasticity = cfg.TILE_RESTITUTION
                self._space.add(shape)
                if tx is not None:
                    run_start = previous = tx

    def _spawn_part_body(self, part: DetachedPart, death_center) -> pymunk.Body:
        cfg = config.DEATH_EXPLOSION
        width, height = part.scaled_size
        width = max(width, 1.0)
        height = max(height, 1.0)

        mass = width * height * cfg.PART_DENSITY
        moment = pymunk.moment_for_box(mass, (width, height))
        body = pymunk.Body(mass, moment)
        center_x, center_y = part.center
        body.position = (center_x, center_y)
        body.angle = -math.radians(part.rotation)

        dx, dy = center_x - death_center[0], center_y - death_center[1]
        distance = math.hypot(dx, dy)
        if distance < 1e-3:
            angle = self._rng.uniform(0.0, math.tau)
            dx, dy = math.cos(angle), math.sin(angle)
        else:
            dx, dy = dx / distance, dy / distance
        speed = cfg.SPEED * (0.6 + 0.8 * self._rng.random())
        body.velocity = (dx * speed, dy * speed + cfg.UPWARD_BIAS)
        body.angular_velocity = self._rng.uniform(-cfg.MAX_SPIN, cfg.MAX_SPIN)

        shape = pymunk.Poly.create_box(body, (width, height))
        shape.friction = cfg.PART_FRICTION
        shape.elasticity = cfg.PART_RESTITUTION
        # Parts share a non-zero collision group: they hit tiles, not each other.
        shape.filter = pymunk.ShapeFilter(group=1)
        self._space.add(body, shape)
        return body
