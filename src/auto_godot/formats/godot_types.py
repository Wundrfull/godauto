"""Known Godot 4.6 built-in Node type allowlist.

Used by commands that take a --type argument (e.g., scene add-node) to
catch typos at CLI time rather than pushing errors to runtime.

The list covers the common Node hierarchy shipped with Godot 4.6. It is
intentionally not exhaustive (rarely-used classes, XR, audio effect
buses). Unknown types emit a warning plus did-you-mean suggestions
but never block; users with plugins or class_name types can silence
the warning with --no-validate-type.

Source: Godot 4.6 stable class reference. Keep sorted alphabetically
within each group to simplify review and cherry-picks.
"""

from __future__ import annotations

import difflib
from typing import Final

# Core Node hierarchy
_CORE_NODES: Final = (
    "Node",
    "CanvasItem",
    "Control",
    "Node2D",
    "Node3D",
)

# 2D nodes
_NODE_2D: Final = (
    "AnimatableBody2D", "AnimatedSprite2D", "Area2D",
    "AudioListener2D", "AudioStreamPlayer2D",
    "BackBufferCopy", "Bone2D",
    "Camera2D", "CanvasGroup", "CanvasLayer",
    "CanvasModulate", "CharacterBody2D", "CollisionObject2D",
    "CollisionPolygon2D", "CollisionShape2D", "ConeTwistJoint2D",
    "CPUParticles2D", "DampedSpringJoint2D",
    "GPUParticles2D", "GrooveJoint2D",
    "HingeJoint2D", "Joint2D", "Light2D", "LightOccluder2D",
    "Line2D", "Marker2D", "MeshInstance2D",
    "MultiMeshInstance2D", "NavigationAgent2D",
    "NavigationLink2D", "NavigationObstacle2D",
    "NavigationRegion2D", "Parallax2D", "ParallaxBackground",
    "ParallaxLayer", "PathFollow2D", "Path2D",
    "PhysicalBone2D", "PhysicsBody2D", "PinJoint2D",
    "PointLight2D", "Polygon2D", "RayCast2D",
    "RemoteTransform2D", "RigidBody2D", "ShapeCast2D",
    "Skeleton2D", "SoftBody2D", "Sprite2D",
    "StaticBody2D", "TileMap", "TileMapLayer",
    "TouchScreenButton", "VisibleOnScreenEnabler2D",
    "VisibleOnScreenNotifier2D",
)

# 3D nodes
_NODE_3D: Final = (
    "AnimatableBody3D", "Area3D", "AudioListener3D",
    "AudioStreamPlayer3D", "BoneAttachment3D",
    "Camera3D", "CharacterBody3D", "CollisionObject3D",
    "CollisionPolygon3D", "CollisionShape3D",
    "ConeTwistJoint3D", "CPUParticles3D",
    "CSGBox3D", "CSGCombiner3D", "CSGCylinder3D",
    "CSGMesh3D", "CSGPolygon3D", "CSGPrimitive3D",
    "CSGShape3D", "CSGSphere3D", "CSGTorus3D",
    "Decal", "DirectionalLight3D", "FogVolume",
    "Generic6DOFJoint3D", "GeometryInstance3D",
    "GPUParticles3D", "GPUParticlesAttractor3D",
    "GPUParticlesAttractorBox3D", "GPUParticlesAttractorSphere3D",
    "GPUParticlesAttractorVectorField3D",
    "GPUParticlesCollision3D", "GPUParticlesCollisionBox3D",
    "GPUParticlesCollisionHeightField3D",
    "GPUParticlesCollisionSDF3D",
    "GPUParticlesCollisionSphere3D", "GridMap",
    "HingeJoint3D", "ImporterMeshInstance3D",
    "Joint3D", "Label3D", "Light3D",
    "LightmapGI", "LightmapProbe", "Marker3D",
    "MeshInstance3D", "MultiMeshInstance3D",
    "NavigationAgent3D", "NavigationLink3D",
    "NavigationObstacle3D", "NavigationRegion3D",
    "OccluderInstance3D", "OmniLight3D",
    "PathFollow3D", "Path3D", "PhysicalBone3D",
    "PhysicsBody3D", "PinJoint3D",
    "ReflectionProbe", "RemoteTransform3D",
    "RigidBody3D", "ShapeCast3D", "Skeleton3D",
    "SkeletonIK3D", "SliderJoint3D", "SoftBody3D",
    "SpotLight3D", "SpringArm3D", "Sprite3D",
    "SpriteBase3D", "StaticBody3D",
    "VehicleBody3D", "VehicleWheel3D",
    "VisibleOnScreenEnabler3D",
    "VisibleOnScreenNotifier3D", "VoxelGI",
    "WorldEnvironment", "XRAnchor3D",
    "XRCamera3D", "XRController3D", "XRNode3D",
    "XROrigin3D",
)

