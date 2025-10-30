#   InterGalactic Banking Clan 2.0
#   A banking plugin for the Godfinger Movie Battles II plugin system
#   By Mantlar/ACHUTA https://www.github.com/mantlar
#   Plugin Dependencies (must be loaded before this in load order!): AccountSystem
#


import logging
import os
import time
from typing import Dict, Optional
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
    }
}
"""

# Create default config if it doesn't exist
if DEFAULT_CFG is None:
    DEFAULT_CFG = config.Config()
    DEFAULT_CFG.cfg = json.loads(CONFIG_FALLBACK)
    Log.error(f"Could not open config file at {DEFAULT_CFG_PATH}, ensure the file is a valid JSON file in the correct file path.")
    with open(DEFAULT_CFG_PATH, "wt") as f:
        f.write(CONFIG_FALLBACK)

class Payment:
    def __init__(self, sender_account, target_account, amount: int):
        self.sender_account = sender_account
        self.target_account = target_account
        self.amount = amount
        self.timestamp = time.time()

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

class BankingPlugin:

    def __init__(self, server_data: ServerData):

        # START OF MODIFIED CODE FOR CONFIG LOADING
        # Check if config loading failed and use fallback data
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

        self.pending_payments = {}  # sender_id: Payment
        self.pending_bounties = {}  # issuer_id: Bounty
        self.active_bounties = {}  # target_id: Bounty
        self.player_rounds = {}  # player_id: rounds_played
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
                ("pay",): ("!pay <pfx> <amount> - Send credits to player",
                          self._handle_pay),
                ("confirm",): ("!confirm - Confirm pending transaction",
                              self._handle_confirm),
                ("bounty",): ("!bounty <pfx> <amount> - Place bounty",
                             self._handle_bounty),
                ("cancel",): ("!cancel - Cancel pending transaction",
                             self._handle_cancel),
                ("bounties",): ("!bounties - View active bounties",
                              self._handle_bounties)
            }
        }
        self._smodCommandList = {
                # ... existing commands ...
            ("modifycredits", "modcredits") : ("!modifycredits <playerid> <amount> - modify a player's credits by the specified amount", self._handle_mod_credits),
            ("resetbounties", "rb") : ("!resetbounties - clears the bounty list", self._handle_reset_bounties),
            ("teamcredits", "tcredits") : ("!teamcredits <team> <amount> - add credits to all players on a team (1=red, 2=blue, 3=spec)", self._handle_team_credits),
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
        return (player_id in self.pending_payments or
                player_id in self.pending_bounties)

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
            payment = Payment(player_account, target_account, amount)
            self.pending_payments[player.GetId()] = payment
            self.SvTell(player.GetId(), f"Pending payment of {amount} credits to {target.GetName()}^7. Type !confirm or !cancel.")
        return True

    def _handle_confirm(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !confirm command for pending transactions"""
        pid = player.GetId()
        # Check for pending payments
        if pid in self.pending_payments:
            payment = self.pending_payments[pid]
            del self.pending_payments[pid]
            sender_account = payment.sender_account
            target_account = payment.target_account
            if self.transfer_credits(sender_account.user_id, target_account.user_id, payment.amount):
                self.SvTell(sender_account.player_id, f"Sent {payment.amount} credits to {target_account.player_name}^7")
                self.SvTell(target_account.player_id, f"Received {payment.amount} credits from {sender_account.player_name}^7")
            else:
                self.SvTell(sender_account.player_id, "Transaction failed")
                self.SvTell(target_account.player_id, "Transaction failed")
            return True
        # Check for pending bounties
        elif pid in self.pending_bounties:
            bounty = self.pending_bounties[pid]
            sender_account = bounty.issuer_account
            target_account = bounty.target_account
            target_id = target_account.player_id
            amount = bounty.amount
            if self.deduct_credits(player.GetId(), amount):
                del self.pending_bounties[pid]
                if target_id in self.active_bounties:
                    if not sender_account in bounty.contributors:
                        self.active_bounties[target_id].contributors.append(sender_account)
                    self.active_bounties[target_id].add_amount(amount)
                    self.SvTell(sender_account.player_id, f"Added {amount} credits to {target_account.player_name}^7's bounty.")
                    self.SvTell(target_account.player_id, f"Your bounty has increased by {amount} credits ({self.active_bounties[target_id].amount}) by {sender_account.player_name}^7")
                else:
                    if not sender_account in bounty.contributors:
                        bounty.contributors.append(sender_account)
                    self.active_bounties[target_account.player_id] = bounty
                    self.SvTell(sender_account.player_id, f"Bounty of {amount} credits placed on {target_account.player_name}^7")
                    self.SvTell(target_account.player_id, f"Bounty of {amount} credits placed on you by {sender_account.player_name}^7")
            else:
                self.SvTell(player.GetId(), "Failed to place bounty")
        else:
            self.SvTell(pid, "No pending transactions")
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
            self.SvTell(player.GetId(), f"No players found matching '{target_name}'")
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
            # Place bounty immediately
            if target_id in self.active_bounties:
                existing_bounty = self.active_bounties[target_id]
                if self.deduct_credits(player.GetId(), amount):
                    existing_bounty.add_amount(amount)
                    if not player_account in existing_bounty.contributors:
                        existing_bounty.contributors.append(player_account)
                    self.Say(f"Added {amount} credits to existing bounty on {target.GetName()}^7. Total: {existing_bounty.amount} credits")
                else:
                    self.SvTell(player.GetId(), "Failed to add to bounty")
            else:
                # Deduct credits immediately
                if self.deduct_credits(player.GetId(), amount):
                    bounty = Bounty(player_account, target_account, amount)
                    self.active_bounties[target_id] = bounty
                    if not player_account in bounty.contributors:
                        bounty.contributors.append(player_account)
                    self.Say(f"Bounty of {amount} credits placed on {target.GetName()}^7")
                    self.SvTell(target_id, f"Bounty of {amount} credits placed on you by {player.GetName()}^7")
                else:
                    self.SvTell(player.GetId(), "Failed to place bounty")
        else:
            # Store pending bounty
            bounty = Bounty(player_account, target_account, amount)
            self.pending_bounties[player.GetId()] = bounty
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
        if pid in self.pending_payments:
            payment = self.pending_payments[pid]
            del self.pending_payments[pid]
            self.SvTell(pid, "Payment canceled.")
            self.SvTell(payment.target_account.player_id, "Payment canceled by sender.")
        elif pid in self.pending_bounties:
            bounty = self.pending_bounties[pid]
            del self.pending_bounties[pid]
            self.SvTell(pid, "Bounty canceled.")
            self.SvTell(bounty.target_account.player_id, "Bounty canceled by issuer.")
        else:
            self.SvTell(pid, "No pending transactions to cancel.")
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
        if pid in self.pending_payments:
            payment = self.pending_payments[pid]
            del self.pending_payments[pid]
            # Notify the target player if they're still online
            if payment.target_account.player_id in [client.GetId() for client in self.server_data.API.GetAllClients()]:
                self.SvTell(payment.target_account.player_id, "Payment canceled - sender disconnected.")

        if pid in self.pending_bounties:
            bounty = self.pending_bounties[pid]
            del self.pending_bounties[pid]
            # Notify the target player if they're still online
            if bounty.target_account.player_id in [client.GetId() for client in self.server_data.API.GetAllClients()]:
                self.SvTell(bounty.target_account.player_id, "Bounty canceled - issuer disconnected.")

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
            else:
                toAdd = self.config.cfg["kill_awards"]["teamkill"]
            if toAdd != 0:
                self.add_credits(killer_id, toAdd)
            if toAdd > 0:
                self.SvTell(
                    killer_id,
                    f"Earned {toAdd} credits ({colors.ColorizeText(str(self.get_credits(killer_id)), self.themecolor)}) for killing {victim_name}^7! {colors.ColorizeText('(TK)', 'red') if is_tk else ''}"
                )
            elif toAdd < 0:
                self.SvTell(
                    killer_id,
                    f"Fined {abs(toAdd)} credits ({colors.ColorizeText(str(self.get_credits(killer_id)), self.themecolor)}) for killing {victim_name}^7! {colors.ColorizeText('(TK)', 'red') if is_tk else ''}"
                )
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
