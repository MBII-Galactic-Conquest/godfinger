TEAM_INVALID = -1337;
TEAM_GLOBAL = -1;
TEAM_GOOD   = 1;
TEAM_EVIL   = 2;
TEAM_SPEC   = 3;
TEAM_COUNT  = 3;

TEAMS = {
TEAM_GLOBAL: 'g',
'g':TEAM_GLOBAL,
'r': TEAM_GOOD,
TEAM_GOOD: 'r',
TEAM_EVIL : 'b',
'b' : TEAM_EVIL, 
TEAM_SPEC: 's',
's' : TEAM_SPEC
}

def TranslateTeam(num):
    return TEAMS[num]