# Control (UI) nodes
_CONTROL: Final = (
    "AcceptDialog", "AnimatedTextureRect", "AspectRatioContainer",
    "BaseButton", "BoxContainer", "Button",
    "CanvasItem", "CenterContainer", "CheckBox",
    "CheckButton", "CodeEdit", "ColorPicker",
    "ColorPickerButton", "ColorRect", "ConfirmationDialog",
    "Container", "Control", "FileDialog",
    "FlowContainer", "FoldableContainer",
    "GraphEdit", "GraphElement", "GraphFrame",
    "GraphNode", "GridContainer", "HBoxContainer",
    "HFlowContainer", "HScrollBar", "HSeparator",
    "HSlider", "HSplitContainer", "ItemList",
    "Label", "LineEdit", "LinkButton",
    "MarginContainer", "MenuBar", "MenuButton",
    "NinePatchRect", "OptionButton", "Panel",
    "PanelContainer", "PopupMenu", "PopupPanel",
    "ProgressBar", "Range", "ReferenceRect",
    "RichTextLabel", "ScrollBar", "ScrollContainer",
    "Separator", "Slider", "SpinBox",
    "SplitContainer", "SubViewportContainer",
    "TabBar", "TabContainer", "TextEdit",
    "TextureButton", "TextureProgressBar",
    "TextureRect", "Tree", "VBoxContainer",
    "VFlowContainer", "VideoStreamPlayer",
    "VScrollBar", "VSeparator", "VSlider",
    "VSplitContainer", "Window",
)

# Misc / top-level nodes
_MISC: Final = (
    "AnimationMixer", "AnimationPlayer", "AnimationTree",
    "AudioStreamPlayer", "HTTPRequest",
    "InstancePlaceholder", "MissingNode",
    "MultiplayerSpawner", "MultiplayerSynchronizer",
    "NavigationAgent", "ProcessGroup",
    "ResourcePreloader", "SceneTree", "ShaderGlobalsOverride",
    "SkeletonModifier3D", "Skeleton3D", "SkeletonProfile",
    "StatusIndicator", "SubViewport",
    "Timer", "Tween", "Viewport",
    "VisualShaderNode",
)

KNOWN_NODE_TYPES: Final[frozenset[str]] = frozenset(
    _CORE_NODES + _NODE_2D + _NODE_3D + _CONTROL + _MISC,
)


def is_known_node_type(name: str) -> bool:
    """Return True if `name` is in the built-in Godot 4.6 node allowlist."""
    return name in KNOWN_NODE_TYPES


def suggest_node_types(name: str, limit: int = 3) -> list[str]:
    """Return up to `limit` closest matches to `name` from the allowlist.

    Uses difflib.get_close_matches with a cutoff tuned to catch typos
    without generating noise on wildly-different strings. Case-insensitive
    matching so "charcterbody2d" suggests "CharacterBody2D".
    """
    if not name:
        return []

    # Case-insensitive: fold both sides for comparison, preserve canonical
    # casing in the return value.
    folded = {t.lower(): t for t in KNOWN_NODE_TYPES}
    hits = difflib.get_close_matches(
        name.lower(), list(folded.keys()), n=limit, cutoff=0.6,
    )
    return [folded[h] for h in hits]
