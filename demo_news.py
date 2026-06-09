import asyncio, json, logging, os, sys
from datetime import date

CODEX_CLI = os.path.join(os.environ["APPDATA"],
    "npm", "node_modules", "@openai", "codex", "bin", "codex.js")
NODE = r"C:\Program Files\nodejs\node.exe"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    desktop = os.environ["USERPROFILE"] + "\\Desktop"
    today = date.today().isoformat()
    out = desktop + "\\ai-news-" + today + ".md"
    
    print("=" * 50)
    print("AI Agent Orchestrator Demo")
    print("=" * 50)
    print("Target: " + out)
    print()
    
    prompt = " and ".join([
        "Fetch today top AI news headlines from the web",
        "save as markdown file to: " + out,
        "include 5-10 items with title, source, summary",
        "organize by categories: Models, Research, Industry, Policy",
    ])
    
    cmd = [
        NODE, CODEX_CLI, "exec",
        "--sandbox", "danger-full-access",
        "--add-dir", desktop,
        "--skip-git-repo-check",
        prompt,
    ]
    
    print("[*] Running Codex exec (non-interactive)...")
    print("[*] This may take 1-2 minutes")
    print()
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), 300)
        print()
        print("-" * 50)
        if os.path.exists(out):
            size = os.path.getsize(out)
            print("[OK] " + out + " (" + str(size) + " bytes)")
            print()
            print("--- Preview ---")
            with open(out, "r", encoding="utf-8") as f:
                print(f.read()[:2000])
            print("--- End ---")
        else:
            print("[!] File not found")
    except asyncio.TimeoutError:
        proc.kill()
        print("[!] Timed out after 300s")
    finally:
        print("=" * 50)

asyncio.run(main())