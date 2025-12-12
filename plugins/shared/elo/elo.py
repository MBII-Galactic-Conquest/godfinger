#   MBII Elo System
#   An Elo system for the Godfinger Movie Battles II plugin system
#   By Mantlar/ACHUTA https://www.github.com/mantlar
#   Plugin Dependencies (must be loaded before this in load order!): AccountSystem
#

import time
import math
import logging
import os
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# Godfinger imports
import godfingerEvent
from godfingerEvent import Event
from lib.shared.serverdata import ServerData
from lib.shared.player import Player
import lib.shared.teams as teams
import lib.shared.colors as colors

Log = logging.getLogger(__name__)

@dataclass
class PlayerStats:
    """Track player statistics for a session"""
    kills: int = 0
    deaths: int = 0
    rating_changes: int = 0
    last_kill_time: float = 0
    kill_streak: int = 0

class EloPlugin:
    def __init__(self, server_data: ServerData):
        self.server_data = server_data
        self._is_initialized = False
        
        # Configuration
        self.default_rating = 1200
        self.k_factor = 32
        self.min_rating = 100
        self.max_rating = 3000
        self.kill_streak_bonus = 5  # Extra rating per kill in streak
        self.max_streak_bonus = 25  # Maximum streak bonus
        
        # Theme and messaging
        self.themecolor = "blue"
        self.msg_prefix = colors.COLOR_CODES[self.themecolor] + "[ELO]^7: "
        
        # Session tracking - now only for temporary session data
        self.last_server_init = 0
        self.server_running = False
        
        # Account system integration
        self.accountsystem_xprts = None
        self.get_account_by_uid = None
        self.get_account_by_pid = None
        self.get_account_data_val_by_pid = None
        self.get_account_data_val_by_uid = None
        self.set_account_data_val_by_pid = None
        self.set_account_data_val_by_uid = None
        self.db_connection = None
        self.account_manager = None
        
        # Extra lives integration
        self.player_class_by_pid = {}  # player_id: current character/class name
        self.extralives_map = {}  # character/class name -> extralives (int >= 0)
        self._load_extralives_map()
        
        # Command registration
        self._setup_commands()

    def _setup_commands(self):
        """Set up chat and SMOD commands"""
        self._command_list = {
            teams.TEAM_GLOBAL: {
                ("myelo", "myrating"): ("Show your current rating", self._handle_rating),
                ("elostats",): ("Show detailed statistics", self._handle_stats),
                ("leaderboard", "top"): ("Show top 10 players", self._handle_leaderboard),
                ("rank", "myrank"): ("Show your rank", self._handle_rank),
            }
        }
        
        self._smodCommandList = {
            ("resetrating", "resetelo"): ("Reset player's rating", self._handle_reset_rating),
            ("setrating", "setelo"): ("Set player's rating", self._handle_set_rating),
            ("eloinfo",): ("Show Elo system information", self._handle_elo_info),
            ("reloadextralives", "relives"): ("Reload extralives.json table", self._handle_reload_extralives),
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

    def initialize_elo_table(self) -> bool:
        """Initialize the Elo ratings database table"""
        try:
            create_table_query = """
                CREATE TABLE IF NOT EXISTS elo_ratings (
                    user_id INTEGER PRIMARY KEY,
                    rating INTEGER DEFAULT 1200,
                    games_played INTEGER DEFAULT 0,
                    kills INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0,
                    highest_rating INTEGER DEFAULT 1200,
                    lowest_rating INTEGER DEFAULT 1200,
                    rating_changes INTEGER DEFAULT 0,
                    last_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            self.db_connection.ExecuteQuery(create_table_query)
            Log.info("Elo ratings table initialized")
            return True
        except Exception as e:
            Log.error(f"Failed to create Elo table: {e}")
            return False

    def _get_session_stats(self, player_id: int) -> dict:
        """Get session stats from account data as dictionary"""
        stats_data = self.get_account_data_val_by_pid(player_id, "elo_session_stats")
        if stats_data and isinstance(stats_data, dict):
            return stats_data
        else:
            # Create new session stats dictionary and store immediately
            new_stats = {
                "kills": 0,
                "deaths": 0,
                "rating_changes": 0,
                "last_kill_time": 0.0,
                "kill_streak": 0
            }
            self.set_account_data_val_by_pid(player_id, "elo_session_stats", new_stats)
            return new_stats
    
    def _set_session_stats(self, player_id: int, stats_dict: dict):
        """Store session stats dictionary in account data"""
        self.set_account_data_val_by_pid(player_id, "elo_session_stats", stats_dict)
    
    def _update_session_stat(self, player_id: int, key: str, value):
        """Update a single session stat field"""
        stats = self._get_session_stats(player_id)
        stats[key] = value
        self.set_account_data_val_by_pid(player_id, "elo_session_stats", stats)
    
    def _increment_session_stat(self, player_id: int, key: str, amount: int = 1):
        """Increment a session stat field"""
        stats = self._get_session_stats(player_id)
        stats[key] = stats.get(key, 0) + amount
        self.set_account_data_val_by_pid(player_id, "elo_session_stats", stats)

    def get_rating(self, player_id: int) -> int:
        """Get player's current rating"""
        account = self.get_account_by_pid(player_id)
        if not account:
            Log.warn("Couldn't find account for elo rating, using default")
            return self.default_rating

        # First try to get from account data (local cache)
        cached_rating = self.get_account_data_val_by_pid(player_id, "elo_rating")
        if cached_rating is not None:
            return cached_rating

        # If not cached, load from database
        user_id = account.user_id
        query = f"SELECT rating FROM elo_ratings WHERE user_id = {user_id}"
        result = self.db_connection.ExecuteQuery(query, withResponse=True)
        
        if result and len(result) > 0:
            rating = result[0][0]
            # Cache the rating in account data
            self.set_account_data_val_by_pid(player_id, "elo_rating", rating)
            return rating
        else:
            # Initialize new player
            self._initialize_player_rating(user_id)
            # Cache default rating
            self.set_account_data_val_by_pid(player_id, "elo_rating", self.default_rating)
            return self.default_rating

    def set_rating(self, player_id: int, new_rating: int) -> bool:
        """Set player's rating"""
        account = self.get_account_by_pid(player_id)
        if not account:
            return False
    
        user_id = account.user_id
        new_rating = max(self.min_rating, min(self.max_rating, new_rating))
        
        # Initialize player if they don't exist
        self._initialize_player_rating(user_id)
        
        # Update database
        query = f"""
            UPDATE elo_ratings 
            SET rating = {new_rating},
                last_played = CURRENT_TIMESTAMP
            WHERE user_id = {user_id}
        """
        self.db_connection.ExecuteQuery(query)
        
        # Update local cache in account data
        self.set_account_data_val_by_pid(player_id, "elo_rating", new_rating)
        
        # Update highest/lowest ratings
        self._update_rating_extremes(user_id, new_rating)
        return True

    def _initialize_player_rating(self, user_id: int):
        """Initialize a new player's rating record only if it doesn't exist"""
        # First check if the record already exists
        check_query = f"SELECT user_id FROM elo_ratings WHERE user_id = {user_id}"
        existing = self.db_connection.ExecuteQuery(check_query, withResponse=True)
        
        if not existing or len(existing) == 0:
            # Only insert if the record doesn't exist
            query = f"""
                INSERT INTO elo_ratings 
                (user_id, rating, highest_rating, lowest_rating, games_played, kills, deaths, rating_changes, last_played) 
                VALUES ({user_id}, {self.default_rating}, {self.default_rating}, {self.default_rating}, 0, 0, 0, 0, CURRENT_TIMESTAMP)
            """
            self.db_connection.ExecuteQuery(query)
            Log.debug(f"Initialized new rating record for user {user_id}")
        else:
            Log.debug(f"Rating record already exists for user {user_id}")

    def _update_rating_extremes(self, user_id: int, new_rating: int):
        """Update player's highest and lowest ratings"""
        query = f"""
            UPDATE elo_ratings 
            SET highest_rating = MAX(highest_rating, {new_rating}),
                lowest_rating = MIN(lowest_rating, {new_rating})
            WHERE user_id = {user_id}
        """
        self.db_connection.ExecuteQuery(query)

    def calculate_rating_change(self, killer_rating: int, victim_rating: int, kill_streak: int = 0, victim_extralives: int = 0) -> Tuple[int, int]:
        """Calculate rating changes for killer and victim, accounting for victim's extra lives"""
        # Expected score calculation (Elo formula)
        expected_killer = 1.0 / (1.0 + math.pow(10, (victim_rating - killer_rating) / 400.0))
        expected_victim = 1.0 - expected_killer
        
        # Base rating changes
        killer_change = int(self.k_factor * (1.0 - expected_killer))
        victim_change = int(self.k_factor * (0.0 - expected_victim))
        
        # Scale rating changes by victim's extra lives: floor(base * (1/(n+1)))
        # Characters with more lives are worth less rating per kill
        if isinstance(victim_extralives, int) and victim_extralives >= 0:
            mult = 1.0 / (victim_extralives + 1)
            killer_change = int(killer_change * mult)
            victim_change = int(victim_change * mult)
        
        # Apply kill streak bonus for killer
        if kill_streak > 1:
            streak_bonus = min(kill_streak * self.kill_streak_bonus, self.max_streak_bonus)
            killer_change += streak_bonus

        # Ensure rating changes are at least 1
        killer_change = max(killer_change, 1)
        victim_change = min(victim_change, -1)
        
        return killer_change, victim_change

    def process_kill(self, killer: Player, victim: Player, weapon_str: str, is_tk: bool = False):
        """Process a kill and update ratings"""
        if not self._is_initialized or not self.server_running:
            return
        
        killer_id = killer.GetId()
        victim_id = victim.GetId()
        
        # Don't process teamkills or suicides for rating
        if is_tk or killer_id == victim_id:
            return
        
        # Only process kills between real teams
        killer_team = killer.GetTeamId()
        victim_team = victim.GetTeamId()
        
        if not (teams.IsRealTeam(killer_team) and teams.IsRealTeam(victim_team)):
            return
        
        # Don't process friendly kills
        if killer_team == victim_team:
            return
        
        # Get current ratings
        killer_rating = self.get_rating(killer_id)
        victim_rating = self.get_rating(victim_id)
        
        # Get session stats from account data
        killer_stats = self._get_session_stats(killer_id)
        victim_stats = self._get_session_stats(victim_id)
        
        # Update kill streak
        current_time = time.time()
        
        # Reset victim's streak
        victim_stats["kill_streak"] = 0
        
        # Update killer's streak (if within reasonable time)
        # if current_time - killer_stats["last_kill_time"] < 30:  # 30 seconds between kills
        #     killer_stats["kill_streak"] += 0
        # else:
        killer_stats["kill_streak"] = 1
        
        killer_stats["last_kill_time"] = current_time
        
        # Get victim's extra lives count
        victim_extralives = self.get_extralives_for_pid(victim_id)
        
        # Calculate rating changes (accounting for extra lives)
        killer_change, victim_change = self.calculate_rating_change(
            killer_rating, victim_rating, killer_stats["kill_streak"], victim_extralives
        )
        
        # Apply rating changes
        new_killer_rating = killer_rating + killer_change
        new_victim_rating = victim_rating + victim_change
        
        self.set_rating(killer_id, new_killer_rating)
        self.set_rating(victim_id, new_victim_rating)
        
        # Update session stats
        killer_stats["kills"] += 1
        killer_stats["rating_changes"] += killer_change
        victim_stats["deaths"] += 1
        victim_stats["rating_changes"] += victim_change
        
        # Store updated session stats back to account data
        self.set_account_data_val_by_pid(killer_id, "elo_session_stats", killer_stats)
        self.set_account_data_val_by_pid(victim_id, "elo_session_stats", victim_stats)
        
        # Update database stats
        self._update_player_kill_stats(killer_id, victim_id)
        
        # Notify players
        self._notify_rating_change(killer, new_killer_rating, killer_change, True, killer_stats["kill_streak"])
        self._notify_rating_change(victim, new_victim_rating, victim_change, False)
        
        Log.info(f"Kill processed: {killer.GetName()} ({killer_rating}→{new_killer_rating}) killed {victim.GetName()} ({victim_rating}→{new_victim_rating})")

    def _update_player_kill_stats(self, killer_id: int, victim_id: int):
        """Update kill/death statistics in database"""
        killer_account = self.get_account_by_pid(killer_id)
        victim_account = self.get_account_by_pid(victim_id)
        
        if killer_account:
            self._initialize_player_rating(killer_account.user_id)

            query = f"""
                UPDATE elo_ratings 
                SET kills = kills + 1, 
                    last_played = CURRENT_TIMESTAMP
                WHERE user_id = {killer_account.user_id}
            """
            self.db_connection.ExecuteQuery(query)
        
        if victim_account:
            self._initialize_player_rating(victim_account.user_id)
            query = f"""
                UPDATE elo_ratings 
                SET deaths = deaths + 1,
                    last_played = CURRENT_TIMESTAMP
                WHERE user_id = {victim_account.user_id}
            """
            self.db_connection.ExecuteQuery(query)

    def _notify_rating_change(self, player: Player, new_rating: int, change: int, is_killer: bool, kill_streak: int = 0):
        """Notify player of rating change"""
        player_id = player.GetId()
        
        if change == 0:
            return
        
        change_color = "green" if change > 0 else "red"
        change_text = f"{'+' if change > 0 else ''}{change}"
        
        # Build message
        rating_text = colors.ColorizeText(str(new_rating), self.themecolor)
        change_display = colors.ColorizeText(change_text, change_color)
        
        message = f"Rating: {rating_text} ({change_display})"
        
        # Add kill streak info for killer
        if is_killer and kill_streak > 1:
            streak_text = colors.ColorizeText(f"{kill_streak}x", "yellow")
            message += f" {streak_text} streak!"
        
        self.server_data.interface.SvTell(player_id, self.msg_prefix + message)

    # Command handlers
    def _handle_rating(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !rating command"""
        player_id = player.GetId()
        rating = self.get_rating(player_id)
        
        # Get session stats from account data
        stats = self._get_session_stats(player_id)
                
        rating_text = colors.ColorizeText(str(rating), self.themecolor)
        message = f"Your rating: {rating_text}"
        
        if stats["rating_changes"] != 0:
            change_color = "green" if stats["rating_changes"] > 0 else "red"
            change_text = f"{'+' if stats['rating_changes'] >= 0 else ''}{stats['rating_changes']}"
            session_change = colors.ColorizeText(change_text, change_color)
            message += f" (Session: {session_change})"
        
        self.server_data.interface.SvTell(player_id, self.msg_prefix + message)
        return True

    def _handle_stats(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !stats command"""
        player_id = player.GetId()
        account = self.get_account_by_pid(player_id)
        
        if not account:
            self.server_data.interface.SvTell(player_id, self.msg_prefix + "Account not found")
            return True
        
        user_id = account.user_id
        query = f"""
            SELECT rating, games_played, kills, deaths, highest_rating, lowest_rating
            FROM elo_ratings WHERE user_id = {user_id}
        """
        result = self.db_connection.ExecuteQuery(query, withResponse=True)
        
        if not result or len(result) == 0:
            self.server_data.interface.SvTell(player_id, self.msg_prefix + "No statistics found")
            return True
        
        rating, games, kills, deaths, highest, lowest = result[0]
        kd_ratio = round(kills / max(deaths, 1), 2)
        
        # Session stats from account data
        session_stats = self._get_session_stats(player_id)
        
        # Build batch commands to avoid rate limit
        batch_commands = []
        batch_commands.append(f"svtell {player_id} {self.msg_prefix}Rating: {colors.ColorizeText(str(rating), self.themecolor)}")
        batch_commands.append("wait 1")
        batch_commands.append(f"svtell {player_id} Games: {games} | K/D: {kills}/{deaths} ({kd_ratio})")
        batch_commands.append("wait 1")
        batch_commands.append(f"svtell {player_id} Peak: {highest} | Low: {lowest}")
        batch_commands.append("wait 1")
        
        if session_stats["kills"] > 0 or session_stats["deaths"] > 0:
            session_kd = round(session_stats["kills"] / max(session_stats["deaths"], 1), 2)
            change_color = "green" if session_stats["rating_changes"] > 0 else "red"
            change_text = f"{'+' if session_stats['rating_changes'] > 0 else ''}{session_stats['rating_changes']}"
            session_change = colors.ColorizeText(change_text, change_color)
            batch_commands.append(f"svtell {player_id} Session: {session_stats['kills']}/{session_stats['deaths']} ({session_kd}) | Change: {session_change}")
        
        # Execute all messages in batch
        self.server_data.interface.BatchExecute("b", batch_commands)
        
        return True

    def _handle_leaderboard(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !leaderboard command"""
        player_id = player.GetId()
        
        query = """
            SELECT er.rating, er.kills, er.deaths, er.games_played, a.player_name
            FROM elo_ratings er
            JOIN user_credentials a ON er.user_id = a.user_id
            ORDER BY er.rating DESC
            LIMIT 10
        """
        result = self.db_connection.ExecuteQuery(query, withResponse=True)
        
        if not result or len(result) == 0:
            self.server_data.interface.SvSay(self.msg_prefix + "No leaderboard data available")
            return True
        
        # Build leaderboard as a single message
        top_players = []
        for i, (rating, kills, deaths, games, name) in enumerate(result, 1):
            kd_ratio = round(kills / max(deaths, 1), 2)
            rating_text = colors.ColorizeText(str(rating), self.themecolor)
            top_players.append(f"{i}. {name}^7 - {rating_text} ({kd_ratio} K/D)")
        
        # Output as single say message
        self.server_data.interface.SvSay(self.msg_prefix + "Top 10 Players: " + ", ".join(top_players))
        
        return True

    def _handle_rank(self, player: Player, team_id: int, args: list[str]) -> bool:
        """Handle !rank command"""
        player_id = player.GetId()
        account = self.get_account_by_pid(player_id)
        
        if not account:
            self.server_data.interface.SvTell(player_id, self.msg_prefix + "Account not found")
            return True
        
        user_id = account.user_id
        rating = self.get_rating(player_id)
        
        # Get player's rank
        rank_query = f"""
            SELECT COUNT(*) + 1 as rank
            FROM elo_ratings
            WHERE rating > {rating}
        """
        rank_result = self.db_connection.ExecuteQuery(rank_query, withResponse=True)
        
        # Get total players
        total_query = "SELECT COUNT(*) FROM elo_ratings"
        total_result = self.db_connection.ExecuteQuery(total_query, withResponse=True)
        
        if rank_result and total_result:
            rank = rank_result[0][0]
            total = total_result[0][0]
            rating_text = colors.ColorizeText(str(rating), self.themecolor)
            
            self.server_data.interface.SvTell(player_id, self.msg_prefix + f"Rank: #{rank} of {total} (Rating: {rating_text})")
        else:
            self.server_data.interface.SvTell(player_id, self.msg_prefix + "Rank data unavailable")
        
        return True

    # SMOD command handlers
    def _handle_reset_rating(self, player_name: str, smod_id: int, admin_ip: str, args: list[str]) -> bool:
        """Handle !resetrating SMOD command"""
        if len(args) < 2:
            self.server_data.interface.SmSay("Usage: !resetrating <player_prefix>")
            return True
        
        target_pfx = args[1]
        target = self._find_player(target_pfx)
        
        if not target:
            self.server_data.interface.SmSay("Player not found")
            return True
        
        if self.set_rating(target.GetId(), self.default_rating):
            self.server_data.interface.SmSay(f"Reset {target.GetName()}^7's rating to {self.default_rating}")
            self.server_data.interface.SvTell(target.GetId(), self.msg_prefix + f"Your rating has been reset to {self.default_rating}")
            Log.info(f"SMOD {player_name} reset {target.GetName()}'s rating")
        else:
            self.server_data.interface.SmSay("Failed to reset rating")
        
        return True

    def _handle_set_rating(self, player_name: str, smod_id: int, admin_ip: str, args: list[str]) -> bool:
        """Handle !setrating SMOD command"""
        if len(args) < 3:
            self.server_data.interface.SmSay("Usage: !setrating <player_prefix> <rating>")
            return True
        
        target_pfx = args[1]
        try:
            new_rating = int(args[2])
            if new_rating < self.min_rating or new_rating > self.max_rating:
                raise ValueError
        except ValueError:
            self.server_data.interface.SmSay(f"Invalid rating (must be {self.min_rating}-{self.max_rating})")
            return True
        
        target = self._find_player(target_pfx)
        if not target:
            self.server_data.interface.SmSay("Player not found")
            return True
        
        if self.set_rating(target.GetId(), new_rating):
            self.server_data.interface.SmSay(f"Set {target.GetName()}^7's rating to {new_rating}")
            self.server_data.interface.SvTell(target.GetId(), self.msg_prefix + f"Your rating has been set to {new_rating}")
            Log.info(f"SMOD {player_name} set {target.GetName()}'s rating to {new_rating}")
        else:
            self.server_data.interface.SmSay("Failed to set rating")
        
        return True

    def _handle_elo_info(self, player_name: str, smod_id: int, admin_ip: str, args: list[str]) -> bool:
        """Handle !eloinfo SMOD command"""
        # Count active players by checking account data for session stats
        active_players = 0
        clients = self.server_data.API.GetAllClients()
        for client in clients:
            if client:
                stats = self._get_session_stats(client.GetId())
                if stats["kills"] > 0 or stats["deaths"] > 0:
                    active_players += 1
        
        server_status = "Running" if self.server_running else "Not Running"
        
        self.server_data.interface.SmSay(self.msg_prefix + "Elo System Info:")
        self.server_data.interface.SmSay(f"Default Rating: {self.default_rating} | K-Factor: {self.k_factor}")
        self.server_data.interface.SmSay(f"Server Status: {server_status} | Active Players: {active_players}")
        self.server_data.interface.SmSay(f"Rating Range: {self.min_rating}-{self.max_rating}")
        return True

    def _handle_reload_extralives(self, player_name: str, smod_id: int, admin_ip: str, args: list[str]) -> bool:
        """SMOD command to reload extralives.json at runtime"""
        try:
            self._load_extralives_map()
            self.server_data.interface.SmSay(self.msg_prefix + f"Reloaded extralives table ({len(self.extralives_map)} entries)")
        except Exception as e:
            self.server_data.interface.SmSay(self.msg_prefix + f"Failed to reload extralives: {e}")
        return True

    def _find_player(self, prefix: str) -> Optional[Player]:
        """Find player by name prefix"""
        prefix_lower = prefix.lower()
        clients = self.server_data.API.GetAllClients()
        
        for client in clients:
            if client and client.GetName().lower().startswith(prefix_lower):
                return client
        
        return None

    # ==== Extra lives integration ====
    def _extralives_path(self) -> str:
        """Get path to extralives.json file"""
        # repo_root/plugins/shared/elo/elo.py -> repo_root/data/extralives.json
        here = os.path.dirname(__file__)
        repo_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
        return os.path.join(repo_root, "data", "extralives.json")

    def _load_extralives_map(self) -> None:
        """Load extralives table from JSON into memory. Keys are plaintext character names."""
        try:
            path = self._extralives_path()
            if not os.path.exists(path):
                Log.warning(f"extralives.json not found at {path}; rating changes will not be scaled by extra lives")
                self.extralives_map = {}
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Expect structure: { total_characters: N, characters: { name: { extralives: int, ... }, ... } }
            chars = data.get("characters", {}) if isinstance(data, dict) else {}
            table = {}
            for name, info in chars.items():
                try:
                    n = info.get("extralives", 0)
                    if n is None:
                        n = 0
                    n = int(n)
                    if n < 0:
                        n = 0
                    table[str(name)] = n
                except Exception:
                    continue
            self.extralives_map = table
            Log.info(f"Loaded extralives map with {len(self.extralives_map)} entries")
        except Exception as e:
            Log.error(f"Failed to load extralives.json: {e}")
            self.extralives_map = {}

    def get_extralives_for_pid(self, player_id: int) -> int:
        """Get extra lives count for the player's current character/class name; returns 0 if unknown."""
        name = self.player_class_by_pid.get(player_id)
        if not name:
            return 0
        return int(self.extralives_map.get(name, 0))

    def _on_client_changed(self, event: Event):
        """Track player's current class/character name when they change class."""
        client = event.client
        if not client:
            return
        player_id = client.GetId()
        # Extract character name from event data
        if hasattr(event, 'data') and isinstance(event.data, dict):
            char_name = event.data.get('sc')
            if char_name:
                self.player_class_by_pid[player_id] = str(char_name)
                Log.debug(f"Player {player_id} changed to class: {char_name}")

    # Event handlers
    def _on_chat_message(self, event: Event):
        """Handle chat messages for commands"""
        client = event.client
        message = event.message
        team_id = client.GetTeamId()
        
        if not message.startswith("!"):
            return
        
        args = message[1:].split()
        if not args:
            return
        
        command = args[0].lower()
        
        # Check team-specific commands
        team_commands = self._command_list.get(teams.TEAM_GLOBAL, {})
        
        for command_variants, (description, handler) in team_commands.items():
            if command in command_variants:
                try:
                    handler(client, team_id, args)
                except Exception as e:
                    Log.error(f"Error handling command {command}: {e}")
                    self.server_data.interface.SvTell(client.GetId(), self.msg_prefix + "Command error occurred")
                return

    def _on_smsay(self, event: Event):
        """Handle SMSAY commands"""
        player_name = event.playerName
        smod_id = event.smodID
        admin_ip = event.adminIP
        message = event.message
        
                
        if not message.startswith("!"):
            return
        
        args = message[1:].split()
        if not args:
            return
        
        command = args[0].lower()
        
        for command_variants, (description, handler) in self._smodCommandList.items():
            if command in command_variants:
                try:
                    handler(player_name, smod_id, admin_ip, args)
                except Exception as e:
                    Log.error(f"Error handling SMOD command {command}: {e}")
                    self.server_data.interface.SmSay("SMOD command error occurred")
                return

    def _on_client_connect(self, event: Event):
        """Handle client connection"""
        if event.isStartup:
            return
        
        client = event.client
        if not client:
            return
        
        player_id = client.GetId()
        
        # Initialize session stats in account data
        if not self.get_account_data_val_by_pid(player_id, "elo_session_stats"):
            new_stats = {
                "kills": 0,
                "deaths": 0,
                "rating_changes": 0,
                "last_kill_time": 0.0,
                "kill_streak": 0
            }
            self.set_account_data_val_by_pid(player_id, "elo_session_stats", new_stats)
        
        # Pre-cache the player's rating from database
        rating = self.get_rating(player_id)
        Log.debug(f"Player {client.GetName()} connected with rating {rating}")
        return False

    def _on_client_disconnect(self, event: Event):
        """Handle client disconnection"""
        client = event.client
        if not client:
            return
        
        player_id = client.GetId()
        
        # Clear session stats from account data
        self.set_account_data_val_by_pid(player_id, "elo_session_stats", None)
        
        # Clear cached rating
        self.set_account_data_val_by_pid(player_id, "elo_rating", None)
        
        # Clear player class tracking
        if player_id in self.player_class_by_pid:
            del self.player_class_by_pid[player_id]
        
        Log.debug(f"Player {client.GetName()} disconnected, cleared session data")

    def _on_kill(self, event: Event):
        """Handle kill events"""
        killer = event.client
        victim = event.victim
        weapon_str = event.weaponStr
        is_tk = event.data.get('tk', False)
        
        if killer and victim:
            self.process_kill(killer, victim, weapon_str, is_tk)

    def _on_server_init(self, event: Event):
        """Handle server initialization"""
        current_time = time.time()
        
        # Prevent rapid re-initialization
        if current_time - self.last_server_init < 5:
            return
        
        self.last_server_init = current_time
        self.server_running = True
        
        # Clear all cached session data on server restart
        clients = self.server_data.API.GetAllClients()
        for client in clients:
            if client:
                player_id = client.GetId()
                # Reset session stats
                # new_stats = {
                #     "kills": 0,
                #     "deaths": 0,
                #     "rating_changes": 0,
                #     "last_kill_time": 0.0,
                #     "kill_streak": 0
                # }
                # self.set_account_data_val_by_pid(player_id, "elo_session_stats", new_stats)
                # # Clear cached rating to force reload from database
                # self.set_account_data_val_by_pid(player_id, "elo_rating", None)
        
        # Log.info("Elo system initialized for new server session")
        return False

    def _on_server_shutdown(self, event: Event):
        """Handle server shutdown"""
        self.server_running = False
        Log.info("Elo system shutting down")

# Global plugin instance
elo_plugin = None


def OnInitialize(server_data: ServerData, exports=None):
    """Initialize the Elo plugin"""
    global elo_plugin
    
    try:
        elo_plugin = EloPlugin(server_data)
        
        # Get account system exports
        accountsystem_plugin = server_data.API.GetPlugin("plugins.shared.accountsystem.accountsystem")
        if accountsystem_plugin:
            accountsystem_xprts = accountsystem_plugin.GetExports()
            elo_plugin.accountsystem_xprts = accountsystem_xprts
            elo_plugin.get_account_by_uid = accountsystem_xprts.Get("GetAccountByUserID").pointer
            elo_plugin.get_account_by_pid = accountsystem_xprts.Get("GetAccountByPlayerID").pointer
            elo_plugin.get_account_data_val_by_pid = accountsystem_xprts.Get("GetAccountDataValByPID").pointer
            elo_plugin.get_account_data_val_by_uid = accountsystem_xprts.Get("GetAccountDataValByUID").pointer
            elo_plugin.set_account_data_val_by_pid = accountsystem_xprts.Get("SetAccountDataValByPID").pointer
            elo_plugin.set_account_data_val_by_uid = accountsystem_xprts.Get("SetAccountDataValByUID").pointer
            elo_plugin.db_connection = accountsystem_xprts.Get("GetDatabaseConnection").pointer()
            elo_plugin.account_manager = accountsystem_xprts.Get("GetAccountManager").pointer()
            
            Log.info("Elo plugin connected to account system")
        else:
            Log.error("Account system exports not found - Elo plugin requires account system")
            return False
        
        # Initialize database table
        if not elo_plugin.initialize_elo_table():
            Log.error("Failed to initialize Elo database table")
            return False
        
        elo_plugin._is_initialized = True
        Log.info("Elo plugin initialized successfully")
        
        # Export functions for other plugins
        if exports:
            exports.Add("GetPlayerRating", elo_plugin.get_rating)
            exports.Add("SetPlayerRating", elo_plugin.set_rating)
            exports.Add("ProcessKill", elo_plugin.process_kill)
    
        return True
                
    except Exception as e:
        Log.error(f"Failed to initialize Elo plugin: {e}")
        return False

def OnStart():
    """Called when platform starts"""
    global elo_plugin
    if elo_plugin:
        elo_plugin.server_running = True
        Log.info("Elo plugin started")
    return True

def OnLoop():
    """Called each loop tick from the system"""
    pass

def OnFinish():
    """Called before plugin is unloaded by the system"""
    global elo_plugin
    if elo_plugin:
        elo_plugin.server_running = False
        Log.info("Elo plugin shutdown complete")

def OnEvent(event) -> bool:
    """Called from system on some event raising, return True to indicate event being captured"""
    global elo_plugin
    if not elo_plugin or not elo_plugin._is_initialized:
        return False
    
    try:
        # Handle different event types
        if hasattr(event, 'type'):
            event_type = event.type
            
            if event_type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
                elo_plugin._on_chat_message(event)
            elif event_type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
                elo_plugin._on_smsay(event)
            elif event_type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
                elo_plugin._on_client_connect(event)
            elif event_type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
                elo_plugin._on_client_disconnect(event)
            elif event_type == godfingerEvent.GODFINGER_EVENT_TYPE_KILL:
                elo_plugin._on_kill(event)
            elif event_type == godfingerEvent.GODFINGER_EVENT_TYPE_INIT:
                elo_plugin._on_server_init(event)
            elif event_type == godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN:
                elo_plugin._on_server_shutdown(event)
            elif event_type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
                elo_plugin._on_client_changed(event)
                
    except Exception as e:
        Log.error(f"Error handling event in Elo plugin: {e}")
    
    return False  # Don't capture events, let other plugins handle them too

def OnShutdown():
    """Shutdown the Elo plugin"""
    global elo_plugin
    if elo_plugin:
        elo_plugin.server_running = False
        Log.info("Elo plugin shutdown complete")

if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system. Please run one of the start scripts in the start directory to use it. Make sure that this python module's path is included in godfingerCfg!")
    input("Press Enter to close this message.")
    exit()