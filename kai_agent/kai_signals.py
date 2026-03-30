"""
Kai Signals — wireless awareness for the companion.

Detects and monitors:
- WiFi networks (signal strength, names, channels)
- Bluetooth devices (nearby devices, types)
- Network interfaces (IP, status)

Usage:
    from kai_agent.kai_signals import KaiSignals
    signals = KaiSignals()
    wifi = signals.scan_wifi()
    bt = signals.scan_bluetooth()

Platform support:
- Linux: nmcli (WiFi), bluetoothctl/hcitool (BT)
- Windows: netsh (WiFi), PowerShell BLE (BT)
- macOS: networksetup (WiFi), system_profiler (BT)
"""

import json
import os
import platform
import re
import shutil
import subprocess
from typing import Optional


class KaiSignals:
    def __init__(self):
        self.system = platform.system()

    # ─── WiFi ───

    def scan_wifi(self) -> dict:
        """Scan for nearby WiFi networks."""
        if self.system == "Linux":
            return self._scan_wifi_linux()
        elif self.system == "Windows":
            return self._scan_wifi_windows()
        elif self.system == "Darwin":
            return self._scan_wifi_macos()
        return {"available": False, "error": "unsupported platform"}

    def get_current_wifi(self) -> dict:
        """Get the currently connected WiFi network."""
        if self.system == "Linux":
            return self._current_wifi_linux()
        elif self.system == "Windows":
            return self._current_wifi_windows()
        elif self.system == "Darwin":
            return self._current_wifi_macos()
        return {"connected": False}

    def _scan_wifi_linux(self) -> dict:
        try:
            # Try nmcli first
            if shutil.which("nmcli"):
                result = subprocess.run(
                    ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,FREQ", "device", "wifi", "list", "--rescan", "yes"],
                    capture_output=True, text=True, timeout=15
                )
                networks = []
                seen = set()
                for line in result.stdout.strip().split("\n"):
                    parts = line.split(":")
                    if len(parts) >= 2:
                        ssid = parts[0].strip()
                        if not ssid or ssid in seen:
                            continue
                        seen.add(ssid)
                        networks.append({
                            "ssid": ssid,
                            "signal": int(parts[1]) if parts[1].isdigit() else 0,
                            "security": parts[2] if len(parts) > 2 else "",
                            "freq": parts[3] if len(parts) > 3 else "",
                        })
                networks.sort(key=lambda n: n["signal"], reverse=True)
                return {"available": True, "networks": networks, "count": len(networks)}

            # Fallback: iwlist
            iface = self._get_wifi_interface()
            if iface:
                result = subprocess.run(
                    ["iwlist", iface, "scan"],
                    capture_output=True, text=True, timeout=15
                )
                return self._parse_iwlist(result.stdout)

        except Exception as e:
            return {"available": False, "error": str(e)}
        return {"available": False, "error": "no wifi tool found"}

    def _scan_wifi_windows(self) -> dict:
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True, text=True, timeout=15
            )
            return self._parse_netsh_wifi(result.stdout)
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _scan_wifi_macos(self) -> dict:
        try:
            result = subprocess.run(
                ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-s"],
                capture_output=True, text=True, timeout=15
            )
            return self._parse_airport(result.stdout)
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _current_wifi_linux(self) -> dict:
        try:
            if shutil.which("nmcli"):
                result = subprocess.run(
                    ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,BSSID", "device", "wifi"],
                    capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.strip().split("\n"):
                    parts = line.split(":")
                    if len(parts) >= 3 and parts[0] == "yes":
                        return {
                            "connected": True,
                            "ssid": parts[1],
                            "signal": int(parts[2]) if parts[2].isdigit() else 0,
                            "bssid": parts[3] if len(parts) > 3 else "",
                        }
        except Exception:
            pass
        return {"connected": False}

    def _current_wifi_windows(self) -> dict:
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=10
            )
            ssid_match = re.search(r"SSID\s*:\s*(.+)", result.stdout)
            signal_match = re.search(r"Signal\s*:\s*(\d+)", result.stdout)
            if ssid_match:
                return {
                    "connected": True,
                    "ssid": ssid_match.group(1).strip(),
                    "signal": int(signal_match.group(1)) if signal_match else 0,
                }
        except Exception:
            pass
        return {"connected": False}

    def _current_wifi_macos(self) -> dict:
        try:
            result = subprocess.run(
                ["networksetup", "-getairportnetwork", "en0"],
                capture_output=True, text=True, timeout=10
            )
            if "Current Wi-Fi Network:" in result.stdout:
                ssid = result.stdout.split("Current Wi-Fi Network:")[1].strip()
                return {"connected": True, "ssid": ssid}
        except Exception:
            pass
        return {"connected": False}

    # ─── Bluetooth ───

    def scan_bluetooth(self) -> dict:
        """Scan for nearby Bluetooth devices."""
        if self.system == "Linux":
            return self._scan_bt_linux()
        elif self.system == "Windows":
            return self._scan_bt_windows()
        elif self.system == "Darwin":
            return self._scan_bt_macos()
        return {"available": False, "error": "unsupported platform"}

    def _scan_bt_linux(self) -> dict:
        devices = []
        try:
            # Try bluetoothctl
            if shutil.which("bluetoothctl"):
                result = subprocess.run(
                    ["bluetoothctl", "devices"],
                    capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.strip().split("\n"):
                    match = re.match(r"Device\s+([0-9A-F:]+)\s+(.*)", line, re.IGNORECASE)
                    if match:
                        devices.append({
                            "mac": match.group(1),
                            "name": match.group(2).strip(),
                            "type": "paired",
                        })

                # Also check for connected devices
                result_conn = subprocess.run(
                    ["bluetoothctl", "info"],
                    capture_output=True, text=True, timeout=10
                )

            # Try hcitool for nearby scan (quick)
            elif shutil.which("hcitool"):
                subprocess.run(["hcitool", "scan", "--flush"], capture_output=True, timeout=12)

        except Exception as e:
            return {"available": False, "error": str(e), "devices": devices}

        return {"available": True, "devices": devices, "count": len(devices)}

    def _scan_bt_windows(self) -> dict:
        devices = []
        try:
            # PowerShell approach for paired devices
            ps_cmd = (
                "Get-PnpDevice -Class Bluetooth | "
                "Where-Object {$_.Status -eq 'OK'} | "
                "Select-Object Name, Status, DeviceID | "
                "ConvertTo-Json"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=15
            )
            if result.stdout.strip():
                try:
                    parsed = json.loads(result.stdout)
                    if isinstance(parsed, dict):
                        parsed = [parsed]
                    for dev in parsed:
                        devices.append({
                            "name": dev.get("Name", "Unknown"),
                            "status": dev.get("Status", ""),
                            "type": "paired",
                        })
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            return {"available": False, "error": str(e)}

        return {"available": True, "devices": devices, "count": len(devices)}

    def _scan_bt_macos(self) -> dict:
        devices = []
        try:
            result = subprocess.run(
                ["system_profiler", "SPBluetoothDataType", "-json"],
                capture_output=True, text=True, timeout=15
            )
            if result.stdout.strip():
                parsed = json.loads(result.stdout)
                bt_data = parsed.get("SPBluetoothDataType", [])
                for controller in bt_data:
                    # Paired devices
                    for key in ("device_connected", "device_not_connected"):
                        for dev in controller.get(key, []):
                            name = dev.get("device_name", "Unknown")
                            devices.append({
                                "name": name,
                                "type": "connected" if key == "device_connected" else "paired",
                            })
        except Exception as e:
            return {"available": False, "error": str(e)}

        return {"available": True, "devices": devices, "count": len(devices)}

    # ─── Network Interfaces ───

    def get_interfaces(self) -> dict:
        """Get all network interfaces and their status."""
        interfaces = []
        try:
            if self.system == "Linux":
                result = subprocess.run(["ip", "-j", "addr"], capture_output=True, text=True, timeout=10)
                if result.stdout.strip():
                    parsed = json.loads(result.stdout)
                    for iface in parsed:
                        addrs = [a["local"] for a in iface.get("addr_info", [])]
                        interfaces.append({
                            "name": iface.get("ifname", ""),
                            "state": iface.get("operstate", ""),
                            "addresses": addrs,
                            "type": self._guess_iface_type(iface.get("ifname", "")),
                        })
            elif self.system == "Windows":
                result = subprocess.run(
                    ["powershell", "-Command",
                     "Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress, PrefixLength | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=10
                )
                if result.stdout.strip():
                    parsed = json.loads(result.stdout)
                    if isinstance(parsed, dict):
                        parsed = [parsed]
                    for iface in parsed:
                        interfaces.append({
                            "name": iface.get("InterfaceAlias", ""),
                            "state": "up",
                            "addresses": [iface.get("IPAddress", "")],
                            "type": self._guess_iface_type(iface.get("InterfaceAlias", "")),
                        })
        except Exception as e:
            return {"error": str(e), "interfaces": interfaces}

        return {"interfaces": interfaces, "count": len(interfaces)}

    # ─── Helpers ───

    def _get_wifi_interface(self) -> Optional[str]:
        """Find the WiFi interface name on Linux."""
        try:
            result = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=5)
            match = re.search(r"Interface\s+(\S+)", result.stdout)
            return match.group(1) if match else None
        except Exception:
            return None

    def _guess_iface_type(self, name: str) -> str:
        """Guess interface type from name."""
        name_lower = name.lower()
        if name_lower.startswith(("wlan", "wifi", "wlp", "wl")):
            return "wifi"
        elif name_lower.startswith(("eth", "en", "ethernet")):
            return "ethernet"
        elif name_lower.startswith(("lo",)):
            return "loopback"
        elif name_lower.startswith(("bt", "bnep")):
            return "bluetooth"
        elif name_lower.startswith(("docker", "br", "veth")):
            return "virtual"
        return "unknown"

    def _parse_netsh_wifi(self, output: str) -> dict:
        """Parse Windows netsh wlan output."""
        networks = []
        current = {}
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("SSID ") and "BSSID" not in line:
                if current.get("ssid"):
                    networks.append(current)
                ssid = line.split(":", 1)[1].strip() if ":" in line else ""
                current = {"ssid": ssid, "signal": 0, "security": ""}
            elif "Signal" in line and ":" in line:
                match = re.search(r"(\d+)", line.split(":", 1)[1])
                current["signal"] = int(match.group(1)) if match else 0
            elif "Authentication" in line and ":" in line:
                current["security"] = line.split(":", 1)[1].strip()
        if current.get("ssid"):
            networks.append(current)
        networks = [n for n in networks if n["ssid"]]
        networks.sort(key=lambda n: n["signal"], reverse=True)
        return {"available": True, "networks": networks, "count": len(networks)}

    def _parse_iwlist(self, output: str) -> dict:
        """Parse Linux iwlist output."""
        networks = []
        for cell in output.split("Cell "):
            ssid_match = re.search(r'ESSID:"([^"]*)"', cell)
            signal_match = re.search(r"Signal level[=:](-?\d+)", cell)
            if ssid_match and ssid_match.group(1):
                networks.append({
                    "ssid": ssid_match.group(1),
                    "signal": int(signal_match.group(1)) + 100 if signal_match else 0,
                })
        networks.sort(key=lambda n: n["signal"], reverse=True)
        return {"available": True, "networks": networks, "count": len(networks)}

    def _parse_airport(self, output: str) -> dict:
        """Parse macOS airport -s output."""
        networks = []
        for line in output.strip().split("\n")[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 2:
                ssid = parts[0]
                signal = int(parts[1]) if parts[1].lstrip("-").isdigit() else 0
                networks.append({"ssid": ssid, "signal": abs(signal)})
        networks.sort(key=lambda n: n["signal"], reverse=True)
        return {"available": True, "networks": networks, "count": len(networks)}

    # ─── Summary ───

    def summarize(self) -> str:
        """Get a human-readable summary of nearby signals."""
        parts = []

        # WiFi
        wifi = self.get_current_wifi()
        if wifi.get("connected"):
            parts.append(f"Connected to WiFi: {wifi['ssid']} ({wifi.get('signal', '?')}%)")

        scan = self.scan_wifi()
        if scan.get("available"):
            parts.append(f"{scan['count']} WiFi networks nearby")

        # Bluetooth
        bt = self.scan_bluetooth()
        if bt.get("available") and bt.get("devices"):
            names = [d["name"] for d in bt["devices"][:5]]
            parts.append(f"Bluetooth: {', '.join(names)}")

        # Interfaces
        ifaces = self.get_interfaces()
        active = [i for i in ifaces.get("interfaces", []) if i.get("state") == "up" and i["type"] != "loopback"]
        if active:
            parts.append(f"{len(active)} active network interfaces")

        if not parts:
            return "No signal data available."

        return " | ".join(parts)
