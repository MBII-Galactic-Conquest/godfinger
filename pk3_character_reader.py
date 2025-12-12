"""
PK3 Character Reader Utility
Extracts and parses character (.mbch) files from Movie Battles II .pk3 archives
"""

import os
import sys
from zipfile import ZipFile
import re
import json
from custom_build_system import CustomBuildSystem


class CharacterInfo:
    """Represents a parsed character from an .mbch file"""
    
    def __init__(self, filename):
        # ===== Basic Info =====
        self.filename = filename
        self.name = None
        self.mb_class = None
        self.class_number_limit = None
        self.description = None
        self.raw_content = None
        self.unknown_fields = []  # List of unparsed lines for future implementation
        
        # ===== Class Configuration =====
        self.weapons = []
        self.weapon_infos = []
        self.weapon_flags = {}  # Dict of weapon: flags
        self.attributes = []
        self.holdables = []
        self.specials = {}  # Dict of special1-4
        self.classflags = []
        self.extralives = None
        
        # ===== Health & Defense =====
        self.max_health = None
        self.max_armor = None
        self.start_health = None
        self.health_regen_rate = None
        self.health_regen_amount = None
        self.health_regen_cap = None
        self.armour_regen_rate = None
        self.armour_regen_amount = None
        self.armour_regen_cap = None
        
        # ===== Movement =====
        self.speed = None
        self.base_speed = None
        
        # ===== Combat Modifiers =====
        self.damage_given = None
        self.damage_taken = None
        self.knockback_given = None
        self.melee_knockback = None
        self.melee_knockback_flat = None
        self.melee_knockback_mult = None
        self.melee_moves = None
        self.rate_of_fire = None
        
        # ===== Force & Resource System =====
        self.forcepool = None
        self.forcepowers = []
        self.resource = None
        self.resource_regen_rate = None
        self.resource_force = None
        self.resource_amount = None
        self.resource_cap = None
        self.resource_cooldown = None
        self.resource_regen_amount = None
        self.resource_regen_cap = None
        
        # ===== Saber Configuration =====
        self.saber1 = None
        self.saber2 = None
        self.saberstyle = []
        self.saber_damage = None
        self.saber_special_damage = None
        self.saber_throw_damage = None
        self.bp_multiplier = None
        self.cs_multiplier = None
        self.as_multiplier = None
        self.ap_modifier = None
        self.ap_bonus = None
        self.block_regen_rate = None
        self.block_regen_amount = None
        self.block_regen_cap = None
        
        # ===== Saber Colors =====
        # Base colors
        self.saber_color = None
        self.saber2_color = None
        self.saber_colors = {}  # Dict: model_num -> (saber1_color, saber2_color)
        # Custom RGB colors
        self.custom_red = None
        self.custom_green = None
        self.custom_blue = None
        self.user_rgb = None  # Flag for using custom RGB
        # Per-model custom RGB colors (dict: model_num -> (r, g, b))
        self.model_custom_rgb = {}
        # Per-model user RGB flags (dict: model_num -> bool)
        self.model_user_rgb = {}
        
        # ===== Model & Visual =====
        self.models = []  # List of (num, model, skin, uishader) tuples
        self.modelscale = None
        self.head_swap_model = None
        self.head_swap_skin = None
        # Model-specific sabers
        self.model_sabers = {}  # Dict: model_num -> (saber1, saber2)
        # Model-specific saber styles
        self.model_saberstyles = {}  # Dict: model_num -> [styles]
        
        # ===== UI Overlays =====
        self.uioverlay = None
        self.uioverlay_l = None
        self.uioverlay_c = None
        self.uioverlay_r = None
        
        # ===== Animations =====
        self.saber_stance_anim = None
        self.flourish_anim = None
        self.walk_backward = None
        self.walk_forward = None
        self.run_backward = None
        self.run_forward = None
        self.gloat_anim = None
        self.taunt_anim = None
        self.bow_anim = None
        self.meditate_anim = None
        self.idle_anim = None
        self.death_anim = None
        
        # ===== Jetpack Configuration =====
        self.jetpack_thrust_effect = None
        self.jetpack_idle_effect = None
        self.jetpack_jet_tag = None
        self.jetpack_jet2_tag = None
        self.jetpack_jet_offset = None
        self.jetpack_jet2_offset = None
        self.jetpack_jet_angles = None
        self.jetpack_jet2_angles = None
        self.jetpack_finish_sound = None
        self.jetpack_thrust_sound = None
        self.jetpack_idle_sound = None
        self.jetpack_start_sound = None
        
        # ===== Sound Overrides =====
        self.barge_sound_override = None
        self.rage_sound_override = None
        
        # ===== Miscellaneous Flags =====
        self.disable_gun_bash = None
        self.force_blocking = None
        self.hack_rate = None
        self.humanoid_skeleton = None
        self.respawn_custom_time = None
        self.custom_veh = None
        
        # ===== Custom Build System =====
        self.custom_build = CustomBuildSystem()
        
    def __repr__(self):
        return f"CharacterInfo(name={self.name}, class={self.mb_class}, file={self.filename})"
    
    def to_dict(self):
        """Convert character info to a dictionary for JSON serialization"""
        return {
            # Basic Info
            'filename': self.filename,
            'name': self.name,
            'mb_class': self.mb_class,
            'class_number_limit': self.class_number_limit,
            'unknown_fields': self.unknown_fields,
            
            # Class Configuration
            'weapons': self.weapons,
            'weapon_infos': self.weapon_infos,
            'weapon_flags': self.weapon_flags,
            'attributes': self.attributes,
            'holdables': self.holdables,
            'specials': self.specials,
            'classflags': self.classflags,
            'extralives': self.extralives,
            
            # Health & Defense
            'max_health': self.max_health,
            'max_armor': self.max_armor,
            'start_health': self.start_health,
            'health_regen_rate': self.health_regen_rate,
            'health_regen_amount': self.health_regen_amount,
            'health_regen_cap': self.health_regen_cap,
            'armour_regen_rate': self.armour_regen_rate,
            'armour_regen_amount': self.armour_regen_amount,
            'armour_regen_cap': self.armour_regen_cap,
            
            # Movement
            'speed': self.speed,
            'base_speed': self.base_speed,
            
            # Combat Modifiers
            'damage_given': self.damage_given,
            'damage_taken': self.damage_taken,
            'knockback_given': self.knockback_given,
            'melee_knockback': self.melee_knockback,
            'melee_knockback_flat': self.melee_knockback_flat,
            'melee_knockback_mult': self.melee_knockback_mult,
            'melee_moves': self.melee_moves,
            'rate_of_fire': self.rate_of_fire,
            
            # Force & Resource System
            'forcepool': self.forcepool,
            'forcepowers': self.forcepowers,
            'resource': self.resource,
            'resource_regen_rate': self.resource_regen_rate,
            'resource_force': self.resource_force,
            'resource_amount': self.resource_amount,
            'resource_cap': self.resource_cap,
            'resource_cooldown': self.resource_cooldown,
            'resource_regen_amount': self.resource_regen_amount,
            'resource_regen_cap': self.resource_regen_cap,
            
            # Saber Configuration
            'saber1': self.saber1,
            'saber2': self.saber2,
            'saberstyle': self.saberstyle,
            'saber_damage': self.saber_damage,
            'saber_special_damage': self.saber_special_damage,
            'saber_throw_damage': self.saber_throw_damage,
            'bp_multiplier': self.bp_multiplier,
            'cs_multiplier': self.cs_multiplier,
            'as_multiplier': self.as_multiplier,
            'ap_modifier': self.ap_modifier,
            'ap_bonus': self.ap_bonus,
            'block_regen_rate': self.block_regen_rate,
            'block_regen_amount': self.block_regen_amount,
            'block_regen_cap': self.block_regen_cap,
            
            # Saber Colors
            'saber_color': self.saber_color,
            'saber2_color': self.saber2_color,
            'saber_colors': self.saber_colors,
            'custom_red': self.custom_red,
            'custom_green': self.custom_green,
            'custom_blue': self.custom_blue,
            'user_rgb': self.user_rgb,
            'model_custom_rgb': self.model_custom_rgb,
            'model_user_rgb': self.model_user_rgb,
            
            # Model & Visual
            'models': [{'number': num, 'model': model, 'skin': skin, 'uishader': uishader} 
                      for num, model, skin, uishader in self.models],
            'modelscale': self.modelscale,
            'head_swap_model': self.head_swap_model,
            'head_swap_skin': self.head_swap_skin,
            'model_sabers': self.model_sabers,
            'model_saberstyles': self.model_saberstyles,
            
            # UI Overlays
            'uioverlay': self.uioverlay,
            'uioverlay_l': self.uioverlay_l,
            'uioverlay_c': self.uioverlay_c,
            'uioverlay_r': self.uioverlay_r,
            
            # Animations
            'saber_stance_anim': self.saber_stance_anim,
            'flourish_anim': self.flourish_anim,
            'walk_backward': self.walk_backward,
            'walk_forward': self.walk_forward,
            'run_backward': self.run_backward,
            'run_forward': self.run_forward,
            'gloat_anim': self.gloat_anim,
            'taunt_anim': self.taunt_anim,
            'bow_anim': self.bow_anim,
            'meditate_anim': self.meditate_anim,
            'idle_anim': self.idle_anim,
            'death_anim': self.death_anim,
            
            # Jetpack Configuration
            'jetpack_thrust_effect': self.jetpack_thrust_effect,
            'jetpack_idle_effect': self.jetpack_idle_effect,
            'jetpack_jet_tag': self.jetpack_jet_tag,
            'jetpack_jet2_tag': self.jetpack_jet2_tag,
            'jetpack_jet_offset': self.jetpack_jet_offset,
            'jetpack_jet2_offset': self.jetpack_jet2_offset,
            'jetpack_jet_angles': self.jetpack_jet_angles,
            'jetpack_jet2_angles': self.jetpack_jet2_angles,
            'jetpack_finish_sound': self.jetpack_finish_sound,
            'jetpack_thrust_sound': self.jetpack_thrust_sound,
            'jetpack_idle_sound': self.jetpack_idle_sound,
            'jetpack_start_sound': self.jetpack_start_sound,
            
            # Sound Overrides
            'barge_sound_override': self.barge_sound_override,
            'rage_sound_override': self.rage_sound_override,
            
            # Miscellaneous Flags
            'disable_gun_bash': self.disable_gun_bash,
            'force_blocking': self.force_blocking,
            'hack_rate': self.hack_rate,
            'humanoid_skeleton': self.humanoid_skeleton,
            'respawn_custom_time': self.respawn_custom_time,
            'custom_veh': self.custom_veh,
            
            # Custom Build System
            'custom_build': self.custom_build.to_dict() if self.custom_build.has_custom_builds() else None,
        }


