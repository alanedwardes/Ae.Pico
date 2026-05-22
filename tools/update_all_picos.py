"""
Trigger a remote update on every Pico listed in tools/secret_config.py.

- Retries each bundle up to MAX_RETRIES times if any file fails
- Hard resets the Pico after update only if files changed
- Stops immediately on unrecoverable failure

Usage:
    python tools/update_all_picos.py [--dry-run] [--port 80]
                                     [--username USER] [--password PASS]
"""
import argparse
import asyncio
import base64
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from secret_config import PICOS
except ImportError:
    print("tools/secret_config.py not found. Create it with:\n  PICOS = ['hostname.home']")
    sys.exit(1)

CONNECT_TIMEOUT = 5.0
MAX_RETRIES = 3


def build_auth_header(username, password):
    if username is None:
        return None
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def strip_html(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


async def post(host, port, path, body, auth_header):
    """POST and stream response. Returns (status_code, any_updated, any_failed)."""
    body_bytes = body.encode()
    request = (
        f"POST {path} HTTP/1.0\r\n"
        f"Host: {host}\r\n"
        f"Content-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"Connection: close\r\n"
    )
    if auth_header:
        request += f"Authorization: {auth_header}\r\n"
    request += "\r\n"

    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout=CONNECT_TIMEOUT
    )
    try:
        writer.write(request.encode() + body_bytes)
        await writer.drain()

        status_line = await asyncio.wait_for(reader.readline(), timeout=30)
        status_code = int(status_line.split(b" ", 2)[1])

        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=30)
            if line in (b"\r\n", b"\n", b""):
                break

        if status_code == 404:
            return 404, False, False

        any_updated = False
        any_failed = False
        buf = b""
        while True:
            chunk = await asyncio.wait_for(reader.read(512), timeout=30)
            if not chunk:
                break
            buf += chunk
            while b">" in buf:
                end = buf.index(b">") + 1
                fragment, buf = buf[:end], buf[end:]
                text = strip_html(fragment)
                if text:
                    print(f"    {text}")
                if "✓" in text:
                    any_updated = True
                if "✗" in text:
                    any_failed = True
        if buf:
            text = strip_html(buf)
            if text:
                print(f"    {text}")

        return status_code, any_updated, any_failed
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def hard_reset(host, port, auth_header):
    body = b"type=hard"
    request = (
        f"POST /reset HTTP/1.0\r\n"
        f"Host: {host}\r\n"
        f"Content-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
    )
    if auth_header:
        request += f"Authorization: {auth_header}\r\n"
    request += "\r\n"
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=CONNECT_TIMEOUT
        )
        writer.write(request.encode() + body)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass  # connection drop on reset is expected


async def wait_for_reboot(host, port, auth_header, timeout=60):
    print(f"  Waiting for {host} to come back up...", end="", flush=True)
    deadline = asyncio.get_event_loop().time() + timeout
    await asyncio.sleep(2)  # give it a moment to actually go down
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2
            )
            writer.close()
            await writer.wait_closed()
            print(" up.")
            return True
        except Exception:
            print(".", end="", flush=True)
            await asyncio.sleep(2)
    print(" timed out.")
    return False


async def update_pico(host, port, auth_header, dry_run, force_reboot=False):
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Updating {host}")
    if dry_run:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=CONNECT_TIMEOUT
            )
            writer.close()
            await writer.wait_closed()
            print("  Up.")
        except Exception as e:
            print(f"  Unreachable: {e}")
            return False
        return True

    any_changed = False
    i = 0
    while True:
        print(f"  Bundle {i}:")
        done = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                status, updated, failed = await post(
                    host, port, f"/remoteupdate/bundle/{i}", "action=update", auth_header
                )
            except Exception as e:
                if i > 0:
                    done = True  # connection reset after last bundle — no more bundles
                    break
                print(f"    [error: {e}]")
                return False

            if status == 404:
                if i == 0:
                    print(f"    [no bundles configured]")
                    return False
                done = True
                break

            if updated:
                any_changed = True

            if not failed:
                break

            if attempt < MAX_RETRIES:
                print(f"    [errors detected, retrying ({attempt}/{MAX_RETRIES})...]")
            else:
                print(f"    [failed after {MAX_RETRIES} attempts — stopping]")
                return False

        if done:
            break
        i += 1

    if any_changed or force_reboot:
        print(f"  {'Force rebooting' if force_reboot and not any_changed else 'Files changed — rebooting'}...")
        await hard_reset(host, port, auth_header)
        return await wait_for_reboot(host, port, auth_header)
    else:
        print(f"  Nothing changed.")
    return True


async def main():
    parser = argparse.ArgumentParser(description="Update all Picos over the network.")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-reboot", action="store_true", help="Reboot every Pico after update regardless of whether files changed")
    args = parser.parse_args()

    auth_header = build_auth_header(args.username, args.password)

    failed = []
    for hostname in PICOS:
        ok = await update_pico(hostname, args.port, auth_header, args.dry_run, args.force_reboot)
        if not ok:
            failed.append(hostname)

    print()
    if failed:
        print(f"Failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
