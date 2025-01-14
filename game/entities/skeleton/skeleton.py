import json
from .bone import Bone
from .slot import Slot
from .animation.skeleton_animation import SkeletonAnimation
from .get_subtextures import get_subtextures, Subtexture
import os
import pyglet


class Skeleton:
    position: tuple[float, float]
    scale: tuple[float, float]
    angle = 0.0

    current_animation: SkeletonAnimation | None
    frame = 0
    framerate: float

    bones: dict[str, Bone]

    subtextures: dict[str, Subtexture]
    batch: pyglet.graphics.Batch

    animation_data: list[dict]

    velocity: tuple[float, float]

    def __init__(self, skeleton_path: str, groups: dict[str, pyglet.graphics.Group]):
        """
        Load a skeleton from a JSON file and create bones and slots.

        Parameters:
        - skeleton_path: The path to the folder containing the skeleton data. The folder should be named similarly to your DragonBones project and must contain the following files:
            - <db project name>_ske.json: The skeleton data in JSON format.
            - <db project name>.json: The subtexture data in JSON format.
            - <db project name>.png: The subtexture image.
        - groups: A dictionary mapping pyglet groups. Each group corresponds to a bone in your DragonBones project and must have the same name as its associated bone. Bones without a corresponding group will be assigned to the skeleton's base group by default.
        """
        self.batch = pyglet.graphics.Batch()

        entity_name = os.path.basename(skeleton_path)
        with open(f"{skeleton_path}/{entity_name}_ske.json", "r") as file:
            skeleton_data = json.load(file)

        self.framerate = skeleton_data["frameRate"]
        armature_data = skeleton_data["armature"][0]
        self.animation_data = armature_data["animation"]

        self.subtextures = get_subtextures(
            f"{skeleton_path}/{entity_name}_tex.json",
            f"{skeleton_path}/{entity_name}_tex.png",
        )

        self.bones = self._load_bones(armature_data["bone"], groups)
        self.slots = self._load_slots(
            (armature_data["slot"], armature_data["skin"][0]["slot"])
        )

        self.set_position(0, 0)
        self.set_scale(1, 1)
        self.set_angle(0)

        self.set_animation(armature_data["animation"][0]["name"])
        self.animation_time = 0

        self.speed = (0, 0)

    def _load_bones(self, data, groups: dict[str, pyglet.graphics.Group]):
        bones: dict[str, Bone] = {}

        for b in data:
            bone_name = b["name"]
            bone_group = groups.get(bone_name) or groups["all"]
            bone = Bone(b, bone_group, self)
            bones[bone_name] = bone

        return bones

    def _load_slots(self, data):
        slots: dict[str, Slot] = {}

        slot_data, skin_data = data
        # Iterate through armature slots
        for slot_info in slot_data:
            slot_displays = None

            # Find matching slot in skin and retrieve display info
            for slot in skin_data:
                if slot["name"] == slot_info["name"]:
                    slot_displays = slot.get("display")  # Use .get() to avoid KeyError
                    break

            # If slot displays are found, create a dictionary for subtextures
            slot_subtextures = {}
            if slot_displays:
                slot_subtextures = [
                    self.subtextures[display["name"]] for display in slot_displays
                ]

            # Create a slot and assign it to the bone's slot dictionary
            bone_name = slot_info["parent"]
            slot_name = slot_info["name"]

            bone = self.bones[bone_name]
            slot = Slot(
                slot_info, bone=bone, subtextures=slot_subtextures, batch=self.batch
            )
            bone.slots[slot_name] = slot
            slot.bone = bone
            slots[slot_name] = slot

        return slots

    def set_position(self, x: float, y: float):
        """Change skeleton's position."""
        self.position = (x, y)

        for bone in self.bones.values():
            bone.update_position()

    def set_angle(self, angle: float):
        """Change skeleton's angle."""
        self.angle = angle

        for bone in self.bones.values():
            bone.update_angle()

    def set_scale(self, x: float, y: float):
        """Change skeleton's scale."""
        self.scale = (x, y)

        for bone in self.bones.values():
            bone.update_scale()

    def set_animation(self, animation_name: str, starting_frame=0, speed=1.0):
        """Change skeleton's animation."""
        animation_info = next(
            (info for info in self.animation_data if info["name"] == animation_name),
            None,
        )
        if animation_info is None:
            raise ValueError(f"Animation {animation_name} not found.")

        animation = SkeletonAnimation(
            info=animation_info,
            skeleton=self,
            framerate=self.framerate,
            frame=starting_frame,
            speed=speed,
        )
        self.current_animation = animation

    def set_smooth(self, smooth: bool):
        if self.current_animation:
            self.current_animation.set_smooth(smooth)
        else:
            raise ValueError("No animation is currently playing.")

    def update(self, dt):
        """Update skeleton's attributes and draw each of its parts."""
        # self.body.update(dt)

        self.current_animation.update(dt)
        self.batch.draw()