def parse_mbch_content(content, filename):
    """Parse the content of an .mbch file"""
    char = CharacterInfo(filename)
    char.raw_content = content
    
    # Parse ClassInfo section
    class_info_match = re.search(r'ClassInfo\s*\{([^}]*)\}', content, re.DOTALL)
    if class_info_match:
        class_info = class_info_match.group(1)
        
        # Extract name
        name_match = re.search(r'name\s+["\']?([^"\'\n]+)["\']?', class_info)
        if name_match:
            char.name = name_match.group(1).strip()
        
        # Extract MBClass
        mbclass_match = re.search(r'MBClass\s+(\S+)', class_info)
        if mbclass_match:
            char.mb_class = mbclass_match.group(1).strip()
        
        # Extract classNumberLimit
        limit_match = re.search(r'classNumberLimit\s+(\d+)', class_info)
        if limit_match:
            char.class_number_limit = int(limit_match.group(1))
        
        # Extract weapons
        weapons_match = re.search(r'weapons\s+([^\n]+)', class_info)
        if weapons_match:
            weapons_str = weapons_match.group(1).strip()
            char.weapons = [w.strip() for w in weapons_str.split('|')]
        
        # Extract attributes
        attr_match = re.search(r'attributes\s+([^\n]+)', class_info)
        if attr_match:
            attr_str = attr_match.group(1).strip()
            char.attributes = [a.strip() for a in attr_str.split('|')]
        
        # Extract health
        health_match = re.search(r'maxhealth\s+(\d+)', class_info)
        if health_match:
            char.max_health = int(health_match.group(1))
        
        # Extract armor
        armor_match = re.search(r'maxarmor\s+(\d+)', class_info)
        if armor_match:
            char.max_armor = int(armor_match.group(1))
        
        # Extract models with skins and uishaders
        model_matches = re.finditer(r'model(?:_(\d+))?\s+["\']?([^"\'\n]+)["\']?', class_info)
        model_dict = {}
        for match in model_matches:
            model_num = match.group(1) if match.group(1) else "0"
            model_name = match.group(2).strip()
            if model_num not in model_dict:
                model_dict[model_num] = {'model': model_name, 'skin': None, 'uishader': None}
            else:
                model_dict[model_num]['model'] = model_name
        
        # Extract skins
        skin_matches = re.finditer(r'skin(?:_(\d+))?\s+["\']?([^"\'\n]+)["\']?', class_info)
        for match in skin_matches:
            skin_num = match.group(1) if match.group(1) else "0"
            skin_name = match.group(2).strip()
            if skin_num not in model_dict:
                model_dict[skin_num] = {'model': None, 'skin': skin_name, 'uishader': None}
            else:
                model_dict[skin_num]['skin'] = skin_name
        
        # Extract uishaders
        uishader_matches = re.finditer(r'uishader(?:_(\d+))?\s+["\']?([^"\'\n]+)["\']?', class_info)
        for match in uishader_matches:
            shader_num = match.group(1) if match.group(1) else "0"
            shader_name = match.group(2).strip()
            if shader_num not in model_dict:
                model_dict[shader_num] = {'model': None, 'skin': None, 'uishader': shader_name}
            else:
                model_dict[shader_num]['uishader'] = shader_name
        
        # Convert to list of tuples
        for num in sorted(model_dict.keys(), key=lambda x: int(x)):
            data = model_dict[num]
            char.models.append((num, data['model'], data['skin'], data['uishader']))
        
        # Extract forcepool
        forcepool_match = re.search(r'forcepool\s+(\d+)', class_info)
        if forcepool_match:
            char.forcepool = int(forcepool_match.group(1))
        
        # Extract resource
        resource_match = re.search(r'resource\s+(\S+)', class_info)
        if resource_match:
            char.resource = resource_match.group(1).strip()
        
        # Extract holdables
        holdables_match = re.search(r'holdables\s+([^\n]+)', class_info)
        if holdables_match:
            holdables_str = holdables_match.group(1).strip()
            char.holdables = [h.strip() for h in holdables_str.split('|')]
        
        # Extract rateOfFire
        rof_match = re.search(r'rateOfFire\s+([\d.]+)', class_info)
        if rof_match:
            char.rate_of_fire = float(rof_match.group(1))
        
        # Extract speed
        speed_match = re.search(r'speed\s+([\d.]+)', class_info)
        if speed_match:
            char.speed = float(speed_match.group(1))
        
        # Extract specials (special1, special2, special3, special4)
        for i in range(1, 5):
            special_match = re.search(rf'special{i}\s+(\S+)', class_info)
            if special_match:
                char.specials[f'special{i}'] = special_match.group(1).strip()
        
        # Extract uioverlay
        uioverlay_match = re.search(r'uioverlay\s+["\']?([^"\'\n]+)["\']?', class_info)
        if uioverlay_match:
            char.uioverlay = uioverlay_match.group(1).strip()
        
        # Extract uioverlay variants (left, center, right)
        uioverlay_l_match = re.search(r'uioverlay_l\s+["\']?([^"\'\n]+)["\']?', class_info)
        if uioverlay_l_match:
            char.uioverlay_l = uioverlay_l_match.group(1).strip()
        
        uioverlay_c_match = re.search(r'uioverlay_c\s+["\']?([^"\'\n]+)["\']?', class_info)
        if uioverlay_c_match:
            char.uioverlay_c = uioverlay_c_match.group(1).strip()
        
        uioverlay_r_match = re.search(r'uioverlay_r\s+["\']?([^"\'\n]+)["\']?', class_info)
        if uioverlay_r_match:
            char.uioverlay_r = uioverlay_r_match.group(1).strip()
        
        # Extract modelscale
        modelscale_match = re.search(r'modelscale\s+([\d.]+)', class_info)
        if modelscale_match:
            char.modelscale = float(modelscale_match.group(1))
        
        # Extract classflags
        classflags_match = re.search(r'classflags\s+([^\n]+)', class_info, re.IGNORECASE)
        if classflags_match:
            classflags_str = classflags_match.group(1).strip()
            char.classflags = [f.strip() for f in classflags_str.split('|')]
        
        # Extract extralives
        extralives_match = re.search(r'extralives\s+(\d+)', class_info, re.IGNORECASE)
        if extralives_match:
            char.extralives = int(extralives_match.group(1))
        else:
            # Check if extralives is specified via MB_ATT_RESPAWNS attribute
            # Attributes are stored as ["MB_ATT_RESPAWNS,2", ...]
            for attr in char.attributes:
                if attr.startswith('MB_ATT_RESPAWNS'):
                    try:
                        # Extract the rank value after the comma
                        parts = attr.split(',')
                        if len(parts) >= 2:
                            rank = int(parts[1].strip())
                            char.extralives = rank
                            break
                    except (ValueError, IndexError):
                        continue
        
        # Extract forcepowers
        forcepowers_match = re.search(r'forcepowers\s+([^\n]+)', class_info)
        if forcepowers_match:
            forcepowers_str = forcepowers_match.group(1).strip()
            char.forcepowers = [f.strip() for f in forcepowers_str.split('|')]
        
        # Extract baseSpeed
        basespeed_match = re.search(r'baseSpeed\s+([\d.]+)', class_info)
        if basespeed_match:
            char.base_speed = float(basespeed_match.group(1))
        
        # Extract multipliers
        bp_match = re.search(r'BPMultiplier\s+([\d.]+)', class_info, re.IGNORECASE)
        if bp_match:
            char.bp_multiplier = float(bp_match.group(1))
        
        cs_match = re.search(r'CSMultiplier\s+([\d.]+)', class_info, re.IGNORECASE)
        if cs_match:
            char.cs_multiplier = float(cs_match.group(1))
        
        as_match = re.search(r'ASMultiplier\s+([\d.]+)', class_info, re.IGNORECASE)
        if as_match:
            char.as_multiplier = float(as_match.group(1))
        
        # Extract saber info
        saber1_match = re.search(r'saber1\s+([^\n]+)', class_info)
        if saber1_match:
            char.saber1 = saber1_match.group(1).strip()
        
        saber2_match = re.search(r'saber2\s+([^\n]+)', class_info)
        if saber2_match:
            char.saber2 = saber2_match.group(1).strip()
        
        saberstyle_match = re.search(r'saberstyle\s+([^\n]+)', class_info)
        if saberstyle_match:
            saberstyle_str = saberstyle_match.group(1).strip()
            char.saberstyle = [s.strip() for s in saberstyle_str.split('|')]
        
        saberdamage_match = re.search(r'saberDamage\s+([\d.]+)', class_info)
        if saberdamage_match:
            char.saber_damage = float(saberdamage_match.group(1))
        
        saberspecialdamage_match = re.search(r'saberSpecialDamage\s+([\d.]+)', class_info)
        if saberspecialdamage_match:
            char.saber_special_damage = float(saberspecialdamage_match.group(1))
        
        # Extract AP modifier
        ap_match = re.search(r'APmodifier\s+([\d.]+)', class_info, re.IGNORECASE)
        if ap_match:
            char.ap_modifier = float(ap_match.group(1))
        
        # Extract saber colors (base)
        sabercolor_match = re.search(r'^sabercolor\s+(\d+)', class_info, re.MULTILINE)
        if sabercolor_match:
            char.saber_color = int(sabercolor_match.group(1))
        
        saber2color_match = re.search(r'^saber2color\s+(\d+)', class_info, re.MULTILINE)
        if saber2color_match:
            char.saber2_color = int(saber2color_match.group(1))
        
        # Extract model-specific saber colors
        sabercolor_model_matches = re.finditer(r'sabercolor_(\d+)\s+(\d+)', class_info)
        for match in sabercolor_model_matches:
            model_num = match.group(1)
            color = int(match.group(2))
            if model_num not in char.saber_colors:
                char.saber_colors[model_num] = [None, None]
            char.saber_colors[model_num][0] = color
        
        saber2color_model_matches = re.finditer(r'saber2color_(\d+)\s+(\d+)', class_info)
        for match in saber2color_model_matches:
            model_num = match.group(1)
            color = int(match.group(2))
            if model_num not in char.saber_colors:
                char.saber_colors[model_num] = [None, None]
            char.saber_colors[model_num][1] = color
        
        # Extract custom RGB colors (base)
        customred_match = re.search(r'^customred\s+([\d.]+)', class_info, re.MULTILINE)
        if customred_match:
            char.custom_red = float(customred_match.group(1))
        
        customgreen_match = re.search(r'^customgreen\s+([\d.]+)', class_info, re.MULTILINE)
        if customgreen_match:
            char.custom_green = float(customgreen_match.group(1))
        
        customblue_match = re.search(r'^customblue\s+([\d.]+)', class_info, re.MULTILINE)
        if customblue_match:
            char.custom_blue = float(customblue_match.group(1))
        
        # Extract user RGB flag (base)
        userrgb_match = re.search(r'^userRGB\s+(\d+)', class_info, re.MULTILINE)
        if userrgb_match:
            char.user_rgb = bool(int(userrgb_match.group(1)))
        
        # Extract per-model custom RGB colors
        customred_model_matches = re.finditer(r'customred_(\d+)\s+([\d.]+)', class_info)
        for match in customred_model_matches:
            model_num = match.group(1)
            value = float(match.group(2))
            if model_num not in char.model_custom_rgb:
                char.model_custom_rgb[model_num] = [None, None, None]
            char.model_custom_rgb[model_num][0] = value
        
        customgreen_model_matches = re.finditer(r'customgreen_(\d+)\s+([\d.]+)', class_info)
        for match in customgreen_model_matches:
            model_num = match.group(1)
            value = float(match.group(2))
            if model_num not in char.model_custom_rgb:
                char.model_custom_rgb[model_num] = [None, None, None]
            char.model_custom_rgb[model_num][1] = value
        
        customblue_model_matches = re.finditer(r'customblue_(\d+)\s+([\d.]+)', class_info)
        for match in customblue_model_matches:
            model_num = match.group(1)
            value = float(match.group(2))
            if model_num not in char.model_custom_rgb:
                char.model_custom_rgb[model_num] = [None, None, None]
            char.model_custom_rgb[model_num][2] = value
        
        # Extract per-model user RGB flags
        userrgb_model_matches = re.finditer(r'userRGB_(\d+)\s+(\d+)', class_info)
        for match in userrgb_model_matches:
            model_num = match.group(1)
            value = bool(int(match.group(2)))
            char.model_user_rgb[model_num] = value
        
        # Extract model-specific sabers
        saber1_model_matches = re.finditer(r'saber1_(\d+)\s+([^\n]+)', class_info)
        for match in saber1_model_matches:
            model_num = match.group(1)
            saber = match.group(2).strip()
            if model_num not in char.model_sabers:
                char.model_sabers[model_num] = [None, None]
            char.model_sabers[model_num][0] = saber
        
        saber2_model_matches = re.finditer(r'saber2_(\d+)\s+([^\n]+)', class_info)
        for match in saber2_model_matches:
            model_num = match.group(1)
            saber = match.group(2).strip()
            if model_num not in char.model_sabers:
                char.model_sabers[model_num] = [None, None]
            char.model_sabers[model_num][1] = saber
        
        # Extract per-model saberstyles
        saberstyle_model_matches = re.finditer(r'saberstyle_(\d+)\s+([^\n]+)', class_info)
        for match in saberstyle_model_matches:
            model_num = match.group(1)
            styles_str = match.group(2).strip()
            char.model_saberstyles[model_num] = [s.strip() for s in styles_str.split('|')]
        
        # Extract sabercolor1 (alternate field name)
        sabercolor1_match = re.search(r'sabercolor1\s+(\d+)', class_info)
        if sabercolor1_match and char.saber_color is None:
            char.saber_color = int(sabercolor1_match.group(1))
        
        # Extract damage modifiers
        damagegiven_match = re.search(r'damageGiven\s+([\d.]+)', class_info)
        if damagegiven_match:
            char.damage_given = float(damagegiven_match.group(1))
        
        damagetaken_match = re.search(r'[Dd]amageTaken\s+([\d.]+)', class_info)
        if damagetaken_match:
            char.damage_taken = float(damagetaken_match.group(1))
        
        meleeknockback_match = re.search(r'meleeknockback\s+([\d.]+)', class_info)
        if meleeknockback_match:
            char.melee_knockback = float(meleeknockback_match.group(1))
        
        meleeknockback_flat_match = re.search(r'meleeknockback_flat\s+([\d.]+)', class_info)
        if meleeknockback_flat_match:
            char.melee_knockback_flat = float(meleeknockback_flat_match.group(1))
        
        meleeknockback_mult_match = re.search(r'meleeknockback_mult\s+([\d.]+)', class_info)
        if meleeknockback_mult_match:
            char.melee_knockback_mult = float(meleeknockback_mult_match.group(1))
        
        meleemoves_match = re.search(r'[Mm]elee[Mm]oves\s+([^\n]+)', class_info)
        if meleemoves_match:
            char.melee_moves = meleemoves_match.group(1).strip()
        
        apbonus_match = re.search(r'APBonus\s+([\d.]+)', class_info, re.IGNORECASE)
        if apbonus_match:
            char.ap_bonus = float(apbonus_match.group(1))
        
        knockbackgiven_match = re.search(r'[Kk]nockback[Gg]iven\s+([\d.]+)', class_info)
        if knockbackgiven_match:
            char.knockback_given = float(knockbackgiven_match.group(1))
        
        # Extract saber throw damage
        saberthrow_match = re.search(r'saber[Tt]hrow[Dd]amage\s+([\d.]+)', class_info)
        if saberthrow_match:
            char.saber_throw_damage = float(saberthrow_match.group(1))
        
        # Extract health regeneration
        healthregenrate_match = re.search(r'[Hh]ealth[Rr]egen[Rr]ate\s+([\d.]+)', class_info)
        if healthregenrate_match:
            char.health_regen_rate = float(healthregenrate_match.group(1))
        
        healthregenamount_match = re.search(r'[Hh]ealth[Rr]egen[Aa]mount\s+([\d.]+)', class_info)
        if healthregenamount_match:
            char.health_regen_amount = float(healthregenamount_match.group(1))
        
        healthregencap_match = re.search(r'[Hh]ealth[Rr]egen[Cc]ap\s+([\d.]+)', class_info)
        if healthregencap_match:
            char.health_regen_cap = float(healthregencap_match.group(1))
        
        # Extract armor regeneration
        armourregenrate_match = re.search(r'[Aa]rmour[Rr]egen[Rr]ate\s+([\d.]+)', class_info)
        if armourregenrate_match:
            char.armour_regen_rate = float(armourregenrate_match.group(1))
        
        armourregenamount_match = re.search(r'[Aa]rmour[Rr]egen[Aa]mount\s+([\d.]+)', class_info)
        if armourregenamount_match:
            char.armour_regen_amount = float(armourregenamount_match.group(1))
        
        armourregencap_match = re.search(r'[Aa]rmour[Rr]egen[Cc]ap\s+([\d.]+)', class_info)
        if armourregencap_match:
            char.armour_regen_cap = float(armourregencap_match.group(1))
        
        # Extract block regeneration
        blockregenrate_match = re.search(r'blockRegen[Rr]ate\s+([\d.]+)', class_info)
        if blockregenrate_match:
            char.block_regen_rate = float(blockregenrate_match.group(1))
        
        blockregenamount_match = re.search(r'blockRegen[Aa]mount\s+([\d.]+)', class_info)
        if blockregenamount_match:
            char.block_regen_amount = float(blockregenamount_match.group(1))
        
        blockregencap_match = re.search(r'blockRegen[Cc]ap\s+([\d.]+)', class_info)
        if blockregencap_match:
            char.block_regen_cap = float(blockregencap_match.group(1))
        
        # Extract start health
        starthealth_match = re.search(r'starthealth\s+([\d.]+)', class_info)
        if starthealth_match:
            char.start_health = float(starthealth_match.group(1))
        
        # Extract resource fields
        resourceamount_match = re.search(r'resourceAmount\s+([\d.]+)', class_info)
        if resourceamount_match:
            char.resource_amount = float(resourceamount_match.group(1))
        
        resourcecap_match = re.search(r'resourceCap\s+([\d.]+)', class_info)
        if resourcecap_match:
            char.resource_cap = float(resourcecap_match.group(1))
        
        resourcecooldown_match = re.search(r'resourceCooldown\s+([\d.]+)', class_info)
        if resourcecooldown_match:
            char.resource_cooldown = float(resourcecooldown_match.group(1))
        
        resourceregenamount_match = re.search(r'resourceRegenAmount\s+([\d.]+)', class_info)
        if resourceregenamount_match:
            char.resource_regen_amount = float(resourceregenamount_match.group(1))
        
        resourceregencap_match = re.search(r'resourceRegenCap\s+([\d.]+)', class_info)
        if resourceregencap_match:
            char.resource_regen_cap = float(resourceregencap_match.group(1))
        
        # Extract misc flags
        disablegunbash_match = re.search(r'disableGunBash\s+(\d+)', class_info)
        if disablegunbash_match:
            char.disable_gun_bash = bool(int(disablegunbash_match.group(1)))
        
        forceblocking_match = re.search(r'forceBlocking\s+(\d+)', class_info)
        if forceblocking_match:
            char.force_blocking = bool(int(forceblocking_match.group(1)))
        
        hackrate_match = re.search(r'hackRate\s+([\d.]+)', class_info)
        if hackrate_match:
            char.hack_rate = float(hackrate_match.group(1))
        
        humanoidskeleton_match = re.search(r'humanoidSkeleton\s+(\d+)', class_info)
        if humanoidskeleton_match:
            char.humanoid_skeleton = bool(int(humanoidskeleton_match.group(1)))
        
        # Extract respawn time
        respawncustomtime_match = re.search(r'respawnCustomTime\s+(\d+)', class_info)
        if respawncustomtime_match:
            char.respawn_custom_time = int(respawncustomtime_match.group(1))
        
        # Extract custom vehicle
        customveh_match = re.search(r'customveh\s+([^\n]+)', class_info)
        if customveh_match:
            char.custom_veh = customveh_match.group(1).strip()
        
        # Extract head swap
        headswapmodel_match = re.search(r'headSwapModel\s+([^\n]+)', class_info)
        if headswapmodel_match:
            char.head_swap_model = headswapmodel_match.group(1).strip()
        
        headswapskin_match = re.search(r'headSwapSkin\s+([^\n]+)', class_info)
        if headswapskin_match:
            char.head_swap_skin = headswapskin_match.group(1).strip()
        
        # Extract resource settings
        resourceregenrate_match = re.search(r'resourceRegenRate\s+([\d.]+)', class_info)
        if resourceregenrate_match:
            char.resource_regen_rate = float(resourceregenrate_match.group(1))
        
        resourceforce_match = re.search(r'resource_force', class_info)
        if resourceforce_match:
            char.resource_force = True
        
        # Extract sound overrides
        bargesound_match = re.search(r'bargeSoundOverride\s+([^\n]+)', class_info)
        if bargesound_match:
            char.barge_sound_override = bargesound_match.group(1).strip()
        
        ragesound_match = re.search(r'rageSoundOverride\s+([^\n]+)', class_info)
        if ragesound_match:
            char.rage_sound_override = ragesound_match.group(1).strip()
        
        # Extract animations
        saberstance_match = re.search(r'saberStanceAnim\s+([^\n]+)', class_info)
        if saberstance_match:
            char.saber_stance_anim = saberstance_match.group(1).strip()
        
        flourish_match = re.search(r'flourishAnim\s+([^\n]+)', class_info)
        if flourish_match:
            char.flourish_anim = flourish_match.group(1).strip()
        
        walkback_match = re.search(r'WalkBackward\s+([^\n]+)', class_info)
        if walkback_match:
            char.walk_backward = walkback_match.group(1).strip()
        
        walkforward_match = re.search(r'WalkForward\s+([^\n]+)', class_info)
        if walkforward_match:
            char.walk_forward = walkforward_match.group(1).strip()
        
        gloat_match = re.search(r'gloatAnim\s+([^\n]+)', class_info)
        if gloat_match:
            char.gloat_anim = gloat_match.group(1).strip()
        
        taunt_match = re.search(r'tauntAnim\s+([^\n]+)', class_info)
        if taunt_match:
            char.taunt_anim = taunt_match.group(1).strip()
        
        runback_match = re.search(r'[Rr]un[Bb]ackward\s+([^\n]+)', class_info)
        if runback_match:
            char.run_backward = runback_match.group(1).strip()
        
        runforward_match = re.search(r'[Rr]un[Ff]orward\s+([^\n]+)', class_info)
        if runforward_match:
            char.run_forward = runforward_match.group(1).strip()
        
        bow_match = re.search(r'bowAnim\s+([^\n]+)', class_info)
        if bow_match:
            char.bow_anim = bow_match.group(1).strip()
        
        meditate_match = re.search(r'meditateAnim\s+([^\n]+)', class_info)
        if meditate_match:
            char.meditate_anim = meditate_match.group(1).strip()
        
        idle_match = re.search(r'[Ii]dle[Aa]nim\s+([^\n]+)', class_info)
        if idle_match:
            char.idle_anim = idle_match.group(1).strip()
        
        death_match = re.search(r'deathAnim\s+([^\n]+)', class_info)
        if death_match:
            char.death_anim = death_match.group(1).strip()
        
        # Extract weapon flags (WP_*Flags)
        weapon_flag_matches = re.finditer(r'(WP_\w+Flags)\s+([^\n]+)', class_info)
        for match in weapon_flag_matches:
            weapon_name = match.group(1)
            flags_str = match.group(2).strip()
            char.weapon_flags[weapon_name] = [f.strip() for f in flags_str.split('|')]
        
        # Extract jetpack configuration
        jetpack_fields = {
            'jetpackThrustEffect': 'jetpack_thrust_effect',
            'jetpackIdleEffect': 'jetpack_idle_effect',
            'jetpackJetTag': 'jetpack_jet_tag',
            'jetpackJet2Tag': 'jetpack_jet2_tag',
            'jetpackJetOffset': 'jetpack_jet_offset',
            'jetpackJet2Offset': 'jetpack_jet2_offset',
            'jetpackJetAngles': 'jetpack_jet_angles',
            'jetpackJet2Angles': 'jetpack_jet2_angles',
            'jetpackFinishSound': 'jetpack_finish_sound',
            'jetpackThrustSound': 'jetpack_thrust_sound',
            'jetpackIdleSound': 'jetpack_idle_sound',
            'jetpackStartSound': 'jetpack_start_sound',
        }
        
        for field_name, attr_name in jetpack_fields.items():
            jetpack_match = re.search(rf'{field_name}\s+["\']?([^"\'\n]*)["\']?', class_info)
            if jetpack_match:
                setattr(char, attr_name, jetpack_match.group(1).strip())
        
        # Extract custom build system fields
        # Basic custom build flags
        iscustombuild_match = re.search(r'isCustomBuild\s+(\d+)', class_info)
        if iscustombuild_match:
            char.custom_build.is_custom_build = bool(int(iscustombuild_match.group(1)))
        
        mbpoints_match = re.search(r'mbPoints\s+(\d+)', class_info)
        if mbpoints_match:
            char.custom_build.mb_points = int(mbpoints_match.group(1))
        
        hascustomspec_match = re.search(r'hasCustomSpec\s+(\d+)', class_info)
        if hascustomspec_match:
            char.custom_build.has_custom_spec = int(hascustomspec_match.group(1))
        
        isonlyonespec_match = re.search(r'isOnlyOneSpec\s+(\d+)', class_info)
        if isonlyonespec_match:
            char.custom_build.is_only_one_spec = bool(int(isonlyonespec_match.group(1)))
        
        # Rank-based stats
        rankbasespeed_match = re.search(r'rankbasespeed\s+([^\n]+)', class_info)
        if rankbasespeed_match:
            char.custom_build.rank_base_speed = [float(x.strip()) for x in rankbasespeed_match.group(1).split(',')]
        
        rankhealth_match = re.search(r'rankHealth\s+([^\n]+)', class_info)
        if rankhealth_match:
            char.custom_build.rank_health = [int(x.strip()) for x in rankhealth_match.group(1).split(',')]
        
        rankarmor_match = re.search(r'rankArmor\s+([^\n]+)', class_info)
        if rankarmor_match:
            char.custom_build.rank_armor = [int(x.strip()) for x in rankarmor_match.group(1).split(',')]
        
        ranksabermaxchain_match = re.search(r'rankSaberMaxChain\s+([^\n]+)', class_info)
        if ranksabermaxchain_match:
            char.custom_build.rank_saber_max_chain = [int(x.strip()) for x in ranksabermaxchain_match.group(1).split(',')]
        
        rankas_match = re.search(r'rankAS\s+([^\n]+)', class_info)
        if rankas_match:
            char.custom_build.rank_as = [float(x.strip()) for x in rankas_match.group(1).split(',')]
        
        rankbp_match = re.search(r'rankBP\s+([^\n]+)', class_info)
        if rankbp_match:
            char.custom_build.rank_bp = [float(x.strip()) for x in rankbp_match.group(1).split(',')]
        
        rankstm_match = re.search(r'rankSTM\s+([^\n]+)', class_info)
        if rankstm_match:
            char.custom_build.rank_stm = [float(x.strip()) for x in rankstm_match.group(1).split(',')]
        
        rankrofmelee_match = re.search(r'rankROFMelee\s+([^\n]+)', class_info)
        if rankrofmelee_match:
            char.custom_build.rank_rof_melee = [float(x.strip()) for x in rankrofmelee_match.group(1).split(',')]
        
        # Other custom build fields
        knockbacktaken_match = re.search(r'knockbackTaken\s+([\d.]+)', class_info)
        if knockbacktaken_match:
            char.custom_build.knockback_taken = float(knockbacktaken_match.group(1))
        
        forceregen_match = re.search(r'forceregen\s+([\d.]+)', class_info)
        if forceregen_match:
            char.custom_build.force_regen = float(forceregen_match.group(1))
        
        sabermaxchain_match = re.search(r'saberMaxChain\s+(\d+)', class_info)
        if sabermaxchain_match:
            char.custom_build.saber_max_chain = int(sabermaxchain_match.group(1))
        
        skilltimermod_match = re.search(r'skilltimermod\s+([\d.]+)', class_info)
        if skilltimermod_match:
            char.custom_build.skilltimermod = float(skilltimermod_match.group(1))
        
        rofmelee_match = re.search(r'rateOfFire_Melee\s+([\d.]+)', class_info)
        if rofmelee_match:
            char.custom_build.rate_of_fire_melee = float(rofmelee_match.group(1))
        
        # Extract custom specializations (customSpecName_N, customSpecIcon_N, customSpecDesc_N)
        customspec_matches = re.finditer(r'customSpec(Name|Icon|Desc)_(\d+)\s+["\']?([^"\'\n]+)["\']?', class_info)
        for match in customspec_matches:
            field_type = match.group(1).lower()  # name, icon, or desc
            spec_num = int(match.group(2))
            value = match.group(3).strip()
            
            if field_type == 'name':
                char.custom_build.add_specialization(spec_num, name=value)
            elif field_type == 'icon':
                char.custom_build.add_specialization(spec_num, icon=value)
            elif field_type == 'desc':
                char.custom_build.add_specialization(spec_num, desc=value)
        
        # Extract custom attributes (c_att_skill_N, c_att_names_N, c_att_ranks_N, c_att_descs_N)
        customatt_matches = re.finditer(r'c_att_(skill|names|ranks|descs)_(\d+)\s+([^\n]+)', class_info)
        for match in customatt_matches:
            field_type = match.group(1)  # skill, names, ranks, or descs
            attr_num = int(match.group(2))
            value = match.group(3).strip().strip('"')
            
            if field_type == 'skill':
                char.custom_build.add_attribute(attr_num, skill=value)
            elif field_type == 'names':
                char.custom_build.add_attribute(attr_num, names=value)
            elif field_type == 'ranks':
                ranks = [x.strip() for x in value.split(',')]
                char.custom_build.add_attribute(attr_num, ranks=ranks)
            elif field_type == 'descs':
                char.custom_build.add_attribute(attr_num, descs=value)
        
        # Identify unknown/unparsed fields
        # List of all known field patterns
        known_patterns = [
            r'name\s+',
            r'MBClass\s+',
            r'classNumberLimit\s+',
            r'weapons\s+',
            r'attributes\s+',
            r'maxhealth\s+',
            r'mmaxhealth\s+',
            r'maxarmor\s+',
            r'model(?:_\d+(?:_\d+)?|1)?\s+',
            r'skin(?:_\d+(?:_\d+)?|1)?\s+',
            r'uishader(?:_\d+(?:_\d+)?|1)?\s+',
            r'forcepool\s+',
            r'resource\s+',
            r'holdables\s+',
            r'rateOfFire\s+',
            r'speed\s+',
            r'special[1-4]\s+',
            r'uioverlay(?:_[lcr])?\s+',
            r'modelscale\s+',
            r'classflags\s+',
            r'extralives\s+',
            r'extrakuves\s+',
            r'forcepowers\s+',
            r'forceallignment\s+',
            r'forgeregen\s+',
            r'baseSpeed\s+',
            r'[ABCD][PS]Multiplier\s+',
            r'[ABCD][PS]multuplier\s+',
            r'saber[12](?:_\d+)?\s+',
            r'saberstyle\s+',
            r'saberDamage\s+',
            r'saberSpecialDamage\s+',
            r'sabercolor(?:_\d+|1)?\s+',
            r'saber2color(?:_\d+)?\s+',
            r'saberstyle(?:s|_\d+)?\s+',
            r'custom(red|green|blue)(?:_\d+)?\s+',
            r'userRGB(?:_\d+)?\s+',
            r'saber[Tt]hrow[Dd]amage\s+',
            r'APmodifier\s+',
            r'APBonus\s+',
            r'damageGiven\s+',
            r'[Dd]amageTaken\s+',
            r'[Kk]nockback[Gg]iven\s+',
            r'meleeknockback(?:_flat|_mult)?\s+',
            r'[Mm]elee[Mm]oves\s+',
            r'[Hh]ealth[Rr]egen[Rr]ate\s+',
            r'[Hh]ealth[Rr]egen[Aa]mount\s+',
            r'[Hh]ealth[Rr]egen[Cc]ap\s+',
            r'[Aa]rmour[Rr]egen[Rr]ate\s+',
            r'[Aa]rmour[Rr]egen[Aa]mount\s+',
            r'[Aa]rmour[Rr]egen[Cc]ap\s+',
            r'blockRegen[RrAaCc][a-z]+\s+',
            r'starthealth\s+',
            r'resource(Amount|Cap|Cooldown|RegenAmount|RegenCap|RegenRate)\s+',
            r'resource_force',
            r'respawn(CustomTime|Wait)\s+',
            r'customveh\s+',
            r'headSwap(Model|Skin)\s+',
            r'disableGunBash\s+',
            r'forceBlocking\s+',
            r'hackRate\s+',
            r'humanoidSkeleton\s+',
            r'(barge|rage)SoundOverride\s+',
            r'saberStanceAnim\s+',
            r'flourishAnim\s+',
            r'[Ww]alk[Bb]ackward\s+',
            r'[Ww]alk[Ff]orward\s+',
            r'[Rr]un[Bb]ackward\s+',
            r'[Rr]un[Ff]orward\s+',
            r'gloatAnim\s+',
            r'tauntAnim\s+',
            r'bowAnim\s+',
            r'meditateAnim\s+',
            r'[Ii]dle[Aa]nim\s+',
            r'deathAnim\s+',
            r'WP_\w+Flags\s+',
            r'jetpack\w+\s+',
            r'isCustomBuild\s+',
            r'mbPoints\s+',
            r'hasCustomSpec\s+',
            r'isOnlyOneSpec\s+',
            r'rank\w+\s+',
            r'knockbackTaken\s+',
            r'forceregen\s+',
            r'saberMaxChain\s+',
            r'skilltimermod\s+',
            r'rateOfFire_Melee\s+',
            r'customSpec\w+_\d+\s+',
            r'c_att_\w+_\d+\s+',
            r'//.*',  # Comments
            r'^\s*$',  # Empty lines
        ]
        
        # Split ClassInfo into lines and check each one
        for line in class_info.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Check if this line matches any known pattern
            is_known = False
            for pattern in known_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    is_known = True
                    break
            
            # If not known, add to unknown_fields
            if not is_known:
                char.unknown_fields.append(line)
    
    # Parse WeaponInfo sections
    weapon_info_matches = re.finditer(r'WeaponInfo(\d+)\s*\{([^}]*)\}', content, re.DOTALL)
    for match in weapon_info_matches:
        weapon_num = match.group(1)
        weapon_content = match.group(2)
        
        weapon_data = {
            'number': weapon_num,
        }
        
        # Extract all weapon fields
        # WeaponToReplace
        replace_match = re.search(r'WeaponToReplace\s+(\S+)', weapon_content)
        if replace_match:
            weapon_data['WeaponToReplace'] = replace_match.group(1).strip()
        
        # WeaponBasedOff
        based_match = re.search(r'WeaponBasedOff\s+(\S+)', weapon_content)
        if based_match:
            weapon_data['WeaponBasedOff'] = based_match.group(1).strip()
        
        # WeaponName
        name_match = re.search(r'WeaponName\s+["\']?([^"\'\n]+)["\']?', weapon_content)
        if name_match:
            weapon_data['WeaponName'] = name_match.group(1).strip()
        
        # Models
        world_model_match = re.search(r'NewWorldModel\s+["\']?([^"\'\n]+)["\']?', weapon_content)
        if world_model_match:
            weapon_data['NewWorldModel'] = world_model_match.group(1).strip()
        
        view_model_match = re.search(r'NewViewModel\s+["\']?([^"\'\n]+)["\']?', weapon_content)
        if view_model_match:
            weapon_data['NewViewModel'] = view_model_match.group(1).strip()
        
        # Icon
        icon_match = re.search(r'Icon\s+["\']?([^"\'\n]+)["\']?', weapon_content)
        if icon_match:
            weapon_data['Icon'] = icon_match.group(1).strip()
        
        # Ammo settings
        custom_ammo_match = re.search(r'customAmmo\s+([\d.]+)', weapon_content)
        if custom_ammo_match:
            weapon_data['customAmmo'] = float(custom_ammo_match.group(1))
        
        clip_size_match = re.search(r'clipSize\s+([\d.]+)', weapon_content)
        if clip_size_match:
            weapon_data['clipSize'] = int(clip_size_match.group(1))
        
        # Reload settings
        reload_time_match = re.search(r'ReloadTimeModifier\s+([\d.]+)', weapon_content)
        if reload_time_match:
            weapon_data['ReloadTimeModifier'] = float(reload_time_match.group(1))
        
        # Damage settings
        prim_damage_match = re.search(r'primDamage\s+([\d.]+)', weapon_content)
        if prim_damage_match:
            weapon_data['primDamage'] = float(prim_damage_match.group(1))
        
        alt_damage_match = re.search(r'altDamage\s+([\d.]+)', weapon_content)
        if alt_damage_match:
            weapon_data['altDamage'] = float(alt_damage_match.group(1))
        
        # Fire rate
        prim_fire_rate_match = re.search(r'primFireRate\s+([\d.]+)', weapon_content)
        if prim_fire_rate_match:
            weapon_data['primFireRate'] = float(prim_fire_rate_match.group(1))
        
        alt_fire_rate_match = re.search(r'altFireRate\s+([\d.]+)', weapon_content)
        if alt_fire_rate_match:
            weapon_data['altFireRate'] = float(alt_fire_rate_match.group(1))
        
        # Gore settings
        prim_gore_match = re.search(r'primGore\s+(\d+)', weapon_content)
        if prim_gore_match:
            weapon_data['primGore'] = bool(int(prim_gore_match.group(1)))
        
        alt_gore_match = re.search(r'altGore\s+(\d+)', weapon_content)
        if alt_gore_match:
            weapon_data['altGore'] = bool(int(alt_gore_match.group(1)))
        
        # Charge settings
        fp_charge_mult_match = re.search(r'FPChargeMult\s+([\d.]+)', weapon_content)
        if fp_charge_mult_match:
            weapon_data['FPChargeMult'] = float(fp_charge_mult_match.group(1))
        
        # Sounds
        charge_sound_match = re.search(r'ChargeSound\s+["\']?([^"\'\n]+)["\']?', weapon_content)
        if charge_sound_match:
            weapon_data['ChargeSound'] = charge_sound_match.group(1).strip()
        
        fire_sound_match = re.search(r'FireSound\s+["\']?([^"\'\n]+)["\']?', weapon_content)
        if fire_sound_match:
            weapon_data['FireSound'] = fire_sound_match.group(1).strip()
        
        alt_fire_sound_match = re.search(r'AltFireSound\s+["\']?([^"\'\n]+)["\']?', weapon_content)
        if alt_fire_sound_match:
            weapon_data['AltFireSound'] = alt_fire_sound_match.group(1).strip()
        
        # Animation overrides
        has_anim_overrides_match = re.search(r'hasAnimOverrides\s+(\d+)', weapon_content)
        if has_anim_overrides_match:
            weapon_data['hasAnimOverrides'] = bool(int(has_anim_overrides_match.group(1)))
        
        # Misc settings
        idle_in_scope_match = re.search(r'idleInScope\s+(\d+)', weapon_content)
        if idle_in_scope_match:
            weapon_data['idleInScope'] = bool(int(idle_in_scope_match.group(1)))
        
        # Projectile settings
        prim_projectile_match = re.search(r'primProjectile\s+(\S+)', weapon_content)
        if prim_projectile_match:
            weapon_data['primProjectile'] = prim_projectile_match.group(1).strip()
        
        alt_projectile_match = re.search(r'altProjectile\s+(\S+)', weapon_content)
        if alt_projectile_match:
            weapon_data['altProjectile'] = alt_projectile_match.group(1).strip()
        
        char.weapon_infos.append(weapon_data)
    
    # Parse description
    desc_match = re.search(r'description\s+"([^"]*)"', content, re.DOTALL)
    if desc_match:
        char.description = desc_match.group(1).strip()
    
    return char


