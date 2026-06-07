import argparse
import tempfile
import os
from tqdm import tqdm
from parse import *
import json
from license import has_legal_license
from datetime import datetime
from githubAsync import *
from dotenv import load_dotenv
import aiohttp
import asyncio
import psycopg2
import os
from db import db

load_dotenv()

def precheck(fullname: str, cur: psycopg2.extensions.cursor, stale_date: str):
    cur.execute('SELECT parsed_at, id FROM scrapedrepos WHERE name = %s', (fullname,))
    match = cur.fetchone()
    if stale_date:
        # get current yy-mm-dd
        if match and match[0]:
            if datetime.datetime.strptime(stale_date, "%Y-%m-%d") < datetime.datetime.strptime(match[0], "%Y-%m-%d"):
                print(f"Skipping {fullname} because it was parsed after {stale_date}")
                return False
    return match[1] if match else None

async def process_repo(repo: Repository, cur: psycopg2.extensions.cursor, id: int | None = None):
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            if repo.name == "hypothesis": return

            license, license_status = has_legal_license(repo)

            if id is None:
                cur.execute(
                    'INSERT INTO scrapedrepos (source, name, url, license, license_status, stars, forks, parsed_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id',
                    ('gh', repo.full_name, repo.clone_url, license, "none" if not license else license_status,
                    repo.stars, repo.forks, datetime.datetime.now().strftime("%Y-%m-%d"))
                )

            res = cur.fetchone()
            repo_id = id if id is not None else res[0]  # type: ignore

            if not license:
                print(f"Skipping {repo.full_name} because of license")
                return

            if license_status == "bad":
                print(f"Skipping {repo.full_name} because of license: {license}")
                return

            url = repo.clone_url
            os.system(f'git clone --depth=1 --quiet {url} {tmpdir}')
            hash = os.popen(f'git -C {tmpdir} rev-parse HEAD').read().strip()

            # if we already have this repo hash, skip
            # this could be this repo or another repo with the same hash
            # but in any case its not worth redoing
            cur.execute('SELECT id FROM scrapedrepos WHERE hash = %s', (hash, ))
            match = cur.fetchone()
            if match:
                print(f"Skipping {repo.full_name} because of hash match")
                cur.execute('UPDATE scrapedrepos SET hash = %s WHERE id = %s', (hash, repo_id))
                cur.connection.commit()
                return
            # otherwise, update the hash
            cur.execute('UPDATE scrapedrepos SET hash = %s WHERE id = %s', (hash, repo_id))

            result = os.system(f"rg -l '@given' {tmpdir}")
            if not result == 0: return

            data = generate_dataset_from_project(tmpdir)

            cur.execute('DELETE FROM scrapedtests WHERE repo_id = %s', (repo_id,))

            for pbt in data:
                try:
                    cur.execute(
                        'INSERT INTO scrapedtests (repo_id, pbt_name, pbt, dep_names, deps, source) VALUES (%s, %s, %s, %s, %s, %s)',
                        (repo_id, pbt[0], pbt[1], json.dumps(pbt[2]), json.dumps(pbt[3]), pbt[4])
                    )
                except Exception as e:
                    print(f"Error inserting {pbt[0]} for {repo.full_name} due to {e}")

            cur.connection.commit()

        except Exception as e:
            print(f"Error processing repository {repo.full_name}: {e}")

async def main(mode, stale_date, timeout):
    con,cur = db()
    if mode == "dependents":
        with open('dependents.json', 'r') as file:
            dependents = json.load(file)
        session = aiohttp.ClientSession()
        with tqdm(total=len(dependents)) as pbar:
            for i in range(len(dependents)):
                owner = dependents[i]["owner"]
                rn = dependents[i]["repo"]
                strk = '' + str(owner) + "/" + str(rn)
                match = precheck(strk, cur, stale_date)
                if match == False:
                    pbar.update(1)
                    continue
                repo = await get_repository_async(session, os.environ['TOKEN'], strk)
                if not repo:
                    pbar.update(1)
                    continue
                try:
                    await asyncio.wait_for(process_repo(repo,cur,match), timeout=timeout)
                except asyncio.TimeoutError:
                    print(f"Timeout occurred for repository {repo.full_name}")
                    continue
                con.commit()
                pbar.update(1)

    elif mode == "gh":
        async with aiohttp.ClientSession() as session:
            repos = await search_repositories_async(session,os.environ['TOKEN'], 'language:python hypothesis in:readme,description stars:100..1000')
            for repo in tqdm(repos, total=len(repos)):
                await process_repo(repo, cur)
                con.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape from dependents')
    parser.add_argument("--mode", required=True, choices=["dependents", "gh"], help="Mode to run in (dependents or gh)")
    parser.add_argument('--stale-date', default=None, help='By default, the script skips repos it has already parsed. If you want to reparse, set the stale date (YYYY-MM-DD)')
    parser.add_argument('--timeout', default=25000, type=int, help='Timeout for processing a single repository')
    args = parser.parse_args()

    asyncio.run(main(args.mode, args.stale_date, args.timeout))
