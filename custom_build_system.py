"""
Custom Build System Classes
Handles the custom build/loadout system for MBII characters
"""

class CustomSpecialization:
    """Represents a custom specialization/build option"""
    
    def __init__(self, spec_num):
        self.number = spec_num
        self.name = None
        self.icon = None
        self.description = None
    
    def __repr__(self):
        return f"CustomSpec({self.number}: {self.name})"


class CustomAttribute:
    """Represents a custom attribute/skill in the build system"""
    
    def __init__(self, attr_num):
        self.number = attr_num
        self.skill = None  # MB_ATT_* identifier
        self.names = None  # Display name(s)
        self.ranks = []    # Cost ranks (comma-separated values)
        self.descs = None  # Optional description
    
    def __repr__(self):
        return f"CustomAttr({self.number}: {self.skill})"


class CustomBuildSystem:
    """Manages the custom build/loadout system for a character"""
    
    def __init__(self):
        # Build system flags
        self.is_custom_build = False
        self.mb_points = None
        self.has_custom_spec = None
        self.is_only_one_spec = False
        
        # Rank-based stats
        self.rank_base_speed = []
        self.rank_health = []
        self.rank_armor = []
        self.rank_saber_max_chain = []
        self.rank_as = []  # Attack Speed
        self.rank_bp = []  # Block Points
        self.rank_stm = []  # Skill Timer Modifier
        self.rank_rof_melee = []  # Rate of Fire Melee
        
        # Other custom build fields
        self.knockback_taken = None
        self.force_regen = None
        self.saber_max_chain = None
        self.skilltimermod = None
        self.rate_of_fire_melee = None
        
        # Specializations (dict: number -> CustomSpecialization)
        self.specializations = {}
        
        # Custom attributes (dict: number -> CustomAttribute)
        self.attributes = {}
    
    def add_specialization(self, spec_num, name=None, icon=None, desc=None):
        """Add or update a specialization"""
        if spec_num not in self.specializations:
            self.specializations[spec_num] = CustomSpecialization(spec_num)
        
        spec = self.specializations[spec_num]
        if name:
            spec.name = name
        if icon:
            spec.icon = icon
        if desc:
            spec.description = desc
    
    def add_attribute(self, attr_num, skill=None, names=None, ranks=None, descs=None):
        """Add or update a custom attribute"""
        if attr_num not in self.attributes:
            self.attributes[attr_num] = CustomAttribute(attr_num)
        
        attr = self.attributes[attr_num]
        if skill:
            attr.skill = skill
        if names:
            attr.names = names
        if ranks:
            attr.ranks = ranks
        if descs:
            attr.descs = descs
    
    def has_custom_builds(self):
        """Check if this character has custom build system"""
        return self.is_custom_build or len(self.specializations) > 0 or len(self.attributes) > 0
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'is_custom_build': self.is_custom_build,
            'mb_points': self.mb_points,
            'has_custom_spec': self.has_custom_spec,
            'is_only_one_spec': self.is_only_one_spec,
            'rank_base_speed': self.rank_base_speed,
            'rank_health': self.rank_health,
            'rank_armor': self.rank_armor,
            'rank_saber_max_chain': self.rank_saber_max_chain,
            'rank_as': self.rank_as,
            'rank_bp': self.rank_bp,
            'rank_stm': self.rank_stm,
            'rank_rof_melee': self.rank_rof_melee,
            'knockback_taken': self.knockback_taken,
            'force_regen': self.force_regen,
            'saber_max_chain': self.saber_max_chain,
            'skilltimermod': self.skilltimermod,
            'rate_of_fire_melee': self.rate_of_fire_melee,
            'specializations': {
                num: {
                    'number': spec.number,
                    'name': spec.name,
                    'icon': spec.icon,
                    'description': spec.description
                }
                for num, spec in self.specializations.items()
            },
            'attributes': {
                num: {
                    'number': attr.number,
                    'skill': attr.skill,
                    'names': attr.names,
                    'ranks': attr.ranks,
                    'descs': attr.descs
                }
                for num, attr in self.attributes.items()
            }
        }
    
    def __repr__(self):
        return f"CustomBuildSystem(specs={len(self.specializations)}, attrs={len(self.attributes)})"
