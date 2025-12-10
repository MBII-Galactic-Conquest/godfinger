#   InterGalactic Banking Clan 2.0
#   A banking plugin for the Godfinger Movie Battles II plugin system
#   By Mantlar/ACHUTA https://www.github.com/mantlar
#   Plugin Dependencies (must be loaded before this in load order!): AccountSystem
#


import logging
import os
import time
from typing import Dict, Optional
from zipfile import ZipFile
from random import sample
from godfingerEvent import Event
from lib.shared.serverdata import ServerData
from database import DatabaseManager, ADatabase
from lib.shared.player import Player
import lib.shared.teams as teams
import lib.shared.colors as colors
import lib.shared.config as config
import godfingerEvent
import json # Required for json.loads()

# Initialize logger
Log = logging.getLogger(__name__)

# Global server data instance
SERVER_DATA = None

# Configuration file paths and defaults
DEFAULT_CFG_PATH = os.path.join(os.path.dirname(__file__), "bankingConfig.json")
DEFAULT_CFG = config.Config.fromJSON(DEFAULT_CFG_PATH)

# Fallback configuration if config file doesn't exist
CONFIG_FALLBACK = \
"""{
    "themecolor": "yellow",
    "kill_awards": {
        "kill": 10,
        "suicide": -5,
        "teamkill": -20
    },
    "smodPerms": {
        "modifycredits": [],
        "resetbounties": [],
        "teamcredits": []
    },
    "roundStartCredits": {
        "enabled": false,
        "minCredits": 10,
        "maxCredits": 50,
        "maxRounds": 5
    },
    "objectiveCredits": {
        "enabled": false,
        "credits": 10
    },
    "MBIIPath": "your/mbii/path/here",
    "siegeteamBanList": [],
    "siegeteamBanListIsWhitelist": false,
    "priceOverride": {},
    "defaultTeamPrice": 1000
}
"""

# Create default config if it doesn't exist
if DEFAULT_CFG is None:
    DEFAULT_CFG = config.Config()
    DEFAULT_CFG.cfg = json.loads(CONFIG_FALLBACK)
    Log.error(f"Could not open config file at {DEFAULT_CFG_PATH}, ensure the file is a valid JSON file in the correct file path.")
    with open(DEFAULT_CFG_PATH, "wt") as f:
        f.write(CONFIG_FALLBACK)

class PendingTransaction:
    def __init__(self, player):
        self.player = player
        self.player_id = player.GetId()
        self.timestamp = time.time()

    def on_confirm(self, plugin):
        pass

    def on_cancel(self, plugin):
        pass

class PendingPayment(PendingTransaction):
    def __init__(self, player, sender_account, target_account, amount):
        super().__init__(player)
        self.sender_account = sender_account
        self.target_account = target_account
        self.amount = amount

    def on_confirm(self, plugin):
        sender_account = self.sender_account
        target_account = self.target_account
        if plugin.transfer_credits(sender_account.user_id, target_account.user_id, self.amount):
            plugin.SvTell(sender_account.player_id, f"Sent {self.amount} credits to {target_account.player_name}^7")
            plugin.SvTell(target_account.player_id, f"Received {self.amount} credits from {sender_account.player_name}^7")
        else:
            plugin.SvTell(sender_account.player_id, "Transaction failed")
            plugin.SvTell(target_account.player_id, "Transaction failed")

    def on_cancel(self, plugin):
        plugin.SvTell(self.player_id, "Payment canceled.")
        plugin.SvTell(self.target_account.player_id, "Payment canceled by sender.")

class PendingBounty(PendingTransaction):
    def __init__(self, player, issuer_account, target_account, amount):
        super().__init__(player)
        self.issuer_account = issuer_account
        self.target_account = target_account
        self.amount = amount

    def on_confirm(self, plugin):
        issuer_player = self.player
        target_player = plugin.server_data.GetClientByID(self.target_account.player_id)
        plugin._place_bounty(issuer_player, target_player, self.amount)

    def on_cancel(self, plugin):
        plugin.SvTell(self.player_id, "Bounty canceled.")
        plugin.SvTell(self.target_account.player_id, "Bounty canceled by issuer.")

class PendingTeamPurchase(PendingTransaction):
    def __init__(self, player, team):
        super().__init__(player)
        self.team = team

    def on_confirm(self, plugin):
        player = self.player
        team = self.team
        price = team._price

        player_team = player.GetLastNonSpecTeamId()
        server_var_key = ""
        if player_team == teams.TEAM_GOOD:
            server_var_key = "team1_purchased_teams"
        elif player_team == teams.TEAM_EVIL:
            server_var_key = "team2_purchased_teams"

        if server_var_key:
            purchased_teams = plugin.server_data.GetServerVar(server_var_key) or []
            purchased_team_names = [t.name for t in purchased_teams]
            if team.GetName() not in purchased_team_names:
                if plugin.deduct_credits(player.GetId(), price):
                    purchased_teams.append(PurchasedTeam(team.GetName(), player.GetId(), price))
                    plugin.server_data.SetServerVar(server_var_key, purchased_teams)
                    team_color = "Red" if player_team == teams.TEAM_GOOD else "Blue"
                    plugin.SvTell(player.GetId(), f"Successfully purchased team: {team.GetName()} for {price} credits for the {team_color} team. ({colors.ColorizeText(str(plugin.get_credits(player.GetId())), plugin.themecolor)})")
                else:
                    plugin.SvTell(player.GetId(), "Transaction failed. Could not deduct credits.")
            else:
                plugin.SvTell(player.GetId(), f"Team '{team.GetName()}' has already been purchased.")
        else:
            plugin.SvTell(player.GetId(), "Transaction failed. Invalid team selection.")

    def on_cancel(self, plugin):
        plugin.SvTell(self.player_id, "Team purchase canceled.")

class PurchasedTeam:
    def __init__(self, name, buyer_id, price):
        self.name = name
        self.buyer_id = buyer_id
        self.price = price

class Bounty:
    def __init__(self, issuer_account, target_account, amount: int):
        self.issuer_account = issuer_account
        self.contributors = []
        self.target_account = target_account
        self.amount = amount
        self.timestamp = time.time()

    def add_amount(self, additional_amount: int) -> None:
        """Add to the existing bounty amount"""
        self.amount += additional_amount

class SiegeTeamContainer:
    def __init__(self, team_array, plugin_instance):
        self.plugin = plugin_instance
        self._teams = {}
        self._pages = []
        ban_list = [x.lower() for x in plugin_instance.config.cfg.get("siegeteamBanList", [])]
        is_whitelist = plugin_instance.config.cfg.get("siegeteamBanListIsWhitelist", False)
        price_override = plugin_instance.config.cfg.get("priceOverride", {})
        default_price = plugin_instance.config.cfg.get("defaultTeamPrice", 1000)
        
        for team in team_array:
            team_lower = team.GetName().lower()
            is_banned = team_lower in ban_list

            if (is_whitelist and not is_banned) or (not is_whitelist and is_banned):
                continue
            
            # Set default price
            team._price = default_price

            # Apply price override if exists
            if team.GetName() in price_override:
                team._price = price_override[team.GetName()]
                
            self._teams[team.GetName()] = team
        
        self._CreatePages()
    
    def GetAllTeams(self):
        return list(self._teams.values())
    
    def GetRandomTeams(self, num):
        return sample(list(self._teams.values()), min(num, len(self._teams)))
    
    def FindTeamWithName(self, name):
        return self._teams.get(name)

    def _CreatePages(self):
        self._pages = []
        all_teams = sorted(self.GetAllTeams(), key=lambda t: t.GetName().lower())
        if not all_teams:
            return

        page_str = ""
        max_len = 900 

        for team in all_teams:
            team_name = team.GetName()
            team_price = team.GetPrice()
            entry = f"{team_name} ({colors.ColorizeText(str(team_price), self.plugin.themecolor)})"
            
            if len(page_str) + len(entry) + 2 < max_len:
                if page_str:
                    page_str += ", " + entry
                else:
                    page_str = entry
            else:
                self._pages.append(page_str)
                page_str = entry
        
        if page_str:
            self._pages.append(page_str)

    def GetPage(self, page_num):
        if 0 <= page_num < len(self._pages):
            return self._pages[page_num]
        return None

    def GetPageCount(self):
        return len(self._pages)

