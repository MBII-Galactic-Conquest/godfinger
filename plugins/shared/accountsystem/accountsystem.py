#   AccountSystem
#   An account system for the Godfinger Movie Battles II plugin system
#   By Mantlar/ACHUTA https://www.github.com/mantlar
#   Plugin Dependencies (must be loaded before this in load order!):
#

import logging
import os
from time import time
from typing import Dict, List, Optional
from godfingerEvent import Event
from lib.shared.serverdata import ServerData
from database import DatabaseManager
from lib.shared.player import Player
import lib.shared.teams as teams
import lib.shared.colors as colors
import godfingerEvent

DB_PATH = os.path.join(os.path.dirname(__file__), "login.db")
DB_NAME = os.path.basename(DB_PATH)

# Initialize logger
Log = logging.getLogger(__name__)


def escape_sql_apostrophes(s: str) -> str:
    """Escapes single apostrophes in a string for SQL insertion by doubling them."""
    return s.replace("'", "''")


class Account:

    def __init__(self, user_id: int, player_id: int, player_name: str,
                 ip_address: str, totp_secret: str, client: Optional[Player] = None):
        self.user_id = user_id
        self.player_id = player_id
        self.player_name = player_name
        self.ip_address = ip_address
        self.totp_secret = totp_secret
        self.client = client  # Optional client object reference
        self.session_id: Optional[str] = None
        self.last_login: Optional[float] = None
        self.account_data = {}

    def get_account_var(self, name):
        return self.account_data.get(name, None)

    def set_account_var(self, name, val):
        self.account_data[name] = val

    def invalidate_session(self):
        self.session_id = None

    def update_last_login(self):
        self.last_login = time()

    def set_client(self, client: Optional[Player]):
        """Set or update the client object associated with this account"""
        self.client = client
        if client:
            self.player_id = client.GetId()
            # Update player name if it has changed
            if self.player_name != client.GetName():
                Log.info(f"Updating player name from '{self.player_name}' to '{client.GetName()}' for user_id {self.user_id}")
                self.player_name = client.GetName()

    def get_client(self) -> Optional[Player]:
        """Get the client object associated with this account"""
        return self.client

    def is_online(self) -> bool:
        """Check if the account has an active client connection"""
        return self.client is not None

    def is_dummy_account(self) -> bool:
        """Check if this is a dummy account (no user_id from database)"""
        return self.user_id is None

    def __str__(self):
        status = "online" if self.is_online() else "offline"
        dummy_status = " (dummy)" if self.is_dummy_account() else ""
        return f"Account: PID {self.player_id}; UID {self.user_id}; Status: {status}{dummy_status}"

    def __repr__(self):
        return self.__str__()