def read_pk3_characters(pk3_path):
    """
    Read all character files from a .pk3 archive
    
    Args:
        pk3_path: Path to the .pk3 file
        
    Returns:
        List of CharacterInfo objects
    """
    characters = []
    
    if not os.path.exists(pk3_path):
        print(f"Error: File not found: {pk3_path}")
        return characters
    
    if not pk3_path.lower().endswith('.pk3'):
        print(f"Warning: File does not have .pk3 extension: {pk3_path}")
    
    try:
        with ZipFile(pk3_path, 'r') as zip_file:
            # Get all files in the archive
            all_files = zip_file.namelist()
            
            # Filter for character files in ext_data/mb2/character/
            char_files = [f for f in all_files 
                         if 'ext_data/mb2/character/' in f.lower() 
                         and f.lower().endswith('.mbch')]
            
            if not char_files:
                print(f"No character files found in {pk3_path}")
                print(f"Searched for files in: ext_data/mb2/character/")
                return characters
            
            print(f"Found {len(char_files)} character file(s) in {os.path.basename(pk3_path)}")
            
            # Parse each character file
            for char_file in char_files:
                try:
                    content = zip_file.read(char_file).decode('utf-8', errors='ignore')
                    char_info = parse_mbch_content(content, char_file)
                    characters.append(char_info)
                    print(f"  - Parsed: {os.path.basename(char_file)} (Name: {char_info.name})")
                except Exception as e:
                    print(f"  - Error parsing {char_file}: {e}")
            
    except Exception as e:
        print(f"Error reading PK3 file: {e}")
    
    return characters


