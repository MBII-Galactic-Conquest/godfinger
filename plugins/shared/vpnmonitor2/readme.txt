ORIGINALLY MADE BY DEVON, MODIFIED BY SPAGHETTI
https://github.com/MBII/VPNMonitor

MODIFIED FURTHER BY YUUREI

Not a new version just another option

To get your API keys goto https://findip.net/ and create an account, then create a API key in the dashboard. It is a free and unlimited service.

Disclaimer - This IP Lookup service (FindIP) does not check if the IP is a Proxy/VPN independently. This plugin goes off the connection type or user type to block IPs. This may cause false positives.

User_Types from findip.net:
residential: IPs associated with residential internet connections, typically used by individuals in their homes. (Usually legitimate users but there are VPN services out there that use residential IP addresses)
cellular: IPs associated with mobile networks, often used by smartphones and tablets or mobile proxies/crawlers. (Can cause false positives on some ISPs that use cellular IPs for residential customers)
business: IPs associated with business internet connections, which may include offices, data centers, or other commercial entities. (Can cause false positives on some ISPs that use business IPs for residential customers)
hosting: IPs associated with hosting providers, which may include servers, virtual private servers (VPS), or cloud services. (Flags most common VPN providers, use business for a more aggressive block)
unknown: IPs that could not be classified into the above categories, which may indicate an unrecognized or inconclusive VPN detection result.
You can always whitelist a specific IP address if they are flagging as a blocked User_Type but you wish to allow the connection.

Block by ASN, a nuclear option, this can be used to block entire ISP/VPN providers. Use with caution as it will block MILLIONS of IP addresses. 
ASN is the autonomous system number, which is a unique identifier assigned to each network on the internet. 
By blocking specific ASNs, you can effectively block all IP addresses associated with that network, which can be useful for blocking known VPN providers that operate large networks. 
However, this approach can lead to false positives and may block legitimate users who happen to be using the same ISP or network as the VPN provider. 
Always research the ASN before adding it to the block list and consider the potential impact on legitimate users.
This is a last resort option for persistent VPN offenders that are not blocked by the normal user type blocking, but use with extreme caution as it can block large swaths of legitimate users.
You can always whitelist specific IP addresses from a blocked ASN if you want to allow certain users while still blocking the overall network.

These block types are added in the config file, ensure you use the exact user_type (lowercase) and/or ASN number.

Config block action - 'action' 0 = kick only, 1 = ban by ip then kick

Commands:
!whitelistip <IP> | !wlip - is used to allow certain IP addresses that may be detected as VPNs but you want to allow them anyway.
!blacklistip <IP/NAME> | !blip - is used incase the VPN is not recognized by third party services like findip, but you still consider those IP addresses a VPN.
!vpnhitcount | !vpnhits - displays how many IPs match the configured block list in the database.
!lookupip <IP> | !lkip - looks up IP info from database or through the API. Displays the user type and ASN.