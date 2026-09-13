from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import os
import re
import shutil
import time
from colorama import Fore, Style, init
import requests

# Initialize colorama for Windows ANSI color support
init(autoreset=True)

# --- CONFIGURATION DEFAULTS ---
CHECK_URL = "https://httpbin.org/ip"

# Regex to strip ANSI color codes for accurate string length calculations
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def clear_screen():
  os.system("cls" if os.name == "nt" else "clear")


def get_terminal_width():
  try:
    return shutil.get_terminal_size().columns
  except Exception:
    return 80


def strip_ansi(text):
  return ANSI_ESCAPE.sub("", text)


def print_centered(text, color=""):
  width = get_terminal_width()
  for line in text.splitlines():
    visible_length = len(strip_ansi(line))
    padding = max(0, (width - visible_length) // 2)
    print(" " * padding + color + line)


def print_banner():
  clear_screen()

  # Centered ASCII Art Banner
  banner = f"""{Style.BRIGHT}
  ______ _____  _______   ______  
 |  ____|  __ \|_   _\ \ / / __ \ 
 | |__   | |__) | | |  \ V / |  | |
 |  __|  |  _  /  | |   > <| |  | |
 | |     | | \ \ _| |_ / . \ |__| |
 |_|     |_|  \_\_____/_/ \_\____/ 
{Style.RESET_ALL}"""
  print_centered(banner, Fore.CYAN)

  # Subtitle text centered cleanly
  subtitle = f"{Style.BRIGHT}{Fore.YELLOW}Proxy Scrapper & Checker || Developed in .gg/tool-hub{Style.RESET_ALL}"
  print_centered(subtitle + "\n", "")

  # 3-Row, 2-Column Box Layout (Perfectly Aligned & Centered)
  box_top = f"{Fore.MAGENTA}┌────────────────────────────────────────────────────────┐"
  row_1 = (
      f"{Fore.MAGENTA}│ {Fore.CYAN}(1) Scrape Proxies          {Fore.MAGENTA}│"
      f" {Fore.CYAN}(3) Check Custom File  {Fore.MAGENTA}│"
  )
  row_2 = (
      f"{Fore.MAGENTA}│ {Fore.CYAN}(2) Set Thread Count        {Fore.MAGENTA}│"
      f" {Fore.CYAN}(4) View Statistics    {Fore.MAGENTA}│"
  )
  row_3 = (
      f"{Fore.MAGENTA}│ {Fore.CYAN}(5) Check Updates           {Fore.MAGENTA}│"
      f" {Fore.CYAN}(6) Exit Tool          {Fore.MAGENTA}│"
  )
  box_bot = f"{Fore.BLUE}└────────────────────────────────────────────────────────┘"

  print_centered(box_top)
  print_centered(row_1)
  print_centered(row_2)
  print_centered(row_3)
  print_centered(box_bot + "\n")


def parse_args():
  parser = argparse.ArgumentParser(
      description="A lightweight proxy scraper and checker tool."
  )
  parser.add_argument(
      "-i",
      "--input",
      type=str,
      default=None,
      help="Optional: Path to a custom proxy text file (IP:PORT format)",
  )
  parser.add_argument(
      "-t",
      "--threads",
      type=int,
      default=50,
      help="Number of concurrent threads (default: 50)",
  )
  parser.add_argument(
      "--timeout",
      type=int,
      default=5,
      help="Proxy connection timeout in seconds (default: 5)",
  )
  parser.add_argument(
      "-o",
      "--output",
      type=str,
      default="working_proxies.txt",
      help="Output file for live proxies (default: working_proxies.txt)",
  )
  return parser.parse_args()


def load_custom_proxies(filepath):
  """Loads proxies from a local text file."""
  proxies = set()
  abs_path = os.path.abspath(filepath)

  if os.path.exists(abs_path):
    print(f"{Fore.YELLOW}[*] Loading custom proxies from: {abs_path}...{Style.RESET_ALL}")
    with open(abs_path, "r") as f:
      for line in f:
        clean_line = line.strip()
        if clean_line and ":" in clean_line:
          proxies.add(clean_line)
    print(f"{Fore.GREEN}[+] Loaded {len(proxies)} custom proxies.{Style.RESET_ALL}")
  else:
    print(f"{Fore.RED}[-] Error: File not found at '{abs_path}'.{Style.RESET_ALL}")
  return list(proxies)


def scrape_proxies():
  """Scrapes free proxies from online public sources."""
  proxies = set()
  print(f"{Fore.YELLOW}[*] Scraping proxies from sources...{Style.RESET_ALL}")

  url = "https://free-proxy-list.net/"
  try:
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
      matches = re.findall(
          r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td><td>(\d+)</td>",
          response.text,
      )
      for ip, port in matches:
        proxies.add(f"{ip}:{port}")
  except Exception as e:
    print(f"{Fore.RED}[-] Error scraping source: {e}{Style.RESET_ALL}")

  print(f"{Fore.GREEN}[+] Found {len(proxies)} unique scraped proxies.{Style.RESET_ALL}")
  return list(proxies)


def check_proxy(proxy, timeout):
  """Tests a single proxy for live status and HTTPS compatibility."""
  proxy_dict = {"http": f"http://{proxy}", "https": f"http://{proxy}"}

  start_time = time.time()
  try:
    response = requests.get(
        CHECK_URL,
        proxies=proxy_dict,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    if response.status_code == 200:
      latency = round(time.time() - start_time, 2)
      return (proxy, latency)
  except Exception:
    pass

  return None


def run_checker(raw_proxies, threads, timeout, output):
  if not raw_proxies:
    print(f"{Fore.RED}[-] No proxies found to check. Exiting.{Style.RESET_ALL}")
    return

  print(f"{Fore.YELLOW}[*] Checking {len(raw_proxies)} proxies using {threads} threads...{Style.RESET_ALL}")
  working_proxies = []

  with ThreadPoolExecutor(max_workers=threads) as executor:
    future_to_proxy = {
        executor.submit(check_proxy, proxy, timeout): proxy
        for proxy in raw_proxies
    }

    for future in as_completed(future_to_proxy):
      result = future.result()
      if result:
        proxy, latency = result
        print(
            f"{Fore.GREEN}[LIVE / HTTPS] {Fore.WHITE}{proxy}"
            f" {Fore.GREEN}| {Fore.BLUE}Latency: {latency}s{Style.RESET_ALL}"
        )
        working_proxies.append(proxy)

  print(f"\n{Fore.GREEN}[+] Scan complete! {len(working_proxies)} working proxies found.{Style.RESET_ALL}")
  if working_proxies:
    with open(output, "w") as f:
      f.write("\n".join(working_proxies))
    print(f"{Fore.GREEN}[+] Results successfully saved to '{output}'.{Style.RESET_ALL}")


def main():
  args = parse_args()
  threads = args.threads
  output_file = args.output
  timeout = args.timeout

  while True:
    print_banner()
    print(f"{Fore.CYAN}Select an option from the menu above:{Style.RESET_ALL}")
    choice = input(f"{Fore.WHITE}FRIXO@ToolHub ~ % {Style.RESET_ALL}").strip()

    if choice == "1":
      print()
      raw_proxies = scrape_proxies()
      run_checker(raw_proxies, threads, timeout, output_file)
      input(f"\n{Fore.CYAN}Press Enter to return to menu...{Style.RESET_ALL}")

    elif choice == "2":
      print()
      try:
        new_threads = int(
            input(
                f"{Fore.CYAN}[?] Enter new thread count (current: {threads}):"
                f" {Style.RESET_ALL}"
            )
        )
        if new_threads > 0:
          threads = new_threads
          print(f"{Fore.GREEN}[+] Thread count updated to {threads}.{Style.RESET_ALL}")
        else:
          print(f"{Fore.RED}[-] Thread count must be greater than 0.{Style.RESET_ALL}")
      except ValueError:
        print(f"{Fore.RED}[-] Invalid number entered.{Style.RESET_ALL}")
      input(f"\n{Fore.CYAN}Press Enter to return to menu...{Style.RESET_ALL}")

    elif choice == "3":
      print()
      file_path = input(
          f"{Fore.CYAN}[?] Enter custom proxy file path (e.g.,"
          f" your_proxy.txt): {Style.RESET_ALL}"
      ).strip()
      raw_proxies = load_custom_proxies(file_path)
      if raw_proxies:
        run_checker(raw_proxies, threads, timeout, output_file)
      input(f"\n{Fore.CYAN}Press Enter to return to menu...{Style.RESET_ALL}")

    elif choice == "4":
      print()
      print(f"{Fore.CYAN}=== STATISTICS ===")
      print(f"Current Thread Count : {threads}")
      print(f"Connection Timeout   : {timeout}s")
      print(f"Default Output File  : {output_file}{Style.RESET_ALL}")
      input(f"\n{Fore.CYAN}Press Enter to return to menu...{Style.RESET_ALL}")

    elif choice == "5":
      print()
      print(f"{Fore.GREEN}[+] You are using the latest version of FRIXO Tool.{Style.RESET_ALL}")
      input(f"\n{Fore.CYAN}Press Enter to return to menu...{Style.RESET_ALL}")

    elif choice == "6":
      print(f"{Fore.CYAN}[*] Exiting tool. Goodbye!{Style.RESET_ALL}")
      break
    else:
      print(f"{Fore.RED}[-] Invalid option! Please choose between 1-6.{Style.RESET_ALL}")
      time.sleep(1)


if __name__ == "__main__":
  main()