def print_character_summary(char):
    """Print a formatted summary of a character"""
    print("\n" + "="*80)
    print(f"CHARACTER: {char.name or 'Unknown'}")
    print("="*80)
    print(f"File: {char.filename}")
    print(f"Class: {char.mb_class or 'Unknown'}")
    if char.class_number_limit:
        print(f"Class Limit: {char.class_number_limit}")
    print(f"Health: {char.max_health or 'N/A'}")
    print(f"Armor: {char.max_armor or 'N/A'}")
    
    # Additional stats
    if char.forcepool:
        print(f"Force Pool: {char.forcepool}")
    if char.resource:
        print(f"Resource: {char.resource}")
    if char.speed:
        print(f"Speed: {char.speed}")
    if char.base_speed:
        print(f"Base Speed: {char.base_speed}")
    if char.rate_of_fire:
        print(f"Rate of Fire: {char.rate_of_fire}")
    if char.modelscale:
        print(f"Model Scale: {char.modelscale}")
    if char.extralives:
        print(f"Extra Lives: {char.extralives}")
    if char.damage_given:
        print(f"Damage Given: {char.damage_given}")
    if char.damage_taken:
        print(f"Damage Taken: {char.damage_taken}")
    if char.melee_knockback:
        print(f"Melee Knockback: {char.melee_knockback}")
    if char.melee_knockback_flat:
        print(f"Melee Knockback Flat: {char.melee_knockback_flat}")
    if char.melee_knockback_mult:
        print(f"Melee Knockback Mult: {char.melee_knockback_mult}")
    if char.melee_moves:
        print(f"Melee Moves: {char.melee_moves}")
    if char.knockback_given:
        print(f"Knockback Given: {char.knockback_given}")
    if char.start_health:
        print(f"Start Health: {char.start_health}")
    if char.respawn_custom_time:
        print(f"Respawn Time: {char.respawn_custom_time}ms")
    if char.custom_veh:
        print(f"Custom Vehicle: {char.custom_veh}")
    if char.head_swap_model:
        print(f"Head Swap Model: {char.head_swap_model}")
    if char.head_swap_skin:
        print(f"Head Swap Skin: {char.head_swap_skin}")
    
    # Regeneration stats
    if any([char.health_regen_rate, char.health_regen_amount, char.health_regen_cap,
            char.armour_regen_rate, char.armour_regen_amount, char.armour_regen_cap,
            char.block_regen_rate, char.block_regen_amount, char.block_regen_cap]):
        print(f"\nRegeneration:")
        if char.health_regen_rate or char.health_regen_amount or char.health_regen_cap:
            print(f"  Health: Rate={char.health_regen_rate or 'N/A'}, Amount={char.health_regen_amount or 'N/A'}, Cap={char.health_regen_cap or 'N/A'}")
        if char.armour_regen_rate or char.armour_regen_amount or char.armour_regen_cap:
            print(f"  Armour: Rate={char.armour_regen_rate or 'N/A'}, Amount={char.armour_regen_amount or 'N/A'}, Cap={char.armour_regen_cap or 'N/A'}")
        if char.block_regen_rate or char.block_regen_amount or char.block_regen_cap:
            print(f"  Block: Rate={char.block_regen_rate or 'N/A'}, Amount={char.block_regen_amount or 'N/A'}, Cap={char.block_regen_cap or 'N/A'}")
    
    # Resource system
    if any([char.resource_amount, char.resource_cap, char.resource_cooldown,
            char.resource_regen_amount, char.resource_regen_cap, char.resource_regen_rate, char.resource_force]):
        print(f"\nResource System:")
        if char.resource_force:
            print(f"  Type: Force")
        if char.resource_amount:
            print(f"  Amount: {char.resource_amount}")
        if char.resource_cap:
            print(f"  Cap: {char.resource_cap}")
        if char.resource_cooldown:
            print(f"  Cooldown: {char.resource_cooldown}")
        if char.resource_regen_rate:
            print(f"  Regen Rate: {char.resource_regen_rate}")
        if char.resource_regen_amount:
            print(f"  Regen Amount: {char.resource_regen_amount}")
        if char.resource_regen_cap:
            print(f"  Regen Cap: {char.resource_regen_cap}")
    
    # Misc flags
    if any([char.disable_gun_bash, char.force_blocking, char.hack_rate, char.humanoid_skeleton, char.user_rgb]):
        print(f"\nMisc Flags:")
        if char.disable_gun_bash:
            print(f"  Disable Gun Bash: Yes")
        if char.force_blocking:
            print(f"  Force Blocking: Yes")
        if char.hack_rate:
            print(f"  Hack Rate: {char.hack_rate}")
        if char.humanoid_skeleton:
            print(f"  Humanoid Skeleton: Yes")
        if char.user_rgb:
            print(f"  User RGB: Yes")
    
    # UI Overlays
    if char.uioverlay:
        print(f"UI Overlay: {char.uioverlay}")
    if char.uioverlay_l or char.uioverlay_c or char.uioverlay_r:
        print(f"UI Overlays: L={char.uioverlay_l or 'N/A'}, C={char.uioverlay_c or 'N/A'}, R={char.uioverlay_r or 'N/A'}")
    
    # Multipliers
    if char.bp_multiplier or char.cs_multiplier or char.as_multiplier or char.ap_modifier or char.ap_bonus:
        print(f"\nMultipliers:")
        if char.bp_multiplier:
            print(f"  BP: {char.bp_multiplier}")
        if char.cs_multiplier:
            print(f"  CS: {char.cs_multiplier}")
        if char.as_multiplier:
            print(f"  AS: {char.as_multiplier}")
        if char.ap_modifier:
            print(f"  AP Modifier: {char.ap_modifier}")
        if char.ap_bonus:
            print(f"  AP Bonus: {char.ap_bonus}")
    
    # Class flags
    if char.classflags:
        print(f"\nClass Flags ({len(char.classflags)}):")
        for flag in char.classflags:
            print(f"  - {flag}")
    
    if char.holdables:
        print(f"\nHoldables ({len(char.holdables)}):")
        for holdable in char.holdables:
            print(f"  - {holdable}")
    
    if char.weapons:
        print(f"\nWeapons ({len(char.weapons)}):")
        for weapon in char.weapons:
            print(f"  - {weapon}")
    
    if char.attributes:
        print(f"\nAttributes ({len(char.attributes)}):")
        for attr in char.attributes:
            print(f"  - {attr}")
    
    if char.models:
        print(f"\nModels ({len(char.models)}):")
        for model_num, model_name, skin_name, uishader in char.models:
            model_str = f"  [{model_num}] Model: {model_name or 'N/A'}"
            if skin_name:
                model_str += f", Skin: {skin_name}"
            if uishader:
                model_str += f", UI: {uishader}"
            print(model_str)
    
    # Force powers
    if char.forcepowers:
        print(f"\nForce Powers ({len(char.forcepowers)}):")
        for power in char.forcepowers:
            print(f"  - {power}")
    
    # Saber configuration
    if (char.saber1 or char.saber2 or char.saberstyle or char.saber_color or 
        char.saber2_color or char.model_sabers or char.saber_colors):
        print(f"\nSaber Configuration:")
        if char.saber1:
            print(f"  Saber 1: {char.saber1}")
        if char.saber2:
            print(f"  Saber 2: {char.saber2}")
        if char.saber_color is not None:
            print(f"  Saber Color: {char.saber_color}")
        if char.saber2_color is not None:
            print(f"  Saber 2 Color: {char.saber2_color}")
        if char.custom_red is not None or char.custom_green is not None or char.custom_blue is not None:
            print(f"  Custom RGB: ({char.custom_red or 0}, {char.custom_green or 0}, {char.custom_blue or 0})")
        if char.saberstyle:
            print(f"  Styles: {', '.join(char.saberstyle)}")
        if char.saber_damage:
            print(f"  Damage: {char.saber_damage}")
        if char.saber_special_damage:
            print(f"  Special Damage: {char.saber_special_damage}")
        if char.saber_throw_damage:
            print(f"  Throw Damage: {char.saber_throw_damage}")
        
        # Model-specific sabers
        if char.model_sabers:
            print(f"  Model-Specific Sabers:")
            for model_num in sorted(char.model_sabers.keys(), key=lambda x: int(x)):
                saber1, saber2 = char.model_sabers[model_num]
                if saber1 or saber2:
                    print(f"    Model {model_num}: Saber1={saber1 or 'N/A'}, Saber2={saber2 or 'N/A'}")
        
        # Model-specific colors
        if char.saber_colors:
            print(f"  Model-Specific Colors:")
            for model_num in sorted(char.saber_colors.keys(), key=lambda x: int(x)):
                color1, color2 = char.saber_colors[model_num]
                if color1 is not None or color2 is not None:
                    print(f"    Model {model_num}: Color1={color1 if color1 is not None else 'N/A'}, Color2={color2 if color2 is not None else 'N/A'}")
        
        # Model-specific custom RGB
        if char.model_custom_rgb:
            print(f"  Model-Specific Custom RGB:")
            for model_num in sorted(char.model_custom_rgb.keys(), key=lambda x: int(x)):
                r, g, b = char.model_custom_rgb[model_num]
                print(f"    Model {model_num}: RGB=({r or 0}, {g or 0}, {b or 0})")
        
        # Model-specific user RGB flags
        if char.model_user_rgb:
            print(f"  Model-Specific User RGB:")
            for model_num in sorted(char.model_user_rgb.keys(), key=lambda x: int(x)):
                if char.model_user_rgb[model_num]:
                    print(f"    Model {model_num}: Enabled")
        
        # Model-specific saberstyles
        if char.model_saberstyles:
            print(f"  Model-Specific Styles:")
            for model_num in sorted(char.model_saberstyles.keys(), key=lambda x: int(x)):
                styles = char.model_saberstyles[model_num]
                print(f"    Model {model_num}: {', '.join(styles)}")
    
    # Animations
    if any([char.saber_stance_anim, char.flourish_anim, char.walk_backward, 
            char.walk_forward, char.run_backward, char.run_forward,
            char.gloat_anim, char.taunt_anim, char.bow_anim, char.meditate_anim,
            char.idle_anim, char.death_anim]):
        print(f"\nAnimations:")
        if char.idle_anim:
            print(f"  Idle: {char.idle_anim}")
        if char.saber_stance_anim:
            print(f"  Saber Stance: {char.saber_stance_anim}")
        if char.flourish_anim:
            print(f"  Flourish: {char.flourish_anim}")
        if char.walk_forward:
            print(f"  Walk Forward: {char.walk_forward}")
        if char.walk_backward:
            print(f"  Walk Backward: {char.walk_backward}")
        if char.run_forward:
            print(f"  Run Forward: {char.run_forward}")
        if char.run_backward:
            print(f"  Run Backward: {char.run_backward}")
        if char.gloat_anim:
            print(f"  Gloat: {char.gloat_anim}")
        if char.taunt_anim:
            print(f"  Taunt: {char.taunt_anim}")
        if char.bow_anim:
            print(f"  Bow: {char.bow_anim}")
        if char.meditate_anim:
            print(f"  Meditate: {char.meditate_anim}")
        if char.death_anim:
            print(f"  Death: {char.death_anim}")
    
    # Sound overrides
    if char.barge_sound_override or char.rage_sound_override:
        print(f"\nSound Overrides:")
        if char.barge_sound_override:
            print(f"  Barge: {char.barge_sound_override}")
        if char.rage_sound_override:
            print(f"  Rage: {char.rage_sound_override}")
    
    # Weapon flags
    if char.weapon_flags:
        print(f"\nWeapon Flags ({len(char.weapon_flags)}):")
        for weapon, flags in sorted(char.weapon_flags.items()):
            print(f"  {weapon}: {', '.join(flags)}")
    
    # Jetpack configuration
    jetpack_fields = [
        char.jetpack_thrust_effect, char.jetpack_idle_effect,
        char.jetpack_jet_tag, char.jetpack_jet2_tag,
        char.jetpack_jet_offset, char.jetpack_jet2_offset,
        char.jetpack_jet_angles, char.jetpack_jet2_angles,
        char.jetpack_finish_sound, char.jetpack_thrust_sound,
        char.jetpack_idle_sound, char.jetpack_start_sound
    ]
    if any(jetpack_fields):
        print(f"\nJetpack Configuration:")
        if char.jetpack_jet_tag:
            print(f"  Jet Tag: {char.jetpack_jet_tag}")
        if char.jetpack_jet2_tag:
            print(f"  Jet2 Tag: {char.jetpack_jet2_tag}")
        if char.jetpack_jet_offset:
            print(f"  Jet Offset: {char.jetpack_jet_offset}")
        if char.jetpack_jet2_offset:
            print(f"  Jet2 Offset: {char.jetpack_jet2_offset}")
        if char.jetpack_jet_angles:
            print(f"  Jet Angles: {char.jetpack_jet_angles}")
        if char.jetpack_jet2_angles:
            print(f"  Jet2 Angles: {char.jetpack_jet2_angles}")
        if char.jetpack_thrust_effect:
            print(f"  Thrust Effect: {char.jetpack_thrust_effect}")
        if char.jetpack_idle_effect:
            print(f"  Idle Effect: {char.jetpack_idle_effect}")
        if char.jetpack_start_sound:
            print(f"  Start Sound: {char.jetpack_start_sound}")
        if char.jetpack_thrust_sound:
            print(f"  Thrust Sound: {char.jetpack_thrust_sound}")
        if char.jetpack_idle_sound:
            print(f"  Idle Sound: {char.jetpack_idle_sound}")
        if char.jetpack_finish_sound:
            print(f"  Finish Sound: {char.jetpack_finish_sound}")
    
    if char.specials:
        print(f"\nSpecial Abilities ({len(char.specials)}):")
        for special_key in sorted(char.specials.keys()):
            print(f"  {special_key}: {char.specials[special_key]}")
    
    if char.weapon_infos:
        print(f"\nWeapon Configurations ({len(char.weapon_infos)}):")
        for weapon_info in char.weapon_infos:
            print(f"  [{weapon_info['number']}] {weapon_info.get('WeaponName', None) or 'Unnamed'}")
            if weapon_info['WeaponToReplace']:
                print(f"      Replaces: {weapon_info['WeaponToReplace']}")
    
    # Custom Build System
    if char.custom_build.has_custom_builds():
        print(f"\n{'='*80}")
        print("CUSTOM BUILD SYSTEM")
        print(f"{'='*80}")
        
        # Basic info
        if char.custom_build.is_custom_build:
            print(f"Custom Build: Enabled")
        if char.custom_build.mb_points:
            print(f"MB Points: {char.custom_build.mb_points}")
        if char.custom_build.has_custom_spec:
            print(f"Custom Specs Available: {char.custom_build.has_custom_spec}")
        if char.custom_build.is_only_one_spec:
            print(f"Only One Spec: Yes")
        
        # Rank-based stats
        if any([char.custom_build.rank_health, char.custom_build.rank_armor, 
                char.custom_build.rank_base_speed]):
            print(f"\nRank-Based Stats:")
            if char.custom_build.rank_health:
                print(f"  Health Ranks: {', '.join(map(str, char.custom_build.rank_health))}")
            if char.custom_build.rank_armor:
                print(f"  Armor Ranks: {', '.join(map(str, char.custom_build.rank_armor))}")
            if char.custom_build.rank_base_speed:
                print(f"  Speed Ranks: {', '.join(map(str, char.custom_build.rank_base_speed))}")
            if char.custom_build.rank_saber_max_chain:
                print(f"  Saber Chain Ranks: {', '.join(map(str, char.custom_build.rank_saber_max_chain))}")
            if char.custom_build.rank_as:
                print(f"  AS Ranks: {', '.join(map(str, char.custom_build.rank_as))}")
            if char.custom_build.rank_bp:
                print(f"  BP Ranks: {', '.join(map(str, char.custom_build.rank_bp))}")
            if char.custom_build.rank_stm:
                print(f"  STM Ranks: {', '.join(map(str, char.custom_build.rank_stm))}")
            if char.custom_build.rank_rof_melee:
                print(f"  Melee RoF Ranks: {', '.join(map(str, char.custom_build.rank_rof_melee))}")
        
        # Other custom fields
        if any([char.custom_build.knockback_taken, char.custom_build.force_regen,
                char.custom_build.saber_max_chain, char.custom_build.skilltimermod,
                char.custom_build.rate_of_fire_melee]):
            print(f"\nBase Values:")
            if char.custom_build.knockback_taken:
                print(f"  Knockback Taken: {char.custom_build.knockback_taken}")
            if char.custom_build.force_regen:
                print(f"  Force Regen: {char.custom_build.force_regen}")
            if char.custom_build.saber_max_chain:
                print(f"  Saber Max Chain: {char.custom_build.saber_max_chain}")
            if char.custom_build.skilltimermod:
                print(f"  Skill Timer Mod: {char.custom_build.skilltimermod}")
            if char.custom_build.rate_of_fire_melee:
                print(f"  Melee RoF: {char.custom_build.rate_of_fire_melee}")
        
        # Specializations
        if char.custom_build.specializations:
            print(f"\nSpecializations ({len(char.custom_build.specializations)}):")
            for spec_num in sorted(char.custom_build.specializations.keys()):
                spec = char.custom_build.specializations[spec_num]
                print(f"  [{spec_num}] {spec.name or 'Unnamed'}")
                if spec.icon:
                    print(f"      Icon: {spec.icon}")
                if spec.description:
                    print(f"      Desc: {spec.description}")
        
        # Custom Attributes
        if char.custom_build.attributes:
            print(f"\nCustom Attributes ({len(char.custom_build.attributes)}):")
            for attr_num in sorted(char.custom_build.attributes.keys()):
                attr = char.custom_build.attributes[attr_num]
                print(f"  [{attr_num}] {attr.skill or 'Unknown'}")
                if attr.names:
                    print(f"      Name: {attr.names}")
                if attr.ranks:
                    print(f"      Ranks: {', '.join(attr.ranks)}")
                if attr.descs:
                    print(f"      Desc: {attr.descs}")
    
    if char.description:
        print(f"\nDescription:")
        # Truncate long descriptions
        desc_lines = char.description.split('\n')
        for line in desc_lines[:10]:  # Show first 10 lines
            # Handle Unicode characters that may not be printable
            safe_line = line.encode('ascii', errors='replace').decode('ascii')
            print(f"  {safe_line}")
        if len(desc_lines) > 10:
            print(f"  ... ({len(desc_lines) - 10} more lines)")
    
    if char.unknown_fields:
        print(f"\n  Unknown/Unparsed Fields ({len(char.unknown_fields)}):")
        for unknown in char.unknown_fields:
            # Handle Unicode characters that may not be printable
            safe_unknown = unknown.encode('ascii', errors='replace').decode('ascii')
            print(f"  - {safe_unknown}")


