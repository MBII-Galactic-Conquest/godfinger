import re


# default aka white, is 7
COLOR_CODES = \
{
    "^1":"red",
    "red":"^1",
    "^2":"green",
    "green":"^2",
    "^3":"yellow",
    "yellow":"^3",
    "^4":"blue",
    "blue":"^4",
    "^5":"lblue",
    "lblue":"^5",
    "^6":"pink",
    "pink":"^6",
    "^7":"default",
    "default":"^7",
    "^8":"orange",
    "orange":"^8",
    "^9":"gray",
    "gray":"^9",
    "^0":"black",
    "black":"^0"
};


# returns a copy of text string with added color wrappings
def ColorizeText(text, colorName, originalColorCode = "default"):
    return "" + COLOR_CODES[colorName] + text + COLOR_CODES[originalColorCode];

def HighlightSubstr(text, startIndex, endIndex, colorCode, originalColorCode="default"):
    return text[:startIndex] + COLOR_CODES[colorCode] + text[startIndex:endIndex] + COLOR_CODES[originalColorCode] + text[endIndex:]

def StripColorCodes(text) -> str:
    return re.sub("(\\^\\d)", '', text)