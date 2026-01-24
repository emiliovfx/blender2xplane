# SPDX-License-Identifier: GPL-2.0-or-later
"""
Compatibility helpers for Blender's Animation/Action API changes (Blender 5.0+ slotted actions).

Blender 4.x code commonly used:
    action.fcurves

In Blender 5.0, direct access to action.fcurves is removed and fcurves live in
Action layers/strips/channelbags (per action slots). Use the helpers below to
iterate fcurves in a version-tolerant way.

Keep this module tiny & dependency-free; it is used in hot paths.
"""
from __future__ import annotations

from typing import Iterable, Optional, Iterator, Any

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None  # type: ignore

def get_action_channelbag(anim_data, ensure=False):
    if not anim_data or not anim_data.action:
        return None

    action = anim_data.action

    # Blender ≤ 4.5
    if hasattr(action, "groups"):
        return action

    # Blender 5.0+
    try:
        from bpy_extras.anim_utils import action_ensure_channelbag_for_slot
        return action_ensure_channelbag_for_slot(
            action,
            anim_data.action_slot,
            ensure=ensure
        )
    except Exception:
        return None


def ensure_action_group(anim_data, group_name):
    if not anim_data or not anim_data.action:
        return None

    container = get_action_channelbag(anim_data, ensure=True)
    if not container:
        return None

    # Blender ≤ 4.5
    if hasattr(container, "groups"):
        return container.groups.get(group_name) or container.groups.new(group_name)

    # Blender 5.0+: Action groups were removed with slotted actions.
    # keyframe_insert(..., group=...) will still work, but there is no groups collection to pre-create.
    return None


def iter_action_fcurves(action: Any) -> Iterator[Any]:
    """
    Yield all F-Curves contained in an action across all slots/layers/strips.

    - Blender <= 4.5: yields action.fcurves
    - Blender 5.0+: yields fcurves from action.layers[*].strips[*].channelbags[*].fcurves
    """
    if action is None:
        return
        yield  # pragma: no cover

    # Blender 2.x-4.x
    if hasattr(action, "fcurves"):
        try:
            for fc in action.fcurves:
                yield fc
            return
        except Exception:
            # fall through to layered API
            pass

    # Blender 5.0+ slotted actions
    layers = getattr(action, "layers", None)
    if not layers:
        return

    for layer in layers:
        strips = getattr(layer, "strips", None)
        if not strips:
            continue
        for strip in strips:
            channelbags = getattr(strip, "channelbags", None)
            if not channelbags:
                continue
            for cb in channelbags:
                fcurves = getattr(cb, "fcurves", None)
                if not fcurves:
                    continue
                for fc in fcurves:
                    yield fc


def get_channelbag_for_anim_data(anim_data: Any) -> Optional[Any]:
    """
    Return the ActionChannelbag for a given AnimationData (object/data-block),
    if available (Blender 5.0+). Returns None on older Blender or when not slotted.
    """
    if anim_data is None:
        return None
    action = getattr(anim_data, "action", None)
    if action is None:
        return None

    # Blender 5.0+ helper exists in bpy_extras.anim_utils
    try:
        from bpy_extras import anim_utils  # type: ignore
    except Exception:
        return None

    slot = getattr(anim_data, "action_slot", None)
    if slot is None:
        # Could be a legacy assignment; no slot info available.
        return None

    try:
        return anim_utils.action_get_channelbag_for_slot(action, slot)
    except Exception:
        return None


def get_fcurves_for_anim_data(anim_data):
    """Return fcurves for the active Action Slot (Blender 4.4+/4.5/5.0), fallback to legacy."""
    if not anim_data or not anim_data.action:
        return []

    action = anim_data.action

    # Slot/channelbag path (Blender 4.4+ including 4.5 and 5.0)
    try:
        from bpy_extras import anim_utils

        slot = getattr(anim_data, "action_slot", None)
        if slot is None and hasattr(action, "slots") and action.slots:
            # Fallback if slot isn't set for some reason
            slot = action.slots[0]

        if slot is not None:
            cb = anim_utils.action_get_channelbag_for_slot(action, slot)
            if cb is not None:
                return list(cb.fcurves)
    except Exception:
        pass

    # Legacy fallback (Blender 4.2 era)
    if hasattr(action, "fcurves"):
        return list(action.fcurves)

    return []



def remove_fcurve_from_collection(fcurves: Any, fcurve: Any) -> bool:
    """
    Remove an fcurve from a collection. Returns True if removed, False otherwise.
    Tries both keyword & positional remove signatures.
    """
    if fcurves is None or fcurve is None:
        return False
    try:
        # Older API used remove(fcurve=<FCurve>)
        fcurves.remove(fcurve=fcurve)
        return True
    except TypeError:
        try:
            fcurves.remove(fcurve)
            return True
        except Exception:
            return False
    except Exception:
        return False