class SiegeTeam:
    def __init__(self, name, path):
        self._name = name
        self._path = path
        self._price = 1000

    def GetName(self):
        return self._name
    
    def GetFilePath(self):
        return self._path
    
    def GetPrice(self):
        return self._price
    
    def __str__(self):
        return f"{self._name}"

def GetAllTeams() -> list[SiegeTeam]:
    """Scan PK3 files in MBII directories to discover available teams"""
    mbiiDir = os.path.abspath(DEFAULT_CFG.cfg["MBIIPath"])
    if not os.path.exists(mbiiDir):
        Log.info("Attempting to find MBII directory relative to the current working directory...")
        searchDir = os.getcwd()
        while True:
            if os.path.exists(os.path.join(searchDir, "MBII")):
                mbiiDir = os.path.join(searchDir, "MBII")
                Log.info(f"SUCCESS! Found MBII directory at {mbiiDir}.")
                break
            else:
                oldDir = searchDir
                searchDir = os.path.dirname(searchDir)
                if oldDir == searchDir:
                    Log.error("FAILURE. No MBII directory found through relative search.")
                    break

    if mbiiDir is None:
        Log.error("Cannot proceed as the MBII directory could not be located.")
        return []

    team_list = []
    dirsToProcess = [mbiiDir, os.path.normpath(os.path.join(mbiiDir, "../base"))];
    for sub_dir in dirsToProcess:
        for filename in os.listdir(sub_dir):
            if filename.endswith(".pk3"):
                try:
                    with ZipFile(os.path.join(sub_dir, filename)) as pk3:
                        for name in pk3.namelist():
                            if name.endswith(".mbtc") and not name.startswith("Sup_"):
                                team_name = os.path.basename(name).replace(".mbtc", "")
                                team_list.append(SiegeTeam(team_name, name))
                except Exception as e:
                    logging.error(f"Error reading PK3 {filename}: {str(e)}")
    return team_list

