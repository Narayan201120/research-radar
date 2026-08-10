import asyncio
import json
import httpx
import psycopg

DSN = "postgresql://research:research@postgres:5432/research_radar"


async def main():
    conn = psycopg.connect(DSN)
    with conn.cursor() as cur:
        cur.execute("SELECT id, doi FROM paper ORDER BY id;")
        rows = cur.fetchall()
    conn.close()
    print(f"total papers: {len(rows)}", flush=True)

    sem = asyncio.Semaphore(12)

    async def check(pid, doi):
        async with sem:
            try:
                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=15.0,
                    headers={"User-Agent": "Mozilla/5.0 (research-radar link check)"},
                ) as c:
                    resp = await c.get(doi)
                    status, final_url = resp.status_code, str(resp.url)
            except Exception as e:
                status, final_url = f"ERR:{type(e).__name__}", ""
        return {"id": pid, "doi": doi, "status": status, "final": final_url[:120]}

    results = await asyncio.gather(*(check(pid, doi) for pid, doi in rows))
    broken = [x for x in results if x["status"] != 200]
    print(f"OK(200): {len(results) - len(broken)}", flush=True)
    print(f"NOT-200/ERR: {len(broken)}", flush=True)
    for b in sorted(broken, key=lambda x: (str(x["status"]), x["id"])):
        print(json.dumps(b), flush=True)


asyncio.run(main())