class AccountManager:

    def __init__(self, db_path: str = DB_PATH):
        self.db_manager = DatabaseManager()
        self.accounts: dict[int, Account] = {}
        self.accounts_db = None
        self._initialize_database(db_path)

    def _initialize_database(self, db_path: str):
        db_name = os.path.basename(db_path)
        result = self.db_manager.CreateDatabase(db_path, db_name)
        if result == DatabaseManager.DBM_RESULT_OK or result == DatabaseManager.DBM_RESULT_ALREADY_EXISTS:
            self.accounts_db = self.db_manager.GetDatabase(db_name)
            self._create_tables()
        else:
            Log.error("Failed to initialize accounts database")

    def _create_tables(self):
        create_user_credentials_table = """
        CREATE TABLE IF NOT EXISTS user_credentials (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            last_login_ip TEXT,
            totp_secret TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
        """
        self.accounts_db.ExecuteQuery(create_user_credentials_table)

    def get_account_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Retrieve account data from database by user_id"""
        query = f"""
        SELECT user_id, player_name, ip_address, last_login_ip, totp_secret, last_login
        FROM user_credentials
        WHERE user_id = {user_id}
        """
        result = self.accounts_db.ExecuteQuery(query, withResponse=True)
        if not result or len(result) == 0:
            return None
        data = {
            "user_id": result[0][0],
            "player_name": result[0][1],
            "ip_address": result[0][2],
            "last_login_ip": result[0][3],
            "totp_secret": result[0][4],
            "last_login": result[0][5]
        }
        return Account(data["user_id"], None, data["player_name"],
                       data["ip_address"], data["totp_secret"], client=None)

    def get_account_by_player_id(self, player_id: int) -> Optional[Account]:
        """Retrieve local account by player_id"""
        # This should be implemented in AccountPlugin
        pass  # To be implemented in AccountPlugin

    def load_account(self, player_name: str,
                     ip_address: str, client: Optional[Player] = None) -> Optional[Account]:
        esc_name = escape_sql_apostrophes(player_name)
        query = f"SELECT user_id, player_name, ip_address, last_login_ip, totp_secret, last_login FROM user_credentials WHERE player_name = '{esc_name}' AND ip_address = '{ip_address}'"
        result = self.accounts_db.ExecuteQuery(query, withResponse=True)
        if result and len(result) > 0:
            res = result[0]
            user_id = res[0]
            # player_name = result[0][1],
            # ip_address = result[0][2],
            last_login_ip = res[3]
            totp_secret = res[4]
            last_login = res[5]

            # Create the Account object
            new_acc = Account(user_id, None, player_name, ip_address,
                              totp_secret, client=client)
            new_acc.last_login = last_login

            # Update last_login and last_login_ip in the database
            update_query = f"""
                UPDATE user_credentials
                SET last_login = CURRENT_TIMESTAMP, last_login_ip = '{ip_address}'
                WHERE user_id = {user_id}
            """
            self.accounts_db.ExecuteQuery(update_query)
            return new_acc
        else:
            Log.error("Unable to retrieve new user ID from database")
            return None

    def create_account(self, player_name: str,
                       ip_address: str, client=None) -> Optional[Account]:
        """Create a new account"""

        totp_secret = os.urandom(16).hex()
        esc_name = escape_sql_apostrophes(player_name)
        insert_query = f"""
        INSERT INTO user_credentials (player_name, ip_address, last_login_ip, totp_secret)
        VALUES ('{esc_name}', '{ip_address}', '{ip_address}', '{totp_secret}')
        """
        self.accounts_db.ExecuteQuery(insert_query)
        query = f"SELECT user_id FROM user_credentials WHERE player_name = '{esc_name}'"
        result = self.accounts_db.ExecuteQuery(query, withResponse=True)
        if result and len(result) > 0:
            user_id = result[0][0]
            Log.info(
                f"Account successfully created for ({player_name}, {ip_address})"
            )
            return Account(user_id, None, player_name, ip_address, totp_secret, client=client)
        else:
            Log.error("Unable to retrieve new user ID from database")
            return -1


class AccountPlugin:

    def __init__(self, server_data: ServerData):
        self.server_data = server_data
        self.account_manager = AccountManager()
        self.account_manager.accounts = {
        }  # player_id: Account object
        self.themecolor = "yellow"
        self.msg_prefix = colors.COLOR_CODES[self.themecolor] + '[Account]^7: '
        self._is_initialized = False
        self._register_commands()

    def get_account_manager(self):
        return self.account_manager

    def get_account_by_user_id(self, user_id: int) -> Optional[Account]:
        """Retrieve account from database and create local Account object"""
        for acc in self.account_manager.accounts.values():
            if acc.user_id == user_id:
                return acc
        # if we couldn't find it in the logged in accounts, return a new dummy account
        account = self.account_manager.get_account_by_user_id(user_id)
        if not account:
            return None
        return account

    def get_account_by_player_id(self, player_id: int) -> Optional[Account]:
        """Retrieve local account by player_id"""
        for account in self.account_manager.accounts.values():
            if account.player_id == player_id:
                return account
        return None

    def set_account_data_val_by_pid(self, pid: int, key: str, val: object):
        if pid in self.account_manager.accounts.keys():
            self.account_manager.accounts[pid].account_data[key] = val
            return True
        return False

    def set_account_data_val_by_uid(self, uid: int, key: str, val: object):
        for i in self.account_manager.accounts.keys():
            if self.account_manager.accounts[i].user_id == uid:
                self.account_manager.accounts[i].account_data[key] = val
                return True
        return False

    def get_account_data_val_by_pid(self,
                                    pid: int,
                                    key: str,
                                    create_if_not_exists: bool = False):
        if pid in self.account_manager.accounts.keys():
            if key in self.account_manager.accounts[pid].account_data:
                return self.account_manager.accounts[pid].account_data[key]
            elif create_if_not_exists:
                self.account_manager.accounts[pid].account_data[key] = None
        return None

    def get_account_data_val_by_uid(self,
                                    uid: int,
                                    key: str,
                                    create_if_not_exists: bool = False):
        for i in self.account_manager.accounts.keys():
            if self.account_manager.accounts[i].user_id == uid:
                if key in self.account_manager.accounts[i].account_data:
                    return self.account_manager.accounts[i].account_data[key]
                elif create_if_not_exists:
                    self.account_manager.accounts[i].account_data[key] = None
                    break
        return None

    def load_or_create_account(self, player_name: str, ip_address: str, client: Player, display_welcome=True) -> tuple[Account, bool]:
        """
        Load an existing account or create a new one if it doesn't exist.
        
        Args:
            player_name: The player's name
            ip_address: The player's IP address
            client: The client object to associate with the account
            display_welcome: Whether to display welcome messages
            
        Returns:
            tuple: (Account object, created_flag) where created_flag is True if a new account was created
        """
        created = False
        client_id = client.GetId()
        
        account = self.account_manager.load_account(player_name, ip_address, client)
        if not account:
            Log.debug(f"Couldn't find existing account with credentials {player_name, ip_address}, attempting to create new account.")
            account = self.account_manager.create_account(player_name, ip_address, client)
            created = True
        
        if account:
            account.set_client(client)  # Ensure client is properly set
            self.account_manager.accounts[client_id] = account
            Log.info(f"Player {player_name} (ID: {client_id}) successfully logged in as user id {account.user_id}.")
            if created and display_welcome:
                self._tell_player(client_id, f"Welcome, {player_name}^7! Your account was automatically created! (ID: {colors.ColorizeText(account.user_id, self.themecolor)})")
            elif display_welcome:
                self._tell_player(client_id, f"Welcome back, {player_name}^7! Your stats were successfully loaded! (ID: {colors.ColorizeText(account.user_id, self.themecolor)})")
        else:
            Log.error(f"UNABLE TO CREATE ACCOUNT FOR {player_name, ip_address}! USING DEFAULT TEMPORARY ACCOUNT, DATA WILL NOT BE SAVED!")
            self._tell_player(client_id, f"Your stats could not be loaded. Using temporary account.")
            # Create dummy account with client
            account = Account(None, client_id, player_name, ip_address, None, client=client)
            self.account_manager.accounts[client_id] = account
        
        return account, created

    def get_database_connection(self):
        return self.account_manager.accounts_db

    def _on_client_connect(self, event: Event):
        client = event.client
        pid = client.GetId()
        player_name = client.GetName()
        ip_address = client.GetIp()
    
        if pid in self.account_manager.accounts:
            if self.account_manager.accounts[pid].player_name == player_name:
                Log.warning(
                    f"Player ID {pid} already exists and name matches. Ignoring new connection."
                )
                return False
            Log.warning(
                f"Player ID {pid} already exists and name doesn't match. Overwriting with new connection."
            )
    
        account, created = self.load_or_create_account(player_name, ip_address, client)
        return False

    def _on_client_disconnect(self, event: Event):
        pid = event.client.GetId()
        if pid in self.account_manager.accounts:
            account = self.account_manager.accounts[pid]
            account.invalidate_session()
            account.set_client(None)  # Clear the client reference
            del self.account_manager.accounts[pid]
            Log.info(
                f"Player {event.client.GetName()} (ID: {pid}) disconnected.")
        return False

    def _on_chat_message(self, event: Event):
        client = event.client
        message = event.message
        team_id = teams.TEAM_GLOBAL

        if message.startswith("!"):
            args = message[1:].split()
            if not args:
                return False

            cmd = args[0].lower()
            for cmd_list, handler in self._command_list[team_id].items():
                if cmd in cmd_list:
                    handler[1](client, team_id, args)
                    break
        return False

    def _on_client_changed(self, event: Event):
        client_id = event.client.GetId()
        if 'n' in event.data and client_id in self.account_manager.accounts:
            if self.account_manager.accounts[client_id].player_name != event.data['n']:
                old_name = self.account_manager.accounts[client_id].player_name
                new_name = event.data['n']
                Log.info(f"Player ID {client_id} changed name from '{old_name}' to '{new_name}'")
                
                # Log out current account
                old_account = self.account_manager.accounts[client_id]
                old_account.invalidate_session()
                old_account.set_client(None)
                del self.account_manager.accounts[client_id]
                
                # Get client IP and attempt to load/create account with new name
                ip_address = event.client.GetIp()
                account, created = self.load_or_create_account(new_name, ip_address, event.client, display_welcome=False)
                if created:
                    self._tell_player(client_id, f"Name changed to {new_name}^7! New account created automatically! (ID: {colors.ColorizeText(account.user_id, self.themecolor)})")
                else:
                    self._tell_player(client_id, f"Name changed to {new_name}^7! Existing account loaded! (ID: {colors.ColorizeText(account.user_id, self.themecolor)})")

    def _register_commands(self):
        self._command_list = {
            teams.TEAM_GLOBAL: {
                ("login", ):
                ("!login - Login to your account", self._handle_login),
                ("register", ):
                ("!register - Register a new account", self._handle_register),
                ("uid", "id", "getuid", "getid"):
                ("!uid/!id - Get your user ID", self._handle_get_uid),
            }
        }
        self._smodCommandList = {
                # ... TODO come up with some of these ...
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

    def _handle_get_uid(self, client, team_id, args):
        pid = client.GetId()
        if pid not in self.account_manager.accounts:
            self._tell_player(pid, "You don't have an account. Please register first.")
            return

        account = self.account_manager.accounts[pid]
        if account.is_dummy_account():
            self._tell_player(pid, "You are using a temporary account with no saved data.")
            return

        self._tell_player(pid, f"Your user ID is: {colors.ColorizeText(str(account.user_id), self.themecolor)}")

    def _handle_login(self, client, team_id, args):
        pid = client.GetId()
        if pid not in self.account_manager.accounts:
            self._tell_player(
                pid, "You don't have an account. Please register first.")
            return

        account = self.account_manager.accounts[pid]
        if account:
            self._tell_player(pid, "You are already logged in.")
            return

        # Implement your login logic here
        self._tell_player(pid, "Login successful!")

    def _handle_register(self, client, team_id, args):
        pid = client.GetId()
        if pid in self.account_manager.accounts:
            self._tell_player(pid, "You already have an account.")
            return

        account = self.account_manager.create_account(client.GetName(),
                                                      client.GetIP())
        if account:
            account.player_id = pid
            self.account_manager.accounts[pid] = account
            self._tell_player(pid, "Registration successful!")
        else:
            self._tell_player(pid, "Registration failed.")

    def _tell_player(self, pid: int, message: str):
        self.server_data.interface.SvTell(pid, f"{self.msg_prefix}{message}")

    def console_say(self, message: str):
        self.server_data.interface.Say(f"{self.msg_prefix}{message}")

    def chat_say(self, message: str):
        self.server_data.interface.SvSay(f"{self.msg_prefix}{message}")


def OnStart() -> bool:
    global account_plugin
    startTime = time()
    batchCmds = []
    for client in account_plugin.server_data.API.GetAllClients():
        pid = client.GetId()
        player_name = client.GetName()
        ip_address = client.GetIp()
        
        account, created = account_plugin.load_or_create_account(player_name, ip_address, client, display_welcome=True)
    
    account_plugin.server_data.interface.BatchExecute("b", batchCmds)
    # Report startup time
    loadTime = time() - startTime
    account_plugin.console_say(
        f"Account system started in {loadTime:.2f} seconds! Loaded {colors.ColorizeText(str(len(account_plugin.account_manager.accounts)), account_plugin.themecolor)} account(s)!"
    )
    return True


def OnLoop() -> bool:
    return False


def OnFinish():
    global account_plugin
    if account_plugin:
        account_plugin.account_manager.accounts_db.Close()
        del account_plugin
        account_plugin = None


def OnInitialize(server_data: ServerData, exports=None):
    global account_plugin
    account_plugin = AccountPlugin(server_data)
    if exports is not None:
        exports.Add("GetAccountByUserID",
                    account_plugin.get_account_by_user_id)
        exports.Add("GetAccountByPlayerID",
                    account_plugin.get_account_by_player_id)
        exports.Add("SetAccountDataValByPID",
                    account_plugin.set_account_data_val_by_pid)
        exports.Add("SetAccountDataValByUID",
                    account_plugin.set_account_data_val_by_uid)
        exports.Add("GetAccountDataValByPID",
                    account_plugin.get_account_data_val_by_pid)
        exports.Add("GetAccountDataValByUID",
                    account_plugin.get_account_data_val_by_uid)
        exports.Add("GetDatabaseConnection",
                    account_plugin.get_database_connection)
        exports.Add("GetAccountManager", account_plugin.get_account_manager)
    return True


def OnEvent(event: Event) -> bool:
    global account_plugin
    if not account_plugin:
        return False

    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        account_plugin._on_client_connect(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        account_plugin._on_client_disconnect(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        account_plugin._on_chat_message(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        account_plugin._on_client_changed(event)
    return False