class BankingPlugin:

    def __init__(self, server_data: ServerData):

        # START OF MODIFIED CODE FOR CONFIG LOADING
        # Check if config loading failed and use fallback data
        if DEFAULT_CFG is None or DEFAULT_CFG.cfg.get("MBIIPath") in [None, "your/mbii/path/here"]:
            Log.error("MBIIPath is not configured in bankingConfig.json. The GetAllTeams function will not work.")
        if DEFAULT_CFG is None:
            Log.warning("Default config failed to load from file. Using fallback configuration.")
            # Create a minimal mock config object to prevent AttributeError: 'NoneType' object has no attribute 'cfg'
            self.config = type('MockConfig', (object,), {'cfg': CONFIG_FALLBACK})()
        else:
            self.config = DEFAULT_CFG
        # END OF MODIFIED CODE FOR CONFIG LOADING

        self.server_data = server_data
        self.accountsystem_xprts = None

        self.get_account_by_uid = None
        self.get_account_data_val_by_pid = None

        self.get_account_data_val_by_uid = None

        self.set_account_data_val_by_pid = None

        self.db_connection: ADatabase = None
        self.account_manager = None

        self.themecolor = self.config.cfg["themecolor"]
        self.msg_prefix = f'{colors.COLOR_CODES[self.themecolor]}[Bank]^7: '
        self._is_initialized = False

        self.pending_transactions : dict[int, PendingTransaction] = {}  # player_id: PendingTransaction
        self.active_bounties : dict[int, Bounty] = {}  # target_id: Bounty
        self.player_rounds : dict[int, int] = {}  # player_id: rounds_played
        self.player_class_by_pid : dict[int, str] = {}  # player_id: current character/class name
        self.team_container = SiegeTeamContainer(GetAllTeams(), self)
        self._register_commands()
        # self.initialize_banking_table()

    def _register_commands(self):
        self._command_list = {
            teams.TEAM_GLOBAL: {
                ("balance", "bal", "credits", "creds"):
                ("!balance - Check your current balance",
                 self._handle_balance),
                ("baltop", "credtop"):
                ("!baltop - View top 10 richest players", self._handle_baltop),
                ("pay", "send"): ("!pay <pfx> <amount> - Send credits to player",
                          self._handle_pay),
                ("confirm",): ("!confirm - Confirm pending transaction",
                              self._handle_confirm),
                ("bounty",): ("!bounty <pfx> <amount> - Place bounty",
                             self._handle_bounty),
                ("cancel",): ("!cancel - Cancel pending transaction",
                             self._handle_cancel),
                ("bounties",): ("!bounties - View active bounties",
                              self._handle_bounties),
                ("credrank", "balrank"): ("!credrank - Check your rank on the balance leaderboard",
                               self._handle_credrank),
                ("buyteam", "bt", "teambuy", "tb"): ("!buyteam <teamname> - Purchase a team for your side",
                                self._handle_buyteam),
                ("teamlist", "tl"): ("!teamlist <page> - List available teams with prices",
                                      self._handle_teamlist),
                ("teamsearch", "ts"): ("!teamsearch <term> - Search for teams by name",
                                          self._handle_teamsearch)
            }
        }
        self._smodCommandList = {
                # ... existing commands ...
            ("modifycredits", "modcredits") : ("!modifycredits <playerid> <amount> - modify a player's credits by the specified amount", self._handle_mod_credits),
            ("resetbounties", "rb") : ("!resetbounties - clears the bounty list", self._handle_reset_bounties),
            ("teamcredits", "tcredits") : ("!teamcredits <team> <amount> - add credits to all players on a team (1=red, 2=blue, 3=spec)", self._handle_team_credits),
            ("reloadextralives", "relives") : ("!reloadextralives - reload extralives.json table", self._handle_reload_extralives),
        }
        # Register commands with server
        newVal = []
        rCommands = self.server_data.GetServerVar("registeredCommands")
        if rCommands != None:
            newVal.extend(rCommands)
        for cmd in self._command_list[teams.TEAM_GLOBAL]:
            for i in cmd:
                if not i.isdecimal():
                    newVal.append((i, self._command_list[teams.TEAM_GLOBAL][cmd][0]))
        self.server_data.SetServerVar("registeredCommands", newVal)

        # Register SMOD commands
        new_smod_commands = []
        r_smod_commands = self.server_data.GetServerVar("registeredSmodCommands")
        if r_smod_commands:
            new_smod_commands.extend(r_smod_commands)
        
        for cmd in self._smodCommandList:
            for alias in cmd:
                new_smod_commands.append((alias, self._smodCommandList[cmd][0]))
        self.server_data.SetServerVar("registeredSmodCommands", new_smod_commands)

    def has_pending_action(self, player_id: int) -> bool:
        """Check if player has any pending actions"""
        return player_id in self.pending_transactions

    def check_smod_permission(self, command_name: str, smod_id: int) -> bool:
        """Check if an smod has permission to execute a command"""
        # Get smodPerms from config, default to empty dict if not present
        smod_perms = self.config.cfg.get("smodPerms", {})
        
        # If command not in config, allow all smods (backward compatibility)
        if command_name not in smod_perms:
            return True
        
        # Get allowed smod IDs for this command
        allowed_ids = smod_perms[command_name]
        
        # Empty list means all smods are allowed
        if not allowed_ids:
            return False
        
        # Check if this smod ID is in the allowed list
        return smod_id in allowed_ids

    def _handle_pay(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !pay command"""
        if self.has_pending_action(player.GetId()):
            self.SvTell(player.GetId(), "You already have a pending transaction!")
            return True

        if len(args) < 3:
            self.SvTell(player.GetId(), "Usage: !pay <name> <amount> [confirm]")
            return True
        
        # Check for confirm flag after amount
        confirm = args[-1].lower() == "confirm"

        # Parse amount - find where the amount argument is
        amount_idx = -2 if confirm else -1
        
        if not args[amount_idx].isdecimal() or int(args[amount_idx]) <= 0:
            self.SvTell(player.GetId(), "Invalid amount. Usage: !pay <name> <amount>")
            return True
        amount = int(args[amount_idx])
        
        # Everything between index 1 and amount_idx is the target name
        target_name = ' '.join(args[1:amount_idx])
        
        

        # Find matching players
        matching_players = self.find_players(target_name, exclude=player.GetId())
        
        if len(matching_players) == 0:
            self.SvTell(player.GetId(), f"No players found matching '{target_name}'")
            return True
        elif len(matching_players) > 1:
            # Multiple matches - show list
            player_list = ", ".join([f"{colors.StripColorCodes(p.GetName())}" for p in matching_players])
            self.SvTell(player.GetId(), f"2+ matches for '{target_name}': {player_list}. Please be more specific.")
            return True
        
        target = matching_players[0]
        target_id = target.GetId()

        # Validate sender's balance
        if self.get_credits(player.GetId()) < amount:
            self.SvTell(player.GetId(), "Insufficient funds")
            return True

        player_account = self.get_account_by_pid(player.GetId())
        target_account = self.get_account_by_pid(target_id)

        if confirm:
            # Transfer credits immediately
            if self.transfer_credits(player_account.user_id, target_account.user_id, amount):
                self.SvTell(player.GetId(), f"Sent {amount} credits to {target.GetName()}^7")
                self.SvTell(target_id, f"Received {amount} credits from {player.GetName()}^7")
            else:
                self.SvTell(player.GetId(), "Transaction failed")
        else:
            # Store pending transaction
            payment = PendingPayment(player, player_account, target_account, amount)
            self.pending_transactions[player.GetId()] = payment
            self.SvTell(player.GetId(), f"Pending payment of {amount} credits to {target.GetName()}^7. Type !confirm or !cancel.")
        return True

    def _handle_confirm(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !confirm command for pending transactions"""
        pid = player.GetId()
        
        if pid not in self.pending_transactions:
            self.SvTell(pid, "No pending transactions")
            return True

        transaction = self.pending_transactions[pid]
        transaction.on_confirm(self)
            
        # Remove transaction after processing
        if pid in self.pending_transactions:
            del self.pending_transactions[pid]
            
        return True

    def _place_bounty(self, issuer_player: Player, target_player: Player, amount: int) -> bool:
        """Handles the logic of placing or adding to a bounty."""
        issuer_id = issuer_player.GetId()
        target_id = target_player.GetId()
        issuer_account = self.get_account_by_pid(issuer_id)
        target_account = self.get_account_by_pid(target_id)

        if not self.deduct_credits(issuer_id, amount):
            self.SvTell(issuer_id, "Failed to place bounty (insufficient funds)")
            return False

        if target_id in self.active_bounties:
            # Add to existing bounty
            existing_bounty = self.active_bounties[target_id]
            existing_bounty.add_amount(amount)
            if issuer_account not in existing_bounty.contributors:
                existing_bounty.contributors.append(issuer_account)
            self.Say(f"Added {amount} credits to existing bounty on {target_player.GetName()}^7. Total: {existing_bounty.amount} credits")
            self.SvTell(target_id, f"Your bounty has increased by {amount} credits ({existing_bounty.amount}) by {issuer_player.GetName()}^7")
        else:
            # Create a new bounty
            bounty = Bounty(issuer_account, target_account, amount)
            if issuer_account not in bounty.contributors:
                bounty.contributors.append(issuer_account)
            self.active_bounties[target_id] = bounty
            self.Say(f"Bounty of {amount} credits placed on {target_player.GetName()}^7")
            self.SvTell(target_id, f"Bounty of {amount} credits placed on you by {issuer_player.GetName()}^7")
        
        return True

    def _handle_bounties(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !bounties command - display all active bounties"""
        if not self.active_bounties:
            self.Say("No active bounties. Use the !bounty <name> <amount> command to place one!")
            return True

        bounties = []
        for target_id, bounty in self.active_bounties.items():
            target_acc = bounty.target_account
            bounties.append(f"{target_acc.player_name}^7: {colors.ColorizeText('$' + str(bounty.amount), self.themecolor)}")

        self.Say("Active Bounties: " + ", ".join(bounties))
        return True

    def _handle_bounty(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !bounty command"""
        if self.has_pending_action(player.GetId()):
            self.SvTell(player.GetId(), "You already have a pending transaction!")
            return True

        if len(args) < 3:
            self.SvTell(player.GetId(), "Usage: !bounty <pfx> <amount>")
            return True

        confirm = len(args) > 3 and args[-1].lower() == "confirm"  # Check if last is "confirm"

        # Join the remaining args to handle names with spaces
        target_name = " ".join(args[1:-2]) if confirm else " ".join(args[1:-1])
        try:
            amount = int(args[-2]) if confirm else int(args[-1])
            if amount <= 0:
                raise ValueError
        except ValueError:
            self.SvTell(player.GetId(), "Invalid amount. Usage: !bounty <name> <amount>")
            return True


        # Find target player(s)
        targets = self.find_players(target_name, exclude=player.GetId())
        if not targets:
            self.SvTell(player.GetId(), f"No players found matching '{target_name}'. Usage: !bounty <name> <amount>")
            return True
        elif len(targets) > 1:
            # Multiple matches found, ask for clarification
            self.SvTell(player.GetId(), f"2+ matches for '{target_name}': {', '.join([t.GetName() for t in targets])}. Please be more specific.")
            return True

        target = targets[0]
        target_id = target.GetId()

        # Check if target is on the same team (prevent friendly bounties)
        player_team = player.GetTeamId()
        target_team = target.GetTeamId()

        # Only allow bounties between opposing teams (TEAM_GOOD vs TEAM_EVIL)
        # if (player_team == target_team and
        #     teams.IsRealTeam(player_team) and teams.IsRealTeam(target_team)):
        #     self.SvTell(player.GetId(), "You cannot place bounties on teammates!")
        #     return True

        # Also prevent bounties on spectators or from spectators
        # if player_team == teams.TEAM_SPEC:
        #     self.SvTell(player.GetId(), "Spectators cannot place bounties!")
        #     return True

        # if target_team == teams.TEAM_SPEC:
        #     self.SvTell(player.GetId(), "You cannot place bounties on spectators!")
        #     return True

        player_account = self.get_account_by_pid(player.GetId())
        target_account = self.get_account_by_pid(target_id)

        # Validate sender's balance
        if self.get_credits(player.GetId()) < amount:
            self.SvTell(player.GetId(), "Insufficient funds")
            return True

        if confirm:
            self._place_bounty(player, target, amount)
        else:
            # Store pending bounty
            bounty = PendingBounty(player, player_account, target_account, amount)
            self.pending_transactions[player.GetId()] = bounty
            self.SvTell(player.GetId(), f"Pending bounty of {amount} credits on {target.GetName()}^7. Type !confirm or !cancel.")
            # self.SvTell(target_id, f"{player.GetName()}^7 wants to place a bounty on you for {amount} credits.")
        return True

    def check_bounty(self, victim_id: int, killer_id: int) -> None:
        """Check for active bounties on killed player"""
        if victim_id in self.active_bounties:
            bounty = self.active_bounties[victim_id]
            del self.active_bounties[victim_id]
            killer_account = self.get_account_by_pid(killer_id)
            if self.add_credits(killer_account.player_id, bounty.amount):
                self.SvTell(killer_id, f"Collected bounty of {bounty.amount} credits for killing {bounty.target_account.player_name}^7.")
                # Notify contributors
                if len(bounty.contributors) == 1:
                    contributor = bounty.contributors[0]
                    self.SvTell(contributor.player_id, f"Bounty of {bounty.amount} credits awarded to {killer_account.player_name}^7.")
                elif len(bounty.contributors) > 1:
                    batchCmds = []
                    for contributor in bounty.contributors:
                        batchCmds.append(f"svtell {contributor.player_id} {self.msg_prefix}A Bounty you contributed to (Total: {bounty.amount}) was awarded to {killer_account.player_name}^7.")
                    self.server_data.interface.BatchExecute("b", batchCmds)
            else:
                Log.error("Failed to award bounty")

    def _handle_cancel(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !cancel command"""
        pid = player.GetId()
        
        if pid not in self.pending_transactions:
            self.SvTell(pid, "No pending transactions to cancel.")
            return True
            
        transaction = self.pending_transactions[pid]
        transaction.on_cancel(self)
        del self.pending_transactions[pid]
            
        return True

    def _handle_balance(self, player: Player, team_id: int,
                        args: list[str]) -> bool:
        pid = player.GetId()
        credits = self.get_credits(pid)
        self.SvTell(pid, f"Your balance: {colors.ColorizeText(str(credits), self.themecolor)} credits")
        return True

    def find_players(self, search_term: str, exclude: int = None) -> list[Player]:
        """Find all players whose names contain the search term as a substring (case-insensitive)"""
        matching_players = []
        search_lower = search_term.lower()
        
        for client in self.server_data.API.GetAllClients():
            if client.GetId() == exclude:
                continue
            # Strip color codes and convert to lowercase for comparison
            fixed_name = colors.StripColorCodes(client.GetName()).lower()
            if search_lower in fixed_name:
                matching_players.append(client)
        
        return matching_players

    def _handle_baltop(self, player: Player, team_id: int,
                       args: list[str]) -> bool:
        db = self.db_connection
        query = """
            SELECT uc.user_id, uc.player_name, b.credits
            FROM banking b
            LEFT JOIN user_credentials uc ON b.user_id = uc.user_id
            ORDER BY b.credits DESC
            LIMIT 10
        """
        result = db.ExecuteQuery(query, withResponse=True)

        if not result:
            self.SvSay("No balance data available")
            return True

        top_players = []
        for row in result:
            uid = row[0]
            name = row[1]
            credits_val = row[2]
            top_players.append(f"{name}^7 (ID: {uid}): {colors.ColorizeText('$' + str(credits_val), self.themecolor)}")

        self.Say("Top 10 Credits Balances: " + ", ".join(top_players))
        return True

    def _handle_credrank(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !credrank command"""
        player_id = player.GetId()
        account = self.get_account_by_pid(player_id)

        if not account or account.is_dummy_account():
            self.SvTell(player_id, "Account not found or is temporary.")
            return True

        credits = self.get_credits(player_id)

        if credits is None:
            self.SvTell(player_id, "Could not retrieve your balance.")
            return True

        # Get player's rank
        rank_query = f"""
            SELECT COUNT(*) + 1 as rank
            FROM banking
            WHERE credits > {credits}
        """
        rank_result = self.db_connection.ExecuteQuery(rank_query, withResponse=True)

        # Get total players
        total_query = "SELECT COUNT(*) FROM banking"
        total_result = self.db_connection.ExecuteQuery(total_query, withResponse=True)

        if rank_result and total_result:
            rank = rank_result[0][0]
            total = total_result[0][0]
            credits_text = colors.ColorizeText(str(credits), self.themecolor)

            self.SvTell(player_id, f"Your balance rank: #{rank} of {total} (Credits: {credits_text})")
        else:
            self.SvTell(player_id, "Rank data unavailable.")

        return True

    def _handle_mod_credits(self, playerName, smodId, adminIP, cmdArgs):
        """Handle smod !modifycredits command - modify a player's credits"""
        Log.info(f"SMOD {playerName} (ID: {smodId}, IP: {adminIP}) executing modifycredits command with args: {cmdArgs}")

        if len(cmdArgs) < 3:
            Log.warning(f"SMOD {playerName} provided insufficient arguments for modifycredits: {cmdArgs}")
            self.server_data.interface.SmSay(self.msg_prefix + "Usage: !modifycredits <playerid> <amount>")
            return True

        try:
            # Parse arguments
            target_player_id = int(cmdArgs[1])
            credit_amount = int(cmdArgs[2])

            Log.debug(f"Parsed modifycredits args - Target ID: {target_player_id}, Amount: {credit_amount}")

            # Find the target player
            target_client = None
            for client in self.server_data.API.GetAllClients():
                if client.GetId() == target_player_id:
                    target_client = client
                    break

            if target_client is None:
                Log.warning(f"SMOD {playerName} attempted to modify credits for non-existent player ID: {target_player_id}")
                self.server_data.interface.SmSay(self.msg_prefix + f"Player with ID {target_player_id} not found.")
                return True

            # Get the target player object (assuming you have a similar player tracking system)
            if target_player_id not in self.account_manager.accounts:
                Log.warning(f"SMOD {playerName} attempted to modify credits for player {target_client.GetName()} (ID: {target_player_id}) with no account data")
                self.server_data.interface.SmSay(self.msg_prefix + f"Player data for ID {target_player_id} not available.")
                return True

            target_player = self.account_manager.accounts[target_player_id]

            # Modify the player's credits in their account_data
            if hasattr(target_player, 'account_data') and 'credits' in target_player.account_data:
                old_credits = target_player.account_data['credits']
                new_credits = old_credits + credit_amount
                # Ensure credits don't go below 0
                if new_credits < 0:
                    Log.info(f"SMOD {playerName} attempted to set negative credits for {target_player.player_name} (ID: {target_player_id}), clamping to 0")
                    self.set_credits(target_player_id, 0)
                    new_credits = 0
                else:
                    self.add_credits(target_player_id, credit_amount)

                Log.info(f"SMOD {playerName} modified credits for {target_player.player_name} (ID: {target_player_id}): {old_credits} -> {new_credits} (change: {credit_amount})")

                # Send confirmation messages
                action_word = "added" if credit_amount > 0 else "removed"
                abs_amount = abs(credit_amount)

                self.server_data.interface.SmSay(
                    self.msg_prefix +
                    f"Admin {playerName}^7 {action_word} {abs_amount} credits {'to' if action_word == 'added' else 'from'} {target_player.player_name}^7. "
                    f"Credits: {old_credits} -> {new_credits}"
                )

                # Optionally notify the target player
                self.SvTell(
                    target_player_id,
                    f"SMOD {action_word} {colors.ColorizeText(str(abs_amount), self.themecolor)} credits. "
                    f"New balance: {colors.ColorizeText(str(new_credits), self.themecolor)} credits."
                )

            else:
                Log.warning(f"SMOD {playerName} attempted to modify credits for {target_player.player_name} (ID: {target_player_id}) but player has no credit data")
                self.server_data.interface.SmSay(self.msg_prefix + f"Player {target_player.player_name}^7 has no credit data available.")

        except ValueError as e:
            Log.error(f"SMOD {playerName} provided invalid arguments for modifycredits: {cmdArgs} - ValueError: {e}")
            self.server_data.interface.SmSay("Invalid player ID or credit amount. Both must be numbers.")
        except Exception as e:
            Log.error(f"Error in modifycredits command by SMOD {playerName}: {str(e)}")
            self.server_data.interface.SmSay(f"Error modifying credits: {str(e)}")

        return True

    def _handle_reset_bounties(self, playerName, smodID, adminIP, cmdArgs):
        """Handle smod !resetbounties command - clear all active bounties"""
        Log.info(f"SMOD {playerName} (ID: {smodID}, IP: {adminIP}) executing resetbounties command")

        if not self.active_bounties:
            self.server_data.interface.SmSay(self.msg_prefix + "No active bounties to clear.")
            return True

        bounty_count = len(self.active_bounties)

        # Notify all affected players before clearing
        for target_id, bounty in self.active_bounties.items():
            target_acc = bounty.target_account
            # target_id = target_acc.player_id

            # Notify the target
            self.SvTell(target_id, f"Your bounty of {bounty.amount} credits has been cleared by SMOD.")

            # Notify the issuer if they're still online
            if bounty.issuer_account.player_id in [client.GetId() for client in self.server_data.API.GetAllClients()]:
                self.SvTell(bounty.issuer_account.player_id, f"Your bounty on {bounty.target_account.player_name}^7 has been cleared by SMOD.")

        # Clear all active bounties
        self.active_bounties.clear()

        # Announce to server
        self.server_data.interface.SmSay(self.msg_prefix + f"Admin {playerName}^7 cleared {bounty_count} active bounties.")

        Log.info(f"SMOD {playerName} cleared {bounty_count} active bounties")
        return True

    def _handle_team_credits(self, playerName, smodId, adminIP, cmdArgs):
        """Handle smod !teamcredits command - add credits to all players on a team"""
        Log.info(f"SMOD {playerName} (ID: {smodId}, IP: {adminIP}) executing teamcredits command with args: {cmdArgs}")

        if len(cmdArgs) < 3:
            self.server_data.interface.SmSay(self.msg_prefix + "Usage: !teamcredits <team> <amount> (team: 1=red, 2=blue, 3=spec)")
            return True

        try:
            # Parse arguments
            team_id = int(cmdArgs[1])
            credit_amount = int(cmdArgs[2])

            # Validate team ID
            if team_id not in [teams.TEAM_EVIL, teams.TEAM_GOOD, teams.TEAM_SPEC]:
                self.server_data.interface.SmSay(self.msg_prefix + f"Invalid team ID. Use 1=red, 2=blue, 3=spec")
                return True

            # Get team name for display
            team_names = {
                teams.TEAM_EVIL: "Red",
                teams.TEAM_GOOD: "Blue",
                teams.TEAM_SPEC: "Spectator"
            }
            team_name = team_names.get(team_id, "Unknown")

            Log.debug(f"Parsed teamcredits args - Team: {team_id} ({team_name}), Amount: {credit_amount}")

            # Find all players on the specified team
            affected_players = []
            for client in self.server_data.API.GetAllClients():
                if client.GetLastNonSpecTeamId() == team_id:
                    player_id = client.GetId()
                    if player_id in self.account_manager.accounts:
                        affected_players.append((player_id, client.GetName()))

            if len(affected_players) == 0:
                self.server_data.interface.SmSay(self.msg_prefix + f"No players found on {team_name} team.")
                Log.info(f"SMOD {playerName} attempted teamcredits but no players on team {team_id}")
                return True

            # Add credits to each player
            success_count = 0
            batch_commands = []
            for player_id, player_name in affected_players:
                try:
                    old_credits = self.get_credits(player_id)
                    if old_credits is not None:
                        self.add_credits(player_id, credit_amount)
                        new_credits = self.get_credits(player_id)
                        
                        # Prepare notification message for batch execution
                        action_word = "received" if credit_amount > 0 else "lost"
                        abs_amount = abs(credit_amount)
                        message = (
                            f"{self.msg_prefix}SMOD {action_word} {colors.ColorizeText(str(abs_amount), self.themecolor)} credits to your team. "
                            f"New balance: {colors.ColorizeText(str(new_credits), self.themecolor)} credits."
                        )
                        batch_commands.append(f"svtell {player_id} {message}")
                        batch_commands.append("wait 1")
                        
                        success_count += 1
                        Log.debug(f"Added {credit_amount} credits to {player_name} (ID: {player_id}): {old_credits} -> {new_credits}")
                except Exception as e:
                    Log.error(f"Failed to add credits to player {player_name} (ID: {player_id}): {e}")
            
            # Send all notifications at once using batch execution
            if batch_commands:
                self.server_data.interface.BatchExecute('b', batch_commands)

            # Announce to server
            action_word = "added" if credit_amount > 0 else "removed"
            abs_amount = abs(credit_amount)
            self.server_data.interface.SmSay(
                self.msg_prefix +
                f"Admin {playerName}^7 {action_word} {colors.ColorizeText(str(abs_amount), self.themecolor)} credits "
                f"{'to' if action_word == 'added' else 'from'} all players on {colors.ColorizeText(team_name, self.themecolor)} team. "
                f"({success_count} players affected)"
            )

            Log.info(f"SMOD {playerName} {action_word} {credit_amount} credits to {success_count} players on team {team_id} ({team_name})")

        except ValueError as e:
            Log.error(f"SMOD {playerName} provided invalid arguments for teamcredits: {cmdArgs} - ValueError: {e}")
            self.server_data.interface.SmSay(self.msg_prefix + "Invalid team ID or credit amount. Both must be numbers.")
        except Exception as e:
            Log.error(f"Error in teamcredits command by SMOD {playerName}: {str(e)}")
            self.server_data.interface.SmSay(self.msg_prefix + f"Error adding team credits: {str(e)}")

        return True

    def initialize_banking_table(self):
        """
        Creates the banking table in the SQLite database if it doesn't exist.

        Args:
            db_connection (sqlite3.Connection): The connection to the SQLite database.

        Returns:
            bool: True if the table was created or already exists, False otherwise.
        """
        try:
            create_table_query = """
                CREATE TABLE IF NOT EXISTS banking (
                    user_id INTEGER PRIMARY KEY,
                    credits INTEGER DEFAULT 0
                )
            """
            self.db_connection.ExecuteQuery(create_table_query)
            Log.info("Banking table initialized successfully.")
            return True
        except Exception as e:
            Log.error(f"Error initializing banking table: {e}")
            return False

    def get_credits(self, player_id: int) -> int:
        """Get player's credits from cache or database using user_id"""
        if player_id in self.account_manager.accounts.keys():
            if "credits" in self.account_manager.accounts[
                    player_id].account_data.keys():
                return self.account_manager.accounts[player_id].account_data[
                    "credits"]
            else:
                self.set_account_data_val_by_pid(player_id, 'credits', 0)

        # Get user_id for the player
        account = self.get_account_by_pid(player_id)
        if not account:
            Log.error(f"Could not find account for player_id: {player_id}")
            return None

        user_id = account.user_id
        query = f"SELECT credits FROM banking WHERE user_id = {user_id}"
        result = self.db_connection.ExecuteQuery(query, withResponse=True)
        if result and len(result) > 0:
            credits = result[0][0]
            self.set_account_data_val_by_pid(player_id, 'credits', credits)
            return credits
        else:
            self.set_account_data_val_by_pid(player_id, 'credits', 0)
            query = f"INSERT INTO banking (user_id, credits) VALUES ({user_id}, {0})"
            result = self.db_connection.ExecuteQuery(query, withResponse=True)
            return 0

    def set_credits(self, player_id: int, amount: int) -> bool:
        """Set player's credits and update both database and account_data using user_id"""
        if amount < 0:
            return False

        # Get user_id for the player
        account = self.get_account_by_pid(player_id)
        if not account:
            Log.error(f"Could not find account for player_id: {player_id}")
            return False

        user_id = account.user_id

        # Update database
        db = self.db_connection
        query = f"UPDATE banking SET credits = {amount} WHERE user_id = {user_id}"
        result = db.ExecuteQuery(query)

        # Update account_data cache
        self.set_account_data_val_by_pid(player_id, 'credits', amount)

        return True

    def add_credits(self, player_id: int, amount: int) -> bool:
        """Add credits to player's balance using user_id"""
        current = self.get_credits(player_id)
        new_amount = current + amount
        return self.set_credits(player_id, new_amount)

    def deduct_credits(self, player_id: int, amount: int) -> bool:
        """Remove credits from player's balance using user_id"""
        current = self.get_credits(player_id)
        new_amount = current - amount
        if new_amount < 0:
            new_amount = 0
        return self.set_credits(player_id, new_amount)

    def get_player_balance(self, player_id: int) -> int:
        """Get player's balance using their account ID"""
        account = self.get_account_by_pid(player_id)
        if account:
            return self.get_credits(player_id)
        return 0

    def transfer_credits(self, sender_id: int, receiver_id: int, amount: int) -> bool:
        """Transfer credits between two players"""
        if amount <= 0:
            return False

        sender_account = self.get_account_by_uid(sender_id)
        receiver_account = self.get_account_by_uid(receiver_id)
        if sender_account and receiver_account:
            sender_balance = self.get_credits(sender_account.player_id)
            if sender_balance < amount:
                return False
            self.deduct_credits(sender_account.player_id, amount)
            self.add_credits(receiver_account.player_id, amount)
            return True
        return False

    def get_account_by_pid(self, player_id: int):
        """Get logged-in account for a player if available"""
        return self.accountsystem_xprts.Get("GetAccountByPlayerID").pointer(player_id)

    def get_credits_by_pid(self, player_id : int):
        creds = self.get_credits(player_id)
        return creds

    def get_credits_by_uid(self, user_id : int):
        return self.get_account_data_val_by_uid(user_id, "credits")



    def _on_chat_message(self, client: Player, message: str,
                         team_id: int) -> bool:
        """Handle incoming chat messages and route commands"""
        if message.startswith("!"):
            args = message[1:].split()
            if not args:
                return False

            cmd = args[0].lower()
            for c in self._command_list[team_id]:
                if cmd in c:
                    return self._command_list[team_id][c][1](client, team_id,
                                                             args)
        return False

    def _on_client_connect(self, event: godfingerEvent.ClientConnectEvent):
        """Load player's credits on connect using user_id"""
        pid = event.client.GetId()
        self.get_credits(pid)  # Load into cache
        # Initialize rounds counter for this player
        self.player_rounds[pid] = 0
        return False

    def _on_client_disconnect(self,
                              event: godfingerEvent.ClientDisconnectEvent):
        """Save player's credits on disconnect using user_id"""
        pid = event.client.GetId()
        if pid in self.account_manager.accounts.keys():
            to_set = self.get_credits_by_pid(pid) # Changed to use get_credits_by_pid without the explicit key argument
            if to_set is not None:
                self.set_credits(pid, to_set)

        # Clean up pending transactions
        if pid in self.pending_transactions:
            transaction = self.pending_transactions[pid]
            del self.pending_transactions[pid]
            
            if isinstance(transaction, PendingPayment):
                # Notify the target player if they're still online
                if transaction.target_account.player_id in [client.GetId() for client in self.server_data.API.GetAllClients()]:
                    self.SvTell(transaction.target_account.player_id, "Payment canceled - sender disconnected.")
            elif isinstance(transaction, PendingBounty):
                # Notify the target player if they're still online
                if transaction.target_account.player_id in [client.GetId() for client in self.server_data.API.GetAllClients()]:
                    self.SvTell(transaction.target_account.player_id, "Bounty canceled - issuer disconnected.")

        # Clean up active bounties on this player
        if pid in self.active_bounties:
            bounty = self.active_bounties[pid]
            del self.active_bounties[pid]
            # Notify the issuer if they're still online
            if bounty.issuer_account.player_id in [client.GetId() for client in self.server_data.API.GetAllClients()]:
                self.SvTell(bounty.issuer_account.player_id, f"Bounty on {bounty.target_account.player_name}^7 canceled - target disconnected.")

        # Clean up rounds tracking
        if pid in self.player_rounds:
            del self.player_rounds[pid]

        return False

    def _on_kill(self, event: Event):
        """Award credits for kills using user_id"""
        killer_id = event.client.GetId()
        victim_id = event.victim.GetId()
        victim_name = event.victim.GetName()

        is_tk = event.data["tk"]

        # Get user_id for killer
        killer_account = self.get_account_by_pid(killer_id)
        if killer_account:
            killer_user_id = killer_account.user_id
            if killer_id == victim_id:  # Special case for suicide
                # some suicide methods don't count as tk in the log so make sure it's set
                is_tk = True    
                toAdd = self.config.cfg["kill_awards"]["suicide"]
                victim_name = "yourself"
                if event.weaponStr == "MOD_WENTSPECTATOR":  # Special case for going spectator
                    return False
            elif not is_tk:
                self.check_bounty(victim_id, killer_id)
                toAdd = self.config.cfg["kill_awards"]["kill"]
                # Scale positive kill awards by victim's extra lives: floor(base * (1/(n+1)))
                try:
                    n_extras = self.get_extralives_for_pid(victim_id)
                    if isinstance(n_extras, int) and n_extras >= 0 and toAdd > 0:
                        mult = 1.0 / (n_extras + 1)
                        toAdd = int(toAdd * mult)
                except Exception:
                    pass
            else:
                toAdd = self.config.cfg["kill_awards"]["teamkill"]
            if toAdd != 0:
                self.add_credits(killer_id, toAdd)
            if toAdd > 0:
                self.SvTell(
                    killer_id,
                    f"Earned {colors.ColorizeText(str(toAdd), self.themecolor)} credits ({colors.ColorizeText(str(self.get_credits(killer_id)), self.themecolor)}) for killing {victim_name}^7! {colors.ColorizeText('(TK)', 'red') if is_tk else ''}"
                )
            elif toAdd < 0:
                self.SvTell(
                    killer_id,
                    f"Fined {colors.ColorizeText(str(abs(toAdd)), self.themecolor)} credits ({colors.ColorizeText(str(self.get_credits(killer_id)), self.themecolor)}) for killing {victim_name}^7! {colors.ColorizeText('(TK)', 'red') if is_tk else ''}"
                )
        return False

    def _handle_reload_extralives(self, playerName, smodId, adminIP, cmdArgs):
        """SMOD command to reload extralives.json at runtime."""
        self.server_data.interface.SmSay(self.msg_prefix + "This command is deprecated. Extra lives data is loaded at server startup.")
        return True

    def _process_team_purchase(self, player: Player, team: 'SiegeTeam', price: int) -> bool:
        """Process a team purchase for the given player.
        
        Args:
            player: The player making the purchase
            team: The team being purchased
            price: The price of the team
            
        Returns:
            bool: True if purchase was successful, False otherwise
        """
        player_team = player.GetLastNonSpecTeamId()
        if player_team not in (teams.TEAM_GOOD, teams.TEAM_EVIL):
            self.SvTell(player.GetId(), "You must be on a team to purchase teams.")
            return False
            
        server_var_key = "team1_purchased_teams" if player_team == teams.TEAM_GOOD else "team2_purchased_teams"
        purchased_teams = self.server_data.GetServerVar(server_var_key) or []
        
        if team.GetName() in purchased_teams:
            self.SvTell(player.GetId(), f"Team '{team.GetName()}' has already been purchased.")
            return False
            
        if not self.deduct_credits(player.GetId(), price):
            self.SvTell(player.GetId(), "Transaction failed. Could not deduct credits.")
            return False
            
        purchased_teams.append(PurchasedTeam(team.GetName(), player.GetId(), price))
        # Just update the server variable, RTV will handle the team assignments
        self.server_data.SetServerVar(server_var_key, purchased_teams)
        
        team_color = "Red" if player_team == teams.TEAM_GOOD else "Blue"
        self.Say(f"Purchased team: {team.GetName()} for {price} credits for the {team_color} team. ({colors.ColorizeText(str(self.get_credits(player.GetId())), self.themecolor)})")
        return True

    def _handle_buyteam(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !buyteam command"""
        if self.has_pending_action(player.GetId()):
            self.SvTell(player.GetId(), "You already have a pending transaction!")
            return True

        if len(args) < 2:
            self.SvTell(player.GetId(), "Usage: !buyteam <teamname> [confirm]")
            return True

        # Check for confirm flag
        confirm = args[-1].lower() == "confirm"
        
        # If confirmed, exclude 'confirm' from team name parsing
        team_name_parts = args[1:-1] if confirm else args[1:]
        team_name = ' '.join(team_name_parts)
        
        # Case insensitive team search
        team = None
        for available_team in self.team_container.GetAllTeams():
            if available_team.GetName().lower() == team_name.lower():
                team = available_team
                break

        if not team:
            self.SvTell(player.GetId(), f"Team '{team_name}' not found.")
            return True

        # Check player balance
        price = team._price
        player_credits = self.get_credits(player.GetId())
        if player_credits < price:
            self.SvTell(player.GetId(), f"Insufficient funds. You need {price} credits to buy this team (you have {player_credits}).")
            return True

        # Check if team has already been purchased
        player_team = player.GetLastNonSpecTeamId()
        if player_team not in [teams.TEAM_GOOD, teams.TEAM_EVIL]:
            self.SvTell(player.GetId(), "You must be on a team (red or blue) to purchase teams.")
            return True
            
        server_var_key = "team1_purchased_teams" if player_team == teams.TEAM_GOOD else "team2_purchased_teams"
        opposing_team_key = "team2_purchased_teams" if player_team == teams.TEAM_GOOD else "team1_purchased_teams"
        
        purchased_teams = self.server_data.GetServerVar(server_var_key) or []
        opposing_teams = self.server_data.GetServerVar(opposing_team_key) or []
        
        # Check if team is already purchased (handle new dict structure)
        purchased_team_names = [t.name for t in purchased_teams]
        opposing_team_names = [t.name for t in opposing_teams]

        if team.GetName() in purchased_team_names:
            self.SvTell(player.GetId(), f"Team '{team.GetName()}' has already been purchased by your team.")
            return True
            
        if team.GetName() in opposing_team_names:
            self.SvTell(player.GetId(), f"Team '{team.GetName()}' has already been purchased by the opposing team.")
            return True

        if confirm:
            # Process immediately if confirmed
            if not self._process_team_purchase(player, team, price):
                return True
        else:
            # Create pending purchase
            purchase = PendingTeamPurchase(player, team)
            self.pending_transactions[player.GetId()] = purchase
            team_color = "Red" if player_team == teams.TEAM_GOOD else "Blue"
            self.SvTell(player.GetId(), f"Pending purchase of team {team.GetName()} for {price} credits for {team_color}. Type !confirm or !cancel.")
            
        return True

    def _handle_teamlist(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !teamlist command - show available teams"""
        page_count = self.team_container.GetPageCount()
        if page_count == 0:
            self.SvTell(player.GetId(), "No teams available.")
            return True

        page_num = 1
        if len(args) >= 2:
            if args[1].isdigit():
                page_num = int(args[1])
        
        if page_num < 1 or page_num > page_count:
            self.SvTell(player.GetId(), 
                      f"Usage: {colors.ColorizeText('!teamlist <page>', self.themecolor)}, " +
                      f"valid pages {colors.ColorizeText(f'1-{page_count}', self.themecolor)}")
            return True
            
        page_content = self.team_container.GetPage(page_num - 1)
        self.Say(f"Available Teams (Page {page_num}/{page_count}): {page_content}")
        return True

    def _handle_teamsearch(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !teamsearch command - search for teams by name"""
        try:
            if len(args) < 2:
                self.SvTell(player.GetId(), 
                          f"Usage: {colors.ColorizeText('!teamsearch <search term>', self.themecolor)}")
                return True

            search_terms = [term.lower() for term in args[1:]]
            results = []

            # Search through all teams
            for team in self.team_container.GetAllTeams():
                team_name = team.GetName().lower()
                # Check if all search terms are in the team name
                if all(term in team_name for term in search_terms):
                    results.append(team)

            if not results:
                self.SvTell(player.GetId(), 
                          f"No teams found matching: {colors.ColorizeText(' '.join(search_terms), self.themecolor)}")
                return True

            # Sort results alphabetically
            results.sort(key=lambda t: t.GetName().lower())

            # Format results with highlighting
            formatted_results = []
            for team in results:
                team_name = team.GetName()
                team_price = team.GetPrice()
                # Highlight search terms in results
                highlighted_name = team_name
                for term in search_terms:
                    idx = highlighted_name.lower().find(term)
                    if idx != -1:
                        highlighted_name = (
                            highlighted_name[:idx] +
                            colors.ColorizeText(highlighted_name[idx:idx+len(term)], self.themecolor) +
                            highlighted_name[idx+len(term):]
                        )
                formatted_results.append(f"{highlighted_name} ({colors.ColorizeText(str(team_price), self.themecolor)})")

            # Send results in chunks based on string length limit (500 chars)
            max_string_size = 900
            
            # Build chunks based on string length limit
            chunks = []
            current_chunk = []
            current_string_length = 0
            
            for formatted_result in formatted_results:
                # Add separator if not first item
                result_entry = formatted_result
                if current_chunk:
                    result_entry = ", " + result_entry
                
                # Check if adding this result would exceed the string limit
                if current_string_length + len(result_entry) > max_string_size and current_chunk:
                    # Save current chunk and start a new one
                    chunks.append(current_chunk)
                    current_chunk = [formatted_result]
                    current_string_length = len(formatted_result)
                else:
                    # Add to current chunk
                    if current_chunk:
                        current_chunk.append(formatted_result)
                        current_string_length += len(result_entry)
                    else:
                        current_chunk = [formatted_result]
                        current_string_length = len(formatted_result)
            
            # Add the last chunk if it has results
            if current_chunk:
                chunks.append(current_chunk)
            
            # Send the chunks using BatchExecute for multiple chunks
            if len(chunks) == 1:
                self.Say(f"Found {len(results)} matching teams: {', '.join(chunks[0])}")
            else:
                # Batch output for multiple chunks - build proper command list
                batchCmds = [f"say {self.msg_prefix}{len(results)} matching teams: {', '.join(chunks[0])}"]
                batchCmds += [f"say {self.msg_prefix}{', '.join(chunk)}" for chunk in chunks[1:]]
                self.server_data.interface.BatchExecute("b", batchCmds, sleepBetweenChunks=0.1)

        except Exception as e:
            logging.error(f"Error in _handle_teamsearch: {str(e)}")
            self.SvTell(player.GetId(), "An error occurred while searching for teams.")

        return True

    def get_extralives_for_pid(self, player_id: int):
        """Get extra lives count for the player's current character/class name; returns 0 if unknown."""
        name = self.player_class_by_pid.get(player_id)
        if not name:
            return 0
        return int(self.server_data.extralives_map.get(name, 0))

    def _on_client_changed(self, event: Event):
        """Track player's current class/character name when they change class."""
        try:
            pid = event.client.GetId()
            # Attempt to read potential keys from event data
            char_name = None
            data = getattr(event, "data", {}) or {}
            key = 'sc'
            if key in data and isinstance(data[key], str) and data[key]:
                char_name = data[key]
            else:
                Log.error(f"Could not find class name for player {pid}")
                return False
            self.player_class_by_pid[pid] = char_name
            return True
        except Exception as e:
            Log.error(f"Error in _on_client_changed: {e}")
            return False

    def _on_init_game(self, event: Event):
        """Handle init game event - distribute scaled round start credits"""
        round_start_config = self.config.cfg.get("roundStartCredits", {})
        
        # Handle legacy config (integer) or check if disabled
        if isinstance(round_start_config, int):
            if round_start_config <= 0:
                return False
            # Legacy mode: use fixed amount
            min_credits = max_credits = round_start_config
            max_rounds = 1
            enabled = True
        else:
            enabled = round_start_config.get("enabled", False)
            if not enabled:
                return False
            min_credits = round_start_config.get("minCredits", 10)
            max_credits = round_start_config.get("maxCredits", 50)
            max_rounds = round_start_config.get("maxRounds", 5)
        
        Log.info(f"Distributing scaled round start credits to active players (min: {min_credits}, max: {max_credits}, maxRounds: {max_rounds})")
        
        # Find all players who have a last non-spec team (were playing)
        eligible_players = []
        for client in self.server_data.API.GetAllClients():
            last_team = client.GetLastNonSpecTeamId()
            if last_team is not None:
                player_id = client.GetId()
                if player_id in self.account_manager.accounts:
                    eligible_players.append((player_id, client.GetName()))
        
        if len(eligible_players) == 0:
            Log.debug("No eligible players for round start credits")
            return False
        
        # Add credits to each eligible player with scaling
        success_count = 0
        batch_commands = []
        for player_id, player_name in eligible_players:
            try:
                # Increment rounds played for this player
                if player_id not in self.player_rounds:
                    self.player_rounds[player_id] = 0
                self.player_rounds[player_id] += 1
                
                rounds_played = self.player_rounds[player_id]
                
                # Calculate scaled credits based on rounds played
                if rounds_played >= max_rounds:
                    credits_to_award = max_credits
                else:
                    # Linear scaling from minCredits to maxCredits
                    credits_range = max_credits - min_credits
                    credits_to_award = min_credits + int((credits_range * rounds_played) / max_rounds)
                
                old_credits = self.get_credits(player_id)
                if old_credits is not None:
                    self.add_credits(player_id, credits_to_award)
                    new_credits = self.get_credits(player_id)
                    
                    # Prepare notification message for batch execution
                    message = (
                        f"{self.msg_prefix}Round start bonus: {colors.ColorizeText(str(credits_to_award), self.themecolor)} credits! "
                        f"(Round {rounds_played}/{max_rounds}) "
                        f"Balance: {colors.ColorizeText(str(new_credits), self.themecolor)} credits."
                    )
                    batch_commands.append(f"svtell {player_id} {message}")
                    batch_commands.append("wait 1")
                    
                    success_count += 1
                    Log.debug(f"Added {credits_to_award} round start credits to {player_name} (ID: {player_id}, Round {rounds_played}): {old_credits} -> {new_credits}")
            except Exception as e:
                Log.error(f"Failed to add round start credits to player {player_name} (ID: {player_id}): {e}")
        
        # Send all notifications at once using batch execution
        if batch_commands:
            self.server_data.interface.BatchExecute('b', batch_commands)
        
        Log.info(f"Distributed round start credits to {success_count} players")
        return False

    def _on_smsay(self, event : Event):
        playerName = event.playerName
        smodID = event.smodID
        adminIP = event.adminIP
        message = event.message
        cmdArgs = message.split()
        command = cmdArgs[0]
        if command.startswith("!"):
            command = command[len("!"):]
        for c in self._smodCommandList:
            if command in c:
                # Get the primary command name (first in the tuple)
                primary_command = c[0]
                
                # Check if smod has permission to execute this command
                if not self.check_smod_permission(primary_command, smodID):
                    self.server_data.interface.SmSay(
                        self.msg_prefix + 
                        f"Access denied. SMOD ID {smodID} does not have permission to use !{primary_command}"
                    )
                    Log.warning(f"SMOD {playerName} (ID: {smodID}) attempted to use !{primary_command} without permission")
                    return True
                
                return self._smodCommandList[c][1](playerName, smodID, adminIP, cmdArgs)
        return False

    def _on_objective(self, event : Event):
        if self.config.GetValue("objectiveCredits", None) != None and self.config.cfg["objectiveCredits"]["enabled"]:
            self.add_credits(event.client.GetId(), self.config.cfg["objectiveCredits"]["credits"])
            self.SvTell(event.client.GetId(), f"You have been awarded {self.config.cfg['objectiveCredits']['credits']} credits ({colors.ColorizeText(str(self.get_credits(event.client.GetId())), self.themecolor)}) for completing the objective!")
        return True

    def _on_map_change(self, event : Event):
        # Refund any purchased teams that weren't applied (because RTV didn't happen)
        for team_var in ["team1_purchased_teams", "team2_purchased_teams"]:
            purchased_teams = self.server_data.GetServerVar(team_var)
            if purchased_teams:
                for team_data in purchased_teams:
                    # Handle both old format (str) and new format (dict) for safety during transition
                    if isinstance(team_data, PurchasedTeam):
                        buyer_id = team_data.buyer_id
                        price = team_data.price
                        team_name = team_data.name
                        
                        if buyer_id != None and price != None:
                            # Re-add credits
                            self.add_credits(buyer_id, price)
                            
                            # Try to notify if player is still there
                            self.SvTell(buyer_id, f"Map changed manually. Refunded {price} credits for team {team_name}.")
                                
                # Clear the variable
                self.server_data.SetServerVar(team_var, None)
                
        return True

    def SvTell(self, pid: int, message: str):
        """Send message to player"""
        self.server_data.interface.SvTell(pid, f"{self.msg_prefix}{message}")

    def SvSay(self, message: str):
        self.server_data.interface.SvSay(f"{self.msg_prefix}{message}")

    def Say(self, message: str):
        self.server_data.interface.Say(f"{self.msg_prefix}{message}")


def OnStart() -> bool:
    global banking_plugin
    if banking_plugin:
        init_accountsystem_xprts(banking_plugin)
        for client in banking_plugin.server_data.API.GetAllClients():
            fakeEvent = godfingerEvent.ClientConnectEvent(client, {})
            banking_plugin._on_client_connect(fakeEvent)
        return True
    else:
        return False

def init_accountsystem_xprts(plugin : BankingPlugin):
    plugin.accountsystem_xprts = plugin.server_data.API.GetPlugin(
                "plugins.shared.accountsystem.accountsystem").GetExports()
    plugin.get_account_by_uid = plugin.accountsystem_xprts.Get(
        "GetAccountByUserID").pointer
    plugin.get_account_data_val_by_pid = plugin.accountsystem_xprts.Get(
        "GetAccountDataValByPID").pointer

    plugin.get_account_data_val_by_uid = plugin.accountsystem_xprts.Get(
        "GetAccountDataValByUID").pointer

    plugin.set_account_data_val_by_pid = plugin.accountsystem_xprts.Get(
        "SetAccountDataValByPID").pointer

    plugin.db_connection = plugin.accountsystem_xprts.Get(
        "GetDatabaseConnection").pointer()
    plugin.account_manager = plugin.accountsystem_xprts.Get(
        "GetAccountManager").pointer()
    plugin.initialize_banking_table()



def OnLoop() -> bool:
    return False


def OnFinish():
    global banking_plugin
    # Corrected potential NameError by checking if banking_plugin is defined in the global scope
    if 'banking_plugin' in globals() and banking_plugin:
        del banking_plugin
        banking_plugin = None


def OnEvent(event: Event) -> bool:
    global banking_plugin
    if not banking_plugin:
        return False

    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return banking_plugin._on_chat_message(event.client, event.message,
                                               event.teamId)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        banking_plugin._on_client_connect(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        banking_plugin._on_client_disconnect(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
        banking_plugin._on_smsay(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_KILL:
        banking_plugin._on_kill(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_INIT:
        banking_plugin._on_init_game(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        banking_plugin._on_client_changed(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_OBJECTIVE:
        banking_plugin._on_objective(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MAPCHANGE:
        banking_plugin._on_map_change(event)
    return False


def OnInitialize(server_data: ServerData, exports=None):
    global banking_plugin
    banking_plugin = BankingPlugin(server_data)
    if exports is not None:
        exports.Add("GetCredits", banking_plugin.get_credits)
        exports.Add("AddCredits", banking_plugin.add_credits)
        exports.Add("DeductCredits", banking_plugin.deduct_credits)
        exports.Add("TransferCredits", banking_plugin.transfer_credits)
        exports.Add("GetCreditsByID", banking_plugin.get_credits_by_pid)
        exports.Add("GetAccountByID", banking_plugin.get_account_by_pid)
    banking_plugin._is_initialized = True
    return True

if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system. Please run one of the start scripts in the start directory to use it. Make sure that this python module's path is included in godfingerCfg!")
    input("Press Enter to close this message.")
    exit()