def export_to_json(characters, output_file):
    """
    Export character data to a JSON file
    
    Args:
        characters: List of CharacterInfo objects
        output_file: Path to output JSON file
    """
    try:
        # Build a dictionary keyed by character name
        characters_by_name = {}
        for idx, char in enumerate(characters, start=1):
            # Prefer the parsed name; fallback to filename or an index-based key
            base_key = (char.name or os.path.basename(char.filename) if char.filename else None) or f"character_{idx}"
            key = base_key
            # Ensure unique keys by appending a numeric suffix when needed
            suffix = 2
            while key in characters_by_name:
                key = f"{base_key} ({suffix})"
                suffix += 1
            characters_by_name[key] = char.to_dict()

        # Convert all characters to JSON structure
        data = {
            'total_characters': len(characters_by_name),
            'characters': characters_by_name
        }

        # Write to JSON file with nice formatting
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n Successfully exported {len(characters_by_name)} characters to: {output_file}")
        print(f"  File size: {os.path.getsize(output_file):,} bytes")
        return True

    except Exception as e:
        print(f"\n✗ Error exporting to JSON: {e}")
        return False


def main():
    """Main entry point for the script"""
    if len(sys.argv) < 2:
        print("PK3 Character Reader Utility")
        print("="*80)
        print("\nUsage:")
        print(f"  python {os.path.basename(__file__)} <path_to_pk3_file> [--json output.json]")
        print("\nExamples:")
        print(f"  python {os.path.basename(__file__)} C:/MBII/zz_MBModels3.pk3")
        print(f"  python {os.path.basename(__file__)} C:/MBII/zz_MBModels3.pk3 --json characters.json")
        print("\nDescription:")
        print("  Extracts and displays character information from .mbch files")
        print("  located in the ext_data/mb2/character/ directory within a .pk3 archive.")
        print("\nOptions:")
        print("  --json <file>  Export character data to JSON file")
        sys.exit(1)
    
    pk3_path = sys.argv[1]
    
    # Check for JSON export option
    json_output = None
    if len(sys.argv) >= 4 and sys.argv[2] == '--json':
        json_output = sys.argv[3]
    
    # Normalize path
    pk3_path = os.path.normpath(pk3_path)
    
    print(f"Reading PK3 file: {pk3_path}")
    print("-"*80)
    
    # Read and parse characters
    characters = read_pk3_characters(pk3_path)
    
    if not characters:
        print("\nNo characters found or parsed.")
        sys.exit(0)
    
    # Print summary for each character
    print(f"\n\nFound {len(characters)} character(s) total")
    print("="*80)
    
    for char in characters:
        print_character_summary(char)
    
    # Print statistics
    print("\n" + "="*80)
    print("STATISTICS")
    print("="*80)
    print(f"Total characters: {len(characters)}")
    
    # Count by class
    class_counts = {}
    for char in characters:
        mb_class = char.mb_class or "Unknown"
        class_counts[mb_class] = class_counts.get(mb_class, 0) + 1
    
    print("\nCharacters by class:")
    for mb_class, count in sorted(class_counts.items()):
        print(f"  {mb_class}: {count}")
    
    # Collect all unique unknown fields
    all_unknown = set()
    chars_with_unknown = 0
    for char in characters:
        if char.unknown_fields:
            chars_with_unknown += 1
            for field in char.unknown_fields:
                # Extract just the field name (first word)
                field_name = field.split()[0] if field.split() else field
                all_unknown.add(field_name)
    
    if all_unknown:
        print(f"\n Unknown Fields Found:")
        print(f"  Characters with unknown fields: {chars_with_unknown}/{len(characters)}")
        print(f"  Unique unknown field names: {len(all_unknown)}")
        print("\n  Field names to implement:")
        for field_name in sorted(all_unknown):
            print(f"    - {field_name}")
    
    # Export to JSON if requested
    if json_output:
        print("\n" + "="*80)
        export_to_json(characters, json_output)


if __name__ == "__main__":
    main()
