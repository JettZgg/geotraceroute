import subprocess
import re
from typing import List, Dict, Optional, AsyncGenerator
from dataclasses import dataclass
import asyncio
import socket
import platform
import ipaddress

@dataclass
class Hop:
    hop_number: int
    ip: Optional[str]
    hostname: Optional[str]
    rtt_ms: Optional[List[float]]

class Traceroute:
    def __init__(self, target: str, max_hops: int = 30, timeout: float = 1.0, retries: int = 3):
        self.target = target
        self.max_hops = max_hops
        self.timeout = timeout
        self.retries = retries
        self.process = None
        self._resolve_target()

    def _resolve_target(self):
        """Resolve target hostname to IP address"""
        try:
            self.target_ip = socket.gethostbyname(self.target)
        except socket.gaierror:
            raise ValueError(f"Could not resolve hostname: {self.target}")

    async def stop(self):
        """Stop the traceroute process if it's running"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            self.process = None

    async def run_stream(self) -> AsyncGenerator[Hop, None]:
        """
        Run traceroute and stream results as they arrive.
        
        Yields:
            Hop: Information about each hop
        """
        os_name = platform.system().lower()
        
        # Use the same command build logic as _build_command
        cmd = self._build_command()
        print(f"Executing stream command: {cmd}")

        self.process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Only skip the actual header line (e.g., "traceroute to example.com")
        # Read the first line
        line = await self.process.stdout.readline()
        if line:
            decoded_line = line.decode().strip()
            print(f"Reading line: {decoded_line}")
            
            # If it's the actual header line, skip it
            if "traceroute to" in decoded_line:
                print(f"Skipping header line: {decoded_line}")
            # Otherwise, try to parse it as hop data
            else:
                hop = self._parse_hop(decoded_line)
                if hop:
                    print(f"Yielding hop: {hop}")
                    yield hop
        
        # Process all remaining lines
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
                
            line = line.decode().strip()
            print(f"Reading line: {line}")
            if not line:
                continue
                
            # Parse hop information
            hop = self._parse_hop(line)
            if hop:
                print(f"Yielding hop: {hop}")
                yield hop
            else:
                print(f"Could not parse line: {line}")

        await self.process.wait()
        self.process = None

    def _parse_hop(self, line: str) -> Optional[Hop]:
        """
        Parse a single line of traceroute output.
        
        Args:
            line: A line from traceroute output
            
        Returns:
            Optional[Hop]: Hop object if parsed successfully, None otherwise
        """
        print(f"Parsing line: {line}")
        # Skip the first line (headline) and empty lines
        if not line.strip() or "traceroute to" in line:
            return None
        
        # Try to extract hop information
        try:
            # Special case: handle mixed asterisks and IP in the last hop
            # Example: "7  * 8.8.8.8  23.323 ms  19.489 ms"
            last_hop_mixed = re.match(r'^\s*(\d+)\s+\*\s+([^\s]+)\s+([0-9.]+)\s*ms\s+([0-9.]+)\s*ms', line)
            if last_hop_mixed:
                hop_num = int(last_hop_mixed.group(1))
                ip = last_hop_mixed.group(2)
                
                # Extract RTT values, skip the first timeout (*)
                rtts = []
                for i in range(3, 5):
                    if last_hop_mixed.group(i):
                        rtts.append(float(last_hop_mixed.group(i)))
                
                print(f"Successfully parsed mixed line: hop={hop_num}, IP={ip}, RTTs={rtts}")
                return Hop(hop_num, ip, None, rtts)

            # Optimized macOS/Linux format parsing
            # Supports hostname with or without parentheses
            # Supports * * * timeout cases
            # Matches different numbers of RTT values
            match = re.match(r'^\s*(\d+)\s+(?:(\*)\s+(\*)\s+(\*)|(?:([^\s]+)(?:\s+\(([^\)]+)\))?\s+([0-9.]+)\s*ms(?:\s+([0-9.]+)\s*ms)?(?:\s+([0-9.]+)\s*ms)?))', line)
            
            if not match:
                # Try a simpler pattern for the -n parameter (not resolving hostnames)
                match = re.match(r'^\s*(\d+)\s+([^\s]+)\s+([0-9.]+)\s*ms\s+([0-9.]+)\s*ms\s+([0-9.]+)\s*ms', line)
                if match:
                    hop_num = int(match.group(1))
                    ip = match.group(2)
                    hostname = None  # -n parameter doesn't resolve hostnames
                    
                    # Extract RTT values
                    rtts = []
                    for i in range(3, 6):
                        if match.group(i):
                            rtts.append(float(match.group(i)))
                    
                    return Hop(hop_num, ip, hostname, rtts)
            
            if match:
                hop_num = int(match.group(1))
                
                # Handle timeout case (* * *)
                if match.group(2) == '*':
                    return Hop(hop_num, None, None, [])
                
                # Normal case: extract IP and hostname
                if len(match.groups()) >= 5:
                    # Process with new pattern
                    ip = match.group(5)
                    hostname = match.group(6)
                    
                    # Extract RTT values
                    rtts = []
                    for i in range(7, 10):
                        if i <= len(match.groups()) and match.group(i):
                            rtts.append(float(match.group(i)))
                
                return Hop(hop_num, ip, hostname, rtts)
                
            # Windows format parsing
            win_match = re.match(r'^\s*(\d+)\s+(?:\*\s*\*\s*\*|(?:(\d+)\s*ms\s+(\d+)\s*ms\s+(\d+)\s*ms\s+([^\s]+)))', line)
            if win_match:
                hop_num = int(win_match.group(1))
                
                # Handle timeout case
                if "*" in line:
                    return Hop(hop_num, None, None, [])
                
                # In Windows format, hostname/IP is in group 5
                hostname_or_ip = win_match.group(5)
                
                # Check if it's an IP address
                try:
                    ipaddress.ip_address(hostname_or_ip)
                    ip = hostname_or_ip
                    hostname = None
                except ValueError:
                    # If not a valid IP, it might be a hostname
                    ip = None
                    hostname = hostname_or_ip
                
                # Extract RTT values
                rtts = []
                for i in range(2, 5):
                    if win_match.group(i):
                        rtts.append(float(win_match.group(i)))
                
                return Hop(hop_num, ip, hostname, rtts)

            # If no pattern matches, log detailed information and continue processing
            print(f"Could not match any known pattern: {line}")
            
        except Exception as e:
            print(f"Parsing error: {e}")
        
        return None

    async def run(self) -> List[Hop]:
        """
        Run traceroute and return a list of hops.
        
        Returns:
            List[Hop]: List of hop objects containing trace information
        """
        print(f"Executing traceroute command: {self.target}")
        proc = await asyncio.create_subprocess_shell(
            self._build_command(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if stderr:
            print(f"Error output: {stderr.decode()}")
        
        print(f"Standard output: {stdout.decode()}")
        
        output = stdout.decode()
        return self._parse_output(output)

    def _build_command(self):
        os_name = platform.system().lower()
        
        if os_name == 'darwin':  # macOS
            cmd = f'traceroute -n -w {int(self.timeout)} -q {self.retries} -m {self.max_hops} {self.target}'
        elif os_name == 'linux':
            cmd = f'traceroute -n -w {int(self.timeout)} -q {self.retries} -m {self.max_hops} {self.target}'
        elif os_name == 'windows':
            cmd = f'tracert -w {int(self.timeout * 1000)} -h {self.max_hops} {self.target}'
        else:
            raise RuntimeError(f"Unsupported operating system: {os_name}")
        
        print(f"Building command: {cmd}")
        return cmd

    def _parse_output(self, output: str) -> List[Hop]:
        hops = []
        lines = output.splitlines()
        for line in lines:
            hop = self._parse_hop(line)
            if hop:
                hops.append(hop)
        return hops 