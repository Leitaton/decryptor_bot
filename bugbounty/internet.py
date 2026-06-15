import asyncio
import aiohttp
import logging
import random
from aiohttp import ClientTimeout, ClientSession

# --- Configuration ---
# Keywords typically found in Safaricom's "Top-Up" or "Out of Data" pages
CAPTIVE_PORTAL_KEYWORDS = [
    "top up",
    "buy a bundle",
    "insufficient balance",
    "safaricom.co.ke/topup",
    "out of data",
    "recharge"
]

TIMEOUT_SECONDS = 5  # How long to wait for a response
CONCURRENT_REQUESTS = 10  # Lowered for stealth to avoid AI anomaly detection
INPUT_FILE = "domains.txt"
OUTPUT_FILE = "results.txt"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ZeroRateProber")

class ZeroRateProber:
    def __init__(self, domains):
        self.domains = domains
        self.found_zero_rated = []
        self.semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async def is_captive_portal(self, text):
        """Check if the response content contains keywords indicating a captive portal."""
        content = text.lower()
        return any(keyword in content for keyword in CAPTIVE_PORTAL_KEYWORDS)

    async def probe(self, session, domain):
        """Probe a domain via HTTP and HTTPS with stealth measures."""
        # We test both HTTP and HTTPS because some proxies only leak one
        protocols = ["http://", "https://"]

        # Mimic a real browser to bypass basic script detection
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }

        async with self.semaphore:
            for protocol in protocols:
                url = f"{protocol}{domain}"
                try:
                    # Use a strict timeout to avoid hanging on slow responses
                    timeout = ClientTimeout(total=TIMEOUT_SECONDS)
                    async with session.get(url, timeout=timeout, allow_redirects=True, headers=headers) as response:
                        if response.status == 200:
                            text = await response.text()

                            if not await self.is_captive_portal(text):
                                logger.info(f"[+] FOUND ZERO-RATED: {url}")
                                self.found_zero_rated.append(url)
                                # Add jitter after a successful find to break pattern recognition
                                await asyncio.sleep(random.uniform(0.5, 1.5))
                                return True # Stop if we found it on either protocol

                    # Add jitter between protocol attempts or failed domains to look more human
                    await asyncio.sleep(random.uniform(0.2, 0.8))

                except Exception:
                    # Silently ignore connection errors, timeouts, and SSL failures
                    pass
        return False

    async def run(self):
        logger.info(f"Starting probe on {len(self.domains)} domains...")

        async with ClientSession() as session:
            tasks = [self.probe(session, domain) for domain in self.domains]
            await asyncio.gather(*tasks)

        self.save_results()

    def save_results(self):
        with open(OUTPUT_FILE, "w") as f:
            f.write("\n".join(self.found_zero_rated))
        logger.info(f"Completed. Found {len(self.found_zero_rated)} zero-rated domains. Saved to {OUTPUT_FILE}")

def load_domains(filename):
    try:
        with open(filename, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logger.error(f"Input file {filename} not found. Creating a sample one.")
        with open(filename, "w") as f:
            f.write("google.com\nsafaricom.co.ke\nwhatsapp.net\nfacebook.com\n")
        return ["google.com", "safaricom.co.ke", "whatsapp.net", "facebook.com"]

async def main():
    domains = load_domains(INPUT_FILE)
    random.shuffle(domains) # Randomize order to avoid sequential scanning patterns
    prober = ZeroRateProber(domains)
    await prober.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Probe interrupted by user.")
